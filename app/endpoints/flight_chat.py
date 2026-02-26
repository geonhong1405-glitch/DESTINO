import json
import os
import re
from datetime import datetime, timedelta
from typing import Any, Optional
from zoneinfo import ZoneInfo
import requests

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
from app.api.google_places import get_google_places, google_place_details, _google_photo_url
from app.api.geoapify import get_attractions
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
GEOAPIFY_API_KEY = os.getenv("GEOAPIFY_API_KEY")
GOOGLE_PLACES_API_KEY = os.getenv("GOOGLE_PLACES_API_KEY")

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


DEFAULT_FX_TO_KRW = {"KRW": 1.0, "USD": 1350.0, "EUR": 1470.0, "JPY": 9.0}


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
    """
    Returns a date (datetime.date) for relative-date expressions, else None.
    NOTE: Uses only unicode-escaped Korean tokens to avoid encoding issues.
    """
    t = re.sub(r"\s+", "", (text or "").lower())
    now = datetime.now()

    # today: \uc624\ub298
    if "\uc624\ub298" in t:
        return now.date()

    # tomorrow: \ub0b4\uc77c
    # avoid false match when phrase contains "tomorrow+day-after-tomorrow"
    if "\ub0b4\uc77c" in t and ("\ub0b4\uc77c\ubaa8\ub808" not in t) and ("\ub0b4\uc77c\ubaa8\ub798" not in t):
        return (now + timedelta(days=1)).date()

    # day after tomorrow:
    # \ubaa8\ub808, \ub0b4\uc77c\ubaa8\ub808, \ub0b4\uc77c\ubaa8\ub798
    if ("\ub0b4\uc77c\ubaa8\ub808" in t) or ("\ub0b4\uc77c\ubaa8\ub798" in t) or ("\ubaa8\ub808" in t):
        return (now + timedelta(days=2)).date()

    # 3 days later: \uae00\ud53c
    if "\uae00\ud53c" in t:
        return (now + timedelta(days=3)).date()

    # 1 week later patterns:
    # \uc77c\uc8fc\uc77c\ub4a4 / \uc77c\uc8fc\uc77c\ud6c4 / 1\uc8fc\uc77c\ub4a4 / 1\uc8fc\uc77c\ud6c4
    if any(x in t for x in ["\uc77c\uc8fc\uc77c\ub4a4", "\uc77c\uc8fc\uc77c\ud6c4", "1\uc8fc\uc77c\ub4a4", "1\uc8fc\uc77c\ud6c4"]):
        return (now + timedelta(days=7)).date()

    # next week / week after next:
    # \ub2e4\uc74c\uc8fc, \ucc28\uc8fc, \ub2e4\ub2e4\uc74c\uc8fc
    if ("\ub2e4\uc74c\uc8fc" in t) or ("\ucc28\uc8fc" in t):
        return (now + timedelta(days=7)).date()
    if "\ub2e4\ub2e4\uc74c\uc8fc" in t:
        return (now + timedelta(days=14)).date()

    # N days later: (\d+)\uc77c(\ub4a4|\ud6c4)
    m = re.search(r"(\d+)\uc77c(?:\ub4a4|\ud6c4)", t)
    if m:
        return (now + timedelta(days=int(m.group(1)))).date()

    # N weeks later: (\d+)\uc8fc(\uc77c)?(\ub4a4|\ud6c4)
    m = re.search(r"(\d+)\uc8fc(?:\uc77c)?(?:\ub4a4|\ud6c4)", t)
    if m:
        return (now + timedelta(days=int(m.group(1)) * 7)).date()

    return None

def _has_date_signal(text: str) -> bool:
    """
    Detects if text contains an absolute or relative date signal.
    """
    t = text or ""

    # absolute date: 20YY-MM-DD
    if re.search(r"\b20\d{2}-\d{2}-\d{2}\b", t):
        return True
    # Korean month/day absolute date: 3월 1일, 03월01일
    if re.search(r"\d{1,2}\s*월\s*\d{1,2}\s*일", t):
        return True
    # short slash dates: 3/1, 03-01 (without year)
    if re.search(r"\b\d{1,2}[/-]\d{1,2}\b", t):
        return True

    # compact/spacing variants like "2\uc77c\ub4a4", "3\uc77c \ud6c4", "2\uc8fc\ub4a4", "1\uc8fc \ud6c4"
    if re.search(r"\d+\s*\uc77c\s*(?:\ub4a4|\ud6c4)", t):
        return True
    if re.search(r"\d+\s*\uc8fc(?:\uc77c)?\s*(?:\ub4a4|\ud6c4)", t):
        return True

    # keyword signals (include BOTH spaced and unspaced "one week later")
    return _contains(
        t,
        [
            "\uc624\ub298",  # today
            "\ub0b4\uc77c",  # tomorrow
            "\ubaa8\ub808",  # day after tomorrow
            "\uae00\ud53c",  # 3 days later
            "\ub2e4\uc74c\uc8fc",  # next week
            "\ub2e4\ub2e4\uc74c\uc8fc",  # week after next
            "\uc774\ubc88\uc8fc",  # this week (signal only)
            "\uc8fc\ub9d0",  # weekend (signal only)
            "\uc77c\uc8fc\uc77c\ub4a4",  # one week later (no space)
            "\uc77c\uc8fc\uc77c\ud6c4",  # one week after (no space)
            "\uc77c\uc8fc\uc77c \ub4a4",  # one week later (spaced)
            "\uc77c\uc8fc\uc77c \ud6c4",  # one week after (spaced)
        ],
    )


def _parse_abs_monthday_range(text: str, now_dt: Optional[datetime] = None) -> dict[str, Optional[str]]:
    """
    Best-effort parser for Korean absolute month/day expressions.
    Examples:
    - 3월1일
    - 3월1일 ~ 3월2일
    - 3월1일에서 2일
    - 2026-03-01 ~ 2026-03-02 (already mostly handled elsewhere, but harmless)
    Returns {"departure_date": ..., "return_date": ...}
    """
    s = str(text or "")
    if not s.strip():
        return {"departure_date": None, "return_date": None}

    now_dt = now_dt or datetime.now(KST)
    now_date = now_dt.date()

    def _infer_year(month: int, day: int, year: Optional[int] = None) -> Optional[int]:
        y = int(year) if year else now_date.year
        try:
            cand = datetime(y, month, day).date()
        except Exception:
            return None
        # If parsed month/day is already long past, assume next year.
        if year is None and cand < (now_date - timedelta(days=1)):
            try:
                cand2 = datetime(y + 1, month, day).date()
            except Exception:
                return None
            return cand2.year
        return cand.year

    def _to_iso(year: Optional[int], month: Optional[int], day: Optional[int]) -> Optional[str]:
        if not year or not month or not day:
            return None
        try:
            return datetime(year, month, day).strftime("%Y-%m-%d")
        except Exception:
            return None

    compact = re.sub(r"\s+", "", s)

    # First, support explicit YYYY-MM-DD/ YYYY.MM.DD ranges if present.
    m_iso_range = re.search(
        r"(20\d{2})[./-](\d{1,2})[./-](\d{1,2}).{0,6}?(20\d{2})[./-](\d{1,2})[./-](\d{1,2})",
        compact,
    )
    if m_iso_range:
        dep = _to_iso(int(m_iso_range.group(1)), int(m_iso_range.group(2)), int(m_iso_range.group(3)))
        ret = _to_iso(int(m_iso_range.group(4)), int(m_iso_range.group(5)), int(m_iso_range.group(6)))
        return {"departure_date": dep, "return_date": ret}

    # Korean month/day range, allowing omitted month in second date.
    m_range = re.search(
        r"(?:(20\d{2})년?)?(\d{1,2})월(\d{1,2})일(?:부터|에서|~|-|—|–|to)(?:(?:(20\d{2})년?)?(\d{1,2})월)?(\d{1,2})일",
        compact,
    )
    if m_range:
        y1 = _infer_year(int(m_range.group(2)), int(m_range.group(3)), int(m_range.group(1)) if m_range.group(1) else None)
        m1 = int(m_range.group(2))
        d1 = int(m_range.group(3))
        m2 = int(m_range.group(5)) if m_range.group(5) else m1
        d2 = int(m_range.group(6))
        y2_hint = int(m_range.group(4)) if m_range.group(4) else None
        y2 = _infer_year(m2, d2, y2_hint or y1)
        dep = _to_iso(y1, m1, d1)
        ret = _to_iso(y2, m2, d2)
        return {"departure_date": dep, "return_date": ret}

    # Single Korean month/day.
    m_single = re.search(r"(?:(20\d{2})년?)?(\d{1,2})월(\d{1,2})일", compact)
    if m_single:
        m1 = int(m_single.group(2))
        d1 = int(m_single.group(3))
        y1 = _infer_year(m1, d1, int(m_single.group(1)) if m_single.group(1) else None)
        dep = _to_iso(y1, m1, d1)
        return {"departure_date": dep, "return_date": None}

    # Short slash forms, e.g. 3/1~3/2, 3-1~3-2
    m_short_range = re.search(r"(\d{1,2})[/-](\d{1,2}).{0,4}?(?:~|-|—|–|to)(\d{1,2})[/-](\d{1,2})", compact)
    if m_short_range:
        m1, d1 = int(m_short_range.group(1)), int(m_short_range.group(2))
        m2, d2 = int(m_short_range.group(3)), int(m_short_range.group(4))
        y1 = _infer_year(m1, d1, None)
        y2 = _infer_year(m2, d2, y1)
        return {"departure_date": _to_iso(y1, m1, d1), "return_date": _to_iso(y2, m2, d2)}

    return {"departure_date": None, "return_date": None}

def _is_date_correction_message(text: str) -> bool:
    """
    Detects corrections like: "\ub0b4\uc77c \ub9d0\uace0 3\uc77c \ub4a4"
    """
    t = text or ""
    has_correction = _contains(
        t,
        [
            "\uc544\ub2c8\ub2e4",  # 아니다
            "\uc544\ub2c8",        # 아니
            "\ucde8\uc18c",        # 취소
            "\ubcc0\uacbd",        # 변경
            "\ub9d0\uace0",        # 말고
        ],
    )
    return bool(has_correction and _has_date_signal(t))

def _parse_rel_date_for_correction(text: str):
    """
    In correction utterances like "\ub0b4\uc77c \ub9d0\uace0 3\uc77c \ub4a4\ub85c",
    prefer the tail phrase after the correction marker.
    """
    t = text or ""

    # correction markers in unicode-escape (no raw Korean literals)
    markers = [
        "\ub9d0\uace0",        # 말고
        "\uc544\ub2c8\ub2e4",  # 아니다
        "\uc544\ub2c8",        # 아니
        "\ubcc0\uacbd",        # 변경
        "\ucde8\uc18c",        # 취소
    ]

    for marker in markers:
        if marker in t:
            tail = t.split(marker)[-1].strip()
            d = _parse_rel_date(tail)
            if d:
                return d

    return _parse_rel_date(t)


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


def _norm_iata(keyword: str) -> Optional[str]:
    raw = (keyword or "").strip()
    if not raw:
        return None
    k = re.sub(r"\s+", "", raw)
    if k in LOCATION_ALIASES:
        return LOCATION_ALIASES[k]
    raw_l = raw.strip().lower()
    if raw_l in LOCATION_ALIASES:
        return LOCATION_ALIASES[raw_l]
    if k in COUNTRY_ALIASES:
        return COUNTRY_ALIASES[k]
    if raw_l in COUNTRY_ALIASES:
        return COUNTRY_ALIASES[raw_l]
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


KST = ZoneInfo("Asia/Seoul")

# assumes you already have:
# - _llm_json(system: str, prompt: str) -> dict[str, Any]
# - _parse_rel_date(text: str) -> Optional[date]
# - _normalize_rag_country_code(v: Any) -> Optional[str]

def _today_kst_str() -> str:
    return datetime.now(KST).strftime("%Y-%m-%d")


def _coerce_int(v: Any, default: int = 0, lo: int = 0, hi: int = 365) -> int:
    try:
        n = int(v)
    except Exception:
        return default
    if n < lo:
        return lo
    if n > hi:
        return hi
    return n


