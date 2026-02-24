import json
import os
import re
from datetime import datetime, timedelta
from typing import Any, Optional

from dotenv import load_dotenv
from fastapi import APIRouter, HTTPException, Query
from openai import OpenAI
from pydantic import BaseModel

from app.api.amadeus_api import (
    resolve_location_to_iata as amadeus_resolve_location_to_iata,
    search_flight_offers_raw,
)
from app.api.booking_hotel_flight_api import (
    recommend_buckets as booking_recommend_buckets,
    search_destination as booking_search_destination,
    search_flights as booking_search_flights,
    search_hotels_by_dest_id,
)
from app.api.exchange_rate import get_exchange_rate
from app.endpoints.rag_api import answer_rag_question

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

DEFAULT_FX_TO_KRW = {"KRW": 1.0, "USD": 1350.0, "EUR": 1470.0, "JPY": 9.0}


class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = None


class NeedMoreInfoError(Exception):
    pass


def _to_float(v: Any) -> Optional[float]:
    try:
        return float(v)
    except Exception:
        return None


def _clean_json(s: str) -> str:
    return (s or "").replace("```json", "").replace("```", "").strip()


def _contains(text: str, kws: list[str]) -> bool:
    return any(k in (text or "") for k in kws)


def _parse_rel_date(text: str):
    t = re.sub(r"\s+", "", (text or "").lower())
    t = t.replace("\ub0b4\uc77c\ubaa8\ub798", "\ub0b4\uc77c\ubaa8\ub808")
    now = datetime.now()
    if "\uc624\ub298" in t:
        return now.date()
    if "\ub0b4\uc77c\ubaa8\ub808" in t or "\ubaa8\ub808" in t:
        return (now + timedelta(days=2)).date()
    if "\uae00\ud53c" in t:
        return (now + timedelta(days=3)).date()
    if "\ub0b4\uc77c" in t:
        return (now + timedelta(days=1)).date()
    m = re.search(r"(\d+)\uc77c\ud6c4", t)
    if m:
        return (now + timedelta(days=int(m.group(1)))).date()
    return None

def _has_date_signal(text: str) -> bool:
    if re.search(r"\b20\d{2}-\d{2}-\d{2}\b", text or ""):
        return True
    return _contains(text or "", ["\uc624\ub298", "\ub0b4\uc77c", "\ubaa8\ub808", "\uae00\ud53c", "\ub2e4\uc74c\uc8fc", "\uc774\ubc88\uc8fc", "\uc8fc\ub9d0"])

def _build_context(history: list[dict[str, str]], max_items: int = 16) -> str:
    return "\n".join(f"{x.get('role')}: {x.get('text')}" for x in history[-max_items:])


def _norm_iata(keyword: str) -> Optional[str]:
    raw = (keyword or "").strip()
    if not raw:
        return None
    k = re.sub(r"\s+", "", raw)
    if k in LOCATION_ALIASES:
        return LOCATION_ALIASES[k]
    if k in COUNTRY_ALIASES:
        return COUNTRY_ALIASES[k]
    if len(k) == 3 and k.isalpha():
        return k.upper()
    return amadeus_resolve_location_to_iata(k)


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


def _resolve_knowledge_context_with_llm(message: str, context: str, prev_state: Optional[dict[str, Any]] = None) -> dict[str, Any]:
    today = datetime.now().strftime("%Y-%m-%d")
    prev_k = (prev_state or {}).get("knowledge_state", {}) if isinstance(prev_state, dict) else {}
    prompt = (
        f"오늘 날짜는 {today}.\n"
        "너는 여행 지식 질문 문맥 해석기다. 아래 JSON만 출력해라.\n"
        '{'
        '"intent":"knowledge|unknown",'
        '"country_code":"JP|KR|... 또는 null",'
        '"city_name":"Tokyo|Osaka|... 또는 null",'
        '"topic":"safety|culture|visa|transport|money|health|emergency|connectivity 또는 null",'
        '"subtopic":"문자열 또는 null",'
        '"exclude_topics":["topic", "..."],'
        '"needs_context_carry":true'
        '}\n'
        "규칙:\n"
        "- 후속 질문(예: '말고는?', '그건?', '어떻게 이용해?')이면 이전 대화 문맥을 적극 반영\n"
        "- '지하철/전철/교통카드/패스'는 topic=transport\n"
        "- '팁/예절/문화'는 topic=culture\n"
        "- '긴급/경찰/119/110'은 topic=emergency 또는 safety\n"
        "- 한국어 질문이면 city_name은 영문 표준명으로 출력 (예: 도쿄->Tokyo, 오사카->Osaka)\n"
        "- 모르면 null\n\n"
        f"이전 지식 상태(있으면 참고): {json.dumps(prev_k, ensure_ascii=False)}\n"
        f"최근 대화:\n{context}\n\n"
        f"사용자 질문:\n{message}"
    )
    parsed = _llm_json("여행 지식 문맥 JSON만 출력", prompt)
    out = {
        "intent": parsed.get("intent") or "unknown",
        "country_code": (parsed.get("country_code") or None),
        "city_name": (parsed.get("city_name") or None),
        "topic": (parsed.get("topic") or None),
        "subtopic": (parsed.get("subtopic") or None),
        "exclude_topics": parsed.get("exclude_topics") or [],
    }
    if isinstance(out["country_code"], str):
        out["country_code"] = out["country_code"].upper().strip() or None
    if isinstance(out["city_name"], str):
        out["city_name"] = out["city_name"].strip() or None
    if isinstance(out["topic"], str):
        out["topic"] = out["topic"].strip() or None
    if isinstance(out["subtopic"], str):
        out["subtopic"] = out["subtopic"].strip() or None
    if not isinstance(out["exclude_topics"], list):
        out["exclude_topics"] = []
    return out


