import json
import os
import re
import uuid
import base64
from datetime import datetime, timedelta
from typing import Any, Optional
from zoneinfo import ZoneInfo
import requests

from dotenv import load_dotenv
from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import HTMLResponse
from openai import OpenAI
from pydantic import BaseModel

from app.services import flight_search_service
from app.services import chat_renderers
from app.services import hotel_service
from app.services import place_search_service
from app.services import place_followup_service
from app.services import chat_parsing_service
from app.services import date_parsing_service
from app.services import intent_router_service
from app.services import knowledge_service
from app.services import knowledge_helpers_service
from app.services import chat_orchestrator_service
from app.services import chat_heuristics_service
from app.endpoints.rag_api import answer_rag_question
from app.session import get_user_id_from_session
from app.services.booking_history_service import save_booking, get_user_bookings

try:
    from pinecone import Pinecone
except Exception:
    Pinecone = None

load_dotenv()
router = APIRouter()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")
PINECONE_INDEX_NAME = os.getenv("PINECONE_INDEX_NAME")
PINECONE_NAMESPACE = os.getenv("PINECONE_NAMESPACE", "travel-knowledge")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")
RAG_TOP_K = int(os.getenv("RAG_TOP_K", "5"))

SESSION_STATE: dict[str, dict[str, Any]] = {}
SESSION_HISTORY: dict[str, list[dict[str, str]]] = {}
pinecone_index = None
PENDING_FLIGHT_ORDERS: dict[str, dict[str, Any]] = {}

SLOT_KEYS = [
    "origin",
    "destination",
    "departure_date",
    "return_date",
    "adults",
    "children",
    "infants",
    "max_price",
    "limit",
    "sort_by",
    "trip_type",
    "time_pref",
    "departure_window",
    "direct_only",
]

LOCATION_ALIASES = {
    "\uc11c\uc6b8": "SEL",
    "\uc778\ucc9c": "ICN",
    "\uae40\ud3ec": "GMP",
    "\ubd80\uc0b0": "PUS",
    "\uc81c\uc8fc": "CJU",
    "\ub3c4\ucfc4": "TYO",
    "\uc624\uc0ac\uce74": "OSA",
    "\ud6c4\ucfe0\uc624\uce74": "FUK",
    "\uc0bf\ud3ec\ub85c": "SPK",
    "\ub098\ub9ac\ud0c0": "NRT",
    "\ud558\ub124\ub2e4": "HND",
    "\ub274\uc695": "NYC",
    "\ub7f0\ub358": "LON",
    "\ud30c\ub9ac": "PAR",
    "\ubc29\ucf55": "BKK",
    "\uc2f1\uac00\ud3ec\ub974": "SIN",
    "\uc2dc\ub4dc\ub2c8": "SYD",
    "seoul": "SEL",
    "incheon": "ICN",
    "gimpo": "GMP",
    "busan": "PUS",
    "jeju": "CJU",
    "tokyo": "TYO",
    "osaka": "OSA",
    "fukuoka": "FUK",
    "sapporo": "SPK",
    "narita": "NRT",
    "haneda": "HND",
    "new york": "NYC",
    "london": "LON",
    "paris": "PAR",
    "bangkok": "BKK",
    "singapore": "SIN",
    "sydney": "SYD",
    "\ubcb3\ubd80": "OIT",
    "beppu": "OIT",
}

COUNTRY_ALIASES = {
    "\ud55c\uad6d": "SEL",
    "\ub300\ud55c\ubbfc\uad6d": "SEL",
    "\uc77c\ubcf8": "TYO",
    "\ubbf8\uad6d": "NYC",
    "\uc601\uad6d": "LON",
    "\ud504\ub791\uc2a4": "PAR",
    "\ud0dc\uad6d": "BKK",
    "\ubca0\ud2b8\ub0a8": "SGN",
    "\uc2f1\uac00\ud3ec\ub974": "SIN",
    "\ub9d0\ub808\uc774\uc2dc\uc544": "KUL",
    "\ud544\ub9ac\ud540": "MNL",
    "\ud638\uc8fc": "SYD",
    "japan": "TYO",
    "australia": "SYD",
    "india": "DEL",
}

RAG_COUNTRY_CODE_ALIASES = {
    "\ud55c\uad6d": "KR",
    "\ub300\ud55c\ubbfc\uad6d": "KR",
    "\uc77c\ubcf8": "JP",
    "\ubbf8\uad6d": "US",
    "\uc601\uad6d": "GB",
    "\ud504\ub791\uc2a4": "FR",
    "\ud0dc\uad6d": "TH",
    "\ubca0\ud2b8\ub0a8": "VN",
    "\uc2f1\uac00\ud3ec\ub974": "SG",
    "\ub9d0\ub808\uc774\uc2dc\uc544": "MY",
    "\ud544\ub9ac\ud540": "PH",
    "\ud638\uc8fc": "AU",
    "japan": "JP",
    "korea": "KR",
    "south korea": "KR",
    "usa": "US",
    "us": "US",
    "u.s.": "US",
    "united states": "US",
    "uk": "GB",
    "u.k.": "GB",
    "united kingdom": "GB",
    "england": "GB",
    "france": "FR",
    "thailand": "TH",
    "vietnam": "VN",
    "singapore": "SG",
    "malaysia": "MY",
    "philippines": "PH",
    "australia": "AU",
    "india": "IN",
}


def _normalize_rag_country_code(v: Any) -> Optional[str]:
    if not v:
        return None
    raw = str(v).strip()
    if not raw:
        return None
    key = raw.lower()
    key_compact = re.sub(r"\s+", " ", key)
    if key_compact in RAG_COUNTRY_CODE_ALIASES:
        return RAG_COUNTRY_CODE_ALIASES[key_compact]
    up = raw.upper().strip()
    if up in {"JP", "KR", "US", "GB", "FR", "TH", "VN", "SG", "MY", "PH", "AU", "IN"}:
        return up
    if up == "USA":
        return "US"
    if up in {"UK", "GBR"}:
        return "GB"
    if up == "KOR":
        return "KR"
    if up == "JPN":
        return "JP"
    return None


