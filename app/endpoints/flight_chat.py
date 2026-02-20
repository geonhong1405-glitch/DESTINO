

from fastapi import APIRouter, Query
from app.api.amadeus_api import search_flight_offers_raw
from app.api.booking_hotel_flight_api import search_flights as booking_search_flights
from app.api.exchange_rate import get_exchange_rate


router = APIRouter()
import requests
import re
import json
from pydantic import BaseModel
from typing import Optional
import os

# 환경변수에서 가져오거나 기본값 사용
RAG_TOP_K = int(os.getenv("RAG_TOP_K", "5"))

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
    "로마": "ROM",
    "방콕": "BKK",
    "다낭": "DAD",
    "하노이": "HAN",
    "호치민": "SGN",
    "싱가포르": "SIN",
}

COUNTRY_ALIASES = {
    "korea": "SEL",
    "south korea": "SEL",
    "usa": "NYC",
    "united states": "NYC",
    "france": "PAR",
    "uk": "LON",
    "england": "LON",
    "united kingdom": "LON",
    "thailand": "BKK",
    "vietnam": "SGN",
    "australia": "SYD",
    "india": "DEL",
    "indonesia": "JKT",
    "philippines": "MNL",
    "malaysia": "KUL",
    "germany": "BER",
    "spain": "MAD",
    "italy": "ROM",
    "canada": "YTO",
    "hong kong": "HKG",
    "taiwan": "TPE",
    "new zealand": "AKL",
}

LOCATION_ALIASES_NORM = {re.sub(r"\s+", "", k).lower(): v for k, v in LOCATION_ALIASES.items()}
COUNTRY_ALIASES_NORM = {re.sub(r"\s+", "", k).lower(): v for k, v in COUNTRY_ALIASES.items()}


class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = None



class NeedMoreInfoError(Exception):
    pass


def _to_float_or_none(value):
    try:
        return float(value)
    except Exception:
        return None


DEFAULT_FX_TO_KRW = {
    "KRW": 1.0,
    "USD": 1350.0,
    "EUR": 1470.0,
    "JPY": 9.0,
    "CNY": 190.0,
}


def _attach_krw_prices(raw):
    offers = raw.get("data", []) if isinstance(raw, dict) else []
    if not isinstance(offers, list):
        return {}

    currencies = set()
    for offer in offers:
        if not isinstance(offer, dict):
            continue
        currency = (offer.get("price", {}) or {}).get("currency")
        if currency:
            currencies.add(str(currency).upper())

    rates = {}
    for currency in currencies:
        if currency == "KRW":
            rates[currency] = 1.0
            continue
        try:
            rates[currency] = get_exchange_rate(base=currency, target="KRW")
            if not rates[currency]:
                rates[currency] = DEFAULT_FX_TO_KRW.get(currency)
        except Exception:
            rates[currency] = DEFAULT_FX_TO_KRW.get(currency)

    for offer in offers:
        if not isinstance(offer, dict):
            continue
        price_obj = offer.get("price", {}) or {}
        currency = str(price_obj.get("currency", "")).upper()
        total = _to_float_or_none(price_obj.get("total"))
        rate = rates.get(currency)
        if total is None or rate is None:
            continue
        price_obj["krwTotal"] = int(round(total * float(rate)))
        price_obj["krwRate"] = float(rate)
        offer["price"] = price_obj

    return rates

# GET /api/flight-search 엔드포인트 추가
from fastapi import HTTPException