def _normalize_date_semantics(parsed: Any) -> dict[str, Any]:
    """
    Force a stable schema:
    {
      "departure": {"kind":..., "date":..., "unit":..., "value":..., "raw":...} | None,
      "return":    {"kind":..., "date":..., "unit":..., "value":..., "raw":...} | None,
      "stay_nights": int | 0
    }
    """
    if not isinstance(parsed, dict):
        return {"departure": None, "return": None, "stay_nights": 0}

    def norm_one(x: Any) -> Optional[dict[str, Any]]:
        if not isinstance(x, dict):
            return None
        kind = (str(x.get("kind") or "").strip().lower()) or None
        date = (str(x.get("date") or "").strip()) or None
        unit = (str(x.get("unit") or "").strip().lower()) or None
        raw  = (str(x.get("raw")  or "").strip()) or None
        value = _coerce_int(x.get("value"), default=0, lo=0, hi=365)

        if kind not in {"absolute", "relative_offset"}:
            # allow None-kind but keep raw for fallback parsing
            kind = None

        if unit not in {"day", "week"}:
            unit = None

        # If absolute, keep only valid date format
        if kind == "absolute":
            if not (date and re.fullmatch(r"20\d{2}-\d{2}-\d{2}", date)):
                date = None

        # If relative, unit/value should be meaningful
        if kind == "relative_offset":
            if unit is None:
                # allow raw fallback
                pass

        return {"kind": kind, "date": date, "unit": unit, "value": value, "raw": raw}

    dep = norm_one(parsed.get("departure"))
    ret = norm_one(parsed.get("return"))
    stay = _coerce_int(parsed.get("stay_nights"), default=0, lo=0, hi=365)

    return {"departure": dep, "return": ret, "stay_nights": stay}


def _extract_date_expr_with_llm(message: str, context: str = "") -> dict[str, Any]:
    today = _today_kst_str()

    # Keep prompt English-only to avoid encoding issues and ambiguity.
    prompt = (
        f"Today is {today} (Asia/Seoul).\n"
        "Extract ONLY date semantics from the user input and output JSON ONLY (no extra text).\n"
        "Schema:\n"
        "{"
        "\"departure\": {\"kind\":\"absolute|relative_offset|null\",\"date\":\"YYYY-MM-DD|null\",\"unit\":\"day|week|null\",\"value\":0,\"raw\":\"string|null\"},"
        "\"return\": {\"kind\":\"absolute|relative_offset|null\",\"date\":\"YYYY-MM-DD|null\",\"unit\":\"day|week|null\",\"value\":0,\"raw\":\"string|null\"},"
        "\"stay_nights\": 0"
        "}\n"
        "Rules:\n"
        "- absolute date => kind=absolute and set date\n"
        "- relative date (e.g., tomorrow, in 3 days, next week) => kind=relative_offset, set unit/value/raw when possible\n"
        "- if missing, set null-like fields (kind can be null)\n"
        "- if phrase includes stay length (e.g., for 3 days / 2 nights), set stay_nights\n\n"
        f"Recent conversation:\n{context}\n\n"
        f"User input:\n{message}\n"
        "Return ONLY the JSON object."
    )

    parsed = _llm_json("Return ONLY JSON for date semantics.", prompt)
    return _normalize_date_semantics(parsed)


def _resolve_date_expr(expr: Any, now_dt: Optional[datetime] = None) -> Optional[str]:
    """
    Resolve normalized date semantics (dict or string) to YYYY-MM-DD, or None.
    Reject dates too far in the past (older than yesterday).
    """
    if not expr:
        return None

    now_dt = now_dt or datetime.now(KST)
    now_date = now_dt.date()

    # dict form (preferred)
    if isinstance(expr, dict):
        kind = (str(expr.get("kind") or "").strip().lower()) or None

        if kind == "absolute":
            s_abs = (str(expr.get("date") or "").strip()) or ""
            if re.fullmatch(r"20\d{2}-\d{2}-\d{2}", s_abs):
                try:
                    d_abs = datetime.strptime(s_abs, "%Y-%m-%d").date()
                except Exception:
                    return None
                if d_abs < now_date - timedelta(days=1):
                    return None
                return d_abs.strftime("%Y-%m-%d")
            return None

        if kind == "relative_offset":
            unit = (str(expr.get("unit") or "").strip().lower()) or None
            raw = (str(expr.get("raw") or "").strip()) or ""
            try:
                value = int(expr.get("value"))
            except Exception:
                value = None

            if unit in {"day", "week"} and value is not None and 0 <= value <= 365:
                days = value if unit == "day" else value * 7
                return (now_date + timedelta(days=days)).strftime("%Y-%m-%d")

            # fallback: try raw phrase with deterministic parser
            if raw:
                d_raw = _parse_rel_date(raw)
                if d_raw and (d_raw >= now_date - timedelta(days=1)):
                    return d_raw.strftime("%Y-%m-%d")
            return None

        # kind is null/unknown: try raw fallback
        raw = (str(expr.get("raw") or "").strip()) if isinstance(expr, dict) else ""
        if raw:
            d_raw = _parse_rel_date(raw)
            if d_raw and (d_raw >= now_date - timedelta(days=1)):
                return d_raw.strftime("%Y-%m-%d")
        return None

    # string form fallback
    s_expr = str(expr).strip()
    if not s_expr:
        return None
    if re.fullmatch(r"20\d{2}-\d{2}-\d{2}", s_expr):
        try:
            d = datetime.strptime(s_expr, "%Y-%m-%d").date()
        except Exception:
            return None
        if d < now_date - timedelta(days=1):
            return None
        return d.strftime("%Y-%m-%d")

    d = _parse_rel_date(s_expr)
    if not d or d < now_date - timedelta(days=1):
        return None
    return d.strftime("%Y-%m-%d")


def _resolve_knowledge_context_with_llm(
    message: str,
    context: str,
    prev_state: Optional[dict[str, Any]] = None
) -> dict[str, Any]:
    """
    Extract knowledge-Q context: intent/country/city/topic/subtopic/exclude_topics.
    Uses English-only prompt to avoid encoding issues, but allows Korean input.
    """
    today = _today_kst_str()
    prev_k = (prev_state or {}).get("knowledge_state", {}) if isinstance(prev_state, dict) else {}

    prompt = (
        f"Today is {today} (Asia/Seoul).\n"
        "You are a travel knowledge context interpreter.\n"
        "Return ONLY JSON with this schema:\n"
        "{"
        "\"intent\":\"knowledge|unknown\","
        "\"country_code\":\"ISO2 like JP|KR|US|GB|FR|TH|VN|SG|MY|PH|AU|IN or null\","
        "\"city_name\":\"English standard city name or null\","
        "\"topic\":\"safety|culture|visa|transport|money|health|emergency|connectivity or null\","
        "\"subtopic\":\"string or null\","
        "\"exclude_topics\":[\"topic\", \"...\"]"
        "}\n"
        "Rules:\n"
        "- If it's a follow-up (e.g. user says 'then what about...'), use conversation context.\n"
        "- subway/train/transport card/pass => topic=transport\n"
        "- etiquette/tips/culture => topic=culture\n"
        "- emergency/police/ambulance/fire => topic=emergency or safety\n"
        "- If user asks in Korean, still output city_name in English.\n"
        "- If unknown, use null.\n\n"
        f"Previous knowledge state (reference): {json.dumps(prev_k, ensure_ascii=False)}\n"
        f"Recent conversation:\n{context}\n\n"
        f"User input:\n{message}\n"
        "Return ONLY the JSON object."
    )

    parsed = _llm_json("Return ONLY JSON for travel knowledge context.", prompt)
    if not isinstance(parsed, dict):
        parsed = {}

    out = {
        "intent": parsed.get("intent") or "unknown",
        "country_code": parsed.get("country_code") or None,
        "city_name": parsed.get("city_name") or None,
        "topic": parsed.get("topic") or None,
        "subtopic": parsed.get("subtopic") or None,
        "exclude_topics": parsed.get("exclude_topics") or [],
    }

    if isinstance(out["country_code"], str):
        out["country_code"] = _normalize_rag_country_code(out["country_code"])

    if isinstance(out["city_name"], str):
        out["city_name"] = out["city_name"].strip() or None

    if isinstance(out["topic"], str):
        out["topic"] = out["topic"].strip().lower() or None

    if isinstance(out["subtopic"], str):
        out["subtopic"] = out["subtopic"].strip() or None

    if not isinstance(out["exclude_topics"], list):
        out["exclude_topics"] = []

    # Final sanity: only allow known topics
    allowed_topics = {"safety", "culture", "visa", "transport", "money", "health", "emergency", "connectivity"}
    if out["topic"] not in allowed_topics:
        out["topic"] = None

    return out