def _infer_rag_country_code(texts: list[str]) -> Optional[str]:
    for txt in texts:
        t = txt or ""
        tl = t.lower()
        for k, code in RAG_COUNTRY_CODE_ALIASES.items():
            if k in tl or k in t:
                return code
    return None


class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = None


class FlightPassengerInput(BaseModel):
    last_name: str
    first_name: str
    birth_date: str
    nationality: str
    passport_number: str
    passport_expiry: str


class FlightCheckoutOfferInput(BaseModel):
    airline: str | None = None
    airline_code: str | None = None
    price: dict[str, Any] | None = None
    itineraries: list[dict[str, Any]] | None = None


class FlightCheckoutRequest(BaseModel):
    offer: FlightCheckoutOfferInput
    customer_name: str
    customer_email: str
    customer_phone: str | None = None
    passengers: list[FlightPassengerInput]


class TossConfirmRequest(BaseModel):
    paymentKey: str
    orderId: str
    amount: int


class NeedMoreInfoError(Exception):
    pass


def _country_currency_hint(country_code: Optional[str]) -> str:
    cc = (country_code or "").upper().strip()
    mapping = {
        "JP": "\uc5d4\ud654(JPY)",
        "US": "\ub2ec\ub7ec(USD)",
        "GB": "\ud30c\uc6b4\ub4dc(GBP)",
        "FR": "\uc720\ub85c(EUR)",
        "DE": "\uc720\ub85c(EUR)",
        "IT": "\uc720\ub85c(EUR)",
        "ES": "\uc720\ub85c(EUR)",
        "PT": "\uc720\ub85c(EUR)",
        "NL": "\uc720\ub85c(EUR)",
        "BE": "\uc720\ub85c(EUR)",
        "AT": "\uc720\ub85c(EUR)",
        "IE": "\uc720\ub85c(EUR)",
        "TH": "\ubc14\ud2b8(THB)",
        "VN": "\ub3d9(VND)",
        "SG": "\uc2f1\uac00\ud3ec\ub974 \ub2ec\ub7ec(SGD)",
        "MY": "\ub9c1\uae43(MYR)",
        "PH": "\ud398\uc18c(PHP)",
        "AU": "\ud638\uc8fc \ub2ec\ub7ec(AUD)",
        "IN": "\ub8e8\ud53c(INR)",
        "KR": "\uc6d0\ud654(KRW)",
    }
    return mapping.get(cc, "\ud604\uc9c0\ud1b5\ud654")

def _to_float(v: Any) -> Optional[float]:
    try:
        return float(v)
    except Exception:
        return None


def _clean_json(s: str) -> str:
    return (s or "").replace("```json", "").replace("```", "").strip()


def _strip_markdown_decorations(text: str) -> str:
    t = str(text or "")
    # Remove markdown headings/bold markers for chat readability
    t = re.sub(r"^\s{0,3}#{1,6}\s*", "", t, flags=re.MULTILINE)
    t = t.replace("**", "")
    t = t.replace("__", "")
    t = re.sub(r"`([^`]*)`", r"\1", t)
    # Normalize list item spacing like "1.  "
    t = re.sub(r"(?m)^(\d+)\.\s+", r"\1. ", t)
    return t.strip()


def _contains(text: str, kws: list[str]) -> bool:
    return any(k in (text or "") for k in kws)


def _parse_rel_date(text: str):
    return date_parsing_service.parse_rel_date(text)

def _has_date_signal(text: str) -> bool:
    return date_parsing_service.has_date_signal(text, contains_fn=_contains)

def _parse_abs_monthday_range(text: str, now_dt: Optional[datetime] = None) -> dict[str, Optional[str]]:
    return date_parsing_service.parse_abs_monthday_range(text, now_dt=(now_dt or datetime.now(KST)))

def _is_date_correction_message(text: str) -> bool:
    return date_parsing_service.is_date_correction_message(
        text,
        contains_fn=_contains,
        has_date_signal_fn=_has_date_signal,
    )

def _parse_rel_date_for_correction(text: str):
    return date_parsing_service.parse_rel_date_for_correction(text, parse_rel_date_fn=_parse_rel_date)


def _has_location_signal(text: str) -> bool:
    """
    Broad location hints; if absent on correction utterance, keep existing route slots unchanged.
    """
    t = text or ""

    # keywords: \ucd9c\ubc1c\uc9c0, \ub3c4\ucc29\uc9c0, \uacf5\ud56d
    if _contains(t, ["\ucd9c\ubc1c\uc9c0", "\ub3c4\ucc29\uc9c0", "\uacf5\ud56d", "from", "to"]):
        return True

    compact = re.sub(r"\s+", "", t)

    if compact in LOCATION_ALIASES or compact in COUNTRY_ALIASES:
        return True

    # NOTE: this can over-match if you have very short english keys.
    # If that becomes an issue, add word-boundary matching for short alpha keys.
    return any(name in t for name in list(LOCATION_ALIASES.keys()) + list(COUNTRY_ALIASES.keys()))


def _should_show_place_distance(message: str, location_query: Optional[str], city_name: Optional[str]) -> bool:
    """
    거리 표시는 '근처/역/주변' 같은 근접 탐색 의도가 분명할 때만 노출한다.
    도시 전체 질의(예: 파리 맛집)에서 도시 중심점 기준 직선거리를 보여주면 오해를 줄 수 있다.
    """
    msg = message or ""
    lq = (location_query or "").strip().lower()
    city = (city_name or "").strip().lower()

    # Explicit proximity intent from user utterance.
    if _contains(msg, ["근처", "주변", "근방", "역", "앞", "도보", "걸어서"]):
        return True

    # If the extracted location itself contains a proximity/landmark cue, distance is still useful.
    if any(k in lq for k in ["station", " st.", "역", "near", "nearby", "공항", "airport"]):
        return True

    # Broad city-level queries should not show center-point straight-line distance.
    if lq and city and (lq == city or lq in city or city in lq):
        return False

    return False