def _parse_flight_slots(message: str, context: str) -> dict[str, Any]:
    today = datetime.now().strftime("%Y-%m-%d")
    prompt = (
        f"\uc624\ub298 \ub0a0\uc9dc\ub294 {today}. \uc544\ub798 JSON\ub9cc \ucd9c\ub825:\n"
        '{"origin":null,"destination":null,"departure_date":null,"return_date":null,"adults":1,"sort_by":null,"trip_type":null,"limit":null}\n'
        "\uaddc\uce59: \uc800\ub834=price_asc, \ube60\ub978=fastest, \ube60\ub974\uace0 \uc800\ub834=fastest_cheap, \uc655\ubcf5\uc774\uba74 trip_type=round.\n"
        f"\uc785\ub825:{message}\n\ub300\ud654:{context}"
    )
    parsed = _llm_json("\ud56d\uacf5\uad8c \uac80\uc0c9 JSON\ub9cc \ucd9c\ub825", prompt)
    parsed.setdefault("origin", None)
    parsed.setdefault("destination", None)
    parsed.setdefault("departure_date", None)
    parsed.setdefault("return_date", None)
    parsed.setdefault("adults", 1)
    parsed.setdefault("sort_by", None)
    parsed.setdefault("trip_type", None)
    parsed.setdefault("limit", None)
    parsed.setdefault("max_price", None)
    parsed.setdefault("time_pref", None)
    parsed.setdefault("departure_window", None)
    parsed.setdefault("direct_only", None)

    msg_l = (message or "").lower()
    has_round_signal = _contains(message, ["\uc655\ubcf5", "\uac14\ub2e4\uac00", "\ub3cc\uc544\uc624\ub294", "\ubcf5\uadc0"]) or "round trip" in msg_l or "roundtrip" in msg_l
    has_oneway_signal = _contains(message, ["\ud3b8\ub3c4"]) or "oneway" in msg_l or "one-way" in msg_l
    if has_round_signal:
        parsed["trip_type"] = "round"
    elif has_oneway_signal:
        parsed["trip_type"] = "oneway"
    else:
        parsed["trip_type"] = None

    if not parsed.get("departure_date"):
        d = _parse_rel_date(message)
        if d:
            parsed["departure_date"] = d.strftime("%Y-%m-%d")

    if "\uc778\ub3c4" in (message or "") or "india" in msg_l:
        if (parsed.get("destination") or "").upper() in {"", "IND", "IN"}:
            parsed["destination"] = "DEL"

    m = re.search(r"(?:\uc131\uc778\\s*)?(\\d+)\\s*\uba85", message or "")
    if m:
        parsed["adults"] = max(1, int(m.group(1)))

    if _contains(message, ["\uc800\ub834", "\uc2fc", "\uac00\uc131\ube44"]):
        parsed["sort_by"] = "price_asc"
    if _contains(message, ["\uac00\uc7a5 \ube68\ub9ac", "\ucd5c\ub2e8", "\ube60\ub974\uac8c"]):
        parsed["sort_by"] = "fastest_cheap" if parsed.get("sort_by") == "price_asc" else "fastest"
    return parsed

