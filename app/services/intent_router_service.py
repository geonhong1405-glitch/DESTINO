import re
from typing import Any, Callable, Optional


def detect_intent(message: str, prev_state: dict[str, Any], *, contains_fn: Callable[[str, list[str]], bool]) -> str:
    m = (message or "").lower()
    msg = str(message or "")

    has_ko_flight = bool(re.search(r"(항공|항공편|비행기|왕복|편도|출발|도착|직항|경유)", msg))
    has_ko_hotel = bool(re.search(r"(호텔|숙소|체크인|체크아웃)", msg))
    has_ko_rental = bool(re.search(r"(렌터카|렌트카|차량)", msg))
    has_ko_itin = bool(re.search(r"(일정|코스|루트|플랜)", msg))
    has_ko_pref = bool(re.search(r"(최저가|저렴|가격|빠른|소요시간|가성비|추천)", msg))
    has_ko_product = bool(re.search(r"(패키지|공동구매|티켓|입장권|관람권|액티비티|체험|투어)", msg))

    if has_ko_flight and not has_ko_hotel:
        return "flight"
    if has_ko_hotel and not has_ko_flight:
        return "hotel"
    if has_ko_rental and not has_ko_flight and not has_ko_hotel:
        return "rentalcar"
    if has_ko_itin and not has_ko_flight and not has_ko_hotel:
        return "itinerary"
    if has_ko_product and not has_ko_flight and not has_ko_hotel and not has_ko_rental:
        return "product"

    if has_ko_pref and not has_ko_hotel and not has_ko_flight:
        last = str(prev_state.get("last_intent") or "")
        if last in {"flight", "hotel", "rentalcar", "itinerary", "product"}:
            return last

    flight_terms = ["flight", "airfare", "round trip", "roundtrip", "one way", "oneway", "항공", "항공권", "비행기", "출발", "도착", "직항", "경유", "편도", "왕복"]
    hotel_terms = ["hotel", "호텔", "숙소", "체크인", "체크아웃"]
    rental_terms = ["rental car", "rent car", "car rental", "렌터카", "렌트카", "차량", "대여", "반납"]
    itinerary_terms = ["itinerary", "plan", "route", "일정", "코스", "루트", "플랜", "동선"]
    pref_terms = ["cheap", "cheapest", "price", "fast", "fastest", "earliest", "sort", "최저가", "저렴", "가격", "빠른", "소요시간", "가성비", "추천", "top"]
    package_terms = ["package", "패키지", "여행 상품", "여행상품"]
    groupbuy_terms = ["groupbuy", "group buy", "공동구매", "모집", "같이"]
    ticket_terms = ["ticket", "activity", "tour", "티켓", "입장권", "관람권", "액티비티", "체험", "투어"]

    score = {"flight": 0, "hotel": 0, "rentalcar": 0, "itinerary": 0, "product": 0}
    if contains_fn(m, flight_terms):
        score["flight"] += 3
    if contains_fn(m, hotel_terms):
        score["hotel"] += 3
    if contains_fn(m, rental_terms):
        score["rentalcar"] += 3
    if contains_fn(m, itinerary_terms):
        score["itinerary"] += 3
    if contains_fn(m, package_terms) or contains_fn(m, groupbuy_terms) or contains_fn(m, ticket_terms):
        score["product"] += 3

    if contains_fn(m, pref_terms):
        last_intent = str(prev_state.get("last_intent") or "")
        if last_intent in score:
            score[last_intent] += 2

    if prev_state.get("hotel_context") and not contains_fn(m, flight_terms):
        score["hotel"] += 1

    best = max(score, key=score.get)
    if score[best] >= 3:
        return best

    if contains_fn(m, ["여행지", "추천지", "가볼만", "관광지", "볼거리", "명소"]):
        if not contains_fn(m, ["항공", "항공권", "비행기", "출발", "도착"]):
            return "knowledge"
    if prev_state.get("last_intent") == "knowledge":
        if not contains_fn(m, ["항공", "항공권", "비행기", "출발", "도착", "호텔", "숙소"]):
            if contains_fn(m, ["먹을거", "음식", "맛집", "추천", "어때", "말고", "그럼"]):
                return "knowledge"
    if contains_fn(m, ["교통", "지하철", "택시", "버스", "기차", "트램"]):
        if not contains_fn(m, ["항공", "항공권", "비행기", "출발", "도착"]):
            return "knowledge"
    if contains_fn(m, ["치안", "안전", "위험", "주의사항", "긴급", "응급", "소매치기", "위도", "강도", "사기", "범죄", "110", "119", "pickpocket", "scam", "crime"]):
        if not contains_fn(m, ["항공", "항공권", "비행기", "출발", "도착"]):
            return "knowledge"
    if contains_fn(m, ["카드", "현금", "결제", "환율", "환전", "수수료", "visa", "mastercard"]):
        if not contains_fn(m, ["항공", "항공권", "비행기", "출발", "도착"]):
            return "knowledge"
    if any(k in msg for k in ["특징", "설명", "정보", "소개", "뭐야", "어때", "팁"]):
        if not any(k in msg for k in ["항공", "비행", "항공권", "출발", "도착", "호텔", "숙소"]):
            return "knowledge"
    if contains_fn(m, ["렌터카", "렌트카", "렌트", "대여", "rental car", "rent car", "car rental"]):
        return "rentalcar"
    if contains_fn(m, ["호텔", "숙소", "숙박", "체크인", "체크아웃"]):
        return "hotel"
    if contains_fn(m, ["일정", "코스", "루트", "플랜", "day 1", "1일차"]):
        return "itinerary"
    if contains_fn(m, ["어디", "문화", "비자", "시차", "환율", "환전", "결제", "카드", "현금", "여행팁", "명소", "맛집", "특징", "설명", "정보", "치안", "안전", "주의사항", "긴급", "소매치기", "위도", "강도", "범죄", "즐길거리", "볼거리", "추천"]) and not contains_fn(m, ["항공", "항공권", "비행기", "출발", "도착"]):
        return "knowledge"
    if prev_state.get("hotel_context") and contains_fn(m, ["후기", "위치", "가성비", "top", "순위", "추천", "다시"]):
        return "hotel"
    if prev_state.get("last_intent") == "hotel" and not contains_fn(m, ["항공", "비행기", "출발", "도착"]):
        return "hotel"
    if prev_state.get("last_intent") == "flight" and contains_fn(m, ["왕복", "편도", "귀국", "복귀", "직항", "경유", "round trip", "one way"]):
        return "flight"

    has_any_travel_signal = contains_fn(
        m,
        [
            "항공", "항공권", "비행기", "flight", "출발", "도착", "직항", "경유", "왕복", "편도",
            "호텔", "숙소", "숙박", "hotel", "체크인", "체크아웃",
            "렌터카", "렌트카", "rental", "car",
            "일정", "itinerary", "plan", "루트", "코스",
            "여행", "trip", "travel",
        ],
    )
    waiting_flight_followup = (
        (prev_state.get("last_intent") == "flight" or str(prev_state.get("pending_intent") or "") == "flight")
        and (
            not prev_state.get("origin")
            or not prev_state.get("destination")
            or not prev_state.get("departure_date")
        )
    )
    if waiting_flight_followup:
        return "flight"
    if not has_any_travel_signal:
        return "knowledge"
    return "flight"