def _is_landmark_like_location_query(location_query: Optional[str]) -> bool:
    q = (location_query or "").strip().lower()
    if not q:
        return False
    return any(k in q for k in ["station", "역", "airport", "공항", "terminal", "터미널"])


def _place_search_radius_m(message: str, location_query: Optional[str] = None) -> int:
    """
    사용자 질의의 근접 의도를 반영해 장소 검색 반경을 조절한다.
    - 근처/역/도보/주변: 좁은 반경
    - 일반 도시 추천: 넓은 반경
    """
    msg = message or ""
    lq = (location_query or "").lower()
    if _contains(msg, ["근처", "주변", "근방", "역", "도보", "걸어서", "근접"]):
        return 2000
    if any(k in lq for k in ["station", "역", "tower", "탑", "airport", "공항"]):
        return 2500
    return 7000

def _build_context(history: list[dict[str, str]], max_items: int = 16) -> str:
    return "\n".join(f"{x.get('role')}: {x.get('text')}" for x in history[-max_items:])


def _llm_json(system: str, prompt: str) -> dict[str, Any]:
    try:
        res = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "system", "content": system}, {"role": "user", "content": prompt}],
            temperature=0,
        )
        return json.loads(_clean_json(res.choices[0].message.content))
    except Exception:
        return {}


KST = ZoneInfo("Asia/Seoul")

# assumes you already have:
# - _llm_json(system: str, prompt: str) -> dict[str, Any]
# - _parse_rel_date(text: str) -> Optional[date]
# - _normalize_rag_country_code(v: Any) -> Optional[str]

def _today_kst_str() -> str:
    return date_parsing_service.today_kst_str(now_dt=datetime.now(KST))

def _coerce_int(v: Any, default: int = 0, lo: int = 0, hi: int = 365) -> int:
    return date_parsing_service.coerce_int(v, default=default, lo=lo, hi=hi)

def _normalize_date_semantics(parsed: Any) -> dict[str, Any]:
    return date_parsing_service.normalize_date_semantics(parsed)

def _extract_date_expr_with_llm(message: str, context: str = "") -> dict[str, Any]:
    return date_parsing_service.extract_date_expr_with_llm(
        message,
        context,
        llm_json_fn=_llm_json,
        today_str=_today_kst_str(),
    )

def _resolve_date_expr(expr: Any, now_dt: Optional[datetime] = None) -> Optional[str]:
    return date_parsing_service.resolve_date_expr(
        expr,
        parse_rel_date_fn=_parse_rel_date,
        now_dt=(now_dt or datetime.now(KST)),
    )


def _resolve_knowledge_context_with_llm(
    message: str,
    context: str,
    prev_state: Optional[dict[str, Any]] = None
) -> dict[str, Any]:
    return knowledge_helpers_service.resolve_knowledge_context_with_llm(
        message,
        context,
        prev_state,
        llm_json_fn=_llm_json,
        today_kst_str_fn=_today_kst_str,
        normalize_rag_country_code_fn=_normalize_rag_country_code,
    )

def _parse_flight_slots(message: str, context: str) -> dict[str, Any]:
    return chat_parsing_service.parse_flight_slots(
        message,
        context,
        llm_json_fn=_llm_json,
        contains_fn=_contains,
        is_date_correction_message_fn=_is_date_correction_message,
        has_location_signal_fn=_has_location_signal,
        parse_rel_date_fn=_parse_rel_date,
        extract_date_expr_with_llm_fn=_extract_date_expr_with_llm,
        resolve_date_expr_fn=_resolve_date_expr,
        parse_rel_date_for_correction_fn=_parse_rel_date_for_correction,
        parse_abs_monthday_range_fn=_parse_abs_monthday_range,
    )

def _parse_hotel_slots(message: str, context: str) -> dict[str, Any]:
    return chat_parsing_service.parse_hotel_slots(
        message,
        context,
        llm_json_fn=_llm_json,
        is_date_correction_message_fn=_is_date_correction_message,
        extract_date_expr_with_llm_fn=_extract_date_expr_with_llm,
        resolve_date_expr_fn=_resolve_date_expr,
        parse_rel_date_fn=_parse_rel_date,
        location_alias_keys=list(LOCATION_ALIASES.keys()),
    )

def _detect_intent(message: str, prev_state: dict[str, Any]) -> str:
    return intent_router_service.detect_intent(message, prev_state, contains_fn=_contains)

def _resolve_intent_with_llm(message: str, context: str, prev_state: Optional[dict[str, Any]] = None) -> Optional[str]:
    return intent_router_service.resolve_intent_with_llm(
        message,
        context,
        prev_state,
        llm_json_fn=_llm_json,
        contains_fn=_contains,
    )

def _classify_travel_domain_with_llm(message: str, context: str = "") -> Optional[dict[str, Any]]:
    return intent_router_service.classify_travel_domain_with_llm(message, context, llm_json_fn=_llm_json)

def _is_smalltalk_greeting(message: str) -> bool:
    return chat_heuristics_service.is_smalltalk_greeting(message)


def _should_ask_intent_clarification(message: str, prev_state: Optional[dict[str, Any]] = None) -> bool:
    _ = prev_state
    return intent_router_service.should_ask_intent_clarification(message, contains_fn=_contains)

def _is_route_guidance_query(message: str) -> bool:
    return intent_router_service.is_route_guidance_query(message, contains_fn=_contains)

def _should_keep_knowledge_followup(message: str, prev_state: Optional[dict[str, Any]] = None) -> bool:
    return intent_router_service.should_keep_knowledge_followup(message, prev_state, contains_fn=_contains)

