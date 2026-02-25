import re
from typing import Any, Dict, Literal

Intent = Literal[
    "FLIGHT_ONLY",
    "HOTEL_ONLY",
    "ITINERARY_ONLY",
    "INFO_ONLY",
    "MIXED_FLIGHT_ITIN",
    "MIXED_ITIN_HOTEL",
    "MIXED_ALL",
    "UNKNOWN",
]


FLIGHT_KW = [
    "항공",
    "항공권",
    "비행기",
    "비행",
    "편도",
    "왕복",
    "스케줄",
    "출발",
    "도착",
    "경유",
    "직항",
    "최저가",
    "가격",
    "fare",
    "flight",
    "airline",
    "departure",
    "arrival",
]

HOTEL_KW = [
    "숙소",
    "호텔",
    "리조트",
    "게스트하우스",
    "에어비앤비",
    "체크인",
    "체크아웃",
    "room",
    "hotel",
    "stay",
    "accommodation",
]

ITIN_KW = [
    "일정",
    "루트",
    "코스",
    "동선",
    "플랜",
    "여행계획",
    "투어",
    "명소",
    "맛집",
    "관광",
    "추천",
    "itinerary",
    "plan",
    "route",
    "things to do",
]

INFO_KW = [
    "치안",
    "안전",
    "주의",
    "사기",
    "비자",
    "입국",
    "환승",
    "금기",
    "문화",
    "예절",
    "교통",
    "지하철",
    "버스",
    "택시",
    "팁",
    "환전",
    "환율",
    "전압",
    "플러그",
    "긴급",
    "응급",
    "카드",
    "현금",
    "결제",
    "laws",
    "safety",
    "visa",
    "custom",
    "etiquette",
    "scam",
    "transport",
    "tipping",
    "currency",
]


def _has_any(q: str, keywords: list[str]) -> bool:
    ql = (q or "").lower()
    return any(k.lower() in ql for k in keywords)


def classify_intent(query: str) -> Dict[str, Any]:
    q = (query or "").strip()

    has_flight = _has_any(q, FLIGHT_KW)
    has_hotel = _has_any(q, HOTEL_KW)
    has_itin = _has_any(q, ITIN_KW)
    has_info = _has_any(q, INFO_KW)

    has_date = bool(re.search(r"\b(20\d{2})[./-]?\d{1,2}[./-]?\d{1,2}\b", q)) or ("월" in q and "일" in q)

    if has_flight and not (has_hotel or has_itin or has_info):
        intent: Intent = "FLIGHT_ONLY"
    elif has_hotel and not (has_flight or has_itin or has_info):
        intent = "HOTEL_ONLY"
    elif has_itin and not (has_flight or has_hotel) and not has_info:
        intent = "ITINERARY_ONLY"
    elif has_info and not (has_flight or has_hotel or has_itin):
        intent = "INFO_ONLY"
    elif has_flight and has_itin and not has_hotel:
        intent = "MIXED_FLIGHT_ITIN"
    elif has_itin and has_hotel and not has_flight:
        intent = "MIXED_ITIN_HOTEL"
    elif has_flight and has_itin and has_hotel:
        intent = "MIXED_ALL"
    else:
        if has_date and (has_itin or has_flight):
            intent = "ITINERARY_ONLY" if has_itin else "FLIGHT_ONLY"
        elif has_info:
            intent = "INFO_ONLY"
        else:
            intent = "UNKNOWN"

    flags = {
        "use_flight_api": intent in ["FLIGHT_ONLY", "MIXED_FLIGHT_ITIN", "MIXED_ALL"],
        "use_hotel_api": intent in ["HOTEL_ONLY", "MIXED_ITIN_HOTEL", "MIXED_ALL"],
        "use_itinerary": intent in ["ITINERARY_ONLY", "MIXED_FLIGHT_ITIN", "MIXED_ITIN_HOTEL", "MIXED_ALL"],
        "use_rag_info": intent in ["INFO_ONLY", "MIXED_FLIGHT_ITIN", "MIXED_ITIN_HOTEL", "MIXED_ALL"],
    }
    return {"intent": intent, "flags": flags}