@router.get("/api/flight-search")
def api_flight_search(
    origin: str = Query(..., description="출발 도시명 또는 IATA 코드"),
    destination: str = Query(..., description="도착 도시명 또는 IATA 코드"),
    departure_date: str = Query(..., description="YYYY-MM-DD"),
    return_date: str = Query(None, description="YYYY-MM-DD, 왕복일 경우"),
    adults: int = Query(1, description="성인 인원"),
    child: int = Query(0, description="소아 인원"),
    infant: int = Query(0, description="유아 인원"),
    cabin: str = Query(None, description="좌석 등급"),
    max_price: float = Query(None, description="최대 가격")
):
    try:
        # cabin 한글/영문 → Amadeus travelClass
        cabin_map = {
            "일반": "ECONOMY",
            "이코노미": "ECONOMY",
            "economy": "ECONOMY",
            "일반석": "ECONOMY",
            "비즈니스": "BUSINESS",
            "business": "BUSINESS",
            "비즈니스석": "BUSINESS",
            "프레스티지": "BUSINESS",
            "퍼스트": "FIRST",
            "first": "FIRST",
            "일등": "FIRST",
            "일등석": "FIRST",
            "퍼스트석": "FIRST",
        }
        if cabin:
            normalized = cabin.strip().lower()
            cabin = cabin_map.get(normalized, cabin_map.get(normalized.replace("석", ""), "ECONOMY"))
        # search_flights 호출 시 cabin 전달
        raw = search_flights(
            origin,
            destination,
            departure_date,
            return_date,
            adults,
            max_price,
            cabin,
            30,
        )
        exchange_rates = _attach_krw_prices(raw)
        booking_ref = raw.get("booking_reference", [])
        if isinstance(booking_ref, list):
            for row in booking_ref:
                if not isinstance(row, dict):
                    continue
                cur = str(row.get("currency", "")).upper()
                p = _to_float_or_none(row.get("price"))
                rate = exchange_rates.get(cur)
                if cur == "KRW":
                    rate = 1.0
                elif rate is None and cur:
                    try:
                        rate = get_exchange_rate(base=cur, target="KRW")
                        if not rate:
                            rate = DEFAULT_FX_TO_KRW.get(cur)
                        exchange_rates[cur] = rate
                    except Exception:
                        rate = DEFAULT_FX_TO_KRW.get(cur)
                        if rate:
                            exchange_rates[cur] = rate
                if p is not None and rate:
                    row["price_krw"] = int(round(p * float(rate)))
        simplified = simplify(raw)
        return {
            # 프론트(airport.js)는 results에 Amadeus 원본 offer를 기대함
            "results": raw.get("data", []),
            "simplified": simplified,
            "meta_query": raw.get("meta_query", {}),
            "booking_reference": raw.get("booking_reference", []),
            "exchange_rates": exchange_rates,
            "raw": raw,
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"항공권 검색 실패: {str(e)}")


def init_pinecone_index():
    global pinecone_index
    if pinecone_index is not None:
        return pinecone_index
    if not Pinecone or not PINECONE_API_KEY or not PINECONE_INDEX_NAME:
        return None
    try:
        pc = Pinecone(api_key=PINECONE_API_KEY)
        pinecone_index = pc.Index(PINECONE_INDEX_NAME)
        return pinecone_index
    except Exception:
        return None


def embed_text(text):
    response = client.embeddings.create(
        model=EMBEDDING_MODEL,
        input=text,
    )
    return response.data[0].embedding


def retrieve_knowledge_chunks(query, top_k=RAG_TOP_K):
    index = init_pinecone_index()
    if index is None:
        return []

    vector = embed_text(query)
    res = index.query(
        vector=vector,
        top_k=top_k,
        include_metadata=True,
        namespace=PINECONE_NAMESPACE,
    )

    matches = getattr(res, "matches", None)
    if matches is None and isinstance(res, dict):
        matches = res.get("matches", [])
    if not matches:
        return []

    chunks = []
    for m in matches:
        meta = getattr(m, "metadata", None)
        if meta is None and isinstance(m, dict):
            meta = m.get("metadata", {}) or {}
        score = getattr(m, "score", None)
        if score is None and isinstance(m, dict):
            score = m.get("score")
        text = (meta or {}).get("text") or (meta or {}).get("content")
        if text:
            chunks.append(
                {
                    "text": text,
                    "source": (meta or {}).get("source", "unknown"),
                    "score": score,
                }
            )
    return chunks


def is_knowledge_query(user_input):
    text = (user_input or "").lower().strip()
    knowledge_keywords = [
        "어디",
        "위치",
        "수도",
        "언어",
        "문화",
        "환율",
        "환전",
        "비자",
        "입국",
        "출입국",
        "교통",
        "치안",
        "주의",
        "날씨",
        "기후",
        "언제 가",
        "여행하기",
        "얼마나 걸려",
        "비행시간",
        "시간 얼마나",
        "시차",
        "추천 명소",
        "맛집",
        "여행 팁",
        "주의사항",
    ]
    flight_keywords = [
        "항공편",
        "비행기",
        "검색",
        "가격",
        "예매",
        "예약",
        "왕복",
        "편도",
        "출발",
        "도착",
    ]
    general_question_patterns = [
        "뭐야",
        "무엇",
        "어때",
        "어떤",
        "알려줘",
        "설명",
        "정보",
    ]
    has_knowledge = any(k in text for k in knowledge_keywords) or any(p in text for p in general_question_patterns)
    has_flight = any(k in text for k in flight_keywords)
    return has_knowledge and not has_flight