def _merge_state(prev: dict[str, Any], cur: dict[str, Any]) -> dict[str, Any]:
    return chat_heuristics_service.merge_state(prev, cur, slot_keys=SLOT_KEYS)


def _missing_questions(state: dict[str, Any]) -> list[str]:
    return chat_heuristics_service.missing_questions(state)


def _build_knowledge_retrieval_query(
    message: str,
    country_code: Optional[str],
    city_name: Optional[str],
    topic: Optional[str],
    subtopic: Optional[str],
) -> str:
    return knowledge_helpers_service.build_knowledge_retrieval_query(
        message, country_code, city_name, topic, subtopic
    )

def _is_food_place_followup(message: str, prev_state: Optional[dict[str, Any]] = None) -> bool:
    m = (message or "")
    if not _contains(m, ["맛집", "식당", "레스토랑", "라멘집", "국밥집", "밥집", "restaurant"]):
        return False
    # "그 음식 맛집" 같은 후속질문 또는 도시+음식+맛집 직접 질문
    if _contains(m, ["그 음식", "그거", "어디", "근처", "추천"]):
        return True
    if prev_state and (prev_state.get("last_intent") == "knowledge"):
        return True
    return False


def _is_local_place_followup(message: str, prev_state: Optional[dict[str, Any]] = None) -> bool:
    m = message or ""
    # 장소 추천 전반: 맛집/명소/놀거리/카페/쇼핑
    place_kws = [
        "맛집", "식당", "레스토랑", "라멘집", "밥집", "먹을만한", "먹을 만한",
        "명소", "관광지", "놀거리", "가볼만", "즐길만", "핫플",
        "카페",
        "쇼핑", "쇼핑몰", "백화점", "마켓", "시장",
        "restaurant", "attraction", "things to do", "cafe", "shopping", "mall", "market",
    ]
    if not _contains(m, place_kws):
        brand_shop = (
            _contains(m, ["브랜드", "매장", "파는곳", "파는 곳", "판매처", "편집샵", "셀렉트샵", "brand", "store", "shop"])
            and _contains(m, ["어디", "추천", "알려", "파는", "구할", "살"])
        )
        if not brand_shop:
            return False
    if _contains(m, ["어디", "근처", "추천", "찾아", "알려"]):
        return True
    if prev_state and prev_state.get("last_intent") == "knowledge":
        return True
    return False


def _extract_local_place_request_with_llm(message: str, context: str, prev_state: Optional[dict[str, Any]] = None) -> dict[str, Any]:
    prev_k = (prev_state or {}).get("knowledge_state", {}) if isinstance(prev_state, dict) else {}
    prompt = (
        "너는 여행 장소 추천 요청 파서다. JSON만 출력해라.\n"
        '{'
        '"city_name":"영문 도시명 또는 null",'
        '"location_query":"사용자가 말한 위치 원문(지역/동네/랜드마크 포함) 또는 null",'
        '"keyword":"장소/음식/주제 키워드 또는 null",'
        '"brand_or_theme":"brand name/theme or null",'
        '"category":"restaurant|attraction|cafe|shopping|generic"'
        '}\n'
        "규칙:\n"
        "- 맛집/식당/레스토랑 질문은 category=restaurant\n"
        "- 명소/관광지/놀거리/가볼만한 곳 질문은 category=attraction\n"
        "- 카페 질문은 category=cafe\n"
        "- 쇼핑/쇼핑몰/백화점/시장 질문은 category=shopping\n"
        "- city_name은 영문 표준명 (Tokyo, Osaka, Busan, Berlin 등)\n"
        "- '그 음식/그거' 같은 표현이면 최근 대화 문맥에서 keyword 추론\n\n"
        f"이전 지식 상태: {json.dumps(prev_k, ensure_ascii=False)}\n"
        f"최근 대화:\n{context}\n\n"
        f"사용자 질문:\n{message}"
    )
    parsed = _llm_json("장소 추천 요청 JSON만 출력", prompt)
    out = {
        "city_name": (parsed.get("city_name") if isinstance(parsed, dict) else None) or None,
        "location_query": (parsed.get("location_query") if isinstance(parsed, dict) else None) or None,
        "keyword": (parsed.get("keyword") if isinstance(parsed, dict) else None) or None,
        "brand_or_theme": (parsed.get("brand_or_theme") if isinstance(parsed, dict) else None) or None,
        "category": (parsed.get("category") if isinstance(parsed, dict) else None) or "generic",
    }
    if isinstance(out["city_name"], str):
        out["city_name"] = out["city_name"].strip() or None
    if isinstance(out["location_query"], str):
        out["location_query"] = out["location_query"].strip() or None
    if isinstance(out["keyword"], str):
        out["keyword"] = out["keyword"].strip() or None
    if isinstance(out["brand_or_theme"], str):
        out["brand_or_theme"] = out["brand_or_theme"].strip() or None
    out["category"] = str(out["category"]).strip().lower()
    if out["category"] not in {"restaurant", "attraction", "cafe", "shopping", "generic"}:
        out["category"] = "generic"
    return out


def _extract_food_place_request_with_llm(message: str, context: str, prev_state: Optional[dict[str, Any]] = None) -> dict[str, Any]:
    prev_k = (prev_state or {}).get("knowledge_state", {}) if isinstance(prev_state, dict) else {}
    prompt = (
        "너는 여행 맛집 검색 요청 파서다. JSON만 출력해라.\n"
        '{'
        '"city_name":"영문 도시명 또는 null",'
        '"food_keyword":"음식명/키워드 또는 null",'
        '"wants_restaurant":true'
        '}\n'
        "규칙:\n"
        "- '그 음식' 같은 표현이면 최근 대화 문맥에서 음식명을 추론\n"
        "- city_name은 영문 표준명 (Tokyo, Osaka, Busan, Berlin 등)\n"
        "- 음식명을 모르겠으면 null\n"
        "- 맛집/식당 추천 의도면 wants_restaurant=true\n\n"
        f"이전 지식 상태: {json.dumps(prev_k, ensure_ascii=False)}\n"
        f"최근 대화:\n{context}\n\n"
        f"사용자 질문:\n{message}"
    )
    parsed = _llm_json("맛집 검색 요청 JSON만 출력", prompt)
    out = {
        "city_name": (parsed.get("city_name") if isinstance(parsed, dict) else None) or None,
        "food_keyword": (parsed.get("food_keyword") if isinstance(parsed, dict) else None) or None,
        "wants_restaurant": bool((parsed or {}).get("wants_restaurant", True)) if isinstance(parsed, dict) else True,
    }
    if isinstance(out["city_name"], str):
        out["city_name"] = out["city_name"].strip() or None
    if isinstance(out["food_keyword"], str):
        out["food_keyword"] = out["food_keyword"].strip() or None
    return out