def _parse_hotel_slots(message: str, context: str) -> dict[str, Any]:
    today = datetime.now().strftime("%Y-%m-%d")
    prompt = (
        f"\uc624\ub298 \ub0a0\uc9dc\ub294 {today}. JSON\ub9cc \ucd9c\ub825:\n"
        '{"query":null,"checkin_date":null,"checkout_date":null,"adults":2,"top_k":5,"bucket":"value_top"}\n'
        "\ud6c4\uae30=review_top, \uc704\uce58=location_top, \uac00\uc131\ube44=value_top.\n"
        f"\uc785\ub825:{message}\n\ub300\ud654:{context}"
    )
    parsed = _llm_json("\ud638\ud154 \ucd94\ucc9c JSON\ub9cc \ucd9c\ub825", prompt)
    parsed.setdefault("query", None)
    parsed.setdefault("checkin_date", None)
    parsed.setdefault("checkout_date", None)
    parsed.setdefault("adults", 2)
    parsed.setdefault("top_k", 5)
    parsed.setdefault("bucket", "value_top")
    if not parsed.get("checkin_date"):
        d = _parse_rel_date(message)
        if d:
            parsed["checkin_date"] = d.strftime("%Y-%m-%d")
    compact = re.sub(r"\\s+", "", message or "")
    m = re.search(r"(\uc624\ub298|\ub0b4\uc77c|\ubaa8\ub808|\ub0b4\uc77c\ubaa8\ub808|\uae00\ud53c)(?:\ubd80\ud130)?(\\d+)\uc77c", compact)
    if m:
        base = _parse_rel_date(m.group(1))
        if base:
            parsed["checkin_date"] = base.strftime("%Y-%m-%d")
            parsed["checkout_date"] = (base + timedelta(days=int(m.group(2)))).strftime("%Y-%m-%d")
    if "\ud6c4\uae30" in (message or ""):
        parsed["bucket"] = "review_top"
    elif any(k in (message or "") for k in ["\uc704\uce58", "\uadfc\ucc98", "\uc8fc\ubcc0"]):
        parsed["bucket"] = "location_top"
    elif "\uac00\uc131\ube44" in (message or ""):
        parsed["bucket"] = "value_top"
    m2 = re.search(r"top\\s*(\\d+)", (message or "").lower()) or re.search(r"(\\d+)\\s*\uac1c", message or "")
    if m2:
        parsed["top_k"] = int(m2.group(1))
    return parsed

def _detect_intent(message: str, prev_state: dict[str, Any]) -> str:
    m = (message or "").lower()
    if _contains(m, ["\uc5ec\ud589\uc9c0", "\ucd94\ucc9c\uc9c0", "\uac00\ubcfc\ub9cc", "\uad00\uad11\uc9c0"]):
        if not _contains(m, ["\ud56d\uacf5", "\ud56d\uacf5\uad8c", "\ube44\ud589\uae30", "\ucd9c\ubc1c", "\ub3c4\ucc29"]):
            return "knowledge"
    if prev_state.get("last_intent") == "knowledge":
        if not _contains(m, ["\ud56d\uacf5", "\ud56d\uacf5\uad8c", "\ube44\ud589\uae30", "\ucd9c\ubc1c", "\ub3c4\ucc29", "\ud638\ud154", "\uc219\uc18c"]):
            if _contains(m, ["\uba39\uc744\uac70", "\uc74c\uc2dd", "\ub9db\uc9d1", "\ucd94\ucc9c", "\uc5b4\ub54c", "\ub9d0\uace0", "\uadf8\ub7fc"]):
                return "knowledge"
    if _contains(m, ["\uad50\ud1b5", "\uc9c0\ud558\ucca0", "\uc804\ucca0", "\ud328\uc2a4", "\uc2a4\uc774\uce74", "\ud30c\uc2a4\ubaa8"]):
        if not _contains(m, ["\ud56d\uacf5", "\ud56d\uacf5\uad8c", "\ube44\ud589\uae30", "\ucd9c\ubc1c", "\ub3c4\ucc29"]):
            return "knowledge"
    if any(k in (message or "") for k in ["\ud2b9\uc9d5", "\uc124\uba85", "\uc815\ubcf4", "\uc18c\uac1c", "\ubb50\uc57c", "\uc5b4\ub54c"]):
        if not any(k in (message or "") for k in ["\ud56d\uacf5", "\ube44\ud589", "\ud56d\uacf5\uad8c", "\ucd9c\ubc1c", "\ub3c4\ucc29", "\ud638\ud154", "\uc219\uc18c"]):
            return "knowledge"
    if _contains(m, ["\ud638\ud154", "\uc219\uc18c", "\uc219\ubc15", "\uccb4\ud06c\uc778", "\uccb4\ud06c\uc544\uc6c3"]):
        return "hotel"
    if _contains(m, ["\uc77c\uc815", "\ucf54\uc2a4", "\ub8e8\ud2b8", "\ud50c\ub79c", "day 1", "1\uc77c\ucc28"]):
        return "itinerary"
    if _contains(m, ["\uc5b4\ub514", "\ubb38\ud654", "\ube44\uc790", "\uc2dc\ucc28", "\ud658\uc728", "\uc5ec\ud589\ud301", "\uba85\uc18c", "\ub9db\uc9d1", "\ud2b9\uc9d5", "\uc124\uba85", "\uc815\ubcf4"]) and not _contains(m, ["\ud56d\uacf5", "\ud56d\uacf5\uad8c", "\ube44\ud589\uae30", "\ucd9c\ubc1c", "\ub3c4\ucc29"]):
        return "knowledge"
    if prev_state.get("hotel_context") and _contains(m, ["\ud6c4\uae30", "\uc704\uce58", "\uac00\uc131\ube44", "top", "\uc21c\uc704", "\ucd94\ucc9c", "\ub2e4\uc2dc"]):
        return "hotel"
    if prev_state.get("last_intent") == "hotel" and not _contains(m, ["\ud56d\uacf5", "\ube44\ud589\uae30", "\ucd9c\ubc1c", "\ub3c4\ucc29"]):
        return "hotel"
    return "flight"

