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
        "정렬: 가격=price_asc, 빠른=fastest, 빠르고 저렴=fastest_cheap, 가장 이른 출발=earliest_departure.\n"
        f"입력:{message}\n문맥:{context}"
    )
    parsed = llm_json_fn("항공 검색 JSON만 출력", prompt)
    if not isinstance(parsed, dict):
        parsed = {}

    for k, v in {
        "origin": None,
        "destination": None,
        "departure_date": None,
        "return_date": None,
        "adults": 1,
        "children": 0,
        "infants": 0,
        "sort_by": None,
        "trip_type": None,
        "limit": None,
        "max_price": None,
        "time_pref": None,
        "departure_window": None,
        "direct_only": None,
    }.items():
        parsed.setdefault(k, v)

    def _none_like(v: Any):
        if v is None:
            return None
        if isinstance(v, str) and v.strip().lower() in {"", "null", "none", "unknown", "n/a", "-"}:
            return None
        return v

    for key in ["origin", "destination", "departure_date", "return_date", "sort_by", "trip_type", "limit"]:
        parsed[key] = _none_like(parsed.get(key))

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
    parsed["trip_type"] = "round" if has_round_signal else ("oneway" if has_oneway_signal else parsed.get("trip_type"))

    # deterministic absolute month/day range first
    abs_md_early = parse_abs_monthday_range_fn(message)
    if abs_md_early.get("departure_date"):
        parsed["departure_date"] = abs_md_early["departure_date"]
    if abs_md_early.get("return_date"):
        parsed["return_date"] = abs_md_early["return_date"]
        parsed["trip_type"] = parsed.get("trip_type") or "round"

    d_inline = parse_rel_date_fn(message)
    if d_inline and not parsed.get("departure_date"):
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

    abs_md = parse_abs_monthday_range_fn(message)
    if not parsed.get("departure_date") and abs_md.get("departure_date"):
        parsed["departure_date"] = abs_md["departure_date"]
    if not parsed.get("return_date") and abs_md.get("return_date"):
        parsed["return_date"] = abs_md["return_date"]

    if parsed.get("return_date"):
        parsed["trip_type"] = parsed.get("trip_type") or "round"

    # passenger count heuristics
    msg = message or ""
    m_adult = re.search(r"(?:성인|어른)\s*(\d+)\s*(?:명|인)?", msg)
    m_child = re.search(r"(?:소아|아동|아이|어린이)\s*(\d+)\s*(?:명|인)?", msg)
    m_infant = re.search(r"(?:유아)\s*(\d+)\s*(?:명|인)?", msg)
    if m_adult:
        parsed["adults"] = max(1, _coerce_nonneg_int(m_adult.group(1), parsed.get("adults", 1)))
    if m_child:
        parsed["children"] = _coerce_nonneg_int(m_child.group(1), parsed.get("children", 0))
    if m_infant:
        parsed["infants"] = _coerce_nonneg_int(m_infant.group(1), parsed.get("infants", 0))

    if contains_fn(message, ["가격", "저렴", "가성비"]):
        parsed["sort_by"] = "price_asc"
    if contains_fn(message, ["출발시간이 가장 빠른", "가장 이른 출발", "제일 빨리 출발"]):
        parsed["sort_by"] = "earliest_departure"
    if contains_fn(message, ["가장 빨리", "최단", "빠르게"]):
        parsed["sort_by"] = "fastest_cheap" if parsed.get("sort_by") == "price_asc" else "fastest"

    return parsed


def _extract_relative_range_dates(message: str) -> tuple[Optional[str], Optional[str]]:
    t = str(message or "").lower()
    compact = re.sub(r"\s+", "", t)
    if not compact:
        return None, None
    has_range_connector = any(k in compact for k in ["에서", "부터", "~", "-", "to", "까지"])
    if not has_range_connector:
        return None, None

    token_offsets = {
        "오늘": 0,
        "내일": 1,
        "내일모레": 2,
        "내일모래": 2,
        "모레": 2,
        "글피": 3,
    }
    token_pat = re.compile(r"내일모레|내일모래|글피|모레|내일|오늘")
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
        f"입력:{message}\n문맥:{context}"
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
    parsed.setdefault("__date_explicit", False)

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
        parsed["checkin_date"] = rel_start
        parsed["checkout_date"] = rel_end

    msg_text = str(message or "")
    has_iso = bool(re.search(r"\b20\d{2}-\d{2}-\d{2}\b", msg_text))
    has_mmdd = bool(re.search(r"\b\d{1,2}[/-]\d{1,2}\b", msg_text))
    has_ko_md = bool(re.search(r"\d{1,2}\s*월\s*\d{1,2}\s*일", msg_text))
    has_rel = bool(parse_rel_date_fn(message) or rel_start or rel_end)
    parsed["__date_explicit"] = bool(has_iso or has_mmdd or has_ko_md or has_rel)

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