def is_itinerary_query(user_input):
    text = (user_input or "").lower().strip()
    itinerary_keywords = [
        "일정",
        "코스",
        "루트",
        "플랜",
        "day 1",
        "day1",
        "1일차",
        "2일차",
        "여행 계획",
    ]
    return any(k in text for k in itinerary_keywords)


def detect_intent(user_input):
    if is_itinerary_query(user_input):
        return "itinerary"
    if is_knowledge_query(user_input):
        return "knowledge"
    return "flight"


def is_ascii_text(value):
    return all(ord(ch) < 128 for ch in value)


def normalize_location_keyword(keyword):
    cleaned = (keyword or "").strip()
    if not cleaned:
        return cleaned

    norm_key = re.sub(r"\s+", "", cleaned).lower()
    if norm_key in LOCATION_ALIASES_NORM:
        return LOCATION_ALIASES_NORM[norm_key]
    if norm_key in COUNTRY_ALIASES_NORM:
        return COUNTRY_ALIASES_NORM[norm_key]

    if len(cleaned) == 3 and cleaned.isalpha():
        return cleaned.upper()

    if is_ascii_text(cleaned):
        return cleaned

    # Non-ASCII 도시명은 영문 키워드 또는 IATA 코드로 변환해 위치 검색 실패를 줄인다.
    try:
        prompt = (
            "다음 지명을 Amadeus Location API용 영문 도시명 또는 3글자 IATA 코드로 변환해라. "
            "나라명이면 대표 허브 도시 IATA(예: Japan->TYO, USA->NYC)를 사용해라. "
            'JSON만 출력: {"keyword":"..."}\n'
            f"입력: {cleaned}"
        )
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "변환 결과 JSON만 출력"},
                {"role": "user", "content": prompt},
            ],
            temperature=0,
        )
        content = (response.choices[0].message.content or "").strip()
        content = content.replace("```json", "").replace("```", "").strip()
        parsed = json.loads(content)
        converted = (parsed.get("keyword") or "").strip()
        return converted or cleaned
    except Exception:
        return cleaned


def resolve_location_to_iata(keyword, token=None):
    keyword = normalize_location_keyword(keyword)
    if not keyword:
        return None

    if len(keyword) == 3 and keyword.isalpha():
        return keyword.upper()
    return amadeus_resolve_location_to_iata(keyword, token=token)


def search_flights(
    origin,
    destination,
    departure_date,
    return_date=None,
    adults=1,
    max_price=None,
    cabin=None,
    api_max=30,
):
    import logging
    logger = logging.getLogger("flight_search")
    if not logger.hasHandlers():
        fh = logging.FileHandler(os.path.join(os.path.dirname(__file__), '../hotel_debug.log'), encoding='utf-8')
        formatter = logging.Formatter('[%(asctime)s] %(levelname)s %(message)s')
        fh.setFormatter(formatter)
        logger.addHandler(fh)
        logger.setLevel(logging.INFO)
    try:
        logger.info(f"[flight_search] origin={origin}, destination={destination}, departure_date={departure_date}, return_date={return_date}, adults={adults}, max_price={max_price}")
        origin_iata = resolve_location_to_iata(origin)
        destination_iata = resolve_location_to_iata(destination)
        logger.info(f"[flight_search] resolved origin_iata={origin_iata}, destination_iata={destination_iata}")
        if not origin_iata or not destination_iata:
            logger.error(f"[flight_search] IATA 변환 실패: origin={origin}, destination={destination}")
            raise ValueError(f"출발/도착지를 공항 코드로 해석하지 못했습니다. origin={origin}, destination={destination}")
        # Amadeus 메인 데이터
        data = search_flight_offers_raw(
            origin_code=origin_iata,
            destination_code=destination_iata,
            departure_date=departure_date,
            return_date=return_date,
            adults=adults,
            cabin=cabin,
            max_results=api_max,
        )
        logger.info(f"[flight_search] amadeus_result: {data}")
        # Booking.com 참고 데이터
        try:
            booking_data = booking_search_flights(origin_iata, destination_iata, departure_date, return_date, adults)
            data["booking_reference"] = booking_data.get("data", [])
            logger.info(f"[flight_search] booking_reference: {booking_data}")
        except Exception as e:
            data["booking_reference_error"] = str(e)
            logger.error(f"[flight_search] booking_reference_error: {e}")
        if max_price:
            filtered = []
            for offer in data.get("data", []):
                price = float(offer["price"]["total"])
                if price <= float(max_price):
                    filtered.append(offer)
            data["data"] = filtered
        data["meta_query"] = {
            "origin": origin_iata,
            "destination": destination_iata,
            "departure_date": departure_date,
            "return_date": return_date,
            "adults": adults,
            "max_price": max_price,
            "cabin": cabin,
        }
        logger.info(f"[flight_search] meta_query: {data['meta_query']}")
        return data
    except Exception as e:
        logger.error(f"[flight_search] Exception: {e}")
        raise