def _parse_flight_slots(message: str, context: str) -> dict[str, Any]:
    today = datetime.now().strftime("%Y-%m-%d")
    prompt = (
        f"\uc624\ub298 \ub0a0\uc9dc\ub294 {today}. \uc544\ub798 JSON\ub9cc \ucd9c\ub825:\n"
        '{"origin":null,"destination":null,"departure_date":null,"return_date":null,"adults":1,"sort_by":null,"trip_type":null,"limit":null}\n'
        "\uaddc\uce59: \uc800\ub834=price_asc, \ube60\ub978=fastest, \ube60\ub974\uace0 \uc800\ub834=fastest_cheap, "
        "\ucd9c\ubc1c\uc2dc\uac04 \uac00\uc7a5 \ube60\ub978/\uac00\uc7a5 \uc774\ub978 \ucd9c\ubc1c=earliest_departure, \uc655\ubcf5\uc774\uba74 trip_type=round.\n"
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
    parsed.setdefault("max_price", None)

    # Date correction utterances (e.g. "아니다 3일 뒤", "취소하고 다음주로") should not rewrite route slots.
    if _is_date_correction_message(message) and not _has_location_signal(message):
        parsed["origin"] = None
        parsed["destination"] = None

    msg_l = (message or "").lower()
    has_round_signal = _contains(message, ["\uc655\ubcf5", "\uac14\ub2e4\uac00", "\ub3cc\uc544\uc624\ub294", "\ubcf5\uadc0"]) or "round trip" in msg_l or "roundtrip" in msg_l
    has_oneway_signal = _contains(message, ["\ud3b8\ub3c4"]) or "oneway" in msg_l or "one-way" in msg_l
    if has_round_signal:
        parsed["trip_type"] = "round"
    elif has_oneway_signal:
        parsed["trip_type"] = "oneway"
    else:
        parsed["trip_type"] = None

    # Server-side relative date parser is more reliable for compact Korean forms
    # like "2일뒤", "3일후". Apply it early from the current utterance first.
    d_inline = _parse_rel_date(message)
    if d_inline:
        parsed["departure_date"] = d_inline.strftime("%Y-%m-%d")

    # LLM extracts date expressions, server resolves/calculates/validates.
    date_context = "" if _is_date_correction_message(message) else context
    date_info = _extract_date_expr_with_llm(message, date_context)
    if not parsed.get("departure_date"):
        parsed["departure_date"] = _resolve_date_expr(date_info.get("departure"))
    if not parsed.get("return_date"):
        parsed["return_date"] = _resolve_date_expr(date_info.get("return"))
    if not parsed.get("return_date") and parsed.get("departure_date"):
        stay_nights = date_info.get("stay_nights")
        try:
            if stay_nights is not None and int(stay_nights) > 0:
                dep_dt = datetime.strptime(parsed["departure_date"], "%Y-%m-%d")
                parsed["return_date"] = (dep_dt + timedelta(days=int(stay_nights))).strftime("%Y-%m-%d")
                parsed["trip_type"] = parsed.get("trip_type") or "round"
        except Exception:
            pass
    # fallback simple rule parser if LLM extraction misses
    # correction utterance should prioritize current message date over previous context
    if _is_date_correction_message(message):
        d_now = _parse_rel_date_for_correction(message)
        if d_now:
            parsed["departure_date"] = d_now.strftime("%Y-%m-%d")
            parsed["return_date"] = None
    if not parsed.get("departure_date"):
        d = _parse_rel_date(message)
        if d:
            parsed["departure_date"] = d.strftime("%Y-%m-%d")

    # Deterministic fallback for compact Korean absolute dates/ranges
    # (e.g. "3월1일에서 3월2일", "3/1~3/2").
    abs_md = _parse_abs_monthday_range(message)
    if not parsed.get("departure_date") and abs_md.get("departure_date"):
        parsed["departure_date"] = abs_md["departure_date"]
    if not parsed.get("return_date") and abs_md.get("return_date"):
        parsed["return_date"] = abs_md["return_date"]
    if parsed.get("return_date"):
        parsed["trip_type"] = parsed.get("trip_type") or "round"

    if "\uc778\ub3c4" in (message or "") or "india" in msg_l:
        if (parsed.get("destination") or "").upper() in {"", "IND", "IN"}:
            parsed["destination"] = "DEL"

    m = re.search(r"(\ud68c:\uc131\uc778\\s*)\ud68c(\\d+)\\s*\uba85", message or "")
    if m:
        parsed["adults"] = max(1, int(m.group(1)))

    if _contains(message, ["\uc800\ub834", "\uc2fc", "\uac00\uc131\ube44"]):
        parsed["sort_by"] = "price_asc"
    if _contains(message, ["\ucd9c\ubc1c\uc2dc\uac04\uc774 \uac00\uc7a5 \ube60\ub978", "\uac00\uc7a5 \uc774\ub978 \ucd9c\ubc1c", "\ucd9c\ubc1c\uc2dc\uac04 \uc21c", "\uc81c\uc77c \ube68\ub9ac \ucd9c\ubc1c"]):
        parsed["sort_by"] = "earliest_departure"
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
    date_context = "" if _is_date_correction_message(message) else context
    date_info = _extract_date_expr_with_llm(message, date_context)
    if not parsed.get("checkin_date"):
        parsed["checkin_date"] = _resolve_date_expr(date_info.get("departure"))
    if not parsed.get("checkout_date"):
        parsed["checkout_date"] = _resolve_date_expr(date_info.get("return"))
    if not parsed.get("checkout_date") and parsed.get("checkin_date"):
        try:
            if date_info.get("stay_nights") is not None and int(date_info["stay_nights"]) > 0:
                chk = datetime.strptime(parsed["checkin_date"], "%Y-%m-%d")
                parsed["checkout_date"] = (chk + timedelta(days=int(date_info["stay_nights"]))).strftime("%Y-%m-%d")
        except Exception:
            pass
    if not parsed.get("checkin_date"):
        d = _parse_rel_date(message)
        if d:
            parsed["checkin_date"] = d.strftime("%Y-%m-%d")
    compact = re.sub(r"\\s+", "", message or "")
    m = re.search(r"(\uc624\ub298|\ub0b4\uc77c|\ubaa8\ub808|\ub0b4\uc77c\ubaa8\ub808|\uae00\ud53c)(\ud68c:\ubd80\ud130)\ud68c(\\d+)\uc77c", compact)
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
    if _contains(m, ["\uc5ec\ud589\uc9c0", "\ucd94\ucc9c\uc9c0", "\uac00\ubcfc\ub9cc", "\uad00\uad11\uc9c0", "\uc990\uae38\ub9cc", "\ub180\uac70\ub9ac", "\ud560\ub9cc\ud55c"]):
        if not _contains(m, ["\ud56d\uacf5", "\ud56d\uacf5\uad8c", "\ube44\ud589\uae30", "\ucd9c\ubc1c", "\ub3c4\ucc29"]):
            return "knowledge"
    if prev_state.get("last_intent") == "knowledge":
        if not _contains(m, ["\ud56d\uacf5", "\ud56d\uacf5\uad8c", "\ube44\ud589\uae30", "\ucd9c\ubc1c", "\ub3c4\ucc29", "\ud638\ud154", "\uc219\uc18c"]):
            if _contains(m, ["\uba39\uc744\uac70", "\uc74c\uc2dd", "\ub9db\uc9d1", "\ucd94\ucc9c", "\uc5b4\ub54c", "\ub9d0\uace0", "\uadf8\ub7fc"]):
                return "knowledge"
    if _contains(m, ["\uad50\ud1b5", "\uc9c0\ud558\ucca0", "\uc804\ucca0", "\ud328\uc2a4", "\uc2a4\uc774\uce74", "\ud30c\uc2a4\ubaa8"]):
        if not _contains(m, ["\ud56d\uacf5", "\ud56d\uacf5\uad8c", "\ube44\ud589\uae30", "\ucd9c\ubc1c", "\ub3c4\ucc29"]):
            return "knowledge"
    if _contains(m, ["\uce58\uc548", "\uc548\uc804", "\uc704\ud5d8", "\uc8fc\uc758\uc0ac\ud56d", "\uae34\uae09", "\uc751\uae09", "\uc18c\ub9e4\uce58\uae30", "\uc808\ub3c4", "\uac15\ub3c4", "\uc0ac\uae30", "\ubc94\uc8c4", "110", "119", "pickpocket", "scam", "crime"]):
        if not _contains(m, ["\ud56d\uacf5", "\ud56d\uacf5\uad8c", "\ube44\ud589\uae30", "\ucd9c\ubc1c", "\ub3c4\ucc29"]):
            return "knowledge"
    if _contains(m, ["\uce74\ub4dc", "\ud604\uae08", "\uacb0\uc81c", "\ud658\uc728", "\ud658\uc804", "\uc218\uc218\ub8cc", "visa", "mastercard"]):
        if not _contains(m, ["\ud56d\uacf5", "\ud56d\uacf5\uad8c", "\ube44\ud589\uae30", "\ucd9c\ubc1c", "\ub3c4\ucc29"]):
            return "knowledge"
    if any(k in (message or "") for k in ["\ud2b9\uc9d5", "\uc124\uba85", "\uc815\ubcf4", "\uc18c\uac1c", "\ubb50\uc57c", "\uc5b4\ub54c", "\uc1fc\ud551"]):
        if not any(k in (message or "") for k in ["\ud56d\uacf5", "\ube44\ud589", "\ud56d\uacf5\uad8c", "\ucd9c\ubc1c", "\ub3c4\ucc29", "\ud638\ud154", "\uc219\uc18c"]):
            return "knowledge"
    if _contains(m, ["\ud638\ud154", "\uc219\uc18c", "\uc219\ubc15", "\uccb4\ud06c\uc778", "\uccb4\ud06c\uc544\uc6c3"]):
        return "hotel"
    if _contains(m, ["\uc77c\uc815", "\ucf54\uc2a4", "\ub8e8\ud2b8", "\ud50c\ub79c", "day 1", "1\uc77c\ucc28"]):
        return "itinerary"
    if _contains(m, ["\uc5b4\ub514", "\ubb38\ud654", "\ube44\uc790", "\uc2dc\ucc28", "\ud658\uc728", "\ud658\uc804", "\uacb0\uc81c", "\uce74\ub4dc", "\ud604\uae08", "\uc5ec\ud589\ud301", "\uba85\uc18c", "\ub9db\uc9d1", "\ud2b9\uc9d5", "\uc124\uba85", "\uc815\ubcf4", "\uce58\uc548", "\uc548\uc804", "\uc8fc\uc758\uc0ac\ud56d", "\uae34\uae09", "\uc18c\ub9e4\uce58\uae30", "\uc808\ub3c4", "\uc0ac\uae30", "\ubc94\uc8c4", "\uc990\uae38\ub9cc", "\ub180\uac70\ub9ac", "\ud560\ub9cc\ud55c", "\uc1fc\ud551"]) and not _contains(m, ["\ud56d\uacf5", "\ud56d\uacf5\uad8c", "\ube44\ud589\uae30", "\ucd9c\ubc1c", "\ub3c4\ucc29"]):
        return "knowledge"
    if prev_state.get("hotel_context") and _contains(m, ["\ud6c4\uae30", "\uc704\uce58", "\uac00\uc131\ube44", "top", "\uc21c\uc704", "\ucd94\ucc9c", "\ub2e4\uc2dc"]):
        return "hotel"
    if prev_state.get("last_intent") == "hotel" and not _contains(m, ["\ud56d\uacf5", "\ube44\ud589\uae30", "\ucd9c\ubc1c", "\ub3c4\ucc29"]):
        return "hotel"
    return "flight"


def _resolve_intent_with_llm(message: str, context: str, prev_state: Optional[dict[str, Any]] = None) -> Optional[str]:
    """
    LLM-first intent routing. Server validates + falls back to rule-based _detect_intent().
    Returns one of: flight|hotel|itinerary|knowledge or None.
    """
    prev_state = prev_state or {}
    prev_intent = str(prev_state.get("last_intent") or "")
    prompt = (
        "너는 여행 챗봇 라우터다. 아래 JSON만 출력해라.\n"
        '{'
        '"intent":"flight|hotel|itinerary|knowledge|mixed|unknown",'
        '"parts":["flight","hotel","itinerary","knowledge"],'
        '"confidence":0.0'
        '}\n'
        "규칙:\n"
        "- 항공권/비행기/출발일/도착지/직항/경유 => flight\n"
        "- 숙소/호텔/체크인/체크아웃 => hotel\n"
        "- 일정/코스/동선/몇박며칠/플랜 => itinerary\n"
        "- 문화/치안/비자/교통/환율/환전/결제/맛집/명소/놀거리/가볼만한 곳 => knowledge\n"
        "- 둘 이상이 섞이면 intent=mixed, parts에 포함\n"
        "- 후속질문(그럼/말고/그거/어디야)은 최근 대화와 이전 intent를 참고\n\n"
        f"이전 intent: {prev_intent}\n"
        f"최근 대화:\n{context}\n\n"
        f"사용자 질문:\n{message}"
    )
    parsed = _llm_json("여행 챗봇 의도 라우팅 JSON만 출력", prompt)
    if not isinstance(parsed, dict):
        return None

    raw_intent = str(parsed.get("intent") or "").strip().lower()
    parts = parsed.get("parts") if isinstance(parsed.get("parts"), list) else []
    try:
        confidence = float(parsed.get("confidence", 0))
    except Exception:
        confidence = 0.0

    m = (message or "").lower()
    has_itinerary_signal = _contains(
        m,
        [
            "\uc77c\uc815",
            "\ucf54\uc2a4",
            "\ub8e8\ud2b8",
            "\ub3d9\uc120",
            "\ud50c\ub79c",
            "\uba87\ubc15",
            "\ubc15",
            "\uba87\uc77c",
            "\ud22c\uc5b4",
            "itinerary",
            "plan",
            "route",
            "day 1",
        ],
    ) or bool(re.search(r"\d+\s*\ubc15|\d+\s*\uc77c", m))
    has_flight_signal = _contains(
        m,
        ["\ud56d\uacf5", "\ud56d\uacf5\uad8c", "\ube44\ud589\uae30", "\ucd9c\ubc1c", "\ub3c4\ucc29", "\uc9c1\ud56d", "\uacbd\uc720"]
    )
    has_hotel_signal = _contains(m, ["\ud638\ud154", "\uc219\uc18c", "\uccb4\ud06c\uc778", "\uccb4\ud06c\uc544\uc6c3"])

    allowed = {"flight", "hotel", "itinerary", "knowledge"}
    if raw_intent in allowed:
        # Guard against over-eager itinerary classification for vague "여행 가고싶어" style prompts.
        if raw_intent == "itinerary" and not has_itinerary_signal and not has_flight_signal and not has_hotel_signal:
            return None
        if confidence >= 0.45:
            return raw_intent
        return None

    if raw_intent == "mixed":
        norm_parts = [str(x).strip().lower() for x in parts if str(x).strip().lower() in allowed]
        if "itinerary" in norm_parts and not has_itinerary_signal and not has_flight_signal and not has_hotel_signal:
            norm_parts = [x for x in norm_parts if x != "itinerary"]
        # Current /chat route handles one intent path at a time. Pick primary component conservatively.
        # Priority: explicit operational APIs first, knowledge fallback last.
        for cand in ["flight", "hotel", "itinerary", "knowledge"]:
            if cand in norm_parts:
                if confidence >= 0.4:
                    return cand
                break
        return None

    if raw_intent == "unknown":
        return None
    return None


def _classify_travel_domain_with_llm(message: str, context: str = "") -> Optional[dict[str, Any]]:
    prompt = (
        "너는 여행 챗봇의 도메인 판별기다. 아래 JSON만 출력해라.\n"
        '{'
        '"is_travel":true,'
        '"confidence":0.0,'
        '"reason":"short"'
        '}\n'
        "기준:\n"
        "- 여행/항공/숙소/여행지 정보/교통/치안/비자/환율/맛집/명소/일정 => is_travel=true\n"
        "- 스포츠, 주식, 코딩, 일반 상식 잡담, 연예 뉴스 등 여행과 무관 => is_travel=false\n"
        "- 애매하면 confidence 낮게\n\n"
        f"최근 대화(참고):\n{context}\n\n"
        f"사용자 질문:\n{message}"
    )
    parsed = _llm_json("여행 도메인 판별 JSON만 출력", prompt)
    if not isinstance(parsed, dict):
        return None
    try:
        conf = float(parsed.get("confidence", 0))
    except Exception:
        conf = 0.0
    return {
        "is_travel": bool(parsed.get("is_travel")),
        "confidence": max(0.0, min(conf, 1.0)),
        "reason": str(parsed.get("reason") or "").strip(),
    }


def _is_smalltalk_greeting(message: str) -> bool:
    m = (message or "").strip().lower()
    if not m:
        return False
    greetings = [
        "안녕",
        "안녕하세요",
        "하이",
        "ㅎㅇ",
        "hello",
        "hi",
        "hey",
        "반가워",
        "반갑습니다",
    ]
    if m in greetings:
        return True
    if len(m) <= 6 and any(g in m for g in ["안녕", "hello", "hi", "hey"]):
        return True
    return False


def _should_ask_intent_clarification(message: str, prev_state: Optional[dict[str, Any]] = None) -> bool:
    """
    Server-side validation guard for vague travel-interest utterances.
    If LLM intent is missing/low-confidence and rule fallback would default to flight,
    ask a clarification instead of forcing flight.
    """
    m = (message or "").strip().lower()
    if not m:
        return False
    if _contains(
        m,
        [
            "항공", "항공권", "비행기", "출발", "도착",
            "호텔", "숙소", "체크인", "체크아웃",
            "일정", "코스", "루트", "플랜",
        ],
    ):
        return False
    return _contains(
        m,
        [
            "여행 가고싶", "가고싶", "놀고싶", "쇼핑",
            "맛집", "명소", "놀거리", "즐길만", "할만한",
            "추천해줘", "어디 좋아", "뭐 하고 놀아",
        ],
    )



def _is_route_guidance_query(message: str) -> bool:
    m = (message or "").lower()
    route_phrases = ["\uac00\ub294 \ubc29\ubc95", "\uac00\ub294\ubc95", "\uc5b4\ub5bb\uac8c \uac00", "\uc774\ub3d9 \ubc29\ubc95", "\uc774\ub3d9\ubc29\ubc95", "\uad50\ud1b5\ud3b8", "how to get", "how do i get"]
    flight_phrases = ["\ud56d\uacf5", "\ud56d\uacf5\ud3b8", "\ud56d\uacf5\uad8c", "\ube44\ud589\uae30", "\uc9c1\ud56d", "\uc655\ubcf5", "\ud3b8\ub3c4", "flight", "airfare"]
    has_route_phrase = _contains(m, route_phrases)
    has_place_connector = ("\uc5d0\uc11c" in m and ("\uac00" in m or "\uae4c\uc9c0" in m)) or (" from " in m and " to " in m)
    return has_route_phrase and has_place_connector and not _contains(m, flight_phrases)

def _should_keep_knowledge_followup(message: str, prev_state: Optional[dict[str, Any]] = None) -> bool:
    """
    Server-side guard: if the previous turn was clearly a knowledge/local-info flow,
    keep short follow-up questions in the knowledge lane unless there is an explicit
    flight/hotel/itinerary signal.
    """
    prev_state = prev_state or {}
    if prev_state.get("last_intent") != "knowledge":
        return False

    prev_k = prev_state.get("knowledge_state") or {}
    if not isinstance(prev_k, dict):
        prev_k = {}
    # Only apply when we actually have some knowledge context to carry.
    if not any(prev_k.get(k) for k in ["country_code", "city_name", "location_query", "topic", "subtopic"]):
        return False

    m = (message or "").strip().lower()
    if not m:
        return False

    # If the user explicitly starts a different workflow, do not force knowledge.
    if _contains(
        m,
        [
            "\ud56d\uacf5", "\ud56d\uacf5\uad8c", "\ube44\ud589\uae30", "\ucd9c\ubc1c", "\ub3c4\ucc29", "\uc9c1\ud56d", "\uacbd\uc720",
            "\ud638\ud154", "\uc219\uc18c", "\uccb4\ud06c\uc778", "\uccb4\ud06c\uc544\uc6c3",
            "\uc77c\uc815", "\ucf54\uc2a4", "\ub8e8\ud2b8", "\ud50c\ub79c",
        ],
    ):
        return False

    # Short follow-up style questions are usually contextual ("버스로 가면 얼마나 걸려", "그럼 입장료는?").
    short_followup = len(m) <= 40
    followup_tone = _contains(
        m,
        [
            "\uadf8\ub7fc", "\uadf8\uac70", "\uadf8\ub807\uac8c", "\uc5b4\ub5bb\uac8c", "\uc5bc\ub9c8\ub098", "\uba87 \ubd84", "\uba87\ubd84",
            "\uc774\ub3d9", "\ubc84\uc2a4", "\uc9c0\ud558\ucca0", "\uc804\ucca0", "\uae30\ucc28", "\ud0dd\uc2dc", "\ub3c4\ubcf4",
            "\uc785\uc7a5\ub8cc", "\uac00\uaca9", "\ud2f0\ucf13", "\uc608\ub9e4", "\uad00\ub78c\ube44",
            "bus", "train", "metro", "subway", "taxi", "walk", "ticket", "price",
        ],
    )
    return short_followup and followup_tone

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

    amadeus_error = None
    try:
        data = search_flight_offers_raw(
            origin_code=origin_iata,
            destination_code=destination_iata,
            departure_date=departure_date,
            return_date=return_date,
            adults=adults,
            cabin=cabin,
            max_results=max_results,
        )
    except Exception as e:
        amadeus_error = str(e)
        data = {"data": []}
    try:
        b = booking_search_flights(origin_iata, destination_iata, departure_date, return_date, adults)
        data["booking_reference"] = b.get("data", [])
    except Exception as e:
        data["booking_reference_error"] = str(e)
    if amadeus_error:
        data["amadeus_error"] = amadeus_error
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
    s = str(v or "").strip().upper()
    if not s.startswith("PT"):
        return 10**9
    m = re.match(r"^PT(?:(\d+)H)?(?:(\d+)M)?$", s)
    if not m:
        return 10**9
    try:
        return int(m.group(1) or 0) * 60 + int(m.group(2) or 0)
    except Exception:
        return 10**9


def _is_short_haul_route(origin: Optional[str], destination: Optional[str]) -> bool:
    o = (origin or "").upper()
    d = (destination or "").upper()
    kr = {"ICN", "GMP", "PUS", "CJU", "SEL"}
    jp = {"TYO", "HND", "NRT", "OSA", "KIX", "ITM", "FUK", "SPK"}
    return (o in kr and d in jp) or (o in jp and d in kr)


def _sort_flights_for_recommendation(rows: list[dict[str, Any]], state: dict[str, Any]) -> list[dict[str, Any]]:
    sort_by = state.get("sort_by")
    if sort_by == "price_asc":
        rows.sort(key=lambda x: (x.get("price_value", float("inf")), x.get("duration_min", 10**9), x.get("stops", 99)))
        return rows
    if sort_by == "price_desc":
        rows.sort(key=lambda x: x.get("price_value", float("-inf")), reverse=True)
        return rows
    if sort_by == "earliest_departure":
        rows.sort(key=lambda x: (x.get("first_departure") or "9999-12-31T23:59:59", x.get("stops", 99), x.get("price_value", float("inf"))))
        return rows
    if sort_by in {"fastest", "fastest_cheap"}:
        rows.sort(key=lambda x: (x.get("duration_min", 10**9), x.get("stops", 99), x.get("price_value", float("inf"))))
        return rows

    short_haul = _is_short_haul_route(state.get("origin"), state.get("destination"))
    if short_haul:
        def _key_short(x: dict[str, Any]):
            stops = int(x.get("stops") or 0)
            dur = int(x.get("duration_min") or 10**9)
            price = float(x.get("price_value") or float("inf"))
            long_penalty = 1 if dur > 360 else 0
            very_long_penalty = 1 if dur > 600 else 0
            return (
                stops > 0,
                long_penalty,
                very_long_penalty,
                dur,
                price,
                x.get("first_departure") or "9999-12-31T23:59:59",
            )
        rows.sort(key=_key_short)
        return rows

    rows.sort(key=lambda x: (
        x.get("stops", 99),
        x.get("duration_min", 10**9),
        x.get("price_value", float("inf")),
        x.get("first_departure") or "9999-12-31T23:59:59",
    ))
    return rows


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
                        "departure_iata": (seg.get("departure") or {}).get("iataCode", "-"),
                        "arrival_iata": (seg.get("arrival") or {}).get("iataCode", "-"),
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
                "price_krw": (offer.get("price") or {}).get("krwTotal"),
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
        return "<p>조건에 맞는 항공편을 찾지 못했어요.</p><p>원하면 날짜를 하루 앞뒤로 넓혀서 다시 찾아볼까요\ud68c</p>"
    top = rows[0]
    s0 = top["segments"][0] if top.get("segments") else {}
    top_price = (
        f"{int(top.get('price_krw')):,} KRW"
        if isinstance(top.get("price_krw"), (int, float))
        else f"{top.get('price')} {top.get('currency')}"
    )
    return (
        "<div style='margin-bottom:10px;padding:10px;border:1px solid #dbeafe;background:#eff6ff;'>"
        f"<b>요청 이해</b>: {state.get('origin')} → {state.get('destination')} 항공편을 찾았어요.<br>"
        f"<b>추천 1순위</b>: {s0.get('departure','-')} 출발 / {s0.get('arrival','-')} 도착 / "
        f"{top.get('itinerary_duration') or s0.get('duration','-')} / {top_price}"
        "</div>"
    )

def _flight_html_table(rows: list[dict[str, Any]], meta: dict[str, Any]) -> str:
    if not rows:
        return "<p>\uc870\uac74\uc5d0 \ub9de\ub294 \ud56d\uacf5\ud3b8\uc744 \ucc3e\uc9c0 \ubabb\ud588\uc2b5\ub2c8\ub2e4.</p>"

    def _fmt_dt(v: Optional[str]) -> str:
        if not v:
            return "-"
        try:
            return datetime.fromisoformat(v).strftime("%m-%d %H:%M")
        except Exception:
            return str(v)

    def _last_arrival(row: dict[str, Any]) -> Optional[str]:
        segs = row.get("segments") or []
        return (segs[-1] or {}).get("arrival") if segs else None

    def _segment_summary(row: dict[str, Any]) -> str:
        parts = []
        for i, seg in enumerate(row.get("segments") or [], 1):
            dep_code = seg.get("departure_iata", "-")
            arr_code = seg.get("arrival_iata", "-")
            parts.append(
                f"{i}) {seg.get('airline','-')} | {dep_code} {_fmt_dt(seg.get('departure'))} -> {arr_code} {_fmt_dt(seg.get('arrival'))} | {seg.get('duration','-')}"
            )
        return "<br>".join(parts) if parts else "-"

    def _price_label(row: dict[str, Any]) -> str:
        krw = row.get("price_krw")
        if isinstance(krw, (int, float)):
            return f"{int(krw):,} KRW"
        return f"{row.get('price')} {row.get('currency')}"

    html = (
        "<div style='margin-bottom:10px;padding:8px;background:#f7f7f7;border:1px solid #ddd;'>"
        f"<b>API \uc870\ud68c\uc870\uac74</b> | \ucd9c\ubc1c: {meta.get('origin')} / \ub3c4\ucc29: {meta.get('destination')} / "
        f"\ucd9c\ubc1c\uc77c: {meta.get('departure_date')} / \ubcf5\uadc0\uc77c: {meta.get('return_date') or '-'} / "
        f"\uc778\uc6d0: {meta.get('adults')} / \ucd5c\ub300\uac00\uaca9: {meta.get('max_price') or '-'}"
        "</div>"
    )
    html += "<table border='1' style='border-collapse:collapse; width:100%; font-size:14px;'>"
    html += "<tr><th>\ub300\ud45c\ud56d\uacf5\uc0ac</th><th>\uccab \ucd9c\ubc1c</th><th>\ucd5c\uc885 \ub3c4\ucc29</th><th>\uc5ec\uc815</th><th>\ucd1d \uc18c\uc694\uc2dc\uac04</th><th>\uac00\uaca9</th></tr>"
    for row in rows:
        stops = int(row.get('stops') or 0)
        route_badge = '\uc9c1\ud56d' if stops == 0 else f'\uacbd\uc720 {stops}\ud68c'
        html += (
            "<tr>"
            f"<td>{row.get('primary_airline','-')}</td>"
            f"<td>{_fmt_dt(row.get('first_departure'))}</td>"
            f"<td>{_fmt_dt(_last_arrival(row))}</td>"
            f"<td>{route_badge}</td>"
            f"<td>{row.get('itinerary_duration') or '-'}</td>"
            f"<td>{_price_label(row)}</td>"
            "</tr>"
        )
        html += (
            "<tr>"
            "<td colspan='6' style='background:#fafafa;padding:6px 8px;'>"
            "<details><summary style='cursor:pointer;'>\uad6c\uac04 \uc0c1\uc138 \ubcf4\uae30</summary>"
            f"<div style='margin-top:6px;line-height:1.5;'>{_segment_summary(row)}</div>"
            "</details></td></tr>"
        )
    html += "</table>"
    html += "<div style='margin-top:8px;color:#666;font-size:12px;'>\ucd1d \uc18c\uc694\uc2dc\uac04\uc740 \ud658\uc2b9 \ub300\uae30 \uc2dc\uac04\uc744 \ud3ec\ud568\ud55c \uc804\uccb4 \uc5ec\uc815 \uae30\uc900\uc785\ub2c8\ub2e4.</div>"
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


def _build_knowledge_retrieval_query(
    message: str,
    country_code: Optional[str],
    city_name: Optional[str],
    topic: Optional[str],
    subtopic: Optional[str],
) -> str:
    base = (message or "").strip()
    region = city_name or country_code or ""
    msg = message or ""

    # Broad "features" questions should span multiple categories.
    if topic is None and any(k in msg for k in ["\ud2b9\uc9d5", "\uc124\uba85", "\uc18c\uac1c", "\uc815\ubcf4"]):
        q = f"{region} travel overview culture etiquette transport money safety tips {base}".strip()
        if any(k in msg for k in ["\ub9d0\uace0", "\uc81c\uc678"]):
            q += " exclude food cuisine"
        return q

    topic_keywords = {
        "transport": "public transport subway metro train bus pass card ticket transfer station route",
        "safety": "travel safety crime police precautions scams night safety local safety advice",
        "emergency": "emergency numbers police ambulance fire emergency contact 110 119 what to do",
        "culture": "culture etiquette customs manners social norms dining tipping",
        "visa": "visa entry requirements immigration passport stay duration documents",
        "money": "money payment cash card exchange currency atm fees",
        "health": "health medical hospital pharmacy insurance clinic treatment",
        "connectivity": "sim esim wifi pocket wifi internet connectivity mobile data",
    }
    subtopic_keywords = {
        "metro_subway": "subway metro train line station transfer how to use",
        "ticket_pass": "ticket pass day pass 24-hour 48-hour 72-hour fare pass",
        "ic_card": "ic card transport card prepaid card suica pasmo tap in tap out",
        "tipping": "tipping gratuity service charge tip etiquette",
        "emergency_numbers": "emergency numbers police ambulance fire emergency phone number 110 119",
        "medical": "hospital clinic ambulance medical insurance emergency treatment",
    }

    parts = [p for p in [region, topic_keywords.get(topic or ""), subtopic_keywords.get(subtopic or ""), base] if p]
    return " ".join(parts).strip() or base


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


def _geocode_place_center_geoapify(location_query: str, country_code: Optional[str] = None, city_name: Optional[str] = None) -> Optional[tuple[float, float]]:
    if not GEOAPIFY_API_KEY or not location_query:
        return None
    text = location_query
    # add soft context to improve geocoding for neighborhoods like "Shibuya"
    extras = []
    if city_name and city_name.lower() not in text.lower():
        extras.append(city_name)
    if country_code and country_code.lower() not in text.lower():
        extras.append(country_code)
    if extras:
        text = f"{location_query}, {', '.join(extras)}"
    try:
        r = requests.get(
            "https://api.geoapify.com/v1/geocode/search",
            params={"text": text, "limit": 1, "apiKey": GEOAPIFY_API_KEY},
            timeout=15,
        )
        if r.status_code != 200:
            return None
        data = r.json() or {}
        feats = data.get("features") or []
        if not feats:
            return None
        coords = ((feats[0] or {}).get("geometry") or {}).get("coordinates") or []
        if len(coords) >= 2:
            lon, lat = float(coords[0]), float(coords[1])
            return (lat, lon)
    except Exception:
        return None
    return None


def _geocode_place_center_google_textsearch(location_query: str, country_code: Optional[str] = None, city_name: Optional[str] = None) -> Optional[tuple[float, float]]:
    if not GOOGLE_PLACES_API_KEY or not location_query:
        return None
    q = location_query
    extras = []
    if city_name and city_name.lower() not in q.lower():
        extras.append(city_name)
    if country_code and country_code.lower() not in q.lower():
        extras.append(country_code)
    if extras:
        q = f"{location_query}, {', '.join(extras)}"
    try:
        r = requests.get(
            "https://maps.googleapis.com/maps/api/place/textsearch/json",
            params={"query": q, "key": GOOGLE_PLACES_API_KEY, "language": "ko"},
            timeout=15,
        )
        if r.status_code != 200:
            return None
        data = r.json() or {}
        rows = data.get("results") or []
        if not rows:
            return None
        loc = (((rows[0] or {}).get("geometry") or {}).get("location") or {})
        lat = loc.get("lat")
        lon = loc.get("lng")
        if lat is None or lon is None:
            return None
        return (float(lat), float(lon))
    except Exception:
        return None


def _google_maps_search_url(name: Optional[str], address: Optional[str] = None) -> Optional[str]:
    q = " ".join([x for x in [str(name or "").strip(), str(address or "").strip()] if x]).strip()
    if not q:
        return None
    try:
        return f"https://www.google.com/maps/search/?api=1&query={requests.utils.quote(q)}"
    except Exception:
        return None


def _google_places_text_search(query: str) -> list[dict[str, Any]]:
    if not GOOGLE_PLACES_API_KEY or not query:
        return []
    try:
        r = requests.get(
            "https://maps.googleapis.com/maps/api/place/textsearch/json",
            params={"query": query, "key": GOOGLE_PLACES_API_KEY, "language": "ko"},
            timeout=15,
        )
        if r.status_code != 200:
            return []
        data = r.json() or {}
        return data.get("results") or []
    except Exception:
        return []


def _haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    from math import radians, sin, cos, asin, sqrt
    r = 6371000.0
    p1, p2 = radians(lat1), radians(lat2)
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)
    a = sin(dlat / 2) ** 2 + cos(p1) * cos(p2) * sin(dlon / 2) ** 2
    return 2 * r * asin(sqrt(a))