def _merge_state(prev: dict[str, Any], cur: dict[str, Any]) -> dict[str, Any]:
    out = dict(prev or {})
    for key in SLOT_KEYS:
        value = cur.get(key)
        if value is None:
            continue
        if isinstance(value, str) and value.strip().lower() in {"", "null", "none", "unknown", "n/a", "-"}:
            continue
        out[key] = value
    out.setdefault("adults", 1)
    return out


def _missing_questions(state: dict[str, Any]) -> list[str]:
    q = []
    if not state.get("origin"):
        q.append("\ucd9c\ubc1c\uc9c0\ub97c \uc54c\ub824\uc8fc\uc138\uc694. (\uc608: \uc11c\uc6b8, \ubd80\uc0b0, ICN)")
    if not state.get("destination"):
        q.append("\ub3c4\ucc29\uc9c0\ub97c \uc54c\ub824\uc8fc\uc138\uc694. (\uc608: \ub3c4\ucfc4, \ubd80\uc0b0, NRT)")
    if not state.get("departure_date"):
        q.append("\ucd9c\ubc1c\uc77c\uc744 \uc54c\ub824\uc8fc\uc138\uc694. (YYYY-MM-DD \ub610\ub294 \uc608: 3\uc6d4 15\uc77c)")
    if state.get("trip_type") == "round" and not state.get("return_date"):
        q.append("\uc655\ubcf5 \uc77c\uc815\uc774\ubbc0\ub85c \ubcf5\uadc0\uc77c\uc744 \uc54c\ub824\uc8fc\uc138\uc694. (YYYY-MM-DD)")
    return q


def _search_flights(
    origin: str,
    destination: str,
    departure_date: str,
    return_date: Optional[str] = None,
    adults: int = 1,
    max_price: Optional[float] = None,
    cabin: Optional[str] = None,
    max_results: int = 30,
) -> dict[str, Any]:
    origin_iata = _norm_iata(origin)
    destination_iata = _norm_iata(destination)
    if not origin_iata or not destination_iata:
        raise ValueError(f"출발/도착지를 공항 코드로 해석하지 못했습니다. origin={origin}, destination={destination}")

    data = search_flight_offers_raw(
        origin_code=origin_iata,
        destination_code=destination_iata,
        departure_date=departure_date,
        return_date=return_date,
        adults=adults,
        cabin=cabin,
        max_results=max_results,
    )
    try:
        b = booking_search_flights(origin_iata, destination_iata, departure_date, return_date, adults)
        data["booking_reference"] = b.get("data", [])
    except Exception as e:
        data["booking_reference_error"] = str(e)
    if max_price is not None:
        data["data"] = [
            x for x in data.get("data", []) if _to_float((x.get("price") or {}).get("total")) is not None and _to_float((x.get("price") or {}).get("total")) <= float(max_price)
        ]
    data["meta_query"] = {
        "origin": origin_iata,
        "destination": destination_iata,
        "departure_date": departure_date,
        "return_date": return_date,
        "adults": adults,
        "max_price": max_price,
        "cabin": cabin,
    }
    return data


def _attach_krw(raw: dict[str, Any]) -> dict[str, float]:
    rates: dict[str, float] = {}
    for offer in raw.get("data", []):
        cur = str((offer.get("price") or {}).get("currency", "")).upper()
        total = _to_float((offer.get("price") or {}).get("total"))
        if not cur or total is None:
            continue
        if cur not in rates:
            if cur == "KRW":
                rates[cur] = 1.0
            else:
                try:
                    rates[cur] = get_exchange_rate(base=cur, target="KRW") or DEFAULT_FX_TO_KRW.get(cur)
                except Exception:
                    rates[cur] = DEFAULT_FX_TO_KRW.get(cur)
        r = rates.get(cur)
        if r:
            offer["price"]["krwTotal"] = int(round(total * float(r)))
    return rates


def _duration_min(v: str) -> int:
    m = re.match(r"^PT(?:(\d+)H)?(?:(\d+)M)?$", v or "")
    return 10**9 if not m else int(m.group(1) or 0) * 60 + int(m.group(2) or 0)


