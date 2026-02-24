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
    "서울": "SEL",
    "인천": "ICN",
    "김포": "GMP",
    "부산": "PUS",
    "제주": "CJU",
    "도쿄": "TYO",
    "오사카": "OSA",
    "후쿠오카": "FUK",
    "삿포로": "SPK",
    "나리타": "NRT",
    "하네다": "HND",
    "뉴욕": "NYC",
    "런던": "LON",
    "파리": "PAR",
    "방콕": "BKK",
    "싱가포르": "SIN",
    "시드니": "SYD",
}
COUNTRY_ALIASES = {
    "한국": "SEL",
    "일본": "TYO",
    "미국": "NYC",
    "영국": "LON",
    "프랑스": "PAR",
    "태국": "BKK",
    "베트남": "SGN",
    "싱가포르": "SIN",
    "말레이시아": "KUL",
    "필리핀": "MNL",
    "호주": "SYD",
    "인도": "DEL",
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
    t = re.sub(r"\s+", "", (text or "").lower()).replace("내일모래", "내일모레")
    now = datetime.now()
    if "오늘" in t:
        return now.date()
    if "내일모레" in t or "모레" in t:
        return (now + timedelta(days=2)).date()
    if "내일" in t:
        return (now + timedelta(days=1)).date()
    if "글피" in t:
        return (now + timedelta(days=3)).date()
    m = re.search(r"(\d+)일(뒤|후)", t)
    if m:
        return (now + timedelta(days=int(m.group(1)))).date()
    return None


def _has_date_signal(text: str) -> bool:
    if re.search(r"\b20\d{2}-\d{2}-\d{2}\b", text or ""):
        return True
    return _contains(text or "", ["오늘", "내일", "모레", "글피", "다음주", "이번주", "주말"])


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


def _parse_flight_slots(message: str, context: str) -> dict[str, Any]:
    today = datetime.now().strftime("%Y-%m-%d")
    prompt = f"""오늘 날짜는 {today}. 아래 JSON만 출력:
{{"origin":null,"destination":null,"departure_date":null,"return_date":null,"adults":1,"sort_by":null,"trip_type":null,"limit":null}}
규칙: 저렴=price_asc, 빠른=fastest, 빠르고저렴=fastest_cheap, 왕복이면 trip_type=round.
입력:{message}\n대화:{context}"""
    parsed = _llm_json("항공권 검색 JSON만 출력", prompt)
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
    if not parsed["departure_date"]:
        d = _parse_rel_date(message)
        if d:
            parsed["departure_date"] = d.strftime("%Y-%m-%d")
    if "인도" in message or "india" in message.lower():
        if (parsed.get("destination") or "").upper() in {"", "IND", "IN"}:
            parsed["destination"] = "DEL"
    m = re.search(r"(?:성인\s*)?(\d+)\s*명", message)
    if m:
        parsed["adults"] = max(1, int(m.group(1)))
    if _contains(message, ["저렴", "싼", "가성비"]):
        parsed["sort_by"] = "price_asc"
    if _contains(message, ["가장 빨리", "최단", "빠르게"]):
        parsed["sort_by"] = "fastest_cheap" if parsed["sort_by"] == "price_asc" else "fastest"
    return parsed


def _parse_hotel_slots(message: str, context: str) -> dict[str, Any]:
    today = datetime.now().strftime("%Y-%m-%d")
    prompt = f"""오늘 날짜는 {today}. JSON만 출력:
{{"query":null,"checkin_date":null,"checkout_date":null,"adults":2,"top_k":5,"bucket":"value_top"}}
후기=review_top, 위치=location_top, 가성비=value_top.
입력:{message}\n대화:{context}"""
    parsed = _llm_json("호텔 추천 JSON만 출력", prompt)
    parsed.setdefault("query", None)
    parsed.setdefault("checkin_date", None)
    parsed.setdefault("checkout_date", None)
    parsed.setdefault("adults", 2)
    parsed.setdefault("top_k", 5)
    parsed.setdefault("bucket", "value_top")
    if not parsed["checkin_date"]:
        d = _parse_rel_date(message)
        if d:
            parsed["checkin_date"] = d.strftime("%Y-%m-%d")
    m = re.search(r"(오늘|내일|모레|내일모레|글피)부터(\d+)일", re.sub(r"\s+", "", message))
    if m:
        base = _parse_rel_date(m.group(1))
        if base:
            parsed["checkin_date"] = base.strftime("%Y-%m-%d")
            parsed["checkout_date"] = (base + timedelta(days=int(m.group(2)))).strftime("%Y-%m-%d")
    if "후기" in message:
        parsed["bucket"] = "review_top"
    elif "위치" in message:
        parsed["bucket"] = "location_top"
    elif "가성비" in message:
        parsed["bucket"] = "value_top"
    m2 = re.search(r"top\s*(\d+)", message.lower()) or re.search(r"(\d+)\s*개", message)
    if m2:
        parsed["top_k"] = int(m2.group(1))
    return parsed


def _detect_intent(message: str, prev_state: dict[str, Any]) -> str:
    m = (message or "").lower()
    if _contains(m, ["호텔", "숙소", "숙박", "체크인", "체크아웃"]):
        return "hotel"
    if _contains(m, ["일정", "코스", "루트", "플랜", "day 1", "1일차"]):
        return "itinerary"
    if _contains(m, ["어디", "문화", "비자", "시차", "환율", "날씨", "명소", "맛집"]) and not _contains(
        m, ["항공", "항공권", "비행기", "출발", "도착"]
    ):
        return "knowledge"
    if prev_state.get("hotel_context") and _contains(m, ["후기", "위치", "가성비", "top", "순위", "추천", "다시"]):
        return "hotel"
    if prev_state.get("last_intent") == "hotel" and not _contains(m, ["항공", "비행기", "출발", "도착"]):
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
        q.append("출발지를 알려주세요. (예: 서울, 부산, ICN)")
    if not state.get("destination"):
        q.append("도착지를 알려주세요. (예: 도쿄, 부산, NRT)")
    if not state.get("departure_date"):
        q.append("출발일을 알려주세요. (YYYY-MM-DD 또는 예: 3월 15일)")
    if state.get("trip_type") == "round" and not state.get("return_date"):
        q.append("왕복 일정이므로 복귀일을 알려주세요. (YYYY-MM-DD)")
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
    s = top["segments"][0] if top.get("segments") else {}
    return (
        "<div style='margin-bottom:10px;padding:10px;border:1px solid #dbeafe;background:#eff6ff;'>"
        f"<b>요청 이해</b>: {state.get('origin')} → {state.get('destination')} 항공편을 찾았어요.<br>"
        f"<b>추천 1순위</b>: {s.get('departure','-')} 출발 / {s.get('arrival','-')} 도착 / "
        f"{top.get('itinerary_duration') or s.get('duration','-')} / {top.get('price')} {top.get('currency')}"
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
        return "<p>호텔을 찾을 도시를 알려주세요. (예: 오사카, 도쿄)</p>", {
            "hotel_context": True,
            "hotel_adults": adults,
        }
    if not checkin or not checkout:
        return "<p>체크인/체크아웃 날짜를 알려주세요. (YYYY-MM-DD)</p>", {
            "hotel_context": True,
            "hotel_query": query,
            "hotel_checkin": checkin,
            "hotel_checkout": checkout,
            "hotel_adults": adults,
        }
    dest = booking_search_destination(query=query)
    cands = dest.get("data", []) if isinstance(dest, dict) else []
    if not cands:
        return "<p>목적지를 찾지 못했습니다. 도시명을 조금 더 구체적으로 입력해 주세요.</p>", {"hotel_context": True}
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
        return f"<pre>호텔 검색 실패: {raw.get('message', 'Booking API error')}</pre>", {"hotel_context": True}
    center = (float(first.get("latitude") or first.get("lat") or 34.703968), float(first.get("longitude") or first.get("lon") or 135.49292))
    rows = booking_recommend_buckets(raw, center=center, top_k=top_k).get(bucket) or []
    if not rows:
        return "<p>조건에 맞는 호텔 결과가 없습니다.</p>", {"hotel_context": True}
    title = {"value_top": "가성비 TOP", "review_top": "후기 TOP", "location_top": "위치 TOP"}.get(bucket, "추천 TOP")
    lines = []
    for i, h in enumerate(rows, 1):
        line = f"{i}) {h.get('name') or '-'} | 가격: {(h.get('price') or {}).get('value')} {(h.get('price') or {}).get('currency') or '-'}"
        if (h.get("review") or {}).get("score") is not None:
            line += f" | 평점: {(h.get('review') or {}).get('score')}"
        if h.get("distance_m") is not None:
            line += f" | 거리: {int(h.get('distance_m'))}m"
        lines.append(line)
    return f"<div><b>{query} {title} {len(rows)}개</b><br>{'<br>'.join(lines)}</div>", {
        "hotel_context": True,
        "hotel_query": query,
        "hotel_checkin": checkin,
        "hotel_checkout": checkout,
        "hotel_adults": adults,
    }


def _answer_knowledge(message: str, context: str) -> str:
    if not Pinecone or not PINECONE_API_KEY or not PINECONE_INDEX_NAME:
        return "<div>지식 문서 인덱스가 아직 설정되지 않았습니다. 원하시면 항공/호텔 검색은 바로 도와드릴게요.</div>"
    try:
        global pinecone_index
        if pinecone_index is None:
            pinecone_index = Pinecone(api_key=PINECONE_API_KEY).Index(PINECONE_INDEX_NAME)
        emb = client.embeddings.create(model=EMBEDDING_MODEL, input=message).data[0].embedding
        q = pinecone_index.query(vector=emb, top_k=RAG_TOP_K, include_metadata=True, namespace=PINECONE_NAMESPACE)
        matches = getattr(q, "matches", None) or (q.get("matches", []) if isinstance(q, dict) else [])
        chunks = []
        for m in matches:
            md = getattr(m, "metadata", None) or (m.get("metadata", {}) if isinstance(m, dict) else {})
            text = (md or {}).get("text") or (md or {}).get("content")
            if text:
                chunks.append(text)
        if not chunks:
            return "<div>관련 여행 지식 문서를 찾지 못했습니다.</div>"
        prompt = f"질문에 한국어 존댓말로 간결히 답하고 마지막에 항공편 검색 안내 한 줄을 추가해. 질문:{message}\n문맥:{chr(10).join(chunks[:5])}\n최근대화:{context}"
        r = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "system", "content": "RAG 기반 여행 도우미"}, {"role": "user", "content": prompt}],
            temperature=0.2,
        )
        content = (r.choices[0].message.content or "").strip()
        return content if content.startswith("<div") else f"<div>{content}</div>"
    except Exception:
        return "<div>지식 답변 생성 중 오류가 발생했습니다.</div>"


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
        raise HTTPException(status_code=400, detail=f"항공권 검색 실패: {e}")


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
            html = _answer_knowledge(req.message, context)
            state = dict(prev_state)
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
        if not rows and raw.get("amadeus_error"):
            err = raw.get("amadeus_error")
            return {"response": (
                f"<p>Amadeus ??? API ??: {err}</p>"
                "<p>??? ??? ??? ??? ??? ????. ?? ??? ???? .env? "
                "<code>AMADEUS_BASE_URL=https://api.amadeus.com</code>"
                " ?? ? ???? ???.</p>"
            )}
        state["last_intent"] = "flight"
        SESSION_STATE[sid] = state
        return {"response": _flight_html_intro(state, rows) + _flight_html_table(rows, raw.get("meta_query", {}))}

    except NeedMoreInfoError as e:
        return {"response": f"<p>좋아요, 이어서 찾을게요. {e}</p>"}
    except Exception as e:
        sid = (req.session_id or "default").strip() or "default"
        history = SESSION_HISTORY.setdefault(sid, [])
        history.append({"role": "assistant", "text": f"요청 처리 실패: {e}"})
        return {"response": f"<pre>요청 처리 실패: {e}</pre>"}