def _price_level_text(v: Any) -> Optional[str]:
    try:
        n = int(v)
    except Exception:
        return None
    if n <= 0:
        return None
    n = max(1, min(n, 4))
    return "₩" * n


def _rank_place_items(items: list[dict[str, Any]], center: tuple[float, float], category: str) -> list[dict[str, Any]]:
    c_lat, c_lon = center
    for x in items:
        lat = x.get("lat")
        lon = x.get("lon")
        try:
            if lat is not None and lon is not None:
                x["distance_m"] = int(round(_haversine_m(c_lat, c_lon, float(lat), float(lon))))
            else:
                x["distance_m"] = None
        except Exception:
            x["distance_m"] = None

    distances = [x["distance_m"] for x in items if isinstance(x.get("distance_m"), int)]
    max_d = max(distances) if distances else 1

    def _score(x: dict[str, Any]) -> float:
        rating = float(x.get("rating") or 0.0)
        reviews = int(x.get("reviews") or 0)
        d = x.get("distance_m")
        dist_score = 0.5 if d is None else max(0.0, 1.0 - (float(d) / max(1.0, float(max_d))))
        review_score = min(reviews, 500) / 500.0
        rating_score = rating / 5.0
        if category == "restaurant":
            return 0.45 * rating_score + 0.25 * review_score + 0.30 * dist_score
        if category == "shopping":
            return 0.35 * rating_score + 0.20 * review_score + 0.45 * dist_score
        return 0.40 * rating_score + 0.20 * review_score + 0.40 * dist_score

    return sorted(items, key=_score, reverse=True)


