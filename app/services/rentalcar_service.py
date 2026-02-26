import datetime as dt
import re
from typing import Any, Optional

from app.api.rental_helper import search_rental_locations
from app.api.sky_cars_api import parse_sky_car_search_results, search_sky_car_rentals


def _detect_country_code(message: str, prev_state: dict[str, Any]) -> Optional[str]:
    m = (message or "").lower()
    if any(k in m for k in ["일본", "japan", "jp"]):
        return "JP"
    if any(k in m for k in ["한국", "대한민국", "korea", "kr"]):
        return "KR"
    if any(k in m for k in ["미국", "usa", "us", "america"]):
        return "US"
    if any(k in m for k in ["프랑스", "france"]):
        return "FR"
    if any(k in m for k in ["태국", "thailand"]):
        return "TH"
    if any(k in m for k in ["베트남", "vietnam"]):
        return "VN"
    if any(k in m for k in ["싱가포르", "singapore"]):
        return "SG"
    if any(k in m for k in ["대만", "taiwan"]):
        return "TW"
    if any(k in m for k in ["호주", "australia"]):
        return "AU"
    if any(k in m for k in ["두바이", "uae", "아랍에미리트"]):
        return "AE"
    rs = (prev_state or {}).get("rental_state") or {}
    return rs.get("country_code")


def _parse_age(message: str, prev_state: dict[str, Any]) -> Optional[int]:
    m = re.search(r"(\d{2})\s*살", message or "")
    if not m:
        m = re.search(r"(?:나이|운전자나이|driver age)\s*[:은는이]?\s*(\d{2})", (message or "").lower())
    if m:
        try:
            age = int(m.group(1))
            return age if 18 <= age <= 90 else None
        except Exception:
            return None
    rs = (prev_state or {}).get("rental_state") or {}
    return rs.get("driver_age")


def _parse_city_query(message: str, prev_state: dict[str, Any]) -> Optional[str]:
    msg = message or ""
    m = re.search(r"([가-힣A-Za-z\s]{1,30})에서", msg)
    if m:
        cand = m.group(1).strip()
        if cand and cand not in {"일본", "한국", "미국"}:
            return cand
    # fallback city mentions
    for cand in [
        "도쿄", "오사카", "교토", "후쿠오카", "삿포로", "나고야", "나하", "벳푸",
        "서울", "부산", "제주", "뉴욕", "런던", "파리", "로마", "방콕",
        "하노이", "호치민", "다낭", "싱가포르", "타이베이", "시드니", "멜버른", "브리즈번", "두바이",
    ]:
        if cand in msg:
            return cand
    rs = (prev_state or {}).get("rental_state") or {}
    return rs.get("city_query")


def _parse_date_ymd(text: str, now: Optional[dt.date] = None) -> Optional[str]:
    now = now or dt.datetime.now().date()
    t = text or ""
    m = re.search(r"\b(20\d{2})-(\d{1,2})-(\d{1,2})\b", t)
    if m:
        try:
            return dt.date(int(m.group(1)), int(m.group(2)), int(m.group(3))).isoformat()
        except Exception:
            return None
    m = re.search(r"(\d{1,2})\s*월\s*(\d{1,2})\s*일", t)
    if m:
        try:
            y = now.year
            d = dt.date(y, int(m.group(1)), int(m.group(2)))
            if d < now - dt.timedelta(days=1):
                d = dt.date(y + 1, int(m.group(1)), int(m.group(2)))
            return d.isoformat()
        except Exception:
            return None
    return None


def _parse_pickup_dropoff_dates(message: str, prev_state: dict[str, Any]) -> tuple[Optional[str], Optional[str]]:
    msg = message or ""
    rs = (prev_state or {}).get("rental_state") or {}
    pickup = rs.get("pickup_date")
    dropoff = rs.get("dropoff_date")

    m_pick = re.search(r"(?:픽업일(?:은|은요|은요)?|픽업(?:은|일은)?)[^\d]*(20\d{2}-\d{1,2}-\d{1,2}|\d{1,2}\s*월\s*\d{1,2}\s*일)", msg)
    if m_pick:
        pickup = _parse_date_ymd(m_pick.group(1)) or pickup
    m_drop = re.search(r"(?:반납일(?:은|은요)?|반납(?:은|일은)?)[^\d]*(20\d{2}-\d{1,2}-\d{1,2}|\d{1,2}\s*월\s*\d{1,2}\s*일)", msg)
    if m_drop:
        dropoff = _parse_date_ymd(m_drop.group(1)) or dropoff

    # fallback: if two dates appear in order
    dates = []
    for m in re.finditer(r"(20\d{2}-\d{1,2}-\d{1,2}|\d{1,2}\s*월\s*\d{1,2}\s*일)", msg):
        parsed = _parse_date_ymd(m.group(1))
        if parsed:
            dates.append(parsed)
    if len(dates) >= 2:
        pickup = pickup or dates[0]
        dropoff = dropoff or dates[1]
    elif len(dates) == 1:
        if pickup is None:
            pickup = dates[0]
        elif dropoff is None and pickup != dates[0]:
            dropoff = dates[0]

    return pickup, dropoff


def _currency_for_country(country_code: str) -> str:
    return {
        "KR": "KRW",
        "JP": "JPY",
        "US": "USD",
        "FR": "EUR",
        "IT": "EUR",
        "AE": "AED",
        "TH": "THB",
        "VN": "VND",
        "SG": "SGD",
        "TW": "TWD",
        "AU": "AUD",
        "GB": "GBP",
    }.get((country_code or "JP").upper(), "JPY")


