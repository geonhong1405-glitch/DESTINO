from typing import Any

from app.api.booking_hotel_flight_api import (
    recommend_buckets as booking_recommend_buckets,
    search_destination as booking_search_destination,
    search_hotels_by_dest_id,
)


def _is_rate_limited(exc: Exception) -> bool:
    text = str(exc or "")
    return "429" in text or "Too Many Requests" in text


def _fmt_price(value: Any, currency: str) -> str:
    try:
        if value is None:
            return f"- {currency or '-'}"
        v = float(value)
        if (currency or "").upper() == "KRW":
            return f"{int(round(v)):,} KRW"
        return f"{v:,.2f} {currency or '-'}"
    except Exception:
        return f"{value} {currency or '-'}"


def _rate_limit_response(query: str, checkin: str, checkout: str, adults: int, destination_phase: bool):
    if destination_phase:
        html = (
            "<p>호텔 목적지 조회 요청이 잠시 많아져서(429) 응답이 지연되고 있어요.</p>"
            "<p>10~30초 후 다시 시도해 주세요.</p>"
        )
    else:
        html = (
            "<p>호텔 검색 요청이 잠시 많아져서(429) 결과를 가져오지 못했어요.</p>"
            "<p>10~30초 후 다시 시도해 주세요.</p>"
        )
    return html, {
        "hotel_context": True,
        "hotel_query": query,
        "hotel_checkin": checkin,
        "hotel_checkout": checkout,
        "hotel_adults": adults,
    }


def answer_hotel_from_parsed(parsed: dict[str, Any], prev_state: dict[str, Any]):
    query = (parsed.get("query") or prev_state.get("hotel_query") or "").strip()
    checkin = parsed.get("checkin_date") or prev_state.get("hotel_checkin")
    checkout = parsed.get("checkout_date") or prev_state.get("hotel_checkout")
    adults = int(parsed.get("adults") or prev_state.get("hotel_adults") or 2)
    top_k = max(1, min(int(parsed.get("top_k") or 5), 20))
    bucket = parsed.get("bucket") or "value_top"

    if not query:
        return "<p>호텔을 찾을 도시를 알려주세요. (예: 오사카, 도쿄)</p>", {"hotel_context": True, "hotel_adults": adults}
    if not checkin or not checkout:
        return "<p>체크인 / 체크아웃 날짜를 알려주세요. (YYYY-MM-DD)</p>", {
            "hotel_context": True,
            "hotel_query": query,
            "hotel_checkin": checkin,
            "hotel_checkout": checkout,
            "hotel_adults": adults,
        }

    try:
        dest = booking_search_destination(query=query)
    except Exception as e:
        if _is_rate_limited(e):
            return _rate_limit_response(query, checkin, checkout, adults, destination_phase=True)
        return f"<pre>호텔 목적지 검색 실패: {e}</pre>", {"hotel_context": True}

    cands = dest.get("data", []) if isinstance(dest, dict) else []
    if not cands:
        return "<p>목적지를 찾지 못했습니다. 도시명을 조금 더 구체적으로 입력해 주세요.</p>", {"hotel_context": True}

    first = cands[0] if isinstance(cands[0], dict) else {}
    try:
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
    except Exception as e:
        if _is_rate_limited(e):
            return _rate_limit_response(query, checkin, checkout, adults, destination_phase=False)
        return f"<pre>호텔 검색 실패: {e}</pre>", {"hotel_context": True}

    if not raw.get("status"):
        return f"<pre>호텔 검색 실패: {raw.get('message', 'Booking API error')}</pre>", {"hotel_context": True}

    center = (
        float(first.get("latitude") or first.get("lat") or 34.703968),
        float(first.get("longitude") or first.get("lon") or 135.49292),
    )
    rows = booking_recommend_buckets(raw, center=center, top_k=top_k).get(bucket) or []
    if not rows:
        return "<p>조건에 맞는 호텔 결과가 없습니다.</p>", {"hotel_context": True}

    bucket_title = {
        "value_top": "가성비 TOP",
        "review_top": "후기 TOP",
        "location_top": "위치 TOP",
    }.get(bucket, "추천 TOP")

    lines: list[str] = []
    for i, h in enumerate(rows, 1):
        price_obj = h.get("price") or {}
        parts = [
            f"{i}) {h.get('name') or '-'}",
            f"가격: {_fmt_price(price_obj.get('value'), str(price_obj.get('currency') or ''))}",
        ]
        score = (h.get("review") or {}).get("score")
        if score is not None:
            parts.append(f"평점: {score}")
        photo_url = h.get("photo_url")
        if photo_url:
            parts.append(f"사진: {photo_url}")
        stars = h.get("stars")
        if stars:
            parts.append(f"성급: {stars}")
        lines.append(" | ".join(parts))

    # planner.js parseListCards() converts numbered "호텔" lines into card section.
    html = f"<div><b>{query} 호텔 추천 ({bucket_title}) {len(rows)}개</b><br>{'<br>'.join(lines)}</div>"
    return html, {
        "hotel_context": True,
        "hotel_query": query,
        "hotel_checkin": checkin,
        "hotel_checkout": checkout,
        "hotel_adults": adults,
    }