def _enrich_google_place_items(results: list[dict[str, Any]], center: tuple[float, float], category: str, top_k: int) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for p in results[: max(top_k * 2, top_k)]:
        loc = (((p.get("geometry") or {}).get("location")) or {})
        photos = p.get("photos") or []
        photo_url = None
        if photos and isinstance(photos, list):
            ref = (photos[0] or {}).get("photo_reference")
            if ref:
                photo_url = _google_photo_url(ref, maxwidth=800)
        items.append(
            {
                "name": p.get("name"),
                "address": p.get("vicinity") or p.get("formatted_address"),
                "rating": p.get("rating"),
                "reviews": p.get("user_ratings_total"),
                "source": "google_places",
                "place_id": p.get("place_id"),
                "lat": loc.get("lat"),
                "lon": loc.get("lng"),
                "photo_url": photo_url,
                "types": p.get("types") or [],
            }
        )

    items = _rank_place_items(items, center=center, category=category)[:top_k]

    # Details for top candidates only (price level / opening / urls)
    for x in items:
        pid = x.get("place_id")
        if not pid:
            continue
        try:
            d = google_place_details(pid, language="ko") or {}
            result = d.get("result") or {}
            x["price_level"] = result.get("price_level")
            x["price_level_text"] = _price_level_text(result.get("price_level"))
            x["maps_url"] = result.get("url")
            x["website"] = result.get("website")
            oh = result.get("opening_hours") or {}
            if isinstance(oh, dict):
                x["open_now"] = oh.get("open_now")
            x["editorial_summary"] = ((result.get("editorial_summary") or {}).get("overview")) if isinstance(result.get("editorial_summary"), dict) else None
            if not x.get("photo_url"):
                photos = result.get("photos") or []
                if photos and isinstance(photos, list):
                    ref = (photos[0] or {}).get("photo_reference")
                    if ref:
                        x["photo_url"] = _google_photo_url(ref, maxwidth=800)
        except Exception:
            continue
    return items


def _search_food_places(
    city_name: str,
    food_keyword: Optional[str],
    country_code: Optional[str] = None,
    top_k: int = 5,
    location_query: Optional[str] = None,
    radius_m: int = 5000,
) -> dict[str, Any]:
    def _normalize_food_keyword(raw_keyword: Optional[str]) -> Optional[str]:
        if not raw_keyword:
            return None
        k = str(raw_keyword).strip()
        if not k:
            return None
        k_l = k.lower()
        generic_food = {
            "맛집", "식당", "레스토랑", "밥집", "먹을만한", "먹을 만한", "추천",
            "restaurant", "restaurants", "food", "eat", "dining", "best",
        }
        compact = re.sub(r"\s+", "", k_l)
        if k in generic_food or k_l in generic_food or compact in {"맛집추천", "식당추천", "레스토랑추천"}:
            return None
        return k

    search_loc = location_query or city_name
    if _is_landmark_like_location_query(location_query):
        center = _geocode_place_center_google_textsearch(search_loc, country_code=country_code, city_name=city_name)
        if not center:
            center = _geocode_place_center_geoapify(search_loc, country_code=country_code, city_name=city_name)
    else:
        center = _geocode_place_center_geoapify(search_loc, country_code=country_code, city_name=city_name)
        if not center:
            center = _geocode_place_center_google_textsearch(search_loc, country_code=country_code, city_name=city_name)
    if not center:
        return {"error": "geocode_failed", "city_name": city_name, "items": []}
    lat, lon = center
    food_keyword = _normalize_food_keyword(food_keyword)

    radius_m = max(800, min(int(radius_m or 5000), 15000))

    # 1) Google Places nearby (preferred for restaurant search)
    try:
        keyword_parts = [x for x in [location_query, food_keyword, "맛집"] if x]
        keyword = " ".join(keyword_parts) if keyword_parts else None
        g = get_google_places(lat, lon, radius=radius_m, keyword=keyword, type="restaurant")
        items = _enrich_google_place_items((g.get("results") or []), center=(lat, lon), category="restaurant", top_k=max(1, min(top_k, 10)))
        if items:
            return {"city_name": city_name, "food_keyword": food_keyword, "location_query": location_query, "items": items}
    except Exception:
        pass

    # 1.5) Google Places text search (better for landmark/brand/city-level queries than nearby)
    try:
        q_parts = [x for x in [location_query, city_name, food_keyword, "restaurant"] if x]
        q = " ".join(dict.fromkeys(q_parts))  # preserve order, dedupe
        rows = _google_places_text_search(q)
        items = _enrich_google_place_items(rows, center=(lat, lon), category="restaurant", top_k=max(1, min(top_k, 10)))
        if items:
            return {"city_name": city_name, "food_keyword": food_keyword, "location_query": location_query, "items": items}
    except Exception:
        pass

    # 2) Geoapify fallback
    try:
        gg = get_attractions(lat, lon, radius=radius_m, kind="catering.restaurant")
        feats = gg.get("features") or []
        items = []
        fk = (food_keyword or "").lower().strip()
        for f in feats:
            props = f.get("properties") or {}
            name = props.get("name") or props.get("formatted")
            if not name:
                continue
            if fk and fk not in str(name).lower() and fk not in str(props.get("formatted", "")).lower():
                # keep some filtering but don't empty the list entirely
                continue
            items.append(
                {
                    "name": name,
                    "address": props.get("formatted"),
                    "rating": props.get("rating"),
                    "reviews": props.get("datasource", {}).get("raw", {}).get("ratings_total") if isinstance(props.get("datasource"), dict) else None,
                    "source": "geoapify",
                    "lat": props.get("lat"),
                    "lon": props.get("lon"),
                    "maps_url": _google_maps_search_url(name, props.get("formatted")),
                }
            )
            if len(items) >= max(1, min(top_k, 10)):
                break
        if items:
            items = _rank_place_items(items, center=(lat, lon), category="restaurant")[: max(1, min(top_k, 10))]
            return {"city_name": city_name, "food_keyword": food_keyword, "location_query": location_query, "items": items}
    except Exception:
        pass

    return {"city_name": city_name, "food_keyword": food_keyword, "location_query": location_query, "items": []}