def duration_to_minutes(duration_text):
    if not duration_text or not isinstance(duration_text, str):
        return 10**9
    match = re.match(r"^PT(?:(\d+)H)?(?:(\d+)M)?$", duration_text)
    if not match:
        return 10**9
    hours = int(match.group(1) or 0)
    minutes = int(match.group(2) or 0)
    return hours * 60 + minutes


def parse_iso_datetime(value):
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except Exception:
        return None


def simplify(raw_data):
    results = []
    seen = set()

    for offer in raw_data.get("data", []):
        itinerary_key = json.dumps(offer["itineraries"], ensure_ascii=False)
        if itinerary_key in seen:
            continue
        seen.add(itinerary_key)

        price = offer["price"]["total"]
        price_value = float(price)
        currency = offer["price"]["currency"]
        airline_codes = offer.get("validatingAirlineCodes", [])
        itinerary_duration = (
            offer.get("itineraries", [{}])[0].get("duration")
            if offer.get("itineraries")
            else None
        )
        segments_info = []

        for itin in offer.get("itineraries", []):
            for seg in itin.get("segments", []):
                segments_info.append(
                    {
                        "airline": seg.get("carrierCode", "-"),
                        "departure": seg.get("departure", {}).get("at", "-"),
                        "arrival": seg.get("arrival", {}).get("at", "-"),
                        "duration": seg.get("duration", "-"),
                    }
                )

        first_departure = segments_info[0]["departure"] if segments_info else None
        first_itinerary_segments = offer.get("itineraries", [{}])[0].get("segments", [])
        stops = max(len(first_itinerary_segments) - 1, 0)
        primary_airline = segments_info[0]["airline"] if segments_info else "-"
        results.append(
            {
                "price": price,
                "price_value": price_value,
                "currency": currency,
                "segments": segments_info,
                "airline_codes": airline_codes,
                "itinerary_duration": itinerary_duration,
                "duration_min": duration_to_minutes(itinerary_duration),
                "first_departure": first_departure,
                "stops": stops,
                "primary_airline": primary_airline,
            }
        )

    return results


def format_html(results, query_meta):
    if not results:
        return "<p>조건에 맞는 항공편을 찾지 못했습니다.</p>"

    html = ""
    html += (
        "<div style='margin-bottom:10px;padding:8px;background:#f7f7f7;border:1px solid #ddd;'>"
        f"<b>API 조회조건</b> | 출발: {query_meta.get('origin')} / 도착: {query_meta.get('destination')} / "
        f"출발일: {query_meta.get('departure_date')} / 복귀일: {query_meta.get('return_date') or '-'} / "
        f"인원: {query_meta.get('adults')} / 최대가격: {query_meta.get('max_price') or '-'}"
        "</div>"
    )

    html += "<table border='1' style='border-collapse:collapse; width:100%;'>"
    html += "<tr><th>항공사</th><th>출발</th><th>도착</th><th>소요시간</th><th>가격</th></tr>"

    for r in results:
        for seg in r["segments"]:
            html += (
                f"<tr><td>{seg['airline']}</td><td>{seg['departure']}</td><td>{seg['arrival']}</td>"
                f"<td>{seg['duration']}</td><td>{r['price']} {r['currency']}</td></tr>"
            )
        html += "<tr><td colspan='5' style='text-align:center;background:#f0f0f0;'>-----</td></tr>"

    html += "</table>"
    return html