def _simplify(raw: dict[str, Any]) -> list[dict[str, Any]]:
    rows, seen = [], set()
    for offer in raw.get("data", []):
        itineraries = offer.get("itineraries", [])
        key = json.dumps(itineraries, ensure_ascii=False)
        if key in seen:
            continue
        seen.add(key)
        segs = []
        for itin in itineraries:
            for seg in itin.get("segments", []):
                segs.append(
                    {
                        "airline": seg.get("carrierCode", "-"),
                        "departure": (seg.get("departure") or {}).get("at", "-"),
                        "arrival": (seg.get("arrival") or {}).get("at", "-"),
                        "duration": seg.get("duration", "-"),
                    }
                )
        dur = itineraries[0].get("duration") if itineraries else None
        rows.append(
            {
                "price": (offer.get("price") or {}).get("total"),
                "price_value": _to_float((offer.get("price") or {}).get("total")) or float("inf"),
                "currency": (offer.get("price") or {}).get("currency"),
                "segments": segs,
                "itinerary_duration": dur,
                "duration_min": _duration_min(dur),
                "first_departure": segs[0]["departure"] if segs else None,
                "stops": max(len((itineraries[0].get("segments", []) if itineraries else [])) - 1, 0),
                "primary_airline": segs[0]["airline"] if segs else "-",
            }
        )
    return rows


def _filter_pref(rows: list[dict[str, Any]], state: dict[str, Any]) -> list[dict[str, Any]]:
    out = rows
    if state.get("direct_only") is True:
        direct = [x for x in out if x.get("stops", 0) == 0]
        if direct:
            out = direct
    if state.get("departure_window"):
        def _in_window(h: int, w: str) -> bool:
            if w == "morning":
                return 6 <= h < 12
            if w == "afternoon":
                return 12 <= h < 18
            if w == "evening":
                return 18 <= h < 22
            if w == "night":
                return h >= 22 or h < 6
            return True
        tmp = []
        for row in out:
            dep = row.get("first_departure")
            try:
                dep_dt = datetime.fromisoformat(dep) if dep else None
            except Exception:
                dep_dt = None
            if dep_dt and _in_window(dep_dt.hour, state["departure_window"]):
                tmp.append(row)
        if tmp:
            out = tmp
    return out


def _flight_html_intro(state: dict[str, Any], rows: list[dict[str, Any]]) -> str:
    if not rows:
        return "<p>조건에 맞는 항공편을 찾지 못했어요.</p><p>원하면 날짜를 하루 앞뒤로 넓혀서 다시 찾아볼까요?</p>"
    top = rows[0]
    s0 = top["segments"][0] if top.get("segments") else {}
    return (
        "<div style='margin-bottom:10px;padding:10px;border:1px solid #dbeafe;background:#eff6ff;'>"
        f"<b>요청 이해</b>: {state.get('origin')} → {state.get('destination')} 항공편을 찾았어요.<br>"
        f"<b>추천 1순위</b>: {s0.get('departure','-')} 출발 / {s0.get('arrival','-')} 도착 / "
        f"{top.get('itinerary_duration') or s0.get('duration','-')} / {top.get('price')} {top.get('currency')}"
        "</div>"
    )

def _flight_html_table(rows: list[dict[str, Any]], meta: dict[str, Any]) -> str:
    if not rows:
        return "<p>조건에 맞는 항공편을 찾지 못했습니다.</p>"
    html = (
        "<div style='margin-bottom:10px;padding:8px;background:#f7f7f7;border:1px solid #ddd;'>"
        f"<b>API 조회조건</b> | 출발: {meta.get('origin')} / 도착: {meta.get('destination')} / "
        f"출발일: {meta.get('departure_date')} / 복귀일: {meta.get('return_date') or '-'} / "
        f"인원: {meta.get('adults')} / 최대가격: {meta.get('max_price') or '-'}"
        "</div>"
    )
    html += "<table border='1' style='border-collapse:collapse; width:100%;'>"
    html += "<tr><th>항공사</th><th>출발</th><th>도착</th><th>소요시간</th><th>가격</th></tr>"
    for row in rows:
        for seg in row["segments"]:
            html += (
                f"<tr><td>{seg['airline']}</td><td>{seg['departure']}</td><td>{seg['arrival']}</td>"
                f"<td>{seg['duration']}</td><td>{row['price']} {row['currency']}</td></tr>"
            )
        html += "<tr><td colspan='5' style='text-align:center;background:#f0f0f0;'>-----</td></tr>"
    html += "</table>"
    return html

