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
    def _coerce_nonneg_int(v: Any, default: int) -> int:
        try:
            n = int(v)
        except Exception:
            return default
        return n if n >= 0 else default

    today = datetime.now().strftime("%Y-%m-%d")
    prompt = (
        f"오늘 날짜는 {today}. 아래 JSON만 출력:\n"
        '{"origin":null,"destination":null,"departure_date":null,"return_date":null,"adults":1,"children":0,"infants":0,"sort_by":null,"trip_type":null,"limit":null}\n'
        "규칙: 저렴=price_asc, 빠른=fastest, 빠르고 저렴=fastest_cheap, "
        "출발시간 가장 빠른/가장 이른 출발=earliest_departure, 왕복이면 trip_type=round.\n"
        f"입력:{message}\n대화:{context}"
    )
    parsed = llm_json_fn("항공권 검색 JSON만 출력", prompt)
    if not isinstance(parsed, dict):
        parsed = {}
    parsed.setdefault("origin", None)
    parsed.setdefault("destination", None)
    parsed.setdefault("departure_date", None)
    parsed.setdefault("return_date", None)

    def _none_like(v: Any):
        if v is None:
            return None
        if isinstance(v, str) and v.strip().lower() in {"", "null", "none", "unknown", "n/a", "-"}:
            return None
        return v

    for key in ["origin", "destination", "departure_date", "return_date", "sort_by", "trip_type", "limit"]:
        parsed[key] = _none_like(parsed.get(key))

    # Deterministic absolute date-range extraction (e.g., 3/1~3/4, 3/1?? 3/4??).
    abs_md_early = parse_abs_monthday_range_fn(message)
    if abs_md_early.get("departure_date"):
        parsed["departure_date"] = abs_md_early["departure_date"]
    if abs_md_early.get("return_date"):
        parsed["return_date"] = abs_md_early["return_date"]
        parsed["trip_type"] = parsed.get("trip_type") or "round"
    parsed.setdefault("adults", 1)
    parsed.setdefault("children", 0)
    parsed.setdefault("infants", 0)
    parsed.setdefault("sort_by", None)
    parsed.setdefault("trip_type", None)
    parsed.setdefault("limit", None)
    parsed.setdefault("max_price", None)
    parsed.setdefault("time_pref", None)
    parsed.setdefault("departure_window", None)
    parsed.setdefault("direct_only", None)
    # Backward-compatible keys that LLM may still emit.
    if parsed.get("children") is None and parsed.get("child") is not None:
        parsed["children"] = parsed.get("child")
    if parsed.get("infants") is None and parsed.get("infant") is not None:
        parsed["infants"] = parsed.get("infant")
    parsed["adults"] = _coerce_nonneg_int(parsed.get("adults"), 1) or 1
    parsed["children"] = _coerce_nonneg_int(parsed.get("children"), 0)
    parsed["infants"] = _coerce_nonneg_int(parsed.get("infants"), 0)

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

    # Passenger-count heuristic fallback when LLM misses explicit counts.
    msg = message or ""
    m_adult = re.search(r"(?:성인|어른)\s*(\d+)\s*(?:명)?", msg)
    m_child = re.search(r"(?:소아|아동|아이|어린이)\s*(\d+)\s*(?:명)?", msg)
    m_infant = re.search(r"(?:유아)\s*(\d+)\s*(?:명)?", msg)
    if m_adult:
        parsed["adults"] = max(1, _coerce_nonneg_int(m_adult.group(1), parsed.get("adults", 1)))
    if m_child:
        parsed["children"] = _coerce_nonneg_int(m_child.group(1), parsed.get("children", 0))
    if m_infant:
        parsed["infants"] = _coerce_nonneg_int(m_infant.group(1), parsed.get("infants", 0))

    if contains_fn(message, ["저렴", "싼", "가성비"]):
        parsed["sort_by"] = "price_asc"
    if contains_fn(message, ["출발시간이 가장 빠른", "가장 이른 출발", "출발시간 순", "제일 빨리 출발"]):
        parsed["sort_by"] = "earliest_departure"
    if contains_fn(message, ["가장 빨리", "최단", "빠르게"]):
        parsed["sort_by"] = "fastest_cheap" if parsed.get("sort_by") == "price_asc" else "fastest"
    return parsed


def _extract_relative_range_dates(message: str) -> tuple[Optional[str], Optional[str]]:
    t = str(message or "").lower()
    compact = re.sub(r"\s+", "", t)
    if not compact:
        return None, None
    has_range_connector = any(k in compact for k in ["\uc5d0\uc11c", "\ubd80\ud130", "~", "-", "to", "\uae4c\uc9c0"])
    if not has_range_connector:
        return None, None

    token_offsets = {
        "\uc624\ub298": 0,
        "\ub0b4\uc77c": 1,
        "\ub0b4\uc77c\ubaa8\ub808": 2,
        "\ub0b4\uc77c\ubaa8\ub798": 2,
        "\ubaa8\ub808": 2,
        "\uae00\ud53c": 3,
    }
    token_pat = re.compile(
        r"\ub0b4\uc77c\ubaa8\ub808|\ub0b4\uc77c\ubaa8\ub798|\uae00\ud53c|\ubaa8\ub808|\ub0b4\uc77c|\uc624\ub298"
    )
    found = [(m.start(), m.group(0)) for m in token_pat.finditer(compact)]
    if len(found) < 2:
        return None, None

    first = found[0][1]
    second = found[1][1]
    d1 = token_offsets.get(first)
    d2 = token_offsets.get(second)
    if d1 is None or d2 is None:
        return None, None

    now = datetime.now().date()
    checkin = now + timedelta(days=d1)
    checkout = now + timedelta(days=d2)
    if checkout <= checkin:
        checkout = checkin + timedelta(days=1)
    return checkin.strftime("%Y-%m-%d"), checkout.strftime("%Y-%m-%d")


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
    if not isinstance(parsed, dict):
        parsed = {}
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

    rel_start, rel_end = _extract_relative_range_dates(message)
    if rel_start and rel_end:
        # Deterministic override for "내일에서 내일모레" style inputs.
        parsed["checkin_date"] = rel_start
        parsed["checkout_date"] = rel_end

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
