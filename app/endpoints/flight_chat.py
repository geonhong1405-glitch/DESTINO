import json
import os
import re
from datetime import datetime, timedelta
from typing import Any, Optional
from zoneinfo import ZoneInfo
import requests

from dotenv import load_dotenv
from fastapi import APIRouter, HTTPException, Query, Request
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