def _answer_hotel(message: str, context: str, prev_state: dict[str, Any]):
    parsed = _parse_hotel_slots(message, context)
    query = (parsed.get("query") or prev_state.get("hotel_query") or "").strip()
    checkin = parsed.get("checkin_date") or prev_state.get("hotel_checkin")
    checkout = parsed.get("checkout_date") or prev_state.get("hotel_checkout")
    adults = int(parsed.get("adults") or prev_state.get("hotel_adults") or 2)
    top_k = max(1, min(int(parsed.get("top_k") or 5), 20))
    bucket = parsed.get("bucket") or "value_top"
    if not query:
        return "<p>\ud638\ud154\uc744 \ucc3e\uc744 \ub3c4\uc2dc\ub97c \uc54c\ub824\uc8fc\uc138\uc694. (\uc608: \uc624\uc0ac\uce74, \ub3c4\ucfc4)</p>", {"hotel_context": True, "hotel_adults": adults}
    if not checkin or not checkout:
        return "<p>\uccb4\ud06c\uc778/\uccb4\ud06c\uc544\uc6c3 \ub0a0\uc9dc\ub97c \uc54c\ub824\uc8fc\uc138\uc694. (YYYY-MM-DD)</p>", {
            "hotel_context": True,
            "hotel_query": query,
            "hotel_checkin": checkin,
            "hotel_checkout": checkout,
            "hotel_adults": adults,
        }
    dest = booking_search_destination(query=query)
    cands = dest.get("data", []) if isinstance(dest, dict) else []
    if not cands:
        return "<p>\ubaa9\uc801\uc9c0\ub97c \ucc3e\uc9c0 \ubabb\ud588\uc2b5\ub2c8\ub2e4. \ub3c4\uc2dc\uba85\uc744 \uc870\uae08 \ub354 \uad6c\uccb4\uc801\uc73c\ub85c \uc785\ub825\ud574 \uc8fc\uc138\uc694.</p>", {"hotel_context": True}
    first = cands[0] if isinstance(cands[0], dict) else {}
    raw = search_hotels_by_dest_id(
        dest_id=str(first.get("dest_id")),
        search_type=str(first.get("search_type") or "CITY"),
        checkin_date=checkin,
        checkout_date=checkout,
        adults=adults,
        room_qty=1,
        currency_code="KRW",
        languagecode="ko",
        page_number=1,
    )
    if not raw.get("status"):
        return f"<pre>\ud638\ud154 \uac80\uc0c9 \uc2e4\ud328: {raw.get('message', 'Booking API error')}</pre>", {"hotel_context": True}
    center = (float(first.get("latitude") or first.get("lat") or 34.703968), float(first.get("longitude") or first.get("lon") or 135.49292))
    rows = booking_recommend_buckets(raw, center=center, top_k=top_k).get(bucket) or []
    if not rows:
        return "<p>\uc870\uac74\uc5d0 \ub9de\ub294 \ud638\ud154 \uacb0\uacfc\uac00 \uc5c6\uc2b5\ub2c8\ub2e4.</p>", {"hotel_context": True}
    title = {"value_top": "\uac00\uc131\ube44 TOP", "review_top": "\ud6c4\uae30 TOP", "location_top": "\uc704\uce58 TOP"}.get(bucket, "\ucd94\ucc9c TOP")
    lines = []
    for i, h in enumerate(rows, 1):
        line = f"{i}) {h.get('name') or '-'} | \uac00\uaca9: {(h.get('price') or {}).get('value')} {(h.get('price') or {}).get('currency') or '-'}"
        if (h.get("review") or {}).get("score") is not None:
            line += f" | \ud3c9\uc810: {(h.get('review') or {}).get('score')}"
        if h.get("distance_m") is not None:
            line += f" | \uac70\ub9ac: {int(h.get('distance_m'))}m"
        lines.append(line)
    return f"<div><b>{query} {title} {len(rows)}\uac1c</b><br>{'<br>'.join(lines)}</div>", {
        "hotel_context": True,
        "hotel_query": query,
        "hotel_checkin": checkin,
        "hotel_checkout": checkout,
        "hotel_adults": adults,
    }