def resolve_intent_with_llm(
    message: str,
    context: str,
    prev_state: Optional[dict[str, Any]] = None,
    *,
    llm_json_fn: Callable[[str, str], dict[str, Any]],
    contains_fn: Callable[[str, list[str]], bool],
) -> Optional[str]:
    prev_state = prev_state or {}
    prev_intent = str(prev_state.get("last_intent") or "")
    prompt = (
        "너는 여행 챗봇 라우터다. 아래 JSON만 출력해라.\n"
        "{"
        '"intent":"flight|hotel|rentalcar|itinerary|product|knowledge|mixed|unknown",'
        '"parts":["flight","hotel","rentalcar","itinerary","product","knowledge"],'
        '"confidence":0.0'
        "}\n"
        "규칙:\n"
        "- 항공권/비행기/출발-도착/직항-경유 => flight\n"
        "- 숙소/호텔/체크인-체크아웃 => hotel\n"
        "- 렌터카/렌트카/차량 대여/반납 => rentalcar\n"
        "- 일정/코스/동선/몇박며칠/플랜 => itinerary\n"
        "- 문화/치안/비자/교통/환율/환전/결제/맛집/명소/볼거리 => knowledge\n"
        "- 둘 이상이면 intent=mixed, parts에 포함\n"
        "- 후속질문(그럼/말고/그거/어디 등)은 최근 문맥 고려\n\n"
        f"이전 intent: {prev_intent}\n최근 대화:\n{context}\n\n사용자 질문:\n{message}"
    )
    parsed = llm_json_fn("여행 챗봇 의도 라우팅 JSON만 출력", prompt)
    if not isinstance(parsed, dict):
        return None
    raw_intent = str(parsed.get("intent") or "").strip().lower()
    parts = parsed.get("parts") if isinstance(parsed.get("parts"), list) else []
    try:
        confidence = float(parsed.get("confidence", 0))
    except Exception:
        confidence = 0.0

    m = (message or "").lower()
    has_itinerary_signal = contains_fn(
        m,
        ["일정", "코스", "루트", "동선", "플랜", "몇박", "며칠", "투어", "itinerary", "plan", "route", "day 1"],
    ) or bool(re.search(r"\d+\s*박\s*\d+\s*일", m))
    has_flight_signal = contains_fn(m, ["항공", "항공권", "비행기", "출발", "도착", "직항", "경유"])
    has_hotel_signal = contains_fn(m, ["호텔", "숙소", "체크인", "체크아웃"])

    allowed = {"flight", "hotel", "rentalcar", "itinerary", "product", "knowledge"}
    if raw_intent in allowed:
        if raw_intent == "itinerary" and not has_itinerary_signal and not has_flight_signal and not has_hotel_signal:
            return None
        if confidence >= 0.45:
            return raw_intent
        return None

    if raw_intent == "mixed":
        norm_parts = [str(x).strip().lower() for x in parts if str(x).strip().lower() in allowed]
        if "itinerary" in norm_parts and not has_itinerary_signal and not has_flight_signal and not has_hotel_signal:
            norm_parts = [x for x in norm_parts if x != "itinerary"]
        for cand in ["flight", "hotel", "rentalcar", "itinerary", "product", "knowledge"]:
            if cand in norm_parts:
                if confidence >= 0.4:
                    return cand
                break
        return None
    return None