def build_conversational_answer(user_input, state, results):
    if not results:
        return (
            "<p>조건에 맞는 항공편을 찾지 못했어요.</p>"
            "<p>원하면 날짜를 하루 앞뒤로 넓혀서 다시 찾아볼까요?</p>"
        )

    best = results[0]
    top3 = select_diverse_recommendations(results, 3)
    first_seg = best["segments"][0] if best.get("segments") else {}
    dep = first_seg.get("departure", "-")
    arr = first_seg.get("arrival", "-")
    dur = best.get("itinerary_duration") or first_seg.get("duration", "-")
    price = f"{best.get('price')} {best.get('currency')}"

    sort_label = {
        "price_asc": "저렴한 순",
        "price_desc": "비싼 순",
        "fastest": "가장 빠른 순",
        "fastest_cheap": "빠르고 저렴한 순",
    }.get(state.get("sort_by"), "조건 기반")

    filter_bits = []
    if state.get("departure_window") == "morning":
        filter_bits.append("오전 출발")
    elif state.get("departure_window") == "afternoon":
        filter_bits.append("오후 출발")
    elif state.get("departure_window") == "evening":
        filter_bits.append("저녁 출발")
    elif state.get("departure_window") == "night":
        filter_bits.append("야간 출발")
    if state.get("direct_only") is True:
        filter_bits.append("직항만")
    filter_text = f" / 추가조건: {', '.join(filter_bits)}" if filter_bits else ""

    lines = []
    for i, row in enumerate(top3, start=1):
        seg = row["segments"][0] if row.get("segments") else {}
        lines.append(
            f"{i}) {row.get('primary_airline', '-')}: {seg.get('departure', '-')} 출발, "
            f"{row.get('itinerary_duration') or seg.get('duration', '-')}, {row.get('price')} {row.get('currency')}"
        )
    picks_html = "<br>".join(lines)

    intro = (
        "<div style='margin-bottom:10px;padding:10px;border:1px solid #dbeafe;background:#eff6ff;'>"
        f"<b>요청 이해</b>: {sort_label}으로 {state.get('origin')} → {state.get('destination')} 항공편을 찾았어요{filter_text}.<br>"
        f"<b>추천 1순위</b>: {dep} 출발 / {arr} 도착 / {dur} / {price}<br>"
        f"<b>추천 바리에이션</b><br>{picks_html}<br>"
        "원하면 지금 결과에서 <b>직항만</b>, <b>수하물 포함</b>, <b>출발 시간대</b> 조건으로 더 좁혀드릴게요."
        "</div>"
    )
    return intro