def _search_local_places(
    city_name: str,
    keyword: Optional[str],
    category: str,
    country_code: Optional[str] = None,
    top_k: int = 5,
    location_query: Optional[str] = None,
    radius_m: int = 7000,
) -> dict[str, Any]:
    def _normalize_place_keyword(raw_keyword: Optional[str], cat: str) -> Optional[str]:
        if not raw_keyword:
            return None
        k = str(raw_keyword).strip()
        if not k:
            return None
        k_l = k.lower()
        generic_tokens = {
            "추천", "추천좀", "추천해줘", "추천해 줘", "어디", "어디가 좋아", "좋은곳", "좋은 곳",
            "명소", "관광지", "놀거리", "가볼만한곳", "가볼만한 곳", "즐길만한곳", "즐길만한 곳",
            "맛집", "식당", "레스토랑", "카페", "장소", "쇼핑", "쇼핑몰", "백화점", "시장", "마켓",
            "recommend", "recommended", "best", "place", "places", "attraction", "attractions",
            "restaurant", "restaurants", "cafe", "cafes", "things to do", "shopping", "mall", "market",
        }
        # For category searches, generic category words should not be used as a hard keyword filter.
        if k in generic_tokens or k_l in generic_tokens:
            return None
        # If the keyword is mostly generic filler, drop it.
        compact = re.sub(r"\s+", "", k_l)
        if compact in {
            "명소추천", "명소추천좀", "관광지추천", "놀거리추천", "맛집추천", "카페추천", "쇼핑추천", "쇼핑몰추천",
            "attractionrecommend", "restaurantrecommend", "caferecommend", "shoppingrecommend",
        }:
            return None
        return k

    if category == "restaurant":
        return _search_food_places(
            city_name=city_name,
            food_keyword=keyword,
            country_code=country_code,
            top_k=top_k,
            location_query=location_query,
            radius_m=radius_m,
        )

    search_loc = location_query or city_name
    if _is_landmark_like_location_query(location_query):
        center = _geocode_place_center_google_textsearch(search_loc, country_code=country_code, city_name=city_name)
        if not center:
            center = _geocode_place_center_geoapify(search_loc, country_code=country_code, city_name=city_name)
    else:
        center = _geocode_place_center_geoapify(search_loc, country_code=country_code, city_name=city_name)
        if not center:
            center = _geocode_place_center_google_textsearch(search_loc, country_code=country_code, city_name=city_name)
    if not center:
        return {"error": "geocode_failed", "city_name": city_name, "items": []}
    lat, lon = center
    top_k = max(1, min(top_k, 10))
    radius_m = max(1000, min(int(radius_m or 7000), 20000))

    google_type = None
    if category == "attraction":
        google_type = "tourist_attraction"
    elif category == "cafe":
        google_type = "cafe"
    elif category == "shopping":
        google_type = "shopping_mall"

    keyword = _normalize_place_keyword(keyword, category)

    # Google Places first
    try:
        place_keyword = " ".join([x for x in [location_query, keyword] if x]) or None
        g = get_google_places(lat, lon, radius=radius_m, keyword=place_keyword, type=google_type)
        items = _enrich_google_place_items((g.get("results") or []), center=(lat, lon), category=category, top_k=top_k)
        # Brand shopping queries often don't show up under shopping_mall.
        # Retry without a strict type filter when shopping has a keyword.
        if not items and category == "shopping" and place_keyword:
            g2 = get_google_places(lat, lon, radius=radius_m, keyword=place_keyword, type=None)
            items = _enrich_google_place_items((g2.get("results") or []), center=(lat, lon), category=category, top_k=top_k)
        if items:
            return {"city_name": city_name, "keyword": keyword, "category": category, "items": items}
    except Exception:
        pass

    # Google Places text search fallback before Geoapify (works better for landmark/brand queries)
    try:
        category_q = {
            "attraction": "tourist attraction",
            "cafe": "cafe",
            "shopping": "shopping",
            "generic": "things to do",
        }.get(category, "")
        q_parts = [x for x in [location_query, city_name, keyword, category_q] if x]
        q = " ".join(dict.fromkeys(q_parts))
        rows = _google_places_text_search(q)
        items = _enrich_google_place_items(rows, center=(lat, lon), category=category, top_k=top_k)
        if items:
            return {"city_name": city_name, "keyword": keyword, "category": category, "items": items}
    except Exception:
        pass

    # Geoapify fallback
    try:
        kind = "tourism.sights"
        if category == "cafe":
            kind = "catering.cafe"
        elif category == "shopping":
            kind = "commercial.shopping_mall"
        elif category == "generic":
            kind = "tourism.sights"
        gg = get_attractions(lat, lon, radius=radius_m, kind=kind)
        feats = gg.get("features") or []
        items = []
        kw = (keyword or "").strip().lower()
        for f in feats:
            props = f.get("properties") or {}
            name = props.get("name") or props.get("formatted")
            if not name:
                continue
            if kw and kw not in str(name).lower() and kw not in str(props.get("formatted", "")).lower():
                continue
            items.append(
                {
                    "name": name,
                    "address": props.get("formatted"),
                    "rating": props.get("rating"),
                    "reviews": props.get("datasource", {}).get("raw", {}).get("ratings_total") if isinstance(props.get("datasource"), dict) else None,
                    "source": "geoapify",
                    "lat": props.get("lat"),
                    "lon": props.get("lon"),
                    "maps_url": _google_maps_search_url(name, props.get("formatted")),
                }
            )
            if len(items) >= top_k:
                break
        if items:
            items = _rank_place_items(items, center=(lat, lon), category=category)[:top_k]
            return {"city_name": city_name, "keyword": keyword, "category": category, "location_query": location_query, "items": items}
    except Exception:
        pass

    return {"city_name": city_name, "keyword": keyword, "category": category, "items": []}


def _answer_food_place_followup(message: str, context: str, prev_state: Optional[dict[str, Any]] = None):
    parsed = _extract_food_place_request_with_llm(message, context, prev_state)
    prev_k = (prev_state or {}).get("knowledge_state", {}) if isinstance(prev_state, dict) else {}
    city_name = parsed.get("city_name") or prev_k.get("city_name")
    country_code = _normalize_rag_country_code(prev_k.get("country_code"))
    food_keyword = parsed.get("food_keyword")

    if not city_name:
        return (
            "<div>어느 도시에서 찾을지 알려주세요. 예: 도쿄, 오사카, 베를린</div>",
            {"knowledge_state": {**(prev_k or {}), "topic": "culture", "subtopic": "dining"}},
        )

    result = _search_food_places(
        city_name=city_name,
        food_keyword=food_keyword,
        country_code=country_code,
        top_k=5,
        location_query=location_query,
        radius_m=_place_search_radius_m(message, location_query),
    )
    items = result.get("items") or []
    if not items:
        fallback = _rewrite_place_recommendation_fallback(
            city_name=city_name,
            category="restaurant",
            keyword=food_keyword,
            message=message,
            context=context,
        )
        if fallback:
            return (
                fallback,
                {"knowledge_state": {**(prev_k or {}), "city_name": city_name, "country_code": country_code, "topic": "culture", "subtopic": "dining"}},
            )
        q = f"{food_keyword} " if food_keyword else ""
        return (
            f"<div>{city_name}에서 {q}맛집 후보를 찾지 못했습니다. 음식명이나 지역명을 더 구체적으로 알려주세요.</div>",
            {"knowledge_state": {**(prev_k or {}), "city_name": city_name, "topic": "culture", "subtopic": "dining"}},
        )

    title_kw = f"{food_keyword} " if food_keyword else ""
    show_distance = _should_show_place_distance(message, location_query, city_name)

    def _food_summary(x: dict[str, Any]) -> str:
        parts = []
        if x.get("rating") is not None:
            parts.append(f"평점 {x.get('rating')} 확인")
        if x.get("reviews"):
            parts.append(f"리뷰 {x.get('reviews')}개")
        if show_distance and x.get("distance_m") is not None:
            parts.append(f"약 {int(x.get('distance_m'))}m")
        if x.get("price_level_text"):
            parts.append(f"가격대 {x.get('price_level_text')}")
        if x.get("address"):
            parts.append("주소 확인 가능")
        src = x.get("source")
        if src == "google_places":
            parts.append("Google Places 기준")
        elif src == "geoapify":
            parts.append("Geoapify 기준(거리/주소 오차 가능)")
        return " · ".join(parts) if parts else "현지 식사 후보"

    def _menu_hint() -> str:
        if food_keyword:
            return f"{food_keyword} 중심으로 찾아본 후보예요."
        return "대표 메뉴는 매장마다 달라서 방문 전 메뉴판/리뷰 확인을 권장해요."

    blocks = []
    for i, x in enumerate(items, 1):
        name = x.get("name") or "-"
        rating = x.get("rating")
        address = x.get("address") or "-"
        source = x.get("source") or "-"
        block = [
            f"<div style='margin:10px 0 14px 0;padding:10px 12px;border:1px solid #e5e7eb;border-radius:10px;'>",
            f"<div><b>{i}. {name}</b></div>",
        ]
        if x.get("photo_url"):
            block.append(
                f"<div style='margin-top:8px;'><img src=\"{x.get('photo_url')}\" alt=\"\" "
                "style='width:100%;max-width:360px;height:160px;object-fit:cover;border-radius:8px;border:1px solid #e5e7eb;'></div>"
            )
        block += [
            f"<div style='margin-top:6px;color:#374151;'>{_food_summary(x)}</div>",
            f"<div style='margin-top:6px;color:#4b5563;'>대표 메뉴/포인트: {_menu_hint()}</div>",
            f"<div style='margin-top:6px;color:#4b5563;'>주소: {address}</div>",
        ]
        if rating is not None:
            block.append(f"<div style='color:#4b5563;'>평점: {rating}</div>")
        if x.get("reviews"):
            block.append(f"<div style='color:#4b5563;'>리뷰 수: {x.get('reviews')}</div>")
        if x.get("price_level_text"):
            block.append(f"<div style='color:#4b5563;'>가격대: {x.get('price_level_text')}</div>")
        if x.get("open_now") is True:
            block.append("<div style='color:#047857;'>현재 영업 중</div>")
        elif x.get("open_now") is False:
            block.append("<div style='color:#b45309;'>현재 영업 여부 확인 필요(비영업 시간일 수 있음)</div>")
        block.append(f"<div style='color:#6b7280;font-size:12px;'>출처: {source}</div>")
        if x.get("maps_url"):
            block.append(f"<div style='font-size:12px;'><a href=\"{x.get('maps_url')}\" target='_blank' rel='noopener'>지도에서 보기</a></div>")
        block.append("</div>")
        blocks.append("".join(block))

    html = (
        f"<div><b>{city_name} {title_kw}맛집 추천</b>"
        f"<div style='margin-top:6px;color:#4b5563;'>위치/평점/데이터 출처를 기준으로 보기 쉽게 정리했어요.</div>"
        f"{''.join(blocks)}</div>"
    )
    return html, {"knowledge_state": {**(prev_k or {}), "city_name": city_name, "country_code": country_code, "topic": "culture", "subtopic": "dining"}}