def _locale_for_country(country_code: str) -> str:
    return {
        "KR": "ko-KR",
        "JP": "ja-JP",
        "TW": "zh-TW",
        "FR": "fr-FR",
        "GB": "en-GB",
    }.get((country_code or "JP").upper(), "en-US")


def _fmt_money(v: Any, ccy: str) -> str:
    try:
        if v is None:
            return f"- {ccy}"
        return f"{int(v):,} {ccy}"
    except Exception:
        return f"{v} {ccy}"


def _rental_cards_html(city_label: str, pickup_date: str, dropoff_date: str, cars: list[dict[str, Any]]) -> str:
    blocks = []
    for i, car in enumerate(cars[:6], 1):
        name = car.get("name") or "렌터카"
        supplier = car.get("supplier") or "Rental Partner"
        price = _fmt_money(car.get("price"), str(car.get("currency") or "KRW"))
        specs = " · ".join([str(x) for x in (car.get("specs") or []) if x]) or "옵션 정보 확인"
        img = car.get("image")
        rating = car.get("rating")
        block = [
            "<div style='margin:10px 0;padding:12px;border:1px solid #e5e7eb;border-radius:12px;'>",
            f"<div><b>{i}. {name}</b></div>",
            f"<div style='margin-top:4px;color:#4b5563;'>업체: {supplier}</div>",
        ]
        if img:
            block.append(
                f"<div style='margin-top:8px;'><img src=\"{img}\" alt=\"\" "
                "style='width:100%;max-width:360px;height:160px;object-fit:cover;border-radius:8px;border:1px solid #e5e7eb;'></div>"
            )
        block.append(f"<div style='margin-top:8px;color:#374151;'>옵션: {specs}</div>")
        if rating is not None:
            block.append(f"<div style='color:#4b5563;'>평점: {rating}</div>")
        block.append(f"<div style='margin-top:6px;font-weight:700;'>가격: {price}</div>")
        block.append("</div>")
        blocks.append("".join(block))

    return (
        f"<div><b>{city_label} 렌터카 추천</b>"
        f"<div style='margin-top:6px;color:#4b5563;'>픽업 {pickup_date} / 반납 {dropoff_date} 기준 후보예요.</div>"
        f"{''.join(blocks)}</div>"
    )


def answer_rentalcar_from_message(message: str, prev_state: Optional[dict[str, Any]] = None) -> tuple[str, dict[str, Any]]:
    prev_state = prev_state or {}
    country_code = _detect_country_code(message, prev_state) or "JP"
    city_query = _parse_city_query(message, prev_state)
    pickup_date, dropoff_date = _parse_pickup_dropoff_dates(message, prev_state)
    driver_age = _parse_age(message, prev_state) or 30

    rental_state = {
        "country_code": country_code,
        "city_query": city_query,
        "pickup_date": pickup_date,
        "dropoff_date": dropoff_date,
        "driver_age": driver_age,
    }

    missing = []
    if not city_query:
        missing.append("도시")
    if not pickup_date:
        missing.append("픽업일")
    if not dropoff_date:
        missing.append("반납일")
    if missing:
        html = (
            "<div>렌터카를 찾으려면 "
            + ", ".join(missing)
            + " 정보를 알려주세요.<br>예: 도쿄에서 픽업일은 3월 2일, 반납일은 3월 3일, 운전자 나이 25살</div>"
        )
        return html, {"rental_context": True, "rental_state": rental_state}

    locs = search_rental_locations(city_query, category="all", limit=5, country_code=country_code)
    if not locs:
        return (
            f"<div>{city_query} 지역의 렌터카 픽업 위치를 찾지 못했어요. 도시명/공항명으로 다시 알려주세요.</div>",
            {"rental_context": True, "rental_state": rental_state},
        )

    loc = locs[0]
    pickup_name = str(loc.get("name") or city_query)
    pickup_lat = loc.get("lat")
    pickup_lon = loc.get("lon")
    if pickup_lat is None or pickup_lon is None:
        return (
            f"<div>{pickup_name} 위치 좌표를 찾지 못했어요. 다른 도시명이나 공항명으로 시도해 주세요.</div>",
            {"rental_context": True, "rental_state": rental_state},
        )

    pickup_at = f"{pickup_date}T10:00:00"
    dropoff_at = f"{dropoff_date}T10:00:00"
    raw = search_sky_car_rentals(
        pickup_name=pickup_name,
        pickup_lat=float(pickup_lat),
        pickup_lon=float(pickup_lon),
        dropoff_name=pickup_name,
        dropoff_lat=float(pickup_lat),
        dropoff_lon=float(pickup_lon),
        pickup_at=pickup_at,
        dropoff_at=dropoff_at,
        market=country_code,
        currency=_currency_for_country(country_code),
        locale=_locale_for_country(country_code),
        driver_age=int(driver_age),
    )
    cars = parse_sky_car_search_results(raw)
    if not cars:
        msg = ""
        if isinstance(raw, dict):
            msg = str(raw.get("message") or raw.get("errors") or "").strip()
        detail = f" ({msg})" if msg else ""
        return (
            f"<div>렌터카 검색 결과를 찾지 못했어요. 다른 도시/날짜로 다시 시도해 주세요.{detail}</div>",
            {"rental_context": True, "rental_state": rental_state},
        )

    html = _rental_cards_html(pickup_name, pickup_date, dropoff_date, cars)
    return html, {"rental_context": True, "rental_state": rental_state}