def llm_parse_partial(user_input, conversation_context=""):
    today = datetime.now().strftime("%Y-%m-%d")
    prompt = f"""
너는 항공권 검색 파라미터 추출기다.
오늘 날짜는 {today} 이다.
사용자 입력에서 아래 JSON만 출력해라(설명 금지):
{{
  "origin": "출발 도시명 또는 IATA 코드",
  "destination": "도착 도시명 또는 IATA 코드",
  "departure_date": "YYYY-MM-DD 또는 null",
  "return_date": "YYYY-MM-DD 또는 null",
  "adults": 숫자,
  "max_price": 숫자 또는 null,
  "limit": 숫자 또는 null,
  "sort_by": "price_asc 또는 price_desc 또는 fastest 또는 fastest_cheap 또는 null",
  "trip_type": "round 또는 oneway 또는 null",
  "time_pref": "after_now 또는 null",
  "departure_window": "morning/afternoon/evening/night 또는 null",
  "direct_only": true/false/null
}}
규칙:
- origin/destination은 가능하면 IATA(예: ICN, TYO, JFK) 또는 영문 도시명으로 출력
- 편도면 trip_type은 oneway, 왕복이면 round
- 인원 언급이 없으면 adults=1
- 최대가격 언급이 없으면 max_price=null
- 출발지/도착지/날짜가 입력에 없으면 null로 둔다
- 자연어 날짜(예: 다음 주 금요일, 3월 15일)를 반드시 YYYY-MM-DD로 변환
- 통화단위는 제거하고 숫자만 넣어라
- "저렴", "싼", "가성비" 표현이 있으면 sort_by는 price_asc
- "비싼", "고가", "높은 가격", "비싼순" 표현이 있으면 sort_by는 price_desc
- "가장 빨리", "최단", "빨리 갈 수 있는" 표현이 있으면 sort_by는 fastest
- "가장 빨리"와 "저렴"이 함께 있으면 sort_by는 fastest_cheap
- "N개", "상위 N개" 표현이 있으면 limit=N, 없으면 null
- "지금", "지금 시간 기준", "오늘 중", "당장" 표현이 있고 날짜가 없으면 departure_date는 오늘 날짜로 추정하고 time_pref는 after_now
- "오전/아침"이면 departure_window는 morning
- "오후"면 departure_window는 afternoon
- "저녁"이면 departure_window는 evening
- "밤/야간"이면 departure_window는 night
- "직항만/경유 없이"면 direct_only=true
- 이전 질문에 대한 짧은 답변이면 언급된 필드만 채우고 나머지는 null

사용자 입력:
{user_input}

최근 대화(있으면 참고):
{conversation_context}
"""

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "항공권 검색 JSON만 출력"},
            {"role": "user", "content": prompt},
        ],
        temperature=0,
    )

    content = (response.choices[0].message.content or "").strip()
    content = content.replace("```json", "").replace("```", "").strip()
    parsed = json.loads(content)

    parsed.setdefault("origin", None)
    parsed.setdefault("destination", None)
    parsed.setdefault("departure_date", None)
    parsed.setdefault("adults", 1)
    parsed.setdefault("return_date", None)
    parsed.setdefault("max_price", None)
    parsed.setdefault("limit", None)
    parsed.setdefault("sort_by", None)
    parsed.setdefault("trip_type", None)
    parsed.setdefault("time_pref", None)
    parsed.setdefault("departure_window", None)
    parsed.setdefault("direct_only", None)

    lowered = (user_input or "").lower()
    wants_fast = any(k in user_input for k in ["가장 빨리", "최단", "빨리 갈 수", "빠르게", "가장 빠르게"])
    wants_cheap = any(k in user_input for k in ["저렴", "싼", "가성비", "저가", "저렴한순", "싼순"]) or "cheap" in lowered
    wants_now = any(k in user_input for k in ["지금", "지금 시간 기준", "오늘 중", "당장"]) or "asap" in lowered

    if any(k in user_input for k in ["비싼", "고가", "높은 가격", "비싼순"]) or "expensive" in lowered:
        parsed["sort_by"] = "price_desc"
    elif wants_fast and wants_cheap:
        parsed["sort_by"] = "fastest_cheap"
    def simplify(raw_data):
        import logging
        import traceback
        logger = logging.getLogger("flight_search")
        # 핸들러 중복 방지 및 강제 파일 핸들러 추가
        if not logger.hasHandlers():
            import os
            fh = logging.FileHandler(os.path.join(os.path.dirname(__file__), '../hotel_debug.log'), encoding='utf-8')
            formatter = logging.Formatter('[%(asctime)s] %(levelname)s %(message)s')
            fh.setFormatter(formatter)
            logger.addHandler(fh)
            logger.setLevel(logging.INFO)
        results = []
        seen = set()
        try:
            for offer in raw_data.get("data", []):
                itinerary_key = json.dumps(offer["itineraries"], ensure_ascii=False)
                if itinerary_key in seen:
                    continue
                seen.add(itinerary_key)

                price = offer["price"]["total"]
                price_value = float(price)
                currency = offer["price"]["currency"]
                airline_codes = offer.get("validatingAirlineCodes", [])
                itinerary_duration = (
                    offer.get("itineraries", [{}])[0].get("duration")
                    if offer.get("itineraries")
                    else None
                )
                segments_info = []

                for itin in offer.get("itineraries", []):
                    for seg in itin.get("segments", []):
                        segments_info.append(
                            {
                                "airline": seg.get("carrierCode", "-"),
                                "departure": seg.get("departure", {}).get("at", "-"),
                                "arrival": seg.get("arrival", {}).get("at", "-"),
                                "duration": seg.get("duration", "-"),
                            }
                        )

                first_departure = segments_info[0]["departure"] if segments_info else None
                first_itinerary_segments = offer.get("itineraries", [{}])[0].get("segments", [])
                stops = max(len(first_itinerary_segments) - 1, 0)
                primary_airline = segments_info[0]["airline"] if segments_info else "-"
                results.append(
                    {
                        "price": price,
                        "price_value": price_value,
                        "currency": currency,
                        "segments": segments_info,
                        "airline_codes": airline_codes,
                        "duration": itinerary_duration,
                        "departure": first_departure,
                        "stops": stops,
                        "primary_airline": primary_airline,
                    }
                )
            logger.info(f"[simplify] 결과 {len(results)}건")
            return results
        except Exception as e:
            logger.error(f"[simplify] Exception: {e}")
            logger.error(f"[simplify] raw_data: {raw_data}")
            tb = traceback.format_exc()
            logger.error(f"[simplify] traceback: {tb}")
            # 파일에 직접 기록
            with open(os.path.join(os.path.dirname(__file__), '../hotel_debug.log'), 'a', encoding='utf-8') as f:
                f.write(f"[simplify Exception] {e}\n[simplify raw_data] {raw_data}\n[simplify traceback] {tb}\n")
            print(f"[simplify Exception] {e}\n[simplify raw_data] {raw_data}\n[simplify traceback] {tb}\n")
            raise