def _answer_food_place_followup(message: str, context: str, prev_state: Optional[dict[str, Any]] = None):
    return place_followup_service.answer_food_place_followup(
        message,
        context,
        prev_state,
        extract_food_place_request_with_llm_fn=_extract_food_place_request_with_llm,
        normalize_rag_country_code_fn=_normalize_rag_country_code,
        place_search_radius_m_fn=_place_search_radius_m,
        should_show_place_distance_fn=_should_show_place_distance,
        rewrite_place_recommendation_fallback_fn=_rewrite_place_recommendation_fallback,
    )


def _answer_local_place_followup(message: str, context: str, prev_state: Optional[dict[str, Any]] = None):
    return place_followup_service.answer_local_place_followup(
        message,
        context,
        prev_state,
        extract_local_place_request_with_llm_fn=_extract_local_place_request_with_llm,
        normalize_rag_country_code_fn=_normalize_rag_country_code,
        place_search_radius_m_fn=_place_search_radius_m,
        should_show_place_distance_fn=_should_show_place_distance,
        rewrite_place_recommendation_fallback_fn=_rewrite_place_recommendation_fallback,
        contains_fn=_contains,
    )


def _rewrite_place_recommendation_fallback(
    city_name: str,
    category: str,
    keyword: Optional[str],
    message: str,
    context: str,
) -> Optional[str]:
    return knowledge_helpers_service.rewrite_place_recommendation_fallback(
        city_name, category, keyword, message, context, client=client
    )

def _knowledge_top_k(message: str, topic: Optional[str], subtopic: Optional[str]) -> int:
    return chat_heuristics_service.knowledge_top_k(message, topic, subtopic, rag_top_k=RAG_TOP_K)


def _is_budget_destination_recommendation_query(message: str) -> bool:
    m = (message or "").lower()
    budget = ["\uac00\uc131\ube44", "\uc608\uc0b0", "\ub9cc\uc6d0", "\uc6d0 \uc774\ud558", "\uc800\ub834", "\uc2f8\uac8c", "budget", "cheap", "affordable"]
    rec = ["\ucd94\ucc9c", "\ucd94\ucc9c\uc9c0", "\uc5ec\ud589\uc9c0", "\uc5b4\ub514", "\uac08\ub9cc", "\uac00고\uc2f6", "trip", "destination"]
    region = ["\ub3d9\ub0a8\uc544", "\uc77c\ubcf8", "\uc720\ub7fd", "\ud574\uc678", "southeast asia", "asia"]
    return (_contains(m, budget) and _contains(m, rec)) or (_contains(m, ["\ub3d9\ub0a8\uc544"]) and _contains(m, rec)) or (_contains(m, region) and _contains(m, ["\uac00\uc131\ube44", "\ucd94\ucc9c"]))


def _rewrite_budget_destination_fallback(message: str, context: str) -> Optional[str]:
    return knowledge_helpers_service.rewrite_budget_destination_fallback(message, context, client=client)

def _answer_knowledge(message: str, context: str, prev_state: Optional[dict[str, Any]] = None):
    return knowledge_service.answer_knowledge(
        message,
        context,
        prev_state,
        _is_local_place_followup=_is_local_place_followup,
        _answer_local_place_followup=_answer_local_place_followup,
        _resolve_knowledge_context_with_llm=_resolve_knowledge_context_with_llm,
        _infer_rag_country_code=_infer_rag_country_code,
        _build_knowledge_retrieval_query=_build_knowledge_retrieval_query,
        _knowledge_top_k=_knowledge_top_k,
        answer_rag_question=answer_rag_question,
        _strip_markdown_decorations=_strip_markdown_decorations,
    )


def _extract_checkout_amount_krw(offer: FlightCheckoutOfferInput) -> int:
    price = offer.price or {}
    try:
        krw_total = price.get("krwTotal")
        if krw_total is not None:
            amount = int(round(float(krw_total)))
            if amount > 0:
                return amount
    except Exception:
        pass

    ccy = str(price.get("currency") or "").upper().strip()
    total = price.get("total")
    if ccy == "KRW":
        try:
            amount = int(round(float(total)))
            if amount > 0:
                return amount
        except Exception:
            pass
    raise HTTPException(status_code=400, detail="결제 금액을 확정할 수 없습니다. KRW 금액이 있는 항공권으로 다시 시도해 주세요.")


def _build_flight_order_name(offer: FlightCheckoutOfferInput) -> str:
    itineraries = offer.itineraries or []
    dep = ""
    arr = ""
    try:
        dep = str((((itineraries[0] or {}).get("segments") or [])[0].get("departure") or {}).get("iataCode") or "")
        outbound_itin = itineraries[0] or {}
        outbound_segs = outbound_itin.get("segments") or []
        arr = str(((outbound_segs[-1].get("arrival") or {}).get("iataCode") if outbound_segs else "") or "")
    except Exception:
        dep = ""
        arr = ""
    route = f"{dep}-{arr}".strip("-")
    airline = str(offer.airline or "항공권").strip() or "항공권"
    if route:
        return f"{airline} {route}"
    return airline


