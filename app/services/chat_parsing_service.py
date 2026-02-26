import re
from datetime import datetime, timedelta
from typing import Any, Callable, Optional


def parse_flight_slots(
    message: str,
    context: str,
    *,
    llm_json_fn: Callable[[str, str], dict[str, Any]],
    contains_fn: Callable[[str, list[str]], bool],
    is_date_correction_message_fn: Callable[[str], bool],
    has_location_signal_fn: Callable[[str], bool],
    parse_rel_date_fn: Callable[[str], Any],
    extract_date_expr_with_llm_fn: Callable[[str, str], dict[str, Any]],
    resolve_date_expr_fn: Callable[[Any], Optional[str]],
    parse_rel_date_for_correction_fn: Callable[[str], Any],
    parse_abs_monthday_range_fn: Callable[[str], dict[str, Optional[str]]],
) -> dict[str, Any]:
    today = datetime.now().strftime("%Y-%m-%d")
    prompt = (
        f"오늘 날짜는 {today}. 아래 JSON만 출력:\n"
        '{"origin":null,"destination":null,"departure_date":null,"return_date":null,"adults":1,"sort_by":null,"trip_type":null,"limit":null}\n'
        "규칙: 저렴=price_asc, 빠른=fastest, 빠르고 저렴=fastest_cheap, "
        "출발시간 가장 빠른/가장 이른 출발=earliest_departure, 왕복이면 trip_type=round.\n"
        f"입력:{message}\n대화:{context}"
    )
    parsed = llm_json_fn("항공권 검색 JSON만 출력", prompt)
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

    if is_date_correction_message_fn(message) and not has_location_signal_fn(message):
        parsed["origin"] = None
        parsed["destination"] = None

    msg_l = (message or "").lower()
    has_round_signal = contains_fn(message, ["왕복", "갔다가", "돌아오는", "복귀"]) or "round trip" in msg_l or "roundtrip" in msg_l
    has_oneway_signal = contains_fn(message, ["편도"]) or "oneway" in msg_l or "one-way" in msg_l
    parsed["trip_type"] = "round" if has_round_signal else ("oneway" if has_oneway_signal else None)

    d_inline = parse_rel_date_fn(message)
    if d_inline:
        parsed["departure_date"] = d_inline.strftime("%Y-%m-%d")

    date_context = "" if is_date_correction_message_fn(message) else context
    date_info = extract_date_expr_with_llm_fn(message, date_context)
    if not parsed.get("departure_date"):
        parsed["departure_date"] = resolve_date_expr_fn(date_info.get("departure"))
    if not parsed.get("return_date"):
        parsed["return_date"] = resolve_date_expr_fn(date_info.get("return"))
    if not parsed.get("return_date") and parsed.get("departure_date"):
        stay_nights = date_info.get("stay_nights")
        try:
            if stay_nights is not None and int(stay_nights) > 0:
                dep_dt = datetime.strptime(parsed["departure_date"], "%Y-%m-%d")
                parsed["return_date"] = (dep_dt + timedelta(days=int(stay_nights))).strftime("%Y-%m-%d")
                parsed["trip_type"] = parsed.get("trip_type") or "round"
        except Exception:
            pass

    if is_date_correction_message_fn(message):
        d_now = parse_rel_date_for_correction_fn(message)
        if d_now:
            parsed["departure_date"] = d_now.strftime("%Y-%m-%d")
            parsed["return_date"] = None
    if not parsed.get("departure_date"):
        d = parse_rel_date_fn(message)
        if d:
            parsed["departure_date"] = d.strftime("%Y-%m-%d")

    abs_md = parse_abs_monthday_range_fn(message)
    if not parsed.get("departure_date") and abs_md.get("departure_date"):
        parsed["departure_date"] = abs_md["departure_date"]
    if not parsed.get("return_date") and abs_md.get("return_date"):
        parsed["return_date"] = abs_md["return_date"]
    if parsed.get("return_date"):
        parsed["trip_type"] = parsed.get("trip_type") or "round"

    if "인도" in (message or "") or "india" in msg_l:
        if (parsed.get("destination") or "").upper() in {"", "IND", "IN"}:
            parsed["destination"] = "DEL"

    if contains_fn(message, ["저렴", "싼", "가성비"]):
        parsed["sort_by"] = "price_asc"
    if contains_fn(message, ["출발시간이 가장 빠른", "가장 이른 출발", "출발시간 순", "제일 빨리 출발"]):
        parsed["sort_by"] = "earliest_departure"
    if contains_fn(message, ["가장 빨리", "최단", "빠르게"]):
        parsed["sort_by"] = "fastest_cheap" if parsed.get("sort_by") == "price_asc" else "fastest"
    return parsed