def _answer_local_place_followup(message: str, context: str, prev_state: Optional[dict[str, Any]] = None):
    parsed = _extract_local_place_request_with_llm(message, context, prev_state)
    prev_k = (prev_state or {}).get("knowledge_state", {}) if isinstance(prev_state, dict) else {}
    city_name = parsed.get("city_name") or prev_k.get("city_name")
    location_query = parsed.get("location_query")
    country_code = _normalize_rag_country_code(prev_k.get("country_code"))
    keyword = parsed.get("keyword")
    brand_or_theme = parsed.get("brand_or_theme")
    category = parsed.get("category") or "generic"

    # direct keyword fallback when LLM misses
    if category == "generic":
        if _contains(message or "", ["맛집", "식당", "레스토랑"]):
            category = "restaurant"
        elif _contains(message or "", ["명소", "관광지", "놀거리", "가볼만", "즐길만", "핫플"]):
            category = "attraction"
        elif _contains(message or "", ["카페"]):
            category = "cafe"
        elif _contains(message or "", ["쇼핑", "쇼핑몰", "백화점", "시장", "마켓"]):
            category = "shopping"

    # LLM이 generic으로 뽑아도 브랜드/매장/판매처 의도면 쇼핑으로 승격
    if category == "generic":
        msg_norm = (message or "").lower()
        if any(tok in msg_norm for tok in ["브랜드", "매장", "파는곳", "파는 곳", "판매처", "편집샵", "셀렉트샵", "brand", "store", "shop"]):
            category = "shopping"

    # LLM이 generic으로 뽑아도 브랜드/매장/판매처 의도면 쇼핑으로 승격
    if category == "generic" and brand_or_theme:
        category = "shopping"

    # LLM brand/theme is preferred for shopping keyword when available.
    if category == "shopping" and not keyword and brand_or_theme:
        keyword = brand_or_theme

    # Server-side fallback extraction for location/keyword when LLM parsing misses.
    if not location_query:
        m_loc = re.search(r"(.{1,30}?)(?:\uc5d0\uc11c|\uadfc\ucc98)\s*", message or "")
        if m_loc:
            candidate = m_loc.group(1).strip(" ,.?")
            if candidate and not _contains(candidate, ["??", "??", "???", "??", "??", "??"]):
                location_query = candidate
    if category == "restaurant" and not keyword:
        cuisine_kws = ["??", "??", "??", "??", "??", "???", "???", "????", "????", "??????", "???"]
        for ck in cuisine_kws:
            if ck in (message or ""):
                keyword = ck
                break
        if not keyword:
            m_food = re.search(r"([A-Za-z?-?0-9]{1,20})\s*?", message or "")
            if m_food:
                keyword = m_food.group(1).strip()
    # 브랜드 쇼핑 질의에서 keyword가 비면 브랜드명 후보 추출
    if category == "shopping" and not keyword:
        msg_raw = message or ""
        m_brand = re.search(r"([A-Za-z0-9가-힣·&'\\-]{1,30})\s*(?:브랜드|매장|파는곳|파는 곳|판매처)", msg_raw)
        if m_brand:
            cand = m_brand.group(1).strip(" ,.?")
            cand = re.sub(r".*(?:\uc5d0\uc11c|\uadfc\ucc98)\s*", "", cand).strip()
            if cand:
                keyword = cand

    if not city_name and location_query:
        city_name = location_query

    if not city_name:
        return (
            "<div>어느 도시에서 찾을지 알려주세요. 예: 도쿄, 오사카, 베를린</div>",
            {"knowledge_state": {**(prev_k or {}), "topic": "culture", "subtopic": "dining" if category == "restaurant" else "general"}},
        )

    result = _search_local_places(
        city_name=city_name,
        keyword=keyword,
        category=category,
        country_code=country_code,
        top_k=5,
        location_query=location_query,
        radius_m=_place_search_radius_m(message, location_query),
    )
    items = result.get("items") or []
    if not items:
        label = {"restaurant": "맛집", "attraction": "명소/놀거리", "cafe": "카페", "shopping": "쇼핑 장소", "generic": "장소"}.get(category, "장소")
        fallback = _rewrite_place_recommendation_fallback(
            city_name=city_name,
            category=category,
            keyword=keyword,
            message=message,
            context=context,
        )
        if fallback:
            return (
                fallback,
                {"knowledge_state": {**(prev_k or {}), "city_name": city_name, "country_code": country_code, "topic": "culture", "subtopic": "dining" if category == "restaurant" else category}},
            )
        return (
            f"<div>{city_name}에서 {label} 후보를 찾지 못했습니다. 지역명이나 키워드를 더 구체적으로 알려주세요.</div>",
            {"knowledge_state": {**(prev_k or {}), "city_name": city_name, "country_code": country_code}},
        )

    title = {"restaurant": "맛집 추천", "attraction": "명소/놀거리 추천", "cafe": "카페 추천", "shopping": "쇼핑 장소 추천", "generic": "장소 추천"}.get(category, "장소 추천")
    title_kw = f"{keyword} " if keyword else ""
    title_loc = location_query or city_name
    show_distance = _should_show_place_distance(message, location_query, city_name)

    category_label = {
        "restaurant": "식사/현지 음식",
        "attraction": "관광/볼거리",
        "cafe": "휴식/카페",
        "shopping": "쇼핑/구매",
        "generic": "여행 장소",
    }.get(category, "여행 장소")

    def _place_summary(x: dict[str, Any]) -> str:
        reasons = [category_label]
        if x.get("rating") is not None:
            reasons.append(f"평점 {x.get('rating')}")
        if x.get("reviews"):
            reasons.append(f"리뷰 {x.get('reviews')}개")
        if show_distance and x.get("distance_m") is not None:
            reasons.append(f"약 {int(x.get('distance_m'))}m")
        if x.get("price_level_text"):
            reasons.append(f"가격대 {x.get('price_level_text')}")
        if x.get("address"):
            reasons.append("주소 확인 가능")
        src = x.get("source")
        if src:
            if str(src) == "geoapify":
                reasons.append("Geoapify 기준(거리/주소 오차 가능)")
            else:
                reasons.append(f"{src} 기준")
        return " · ".join(reasons)

    blocks = []
    for i, x in enumerate(items, 1):
        name = x.get("name") or "-"
        rating = x.get("rating")
        address = x.get("address") or "-"
        source = x.get("source") or "-"
        block = [
            f"<div style='margin:10px 0 14px 0;padding:10px 12px;border:1px solid #e5e7eb;border-radius:10px;'>",
            f"<div><b>{i}. {name}</b></div>",
        ]
        if x.get("photo_url"):
            block.append(
                f"<div style='margin-top:8px;'><img src=\"{x.get('photo_url')}\" alt=\"\" "
                "style='width:100%;max-width:360px;height:160px;object-fit:cover;border-radius:8px;border:1px solid #e5e7eb;'></div>"
            )
        block += [
            f"<div style='margin-top:6px;color:#374151;'>{_place_summary(x)}</div>",
            f"<div style='margin-top:6px;color:#4b5563;'>주소: {address}</div>",
        ]
        if rating is not None:
            block.append(f"<div style='color:#4b5563;'>평점: {rating}</div>")
        if x.get("reviews"):
            block.append(f"<div style='color:#4b5563;'>리뷰 수: {x.get('reviews')}</div>")
        if x.get("price_level_text"):
            block.append(f"<div style='color:#4b5563;'>가격대: {x.get('price_level_text')}</div>")
        block.append(f"<div style='color:#6b7280;font-size:12px;'>출처: {source}</div>")
        if x.get("maps_url"):
            block.append(f"<div style='font-size:12px;'><a href=\"{x.get('maps_url')}\" target='_blank' rel='noopener'>지도에서 보기</a></div>")
        block.append("</div>")
        blocks.append("".join(block))

    html = (
        f"<div><b>{title_loc} {title_kw}{title}</b>"
        f"<div style='margin-top:6px;color:#4b5563;'>후보별 핵심 정보만 빠르게 비교할 수 있게 정리했어요.</div>"
        f"{''.join(blocks)}</div>"
    )
    next_subtopic = "dining" if category == "restaurant" else ("shopping" if category == "shopping" else "general")
    next_topic = "money" if category == "shopping" else "culture"
    return html, {"knowledge_state": {**(prev_k or {}), "city_name": city_name, "country_code": country_code, "topic": next_topic, "subtopic": next_subtopic, "location_query": location_query or prev_k.get("location_query")}}


def _rewrite_place_recommendation_fallback(
    city_name: str,
    category: str,
    keyword: Optional[str],
    message: str,
    context: str,
) -> Optional[str]:
    """
    API 후보를 못 찾았을 때도 사용자가 끊기지 않도록, 도시/카테고리/키워드 기준의
    일반 여행지식 추천을 LLM으로 생성한다. (실시간 재고/운영정보는 단정 금지)
    """
    try:
        category_ko = {
            "restaurant": "맛집",
            "attraction": "명소/놀거리",
            "cafe": "카페",
            "shopping": "쇼핑",
            "generic": "추천 장소",
        }.get(category, "추천 장소")
        kw = (keyword or "").strip()
        q_hint = f"{city_name} {kw} {category_ko}".strip()
        prompt = (
            "You are a travel recommendation assistant.\n"
            "The place APIs returned no reliable candidates, so provide a helpful fallback answer in Korean.\n"
            "Requirements:\n"
            "- Answer in Korean.\n"
            "- Do NOT pretend you found exact API results.\n"
            "- Give 3-5 practical area/store-type recommendations for the city and query intent.\n"
            "- If query is brand shopping, suggest neighborhoods/department stores/select shops to check.\n"
            "- Keep it readable for customers (short sections/bullets, no markdown ### or **).\n"
            "- Include a short note to verify current availability/hours before visiting.\n\n"
            f"City: {city_name}\n"
            f"Category: {category}\n"
            f"Keyword: {kw or '(none)'}\n"
            f"Query intent hint: {q_hint}\n"
            f"Recent context:\n{context}\n\n"
            f"User message:\n{message}\n"
        )
        r = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "Travel recommendation fallback writer. Output customer-friendly Korean only."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.4,
        )
        out = (r.choices[0].message.content or "").strip()
        if not out:
            return None
        # strip markdown decorations for UI consistency
        out = out.replace("###", "").replace("**", "").replace("`", "")
        return f"<div>{out}</div>"
    except Exception:
        return None


def _knowledge_top_k(message: str, topic: Optional[str], subtopic: Optional[str]) -> int:
    msg = message or ""
    k = RAG_TOP_K

    # Broad questions need more recall.
    if any(x in msg for x in ["\ud2b9\uc9d5", "\uc124\uba85", "\uc18c\uac1c", "\uc815\ubcf4", "\ucd94\ucc9c"]):
        k = max(k, 8)

    # Safety/emergency often needs broader evidence to avoid weak/no-context answers.
    if topic in {"safety", "emergency", "health"}:
        k = max(k, 8)

    # Specific operational questions can use tighter context.
    if subtopic in {"metro_subway", "ticket_pass", "ic_card", "tipping", "emergency_numbers"}:
        k = min(max(k, 4), 6)

    if topic in {"visa", "money", "connectivity"} and not any(x in msg for x in ["\ud2b9\uc9d5", "\uc124\uba85", "\uc18c\uac1c"]):
        k = min(max(k, 4), 6)

    return max(3, min(k, 10))


def _is_sports_spectator_travel_query(message: str) -> bool:
    m = (message or "").lower()
    sports = ["축구", "농구", "야구", "경기", "시합", "구단", "팬", "stadium", "arena", "match", "game"]
    spectate = ["관람", "직관", "티켓", "입장권", "예매", "좌석", "관람비", "가격", "얼마", "위치", "어디"]
    return _contains(m, sports) and _contains(m, spectate)


def _rewrite_sports_travel_fallback(message: str, context: str) -> Optional[str]:
    try:
        r = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "너는 여행자 관점의 스포츠 경기 관람 도우미다. 한국어 존댓말로 답하라. "
                        "정확한 실시간 티켓 가격은 단정하지 말고, 가격이 달라지는 요인(상대팀/좌석/경기일/예매 시점)을 설명하라. "
                        "질문에 팀/도시 단서가 있으면 경기장 위치(도시/경기장명)를 일반상식 범위에서 안내해도 된다. "
                        "'문맥에 포함되어 있지 않다' 같은 기계적인 표현은 쓰지 마라. "
                        "반드시 마지막에 공식 구단 사이트/공식 티켓 페이지 확인을 권장하라."
                    ),
                },
                {
                    "role": "user",
                    "content": f"최근 대화:\n{context}\n\n질문: {message}\n\n여행자에게 실용적으로 답변해줘.",
                },
            ],
            temperature=0.3,
        )
        return (r.choices[0].message.content or "").strip() or None
    except Exception:
        return None

def _is_budget_destination_recommendation_query(message: str) -> bool:
    m = (message or "").lower()
    budget = ["\uac00\uc131\ube44", "\uc608\uc0b0", "\ub9cc\uc6d0", "\uc6d0 \uc774\ud558", "\uc800\ub834", "\uc2f8\uac8c", "budget", "cheap", "affordable"]
    rec = ["\ucd94\ucc9c", "\ucd94\ucc9c\uc9c0", "\uc5ec\ud589\uc9c0", "\uc5b4\ub514", "\uac08\ub9cc", "\uac00고\uc2f6", "trip", "destination"]
    region = ["\ub3d9\ub0a8\uc544", "\uc77c\ubcf8", "\uc720\ub7fd", "\ud574\uc678", "southeast asia", "asia"]
    return (_contains(m, budget) and _contains(m, rec)) or (_contains(m, ["\ub3d9\ub0a8\uc544"]) and _contains(m, rec)) or (_contains(m, region) and _contains(m, ["\uac00\uc131\ube44", "\ucd94\ucc9c"]))