@router.post("/api/flight/checkout")
def api_flight_checkout(payload: FlightCheckoutRequest, request: Request):
    session_token = request.cookies.get("session_token")
    user_id = get_user_id_from_session(session_token) if session_token else None
    if not user_id:
        raise HTTPException(status_code=401, detail="LOGIN_REQUIRED")

    if not payload.passengers:
        raise HTTPException(status_code=400, detail="탑승자 정보가 필요합니다.")

    amount = _extract_checkout_amount_krw(payload.offer)
    order_id = f"FLT-{datetime.now().strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:8]}"
    order_name = _build_flight_order_name(payload.offer)
    toss_client_key = (os.getenv("TOSS_PAYMENTS_CLIENT_KEY") or os.getenv("TOSS_CLIENT_KEY") or "").strip()
    base_url = str(request.base_url).rstrip("/")

    PENDING_FLIGHT_ORDERS[order_id] = {
        "user_id": str(user_id),
        "amount": amount,
        "order_name": order_name,
        "customer_name": payload.customer_name,
        "customer_email": payload.customer_email,
        "customer_phone": payload.customer_phone,
        "passengers": [p.model_dump() for p in payload.passengers],
        "offer": payload.offer.model_dump(),
        "created_at": datetime.now().isoformat(),
    }

    return {
        "order_id": order_id,
        "order_name": order_name,
        "amount": amount,
        "currency": "KRW",
        "payment_mode": "toss" if toss_client_key else "mock",
        "toss_client_key": toss_client_key,
        "success_url": f"{base_url}/payment/flight/success",
        "fail_url": f"{base_url}/payment/flight/fail",
        "message": "결제 준비가 완료되었습니다." if toss_client_key else "토스 클라이언트 키가 없어 모의 결제 모드로 동작합니다.",
    }


@router.post("/api/payments/toss/confirm")
def api_toss_confirm(payload: TossConfirmRequest):
    pending = PENDING_FLIGHT_ORDERS.get(payload.orderId)
    if not pending:
        raise HTTPException(status_code=404, detail="주문 정보를 찾을 수 없습니다.")
    if int(pending.get("amount") or 0) != int(payload.amount):
        raise HTTPException(status_code=400, detail="결제 금액 검증에 실패했습니다.")

    secret_key = (os.getenv("TOSS_PAYMENTS_SECRET_KEY") or os.getenv("TOSS_SECRET_KEY") or "").strip()
    if not secret_key:
        pending["status"] = "confirmed_mock"
        pending["payment_key"] = payload.paymentKey
        pending["confirmed_at"] = datetime.now().isoformat()
        save_booking(
            user_id=int(pending.get("user_id") or 0),
            item_type="flight",
            order_id=payload.orderId,
            order_name=str(pending.get("order_name") or "항공권"),
            amount=int(payload.amount),
            currency="KRW",
            status="confirmed_mock",
            status_label="예약 확정(모의 결제)",
            route=_extract_flight_route_from_offer(pending.get("offer")),
            payment_key=payload.paymentKey,
            payload=pending,
            created_at_iso=str(pending.get("created_at") or ""),
            confirmed_at_iso=str(pending.get("confirmed_at") or ""),
        )
        return {
            "status": "confirmed_mock",
            "order_id": payload.orderId,
            "amount": payload.amount,
            "message": "토스 시크릿 키가 없어 모의 승인 처리되었습니다.",
        }

    auth = base64.b64encode(f"{secret_key}:".encode("utf-8")).decode("ascii")
    try:
        res = requests.post(
            "https://api.tosspayments.com/v1/payments/confirm",
            headers={
                "Authorization": f"Basic {auth}",
                "Content-Type": "application/json",
            },
            json={
                "paymentKey": payload.paymentKey,
                "orderId": payload.orderId,
                "amount": payload.amount,
            },
            timeout=15,
        )
        data = res.json() if res.content else {}
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"토스 승인 요청 실패: {e}")

    if not res.ok:
        msg = (data or {}).get("message") if isinstance(data, dict) else None
        raise HTTPException(status_code=400, detail=msg or f"토스 승인 실패 ({res.status_code})")

    pending["status"] = "confirmed"
    pending["payment_key"] = payload.paymentKey
    pending["confirmed_at"] = datetime.now().isoformat()
    pending["toss_response"] = data
    save_booking(
        user_id=int(pending.get("user_id") or 0),
        item_type="flight",
        order_id=payload.orderId,
        order_name=str(pending.get("order_name") or "항공권"),
        amount=int(payload.amount),
        currency="KRW",
        status="confirmed",
        status_label="예약 확정",
        route=_extract_flight_route_from_offer(pending.get("offer")),
        payment_key=payload.paymentKey,
        payload=pending,
        created_at_iso=str(pending.get("created_at") or ""),
        confirmed_at_iso=str(pending.get("confirmed_at") or ""),
    )
    return {"status": "confirmed", "order_id": payload.orderId, "amount": payload.amount, "payment": data}


def _extract_flight_route_from_offer(offer: Any) -> str:
    if not isinstance(offer, dict):
        return ""
    itineraries = offer.get("itineraries") if isinstance(offer.get("itineraries"), list) else []
    out_segs = itineraries[0].get("segments") if itineraries and isinstance(itineraries[0], dict) else []
    first_seg = out_segs[0] if out_segs and isinstance(out_segs[0], dict) else {}
    last_seg = out_segs[-1] if out_segs and isinstance(out_segs[-1], dict) else {}
    dep = ((first_seg.get("departure") or {}).get("iataCode") if isinstance(first_seg, dict) else "") or ""
    arr = ((last_seg.get("arrival") or {}).get("iataCode") if isinstance(last_seg, dict) else "") or ""
    return f"{dep} -> {arr}".strip(" ->")