def classify_travel_domain_with_llm(message: str, context: str = "", *, llm_json_fn: Callable[[str, str], dict[str, Any]]) -> Optional[dict[str, Any]]:
    prompt = (
        "너는 여행 챗봇 도메인 분류기다. 아래 JSON만 출력해라.\n"
        "{"
        '"is_travel":true,'
        '"confidence":0.0,'
        '"reason":"short"'
        "}\n"
        "기준:\n"
        "- 여행/항공/숙소/여행지 정보/교통/치안/비자/환율/맛집/명소/일정 => is_travel=true\n"
        "- 스포츠, 주식, 코딩, 일반 상식 잡담, 연예 뉴스 등 여행과 무관 => is_travel=false\n"
        "- 애매하면 confidence 낮게\n\n"
        f"최근 대화(참고):\n{context}\n\n사용자 질문:\n{message}"
    )
    parsed = llm_json_fn("여행 도메인 분류 JSON만 출력", prompt)
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


def should_ask_intent_clarification(message: str, *, contains_fn: Callable[[str, list[str]], bool]) -> bool:
    m = (message or "").strip().lower()
    if not m:
        return False
    if contains_fn(
        m,
        [
            "항공", "항공권", "비행기", "출발", "도착",
            "호텔", "숙소", "체크인", "체크아웃",
            "렌터카", "렌트카", "렌트", "대여",
            "일정", "코스", "루트", "플랜",
            "패키지", "공동구매", "티켓", "입장권", "package", "groupbuy", "group buy", "ticket",
        ],
    ):
        return False
    return contains_fn(
        m,
        ["여행 가고싶다", "가고싶다", "떠나고싶다", "여행", "맛집", "명소", "볼거리", "즐길거리", "추천해줘", "어디 좋아", "뭐가 좋아"],
    )


def is_route_guidance_query(message: str, *, contains_fn: Callable[[str, list[str]], bool]) -> bool:
    m = (message or "").lower()
    route_phrases = ["가는 방법", "가는법", "어떻게 가", "이동 방법", "이동방법", "교통편", "how to get", "how do i get"]
    flight_phrases = ["항공", "항공편", "항공권", "비행기", "직항", "편도", "flight", "airfare"]
    has_route_phrase = contains_fn(m, route_phrases)
    has_place_connector = ("에서" in m and ("가" in m or "까지" in m)) or (" from " in m and " to " in m)
    return has_route_phrase and has_place_connector and not contains_fn(m, flight_phrases)


def should_keep_knowledge_followup(
    message: str,
    prev_state: Optional[dict[str, Any]] = None,
    *,
    contains_fn: Callable[[str, list[str]], bool],
) -> bool:
    prev_state = prev_state or {}
    if prev_state.get("last_intent") != "knowledge":
        return False
    prev_k = prev_state.get("knowledge_state") or {}
    if not isinstance(prev_k, dict):
        prev_k = {}
    if not any(prev_k.get(k) for k in ["country_code", "city_name", "location_query", "topic", "subtopic"]):
        return False
    m = (message or "").strip().lower()
    if not m:
        return False
    if contains_fn(
        m,
        [
            "항공", "항공권", "비행기", "출발", "도착", "직항", "경유",
            "호텔", "숙소", "체크인", "체크아웃",
            "일정", "코스", "루트", "플랜",
        ],
    ):
        return False
    short_followup = len(m) <= 40
    followup_tone = contains_fn(
        m,
        [
            "그럼", "그거", "그렇게", "어떻게", "얼마야", "몇 분", "몇시간",
            "이동", "버스", "지하철", "택시", "기차", "트램",
            "입장료", "가격", "예약", "예매", "관리비",
            "bus", "train", "metro", "subway", "taxi", "walk", "ticket", "price",
        ],
    )
    return short_followup and followup_tone