def _rewrite_budget_destination_fallback(message: str, context: str) -> Optional[str]:
    try:
        r = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "\ub108\ub294 \uc5ec\ud589 \uc608\uc0b0 \uc0c1\ub2f4 \ub3c4\uc6b0\ubbf8\ub2e4. RAG \uadfc\uac70\uac00 \ubd80\uc871\ud574\ub3c4 \uc77c\ubc18\uc801\uc778 \uc5ec\ud589 \uc0c1\uc2dd \ubc94\uc704\uc5d0\uc11c \uc2e4\uc6a9\uc801\uc73c\ub85c \ub2f5\ud558\ub77c. "
                        "\uc2e4\uc2dc\uac04 \uac00\uaca9\uc744 \ub2e8\uc815\ud558\uc9c0 \ub9d0\uace0, \uc608\uc0b0 \uae30\uc900\uc774 \ub2ec\ub77c\uc9c8 \uc218 \uc788\uc74c\uc744 \uc9e7\uac8c \ubc1d\ud78c \ub4a4 \ud6c4\ubcf4\uc9c0\ub97c 3~5\uac1c \ucd94\ucc9c\ud558\ub77c. "
                        "\ub2f5\ubcc0\uc740 \ud55c\uad6d\uc5b4\ub85c, \uacfc\ud55c \ub9c8\ud06c\ub2e4\uc6b4(###, ** \ub4f1) \uc5c6\uc774 \uae54\ub054\ud55c \ubb38\uc7a5/\ubc88\ud638 \ubaa9\ub85d\uc73c\ub85c \uc791\uc131\ud558\ub77c. "
                        "\uac01 \ud6c4\ubcf4\ub9c8\ub2e4 \uc65c \uac00\uc131\ube44\uac00 \uc88b\uc740\uc9c0(\ud56d\uacf5/\uc219\uc18c/\ubb3c\uac00/\uc774\ub3d9/\uc2dc\uc98c\uc131)\ub97c \ud55c \uc904\uc529 \uc801\uace0, \ub9c8\uc9c0\ub9c9\uc5d0 \ube44\uc6a9 \uc808\uc57d \ud301 2~3\uac1c\ub97c \ubd99\uc5ec\ub77c."
                    ),
                },
                {
                    "role": "user",
                    "content": f"\ucd5c\uadfc \ub300\ud654:\n{context}\n\n\uc9c8\ubb38: {message}",
                },
            ],
            temperature=0.4,
        )
        return (r.choices[0].message.content or "").strip() or None
    except Exception:
        return None

def _answer_knowledge(message: str, context: str, prev_state: Optional[dict[str, Any]] = None):
    msg = message or ""
    if _is_local_place_followup(message, prev_state):
        try:
            return _answer_local_place_followup(message, context, prev_state)
        except Exception:
            pass

    llm_ctx = _resolve_knowledge_context_with_llm(message, context, prev_state)

    country_code = llm_ctx.get("country_code")
    city_name = llm_ctx.get("city_name")
    topic = llm_ctx.get("topic")
    subtopic = llm_ctx.get("subtopic")
    namespace = None

    # Fallback: infer country/city from current message or recent context.
    if not country_code:
        country_code = _infer_rag_country_code([msg, context or ""])

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
    elif topic is None and any(k in msg for k in ["\ubb38\ud654", "\uc608\uc808", "\ud301", "\uc2dd\ub2f9", "\ub808\uc2a4\ud1a0\ub791", "\uc74c\uc2dd", "\uba39\uc744\uac70", "\uc694\ub9ac", "food", "cuisine"]):
        topic = "culture"
        if any(k in msg for k in ["\ud301", "\ud301\ubb38\ud654", "tipping"]):
            subtopic = subtopic or "tipping"
        elif any(k in msg for k in ["\uc74c\uc2dd", "\uba39\uc744\uac70", "\uc694\ub9ac", "food", "cuisine"]):
            subtopic = subtopic or "dining"
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

    retrieval_query = _build_knowledge_retrieval_query(
        message=message,
        country_code=country_code,
        city_name=city_name,
        topic=topic,
        subtopic=subtopic,
    )
    top_k = _knowledge_top_k(message, topic, subtopic)

    try:
        result = answer_rag_question(
            question=message,
            top_k=top_k,
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
                top_k=top_k,
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
        # Some safety/emergency queries retrieve weak chunks and the LLM answers with a strict "no context" template.
        # In that case, retry once with broader country-level retrieval focused on safety keywords.
        if (
            topic in {"safety", "emergency"}
            and country_code
            and any(
                x in content
                for x in [
                    "\uad00\ub828 \ubb38\uc11c\ub97c \ucc3e\uc9c0 \ubabb\ud588\uc2b5\ub2c8\ub2e4",
                    "\uc81c\uacf5\ud560 \uc218 \uc5c6\uc2b5\ub2c8\ub2e4",
                    "\ubb38\ub9e5\uc5d0",
                    "\uc8c4\uc1a1\ud558\uc9c0\ub9cc",
                    "\ud655\uc778 \ud544\uc694",
                ]
            )
        ):
            broad_query = _build_knowledge_retrieval_query(
                message=f"{message} \uc548\uc804 \uce58\uc548 \uc8fc\uc758\uc0ac\ud56d \ubc94\uc8c4 \uacbd\ucc30 \uae34\uae09\ubc88\ud638",
                country_code=country_code,
                city_name=None,
                topic=None,
                subtopic=None,
            )
            retry = answer_rag_question(
                question=message,
                top_k=max(top_k, 8),
                namespace="country",
                country_code=country_code,
                city_name=None,
                topic=None,
                subtopic=None,
                trust_tier_min=1,
                conversation_context=context,
                retrieval_query=broad_query,
            )
            if retry.get("answer"):
                result = retry
                content = (retry.get("answer") or "").strip()
        # Money/exchange-rate questions should avoid misleading generic currency descriptions
        # when the retrieved context does not contain a current numeric rate.
        if topic == "money" and any(k in msg for k in ["환율", "환전"]):
            money_noise_markers = ["지폐", "동전", "1,000엔", "10,000엔"]
            if any(x in content for x in money_noise_markers) and "환율" in msg:
                content = (
                    "실시간 환율은 시점에 따라 계속 변동되므로 여기서 정확한 숫자를 단정해 드리기 어렵습니다. "
                    "대신 여행 준비 기준으로는 공항 환전소/은행 환전 수수료와 카드 해외결제 수수료를 함께 비교하시는 게 좋습니다. "
                    "원하시면 현재 환율 조회 기준(원화↔엔화)으로 확인하는 방법도 안내해드릴게요."
                )
        no_context_markers = [
            "문맥에 포함",
            "제공할 수 없습니다",
            "관련 문서를 찾지 못했습니다",
            "정확한 답변을 드릴 수 없습니다",
        ]
        if _is_sports_spectator_travel_query(message) and any(x in content for x in no_context_markers):
            rewritten = _rewrite_sports_travel_fallback(message, context)
            if rewritten:
                content = rewritten

        # Tone cleanup: avoid machine-like RAG refusal phrasing for user-facing travel chat.
        if "문맥에 포함되어" in content:
            content = content.replace("문맥에 포함되어 있지 않아", "현재 확보된 정보만으로는").replace("문맥에 포함되어 있지 않습니다", "현재 확보된 정보만으로는 확인되지 않습니다")

        if content and not content.startswith("<div"):
            content = _strip_markdown_decorations(content)
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
        raise HTTPException(status_code=400, detail=f"\uc9c1\ud56d\ud68c \uc9c1\ud56d \uc9c1\ud56d: {e}")


@router.post("/chat")
def chat(req: ChatRequest):
    try:
        sid = (req.session_id or "default").strip() or "default"
        history = SESSION_HISTORY.setdefault(sid, [])
        history.append({"role": "user", "text": req.message})
        context = _build_context(history)
        prev_state = SESSION_STATE.get(sid, {})

        if _is_smalltalk_greeting(req.message):
            state = dict(prev_state)
            state["last_intent"] = "knowledge"
            SESSION_STATE[sid] = state
            return {
                "response": (
                    "<div>안녕하세요. DESTINO AI 여행 플래너입니다.<br>"
                    "항공편, 숙소, 여행지 정보, 일정 추천까지 도와드릴게요.</div>"
                )
            }

        domain = _classify_travel_domain_with_llm(req.message, context)
        if domain and (domain.get("is_travel") is False) and float(domain.get("confidence") or 0) >= 0.6:
            state = dict(prev_state)
            state["last_intent"] = "knowledge"
            SESSION_STATE[sid] = state
            return {
                "response": (
                    "<div>여행 관련 질문에 집중해서 도와드리고 있어요.<br>"
                    "항공편, 숙소, 여행지 정보, 일정, 맛집/명소 추천처럼 여행 주제로 질문해 주세요.</div>"
                )
            }

        llm_intent = _resolve_intent_with_llm(req.message, context, prev_state)
        rule_intent = _detect_intent(req.message, prev_state)
        intent = llm_intent or rule_intent

        # Keep contextual knowledge follow-ups out of the flight default path.
        if intent == "flight" and _should_keep_knowledge_followup(req.message, prev_state):
            intent = "knowledge"

        # Local recommendation queries (shopping/spots/food/cafe) should not fall into flight search.
        if intent == "flight" and _is_local_place_followup(req.message, prev_state):
            intent = "knowledge"

        # Route place-to-place guidance questions to travel info (transport) unless flights are explicit.
        if intent == "flight" and _is_route_guidance_query(req.message):
            intent = "knowledge"

        if (
            not _is_local_place_followup(req.message, prev_state)
            and _should_ask_intent_clarification(req.message, prev_state)
            and (
                (llm_intent is None and rule_intent == "flight")
                or (intent == "knowledge" and not _contains((req.message or "").lower(), ["치안", "비자", "교통", "환율", "환전", "맛집", "명소", "카페", "쇼핑", "일정"]))
            )
        ):
            state = dict(prev_state)
            state["last_intent"] = "knowledge"
            SESSION_STATE[sid] = state
            return {
                "response": (
                    "<div>\uc88b\uc544\uc694. \ubb34\uc5c7\uc744 \ub3c4\uc640\ub4dc\ub9b4\uc9c0 \ud655\uc778\ud574\ubcfc\uac8c\uc694.<br>"
                    "\uc6d0\ud558\uc2dc\ub294 \uac83\uc740 <b>\ud56d\uacf5\ud3b8</b> / <b>\uc219\uc18c</b> / <b>\uc5ec\ud589 \uc77c\uc815</b> / "
                    "<b>\uc5ec\ud589 \uc815\ubcf4(\ubb38\ud654\u00b7\uce58\uc548\u00b7\uad50\ud1b5)</b> \uc911 \uc5b4\ub290 \uac83\uc778\uac00\uc694?</div>"
                )
            }

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
            content = _strip_markdown_decorations((r.choices[0].message.content or "").strip())
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
        _attach_krw(raw)
        rows = _filter_pref(_simplify(raw), state)
        rows = _sort_flights_for_recommendation(rows, state)
        limit = state.get("limit")
        if not isinstance(limit, int) or limit <= 0:
            limit = 8
        rows = rows[:limit]
        if not rows and raw.get("amadeus_error"):
            err = raw.get("amadeus_error")
            return {"response": (
                f"<p>Amadeus \uc9c1\ud56d\ud68c API \uc9c1\ud56d: {err}</p>"
                "<p>\uc9c1\ud56d\ud68c \uc9c1\ud56d\ud68c \uc9c1\ud56d\ud68c \uc9c1\ud56d\ud68c \uc9c1\ud56d\ud68c \uc9c1\ud56d\uc9c1\ud56d. \uc9c1\ud56d \uc9c1\ud56d\ud68c \uc9c1\ud56d\uc9c1\ud56d .env\ud68c "
                "<code>AMADEUS_BASE_URL=https://api.amadeus.com</code>"
                " \uc9c1\ud56d \ud68c \uc9c1\ud56d\uc9c1\ud56d \uc9c1\ud56d\ud68c.</p>"
            )}
        state["last_intent"] = "flight"
        SESSION_STATE[sid] = state
        return {"response": _flight_html_intro(state, rows) + _flight_html_table(rows, raw.get("meta_query", {}))}
    except NeedMoreInfoError as e:
        return {"response": f"<p>좋아요, 이어서 찾을게요. {e}</p>"}
    except Exception as e:
        sid = (req.session_id or "default").strip() or "default"
        history = SESSION_HISTORY.setdefault(sid, [])
        err_text = str(e)
        if "500 Server Error" in err_text and "amadeus.com/v2/shopping/flight-offers" in err_text:
            msg = "Amadeus \uc9c1\ud56d\ud68c \uc9c1\ud56d\ud68c \uc9c1\ud56d\uc9c1\ud56d\ud68c \uc9c1\ud56d\uc9c1\ud56d\uc9c1\ud56d. \uc9c1\ud56d\ud68c \uc9c1\ud56d \uc9c1\ud56d\ud68c \uc9c1\ud56d\uc9c1\ud56d \uc9c1\ud56d \ud68c \uc9c1\ud56d \uc9c1\ud56d\ud68c \uc9c1\ud56d\ud68c."
            history.append({"role": "assistant", "text": msg})
            return {"response": f"<div>{msg}</div>"}
        history.append({"role": "assistant", "text": f"\uc9c1\ud56d \uc9c1\ud56d \uc9c1\ud56d: {err_text}"})
        return {"response": f"<pre>\uc9c1\ud56d \uc9c1\ud56d \uc9c1\ud56d: {err_text}</pre>"}