def parse_hotel_slots(
    message: str,
    context: str,
    *,
    llm_json_fn: Callable[[str, str], dict[str, Any]],
    is_date_correction_message_fn: Callable[[str], bool],
    extract_date_expr_with_llm_fn: Callable[[str, str], dict[str, Any]],
    resolve_date_expr_fn: Callable[[Any], Optional[str]],
    parse_rel_date_fn: Callable[[str], Any],
    location_alias_keys: list[str],
) -> dict[str, Any]:
    today = datetime.now().strftime("%Y-%m-%d")
    prompt = (
        f"오늘 날짜는 {today}. JSON만 출력:\n"
        '{"query":null,"checkin_date":null,"checkout_date":null,"adults":2,"top_k":5,"bucket":"value_top"}\n'
        "후기=review_top, 위치=location_top, 가성비=value_top.\n"
        f"입력:{message}\n대화:{context}"
    )
    parsed = llm_json_fn("호텔 추천 JSON만 출력", prompt)
    parsed.setdefault("query", None)
    parsed.setdefault("checkin_date", None)
    parsed.setdefault("checkout_date", None)
    parsed.setdefault("adults", 2)
    parsed.setdefault("top_k", 5)
    parsed.setdefault("bucket", "value_top")

    if not parsed.get("query"):
        msg = (message or "").strip()
        m_city = re.search(r"(.{1,30}?)(?:\s*(?:호텔|숙소|숙박))", msg)
        if m_city:
            candidate = m_city.group(1).strip(" ,.?")
            if candidate and len(candidate) >= 2:
                parsed["query"] = candidate
        if not parsed.get("query"):
            for city_kw in sorted(location_alias_keys, key=len, reverse=True):
                if city_kw and city_kw in msg:
                    parsed["query"] = city_kw
                    break

    date_context = "" if is_date_correction_message_fn(message) else context
    date_info = extract_date_expr_with_llm_fn(message, date_context)
    if not parsed.get("checkin_date"):
        parsed["checkin_date"] = resolve_date_expr_fn(date_info.get("departure"))
    if not parsed.get("checkout_date"):
        parsed["checkout_date"] = resolve_date_expr_fn(date_info.get("return"))
    if not parsed.get("checkout_date") and parsed.get("checkin_date"):
        try:
            if date_info.get("stay_nights") is not None and int(date_info["stay_nights"]) > 0:
                chk = datetime.strptime(parsed["checkin_date"], "%Y-%m-%d")
                parsed["checkout_date"] = (chk + timedelta(days=int(date_info["stay_nights"]))).strftime("%Y-%m-%d")
        except Exception:
            pass
    if not parsed.get("checkin_date"):
        d = parse_rel_date_fn(message)
        if d:
            parsed["checkin_date"] = d.strftime("%Y-%m-%d")

    if "후기" in (message or ""):
        parsed["bucket"] = "review_top"
    elif any(k in (message or "") for k in ["위치", "근처", "주변"]):
        parsed["bucket"] = "location_top"
    elif "가성비" in (message or ""):
        parsed["bucket"] = "value_top"

    m2 = re.search(r"top\s*(\d+)", (message or "").lower()) or re.search(r"(\d+)\s*개", message or "")
    if m2:
        try:
            parsed["top_k"] = int(m2.group(1))
        except Exception:
            pass
    return parsed