def _answer_knowledge(message: str, context: str, prev_state: Optional[dict[str, Any]] = None):
    msg = message or ""
    llm_ctx = _resolve_knowledge_context_with_llm(message, context, prev_state)

    country_code = llm_ctx.get("country_code")
    city_name = llm_ctx.get("city_name")
    topic = llm_ctx.get("topic")
    subtopic = llm_ctx.get("subtopic")
    namespace = None

    # Fallback: infer country/city from current message or recent context.
    if not country_code:
        if any(k in msg for k in ["\uc77c\ubcf8", "\ub3c4\ucfc4", "\uc624\uc0ac\uce74", "\ud6c4\ucfe0\uc624\uce74", "\uc0bf\ud3ec\ub85c", "\ub3c4\ucfc4\ud0c0\uc6cc"]):
            country_code = "JP"
        elif any(k in (context or "") for k in ["\uc77c\ubcf8", "\ub3c4\ucfc4", "\uc624\uc0ac\uce74"]):
            country_code = "JP"

    if not city_name:
        if any(k in msg for k in ["\ub3c4\ucfc4"]) or any(k in (context or "") for k in ["\ub3c4\ucfc4"]):
            city_name = "Tokyo"
        elif any(k in msg for k in ["\uc624\uc0ac\uce74"]) or any(k in (context or "") for k in ["\uc624\uc0ac\uce74"]):
            city_name = "Osaka"

    # Fallback: infer topic/subtopic only when LLM didn't resolve it.
    if topic is None and any(k in msg for k in ["\uad50\ud1b5", "\uc9c0\ud558\ucca0", "\uc804\ucca0", "\ubc84\uc2a4", "\uc774\ub3d9", "\ud328\uc2a4", "\uc2a4\uc774\uce74", "\ud30c\uc2a4\ubaa8"]):
        topic = "transport"
        if any(k in msg for k in ["\uc9c0\ud558\ucca0", "\uc804\ucca0", "\uba54\ud2b8\ub85c", "subway"]):
            subtopic = subtopic or "metro_subway"
        elif any(k in msg for k in ["\ud328\uc2a4", "\ud2f0\ucf13", "\uad50\ud1b5\uce74\ub4dc", "\uc2a4\uc774\uce74", "\ud30c\uc2a4\ubaa8"]):
            subtopic = subtopic or "ticket_pass"
    elif topic is None and any(k in msg for k in ["\uce58\uc548", "\uc548\uc804", "\uc704\ud5d8", "\uc8fc\uc758"]):
        topic = "safety"
    elif topic is None and any(k in msg for k in ["\ube44\uc790", "\uc785\uad6d"]):
        topic = "visa"
    elif topic is None and any(k in msg for k in ["\ubb38\ud654", "\uc608\uc808", "\ud301", "\uc2dd\ub2f9", "\ub808\uc2a4\ud1a0\ub791"]):
        topic = "culture"
        if any(k in msg for k in ["\ud301", "\ud301\ubb38\ud654", "tipping"]):
            subtopic = subtopic or "tipping"
    elif topic is None and any(k in msg for k in ["\uc751\uae09", "\uae34\uae09", "\uacbd\ucc30", "\uad6c\uae09\ucc28", "119", "110"]):
        topic = "emergency"
        subtopic = subtopic or "emergency_numbers"

    # Namespace selection (LLM-first, then fallback).
    if topic == "transport":
        namespace = "city" if city_name else "country"
    elif topic in {"culture", "visa", "safety", "emergency", "health", "money", "connectivity"}:
        namespace = "country"
    elif country_code:
        namespace = "country"

    # Country-level knowledge should not carry a city filter unless explicitly city-specific transport context.
    if namespace == "country" and topic != "transport":
        city_name = None

    retrieval_query = message
    if country_code == "JP" and "\ud2b9\uc9d5" in msg and topic is None:
        retrieval_query = (
            "\uc77c\ubcf8 \ud2b9\uc9d5 \ubb38\ud654 \uc608\uc808 \uad50\ud1b5 \uacb0\uc81c \uc548\uc804 \uc5ec\ud589 \ud301 "
            "\uc77c\ubcf8 \uad6d\uac00 \ud2b9\uc9d5"
        )
    if ("\ub9d0\uace0" in msg or "\uc81c\uc678" in msg) and country_code == "JP":
        retrieval_query = (
            "\uc77c\ubcf8 \ud2b9\uc9d5 \uc74c\uc2dd \uc81c\uc678 \ubb38\ud654 \uc608\uc808 \uad50\ud1b5 \uacb0\uc81c \uc548\uc804 \uae34\uae09 \uc5ec\ud589\ud301"
        )
    if topic == "transport" and city_name == "Tokyo":
        retrieval_query = (
            "Tokyo subway train metro how to use ticket pass Suica Pasmo station transfer "
            "\ub3c4\ucfc4 \uc9c0\ud558\ucca0 \ud328\uc2a4 \uc2a4\uc774\uce74 \ud30c\uc2a4\ubaa8 \uc774\uc6a9\ubc95"
        )

    try:
        result = answer_rag_question(
            question=message,
            top_k=RAG_TOP_K,
            namespace=namespace,
            country_code=country_code,
            city_name=city_name,
            topic=topic,
            subtopic=subtopic,
            trust_tier_min=1,
            conversation_context=context,
            retrieval_query=retrieval_query,
        )

        # Fallback: if strict filters return nothing, relax topic/subtopic/city filters for same country namespace.
        if not result.get("chunks") and country_code:
            result = answer_rag_question(
                question=message,
                top_k=RAG_TOP_K,
                namespace="country",
                country_code=country_code,
                city_name=None,
                topic=None,
                subtopic=None,
                trust_tier_min=1,
                conversation_context=context,
                retrieval_query=retrieval_query,
            )

        content = (result.get("answer") or "").strip()
        html = content if content and content.startswith("<div") else (f"<div>{content}</div>" if content else "<div>\uad00\ub828 \uc5ec\ud589 \uc9c0\uc2dd \ub2f5\ubcc0\uc744 \uc0dd\uc131\ud558\uc9c0 \ubabb\ud588\uc2b5\ub2c8\ub2e4.</div>")
        return html, {
            "knowledge_state": {
                "country_code": country_code,
                "city_name": city_name,
                "topic": topic,
                "subtopic": subtopic,
                "namespace": namespace,
            }
        }
    except Exception:
        return "<div>\uc9c0\uc2dd \ub2f5\ubcc0 \uc0dd\uc131 \uc911 \uc624\ub958\uac00 \ubc1c\uc0dd\ud588\uc2b5\ub2c8\ub2e4.</div>", {
            "knowledge_state": {
                "country_code": country_code,
                "city_name": city_name,
                "topic": topic,
                "subtopic": subtopic,
                "namespace": namespace,
            }
        }


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
    _ = (child, infant)
    try:
        raw = _search_flights(origin, destination, departure_date, return_date, adults, max_price, cabin, 30)
        rates = _attach_krw(raw)
        return {
            "results": raw.get("data", []),
            "simplified": _simplify(raw),
            "meta_query": raw.get("meta_query", {}),
            "booking_reference": raw.get("booking_reference", []),
            "exchange_rates": rates,
            "raw": raw,
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"??? ?? ??: {e}")