def has_explicit_date_signal(text: str) -> bool:
    if not text:
        return False
    lowered = text.lower()
    if re.search(r"\b20\d{2}-\d{2}-\d{2}\b", text):
        return True
    date_keywords = [
        "오늘",
        "내일",
        "모레",
        "글피",
        "이번주",
        "다음주",
        "주말",
        "월요일",
        "화요일",
        "수요일",
        "목요일",
        "금요일",
        "토요일",
        "일요일",
        "tomorrow",
        "today",
        "next week",
        "this week",
    ]
    return any(k in lowered for k in date_keywords)


def sanitize_slot_value(value):
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"", "null", "none", "unknown", "n/a", "-"}:
            return None
    return value


def merge_with_session(previous, current):
    merged = dict(previous or {})
    for key in SLOT_KEYS:
        value = sanitize_slot_value(current.get(key))
        if value is not None and value != "":
            merged[key] = value
    merged.setdefault("adults", 1)
    return merged


def build_missing_questions(state):
    missing = []
    if not state.get("origin"):
        missing.append("출발지를 알려주세요. (예: 서울, 부산, ICN)")
    if not state.get("destination"):
        missing.append("도착지를 알려주세요. (예: 도쿄, 부산, NRT)")
    if not state.get("departure_date"):
        missing.append("출발일을 알려주세요. (YYYY-MM-DD 또는 예: 3월 15일)")
    if state.get("trip_type") == "round" and not state.get("return_date"):
        missing.append("왕복 일정이므로 복귀일을 알려주세요. (YYYY-MM-DD)")
    return missing


def pick_next_question(missing_questions):
    if not missing_questions:
        return None
    return missing_questions[0]


def is_in_window(hour, window):
    if window == "morning":
        return 6 <= hour < 12
    if window == "afternoon":
        return 12 <= hour < 18
    if window == "evening":
        return 18 <= hour < 22
    if window == "night":
        return hour >= 22 or hour < 6
    return True


def apply_preference_filters(results, state):
    filtered = results

    if state.get("time_pref") == "after_now":
        now = datetime.now()
        temp = []
        for row in filtered:
            dep_dt = parse_iso_datetime(row.get("first_departure"))
            if dep_dt and dep_dt >= now:
                temp.append(row)
        if temp:
            filtered = temp

    dep_window = state.get("departure_window")
    if dep_window:
        temp = []
        for row in filtered:
            dep_dt = parse_iso_datetime(row.get("first_departure"))
            if dep_dt and is_in_window(dep_dt.hour, dep_window):
                temp.append(row)
        if temp:
            filtered = temp

    if state.get("direct_only") is True:
        temp = [row for row in filtered if row.get("stops", 0) == 0]
        if temp:
            filtered = temp

    return filtered


def select_diverse_recommendations(sorted_rows, limit):
    if not sorted_rows:
        return []

    selected = []
    used_airlines = set()

    for row in sorted_rows:
        airline = row.get("primary_airline")
        if airline not in used_airlines:
            selected.append(row)
            used_airlines.add(airline)
        if len(selected) >= limit:
            return selected

    for row in sorted_rows:
        if row not in selected:
            selected.append(row)
        if len(selected) >= limit:
            break
    return selected


def build_session_context(history, max_items=16):
    items = history[-max_items:]
    lines = []
    for item in items:
        role = item.get("role", "user")
        text = item.get("text", "")
        lines.append(f"{role}: {text}")
    return "\n".join(lines)


def answer_travel_knowledge(user_input, state, conversation_context):
    chunks = retrieve_knowledge_chunks(user_input)
    if not chunks:
        return (
            "<div>관련 여행 지식 문서를 찾지 못했습니다. "
            "원하시면 질문을 조금 더 구체적으로 말씀해 주세요. "
            "또는 날짜/예산/인원을 알려주시면 항공편 검색부터 도와드릴게요.</div>"
        )

    context_text = "\n\n".join(
        [f"[문서{i+1}] {c['text']}" for i, c in enumerate(chunks)]
    )
    source_text = ", ".join(sorted(set([c["source"] for c in chunks])))
    prompt = f"""
아래 검색 문맥에 근거해서만 사용자 질문에 답변해 주세요.
문맥에 없는 내용은 추측하지 말고, 모른다고 분명히 말해 주세요.
한국어 존댓말로 간결하게 답해 주세요.
마지막 한 줄에는 "원하시면 조건(날짜/예산/인원)을 알려주시면 항공편도 찾아드릴게요."를 포함해 주세요.
출력은 HTML <div> 하나로만 해 주세요.

사용자 질문:
{user_input}

최근 대화:
{conversation_context}

검색 문맥:
{context_text}

참고 출처:
{source_text}
"""

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "RAG 문맥 기반 여행 도우미"},
            {"role": "user", "content": prompt},
        ],
        temperature=0.2,
    )
    content = (response.choices[0].message.content or "").strip()
    if not content.startswith("<div"):
        content = f"<div>{content}</div>"
    return content