@router.get("/api/flight/bookings")
def api_flight_bookings(request: Request, limit: int = Query(20, ge=1, le=100)):
    session_token = request.cookies.get("session_token")
    user_id = get_user_id_from_session(session_token) if session_token else None
    if not user_id:
        raise HTTPException(status_code=401, detail="LOGIN_REQUIRED")

    rows = [row for row in get_user_bookings(int(user_id), limit=limit) if str(row.get("item_type") or "") == "flight"]
    return {"bookings": rows[:limit]}


@router.get("/payment/flight/success", response_class=HTMLResponse)
def payment_flight_success_page():
    return """
<!doctype html>
<html lang="ko">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width,initial-scale=1">
    <title>DESTINO | 결제 확인</title>
    <link rel="stylesheet" as="style" crossorigin href="https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/static/pretendard.css" />
    <style>
        :root {
            --primary-blue: #00AEEF;
            --dark-navy: #1A202C;
            --bg-gray: #F8F9FA;
            --text-muted: #718096;
        }
        * { box-sizing: border-box; font-family: 'Pretendard', -apple-system, sans-serif; }
        body {
            background-color: var(--bg-gray);
            display: flex; align-items: center; justify-content: center;
            height: 100vh; margin: 0; color: var(--dark-navy);
        }
        .container {
            background: #fff;
            width: 100%;
            max-width: 480px;
            padding: 40px 24px;
            border-radius: 20px;
            box-shadow: 0 10px 25px rgba(0,0,0,0.05);
            text-align: center;
        }
        .status-icon {
            width: 64px; height: 64px;
            background: #f0f9ff;
            border-radius: 50%;
            display: flex; align-items: center; justify-content: center;
            margin: 0 auto 24px;
        }
        .spinner {
            width: 24px; height: 24px;
            border: 3px solid #e2e8f0;
            border-top-color: var(--primary-blue);
            border-radius: 50%;
            animation: spin 1s linear infinite;
        }
        @keyframes spin { to { transform: rotate(360deg); } }
        h2 { font-size: 24px; font-weight: 700; margin-bottom: 12px; letter-spacing: -0.5px; }
        p { color: var(--text-muted); line-height: 1.6; margin-bottom: 32px; }
        .info-card {
            background: #f8fafc;
            border-radius: 12px;
            padding: 20px;
            margin-bottom: 32px;
            text-align: left;
            display: none;
        }
        .info-row {
            display: flex; justify-content: space-between; margin-bottom: 8px;
            font-size: 14px;
        }
        .info-row span:first-child { color: var(--text-muted); }
        .info-row span:last-child { font-weight: 600; }
        .btn {
            display: block;
            width: 100%;
            padding: 16px;
            border-radius: 12px;
            text-decoration: none;
            font-weight: 600;
            transition: all 0.2s;
        }
        .btn-primary { background-color: var(--primary-blue); color: white; }
        .btn-primary:hover { background-color: #0096ce; }
        .btn-outline { border: 1px solid #e2e8f0; color: var(--text-muted); margin-top: 12px; font-size: 14px; }
    </style>
</head>
<body>
    <div class="container">
        <div class="status-icon" id="icon-box">
            <div class="spinner" id="spinner"></div>
        </div>
        <h2 id="title">결제 확인 중</h2>
        <p id="msg">안전한 결제 승인을 위해 잠시만 기다려 주세요.</p>
        <div class="info-card" id="info-card">
            <div class="info-row">
                <span>주문번호</span>
                <span id="res-orderId">-</span>
            </div>
            <div class="info-row">
                <span>결제금액</span>
                <span id="res-amount">-</span>
            </div>
        </div>
        <a href="/mypage" class="btn btn-primary" id="main-btn">마이페이지로 이동</a>
        <a href="/airport" class="btn btn-outline">항공 검색으로</a>
    </div>
    <script>
        const qs = new URLSearchParams(location.search);
        const orderId = qs.get('orderId');
        const amount = Number(qs.get('amount') || 0);
        const body = { paymentKey: qs.get('paymentKey'), orderId: orderId, amount: amount };
        fetch('/api/payments/toss/confirm', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(body)
        })
        .then(async r => ({ ok: r.ok, data: await r.json().catch(() => ({})) }))
        .then(x => {
            const iconBox = document.getElementById('icon-box');
            const title = document.getElementById('title');
            const msg = document.getElementById('msg');
            const infoCard = document.getElementById('info-card');
            if (x.ok) {
                iconBox.innerHTML = '✅';
                iconBox.style.fontSize = '32px';
                title.textContent = '결제가 완료되었습니다!';
                msg.textContent = '항공권 예약이 완료되었습니다. 마이페이지에서 상세 내역을 확인하세요.';
                infoCard.style.display = 'block';
                document.getElementById('res-orderId').textContent = orderId;
                document.getElementById('res-amount').textContent = amount.toLocaleString() + '원';
                document.getElementById('main-btn').textContent = '항공 상품 페이지로 돌아가기';
            } else {
                iconBox.innerHTML = '❌';
                iconBox.style.fontSize = '32px';
                title.textContent = '결제에 실패했습니다';
                msg.textContent = x.data?.detail || x.data?.message || '알 수 없는 오류가 발생했습니다.';
            }
        })
        .catch(() => {
            document.getElementById('title').textContent = '오류 발생';
            document.getElementById('msg').textContent = '서버와의 통신 중 문제가 발생했습니다.';
        });
    </script>
</body>
</html>
"""