@router.post("/chat")
def chat(req: ChatRequest):
    try:
        sid = (req.session_id or "default").strip() or "default"
        history = SESSION_HISTORY.setdefault(sid, [])
        history.append({"role": "user", "text": req.message})
        context = _build_context(history)
        prev_state = SESSION_STATE.get(sid, {})
        intent = _detect_intent(req.message, prev_state)

        if intent == "knowledge":
            html, delta = _answer_knowledge(req.message, context, prev_state)
            state = dict(prev_state)
            state.update(delta or {})
            state["last_intent"] = "knowledge"
            SESSION_STATE[sid] = state
            return {"response": html}

        if intent == "hotel":
            html, delta = _answer_hotel(req.message, context, prev_state)
            state = dict(prev_state)
            state.update(delta or {})
            state["last_intent"] = "hotel"
            SESSION_STATE[sid] = state
            return {"response": html}

        if intent == "itinerary":
            p = f"질문 기반으로 Day1~Day3 여행일정을 한국어 존댓말로 작성. 질문:{req.message}\n대화:{context}"
            r = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "system", "content": "여행 일정 도우미"}, {"role": "user", "content": p}],
                temperature=0.3,
            )
            content = (r.choices[0].message.content or "").strip()
            state = dict(prev_state)
            state["last_intent"] = "itinerary"
            SESSION_STATE[sid] = state
            return {"response": content if content.startswith("<div") else f"<div>{content}</div>"}

        parsed = _parse_flight_slots(req.message, context)
        if not _has_date_signal(req.message):
            parsed["departure_date"] = None
            parsed["return_date"] = None
        state = _merge_state(prev_state, parsed)
        missing = _missing_questions(state)
        if missing:
            SESSION_STATE[sid] = state
            raise NeedMoreInfoError(missing[0])

        raw = _search_flights(
            origin=state["origin"],
            destination=state["destination"],
            departure_date=state["departure_date"],
            return_date=state.get("return_date"),
            adults=state.get("adults", 1),
            max_price=state.get("max_price"),
            max_results=30,
        )
        rows = _filter_pref(_simplify(raw), state)
        sort_by = state.get("sort_by")
        if sort_by == "price_asc":
            rows.sort(key=lambda x: x.get("price_value", float("inf")))
        elif sort_by == "price_desc":
            rows.sort(key=lambda x: x.get("price_value", float("-inf")), reverse=True)
        elif sort_by in {"fastest", "fastest_cheap"}:
            rows.sort(key=lambda x: (x.get("duration_min", 10**9), x.get("price_value", float("inf"))))
        limit = state.get("limit")
        if not isinstance(limit, int) or limit <= 0:
            limit = 8
        rows = rows[:limit]
        state["last_intent"] = "flight"
        SESSION_STATE[sid] = state
        return {"response": _flight_html_intro(state, rows) + _flight_html_table(rows, raw.get("meta_query", {}))}
    except NeedMoreInfoError as e:
        return {"response": f"<p>???, ??? ????. {e}</p>"}
    except Exception as e:
        sid = (req.session_id or "default").strip() or "default"
        history = SESSION_HISTORY.setdefault(sid, [])
        err_text = str(e)
        if "500 Server Error" in err_text and "amadeus.com/v2/shopping/flight-offers" in err_text:
            msg = "Amadeus ??? ??? ????? ??????. ??? ?? ??? ???? ?? ? ?? ??? ???."
            history.append({"role": "assistant", "text": msg})
            return {"response": f"<div>{msg}</div>"}
        history.append({"role": "assistant", "text": f"?? ?? ??: {err_text}"})
        return {"response": f"<pre>?? ?? ??: {err_text}</pre>"}