def answer_itinerary_plan(user_input, state, conversation_context):
    chunks = retrieve_knowledge_chunks(user_input)
    context_text = "\n\n".join([f"[문서{i+1}] {c['text']}" for i, c in enumerate(chunks)]) if chunks else "관련 문서 없음"
    destination = state.get("destination") or "요청 목적지"

    prompt = f"""
사용자 요청과 문맥을 보고 여행 일정을 제안해 주세요.
- 한국어 존댓말
- Day 1~Day 3 형식으로 간단한 일정
- 각 day마다 아침/점심/저녁 또는 오전/오후/저녁 활동 제시
- 마지막에 짧은 팁 2개
- HTML <div> 하나로만 출력

목적지: {destination}
사용자 요청: {user_input}
최근 대화: {conversation_context}
문맥:
{context_text}
"""

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "여행 일정 설계 도우미"},
            {"role": "user", "content": prompt},
        ],
        temperature=0.3,
    )
    content = (response.choices[0].message.content or "").strip()
    if not content.startswith("<div"):
        content = f"<div>{content}</div>"
    return content


@router.post("/chat")
def chat(req: ChatRequest):
    try:
        session_id = (req.session_id or "default").strip() or "default"
        history = SESSION_HISTORY.setdefault(session_id, [])
        history.append({"role": "user", "text": req.message})
        context = build_session_context(history)

        parsed = llm_parse_partial(req.message, context)
        prev_state = SESSION_STATE.get(session_id, {})

        # Follow-up query without date expression should keep previous travel date.
        if not has_explicit_date_signal(req.message):
            if prev_state.get("departure_date"):
                parsed["departure_date"] = None
            if prev_state.get("return_date"):
                parsed["return_date"] = None
        state = merge_with_session(prev_state, parsed)

        intent = detect_intent(req.message)

        if intent == "knowledge":
            SESSION_STATE[session_id] = state
            knowledge_html = answer_travel_knowledge(req.message, state, context)
            history.append({"role": "assistant", "text": "여행 지식 답변을 반환했습니다."})
            return {"response": knowledge_html}
        if intent == "itinerary":
            SESSION_STATE[session_id] = state
            itinerary_html = answer_itinerary_plan(req.message, state, context)
            history.append({"role": "assistant", "text": "여행 일정 답변을 반환했습니다."})
            return {"response": itinerary_html}

        missing_questions = build_missing_questions(state)
        if missing_questions:
            SESSION_STATE[session_id] = state
            question_text = pick_next_question(missing_questions)
            history.append({"role": "assistant", "text": f"추가 정보가 필요합니다: {question_text}"})
            raise NeedMoreInfoError(question_text)

        raw = search_flights(
            state["origin"],
            state["destination"],
            state["departure_date"],
            state.get("return_date"),
            state.get("adults", 1),
            state.get("max_price"),
            30,
        )
        simplified = simplify(raw)
        simplified = apply_preference_filters(simplified, state)

        if state.get("sort_by") == "price_asc":
            simplified.sort(key=lambda x: x.get("price_value", float("inf")))
        elif state.get("sort_by") == "price_desc":
            simplified.sort(key=lambda x: x.get("price_value", float("-inf")), reverse=True)
        elif state.get("sort_by") in ("fastest", "fastest_cheap"):
            simplified.sort(key=lambda x: (x.get("duration_min", 10**9), x.get("price_value", float("inf"))))

        limit = state.get("limit")
        if not isinstance(limit, int) or limit <= 0:
            limit = 8
        if isinstance(limit, int) and limit > 0:
            simplified = simplified[:limit]

        SESSION_STATE[session_id] = state
        convo_html = build_conversational_answer(req.message, state, simplified)
        html = convo_html + format_html(simplified, raw.get("meta_query", {}))
        history.append({"role": "assistant", "text": "항공편 검색 결과를 반환했습니다."})
        return {"response": html}
    except NeedMoreInfoError as e:
        return {"response": f"<p>좋아요, 이어서 찾을게요. {str(e)}</p>"}
    except Exception as e:
        session_id = (req.session_id or "default").strip() or "default"
        history = SESSION_HISTORY.setdefault(session_id, [])
        history.append({"role": "assistant", "text": f"요청 처리 실패: {str(e)}"})
        return {"response": f"<pre>요청 처리 실패: {str(e)}</pre>"}