@router.get("/payment/flight/confirmed", response_class=HTMLResponse)
def payment_flight_confirmed_page(orderId: str | None = Query(None)):
    oid = (orderId or "").strip()
    row = PENDING_FLIGHT_ORDERS.get(oid) if oid else None
    amount = int(row.get("amount") or 0) if isinstance(row, dict) else 0
    order_name = str(row.get("order_name") or "항공권") if isinstance(row, dict) else "항공권"
    status = str(row.get("status") or "confirmed") if isinstance(row, dict) else "confirmed"
    confirmed_at = str(row.get("confirmed_at") or "") if isinstance(row, dict) else ""
    status_label = "예약 확정"
    if status == "confirmed_mock":
        status_label = "예약 확정(모의 결제)"

    return f"""
<!doctype html>
<html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>예약 확정</title>
<style>
body{{font-family:Pretendard,sans-serif;padding:24px;background:#f8fafc;color:#0f172a}}
.box{{max-width:640px;margin:24px auto;background:#fff;border:1px solid #e2e8f0;border-radius:12px;padding:20px}}
.ok{{display:inline-block;padding:4px 10px;border-radius:999px;background:#dcfce7;color:#166534;font-size:12px;font-weight:700}}
.row{{margin-top:10px;color:#334155;font-size:14px}}
.amt{{margin-top:12px;font-size:30px;font-weight:800;color:#0f172a}}
.actions{{margin-top:18px;display:flex;gap:10px;flex-wrap:wrap}}
.btn{{display:inline-flex;align-items:center;justify-content:center;padding:10px 14px;border-radius:10px;text-decoration:none;font-weight:700}}
.btn-primary{{background:#1d4ed8;color:#fff}}
.btn-ghost{{border:1px solid #cbd5e1;color:#0f172a;background:#fff}}
</style>
</head>
<body>
  <div class="box">
    <span class="ok">{status_label}</span>
    <h2 style="margin:10px 0 4px;">예약이 완료되었습니다.</h2>
    <div class="row">상품: {order_name}</div>
    <div class="row">주문번호: {oid or '-'}</div>
    <div class="row">승인시각: {confirmed_at or '-'}</div>
    <div class="amt">KRW {amount:,}</div>
    <div class="row">2초 후 마이페이지로 이동합니다.</div>
    <div class="actions">
      <a class="btn btn-primary" href="/airport">항공 상품 페이지로 돌아가기</a>
      <a class="btn btn-ghost" href="/">메인페이지로 돌아가기</a>
    </div>
  </div>
  <script>
    setTimeout(function () {{
      window.location.replace('/mypage');
    }}, 2000);
  </script>
</body></html>
"""


@router.get("/payment/flight/fail", response_class=HTMLResponse)
def payment_flight_fail_page(code: str | None = Query(None), message: str | None = Query(None)):
    c = (code or "").strip()
    m = (message or "").strip()
    return f"""
<!doctype html>
<html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>결제 실패</title>
<style>body{{font-family:Pretendard,sans-serif;padding:24px;background:#f8fafc;color:#0f172a}} .box{{max-width:560px;margin:24px auto;background:#fff;border:1px solid #fecaca;border-radius:12px;padding:18px}} .muted{{color:#64748b;font-size:14px}}</style>
</head><body><div class="box"><h2>결제가 완료되지 않았습니다.</h2><p class="muted">코드: {c or '-'}</p><p class="muted">메시지: {m or '-'}</p><a href="/airport">항공 페이지로 돌아가기</a></div></body></html>
"""


@router.get("/api/flight-search")
def api_flight_search(
    origin: str = Query(...),
    destination: str = Query(...),
    departure_date: str = Query(...),
    return_date: Optional[str] = Query(None),
    adults: int = Query(1),
    child: int = Query(0),
    infant: int = Query(0),
    cabin: Optional[str] = Query(None),
    max_price: Optional[float] = Query(None),
):
    try:
        amadeus_base = str(os.getenv("AMADEUS_BASE_URL") or "https://test.api.amadeus.com").strip().lower()
        pricing_mode = "test" if "test.api.amadeus.com" in amadeus_base else "live"
        raw = flight_search_service._search_flights(
            origin=origin,
            destination=destination,
            departure_date=departure_date,
            return_date=return_date,
            adults=adults,
            children=child,
            infants=infant,
            max_price=max_price,
            cabin=cabin,
            max_results=30,
        )
        rates = flight_search_service._attach_krw(raw)
        return {
            "results": raw.get("data", []),
            "simplified": flight_search_service._simplify(raw),
            "meta_query": raw.get("meta_query", {}),
            "booking_reference": raw.get("booking_reference", []),
            "exchange_rates": rates,
            "pricing_mode": pricing_mode,
            "pricing_notice": "테스트 요금(참고용)" if pricing_mode == "test" else "",
            "raw": raw,
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"항공권 검색 실패: {e}")


@router.post("/chat")
def chat(req: ChatRequest, request: Request):
    session_token = request.cookies.get("session_token")
    user_id = get_user_id_from_session(session_token) if session_token else None
    if not user_id:
        raise HTTPException(status_code=401, detail="LOGIN_REQUIRED")

    return chat_orchestrator_service.handle_chat_request(
        req,
        SESSION_HISTORY=SESSION_HISTORY,
        SESSION_STATE=SESSION_STATE,
        NeedMoreInfoError=NeedMoreInfoError,
        _build_context=_build_context,
        _is_smalltalk_greeting=_is_smalltalk_greeting,
        _classify_travel_domain_with_llm=_classify_travel_domain_with_llm,
        _resolve_intent_with_llm=_resolve_intent_with_llm,
        _detect_intent=_detect_intent,
        _has_date_signal=_has_date_signal,
        _contains=_contains,
        _should_keep_knowledge_followup=_should_keep_knowledge_followup,
        _is_local_place_followup=_is_local_place_followup,
        _is_route_guidance_query=_is_route_guidance_query,
        _should_ask_intent_clarification=_should_ask_intent_clarification,
        _answer_knowledge=_answer_knowledge,
        _parse_hotel_slots=_parse_hotel_slots,
        hotel_service=hotel_service,
        client=client,
        _strip_markdown_decorations=_strip_markdown_decorations,
        _parse_flight_slots=_parse_flight_slots,
        _merge_state=_merge_state,
        _missing_questions=_missing_questions,
        flight_search_service=flight_search_service,
        chat_renderers=chat_renderers,
    )
