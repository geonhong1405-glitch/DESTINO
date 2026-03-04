import datetime as dt
import re
from typing import Any, Optional

from app.api.rental_helper import search_rental_locations, parse_rental_search_results
from app.api.sky_cars_api import parse_sky_car_search_results, search_sky_car_rentals
from app.services.location_alias_service import LOCATION_ALIASES, COUNTRY_ALIASES
from app.services import date_parsing_service


def _normalize_city_query_for_rental(city_query: str | None) -> str | None:
    q = str(city_query or "").strip()
    if not q:
        return None
    ql = q.lower()
    compact = re.sub(r"\s+", "", ql)

    # Resolve through shared aliases first.
    iata = None
    for k, v in LOCATION_ALIASES.items():
        kk = str(k or "").strip().lower()
        if not kk:
            continue
        if kk == ql or kk.replace(" ", "") == compact:
            iata = str(v or "").upper()
            break
    if not iata and re.fullmatch(r"[A-Za-z]{3}", q):
        iata = q.upper()

    iata_to_city = {
        "NYC": "New York",
        "TYO": "Tokyo",
        "OSA": "Osaka",
        "LON": "London",
        "PAR": "Paris",
        "ROM": "Rome",
        "SEL": "Seoul",
        "BKK": "Bangkok",
        "SGN": "Ho Chi Minh City",
        "HAN": "Hanoi",
        "SIN": "Singapore",
    }
    if iata and iata in iata_to_city:
        return iata_to_city[iata]
    return q


def _entity_retry_hints(city_query: str | None, country_code: str | None) -> list[str]:
    q = re.sub(r"\s+", "", str(city_query or "").lower())
    cc = str(country_code or "").upper().strip()
    hints: list[str] = []

    def _add(x: str):
        if x and x not in hints:
            hints.append(x)

    if cc == "US" and any(k in q for k in ["?댁슃", "newyork", "nyc", "newyorkcity"]):
        for x in ["JFK", "EWR", "LGA", "New York"]:
            _add(x)
    if cc == "JP" and any(k in q for k in ["?꾩퓙", "tokyo", "tyo"]):
        for x in ["NRT", "HND", "Tokyo"]:
            _add(x)
    if cc == "KR" and any(k in q for k in ["?쒖슱", "seoul", "sel"]):
        for x in ["ICN", "GMP", "Seoul"]:
            _add(x)
    return hints


def _detect_country_code(message: str, prev_state: dict[str, Any]) -> Optional[str]:
    m = str(message or "").lower()

    # Unicode-safe Korean + English country cues.
    country_patterns = [
        ("JP", ["\uC77C\uBCF8", "japan", "jp"]),
        ("KR", ["\uD55C\uAD6D", "\uB300\uD55C\uBBFC\uAD6D", "korea", "kr"]),
        ("US", ["\uBBF8\uAD6D", "usa", "us", "america", "united states"]),
        ("GB", ["\uC601\uAD6D", "uk", "united kingdom", "england", "gb"]),
        ("FR", ["\uD504\uB791\uC2A4", "france", "fr"]),
        ("IT", ["\uC774\uD0C8\uB9AC\uC544", "italy", "it"]),
        ("TH", ["\uD0DC\uAD6D", "thailand", "th"]),
        ("VN", ["\uBCA0\uD2B8\uB0A8", "vietnam", "vn"]),
        ("SG", ["\uC2F1\uAC00\uD3EC\uB974", "singapore", "sg"]),
        ("TW", ["\uB300\uB9CC", "taiwan", "tw"]),
        ("AU", ["\uD638\uC8FC", "australia", "au"]),
        ("AE", ["\uB450\uBC14\uC774", "\uC544\uB78D\uC5D0\uBBF8\uB9AC\uD2B8", "uae", "dubai", "ae"]),
    ]
    for cc, kws in country_patterns:
        if any(k in m for k in kws):
            return cc

    # City-level cues when country name is omitted.
    city_cc_patterns = [
        ("JP", ["\uB3C4\uCFC4", "\uC624\uC0AC\uCE74", "\uB098\uB9AC\uD0C0", "\uD558\uB124\uB2E4", "tokyo", "osaka", "narita", "haneda"]),
        ("KR", ["\uC11C\uC6B8", "\uC778\uCC9C", "\uBD80\uC0B0", "seoul", "incheon", "busan"]),
        ("US", ["\uB274\uC695", "\uB77C\uC2A4\uBCA0\uAC00\uC2A4", "new york", "jfk", "ewr", "lga", "los angeles", "lax"]),
        ("GB", ["\uB7F0\uB358", "london", "lhr", "lgw"]),
        ("FR", ["\uD30C\uB9AC", "paris", "cdg", "ory"]),
        ("IT", ["\uB85C\uB9C8", "rome", "fco"]),
        ("TH", ["\uBC29\uCF55", "bangkok", "bkk"]),
        ("VN", ["\uD558\uB178\uC774", "\uD638\uCE58\uBBFC", "\uB2E4\uB0AD", "hanoi", "ho chi minh", "saigon", "danang", "han", "sgn", "dad"]),
        ("SG", ["\uC2F1\uAC00\uD3EC\uB974", "singapore", "sin"]),
        ("TW", ["\uB300\uB9CC", "\uD0C0\uC774\uD398\uC774", "taipei", "taiwan", "tpe"]),
        ("AU", ["\uC2DC\uB4DC\uB2C8", "\uBA5C\uBC84\uB978", "sydney", "melbourne", "syd", "mel"]),
        ("AE", ["\uB450\uBC14\uC774", "dubai", "dxb"]),
    ]
    for cc, kws in city_cc_patterns:
        if any(k in m for k in kws):
            return cc

    # Country aliases map fallback (English keys are stable even if mojibake exists).
    m_compact = re.sub(r"\s+", "", m)
    for key, iata in COUNTRY_ALIASES.items():
        kk = str(key or "").strip().lower().replace(" ", "")
        if not kk:
            continue
        if kk in m_compact:
            iata_u = str(iata or "").upper()
            iata_to_cc = {
                "SEL": "KR", "TYO": "JP", "NYC": "US", "LON": "GB", "PAR": "FR", "ROM": "IT",
                "BKK": "TH", "SGN": "VN", "SIN": "SG", "TPE": "TW", "SYD": "AU", "DXB": "AE",
                "DEL": "IN", "MNL": "PH", "KUL": "MY",
            }
            if iata_u in iata_to_cc:
                return iata_to_cc[iata_u]

    rs = (prev_state or {}).get("rental_state") or {}
    return rs.get("country_code")


def _parse_age(message: str, prev_state: dict[str, Any]) -> Optional[int]:
    msg = str(message or "")
    m = re.search(r"(\d{2})\s*살", msg)
    if not m:
        m = re.search(r"(?:나이|driver\s*age)\s*[:=]?\s*(\d{2})", msg.lower())
    if m:
        try:
            age = int(m.group(1))
            return age if 18 <= age <= 90 else None
        except Exception:
            return None
    rs = (prev_state or {}).get("rental_state") or {}
    return rs.get("driver_age")


def _parse_city_query(message: str, prev_state: dict[str, Any]) -> Optional[str]:
    msg = str(message or "")
    msg_compact = re.sub(r"\s+", "", msg)
    date_only_tokens = {"오늘", "내일", "내일모레", "내일모래", "모레", "글피"}
    numeric_rel_date = bool(
        re.search(r"\d+\s*일\s*(뒤|후)", msg)
        or re.search(r"\d+\s*주\s*(뒤|후)", msg)
    )

    # "X에서" pattern (non-greedy: stop at the first "에서").
    m = re.search(r"([\uAC00-\uD7A3A-Za-z\s]{1,40}?)\uC5D0\uC11C", msg)
    if m:
        cand = m.group(1).strip(" ,.")
        # Remove trailing date-like tokens accidentally captured in chained "...에서" phrases.
        cand = re.sub(r"\s*(오늘|내일|내일모레|내일모래|모레|글피)\s*$", "", cand).strip(" ,.")
        cand = re.sub(r"\s*\d+\s*(일|주)\s*(뒤|후)\s*$", "", cand).strip(" ,.")
        cand_compact = re.sub(r"\s+", "", cand)
        if cand and len(cand) >= 2 and cand_compact not in date_only_tokens:
            return cand

    ml = msg.lower()
    # Shared location aliases fallback (multi-country).
    keys = sorted([str(k) for k in LOCATION_ALIASES.keys() if str(k).strip()], key=len, reverse=True)
    for k in keys:
        ks = k.lower()
        if ks and ks in ml:
            return k

    # IATA code fallback
    m_iata = re.search(r"\b([A-Z]{3})\b", msg.upper())
    if m_iata:
        return m_iata.group(1)

    rs = (prev_state or {}).get("rental_state") or {}
    if any(tok in msg_compact for tok in date_only_tokens) or numeric_rel_date:
        return rs.get("city_query")
    return rs.get("city_query")


def _parse_date_ymd(text: str, now: Optional[dt.date] = None) -> Optional[str]:
    now = now or dt.datetime.now().date()
    s = str(text or "").strip()
    if not s:
        return None

    # Use shared date parser first (single absolute date or range start).
    try:
        parsed = date_parsing_service.parse_abs_monthday_range(
            s,
            now_dt=dt.datetime(now.year, now.month, now.day),
        )
        dep = parsed.get("departure_date") if isinstance(parsed, dict) else None
        if dep:
            return dep
    except Exception:
        pass

    # Fallback for fully qualified yyyy-mm-dd
    m = re.search(r"\b(20\d{2})-(\d{1,2})-(\d{1,2})\b", s)
    if m:
        try:
            return dt.date(int(m.group(1)), int(m.group(2)), int(m.group(3))).isoformat()
        except Exception:
            return None
    return None


def _parse_pickup_dropoff_dates(message: str, prev_state: dict[str, Any]) -> tuple[Optional[str], Optional[str]]:
    msg = str(message or "")
    rs = (prev_state or {}).get("rental_state") or {}
    pickup = rs.get("pickup_date")
    dropoff = rs.get("dropoff_date")

    # 1) Explicit pickup/dropoff markers with absolute date expressions.
    m_pick = re.search(r"(?:pick\s*up|pickup|\uD53D\uC5C5|\uC778\uC218|\uB300\uC5EC)[^\d]*(20\d{2}-\d{1,2}-\d{1,2}|\d{1,2}\s*[/-]\s*\d{1,2}|\d{1,2}\s*\uC6D4\s*\d{1,2}\s*\uC77C)", msg, re.IGNORECASE)
    if m_pick:
        pickup = _parse_date_ymd(m_pick.group(1)) or pickup

    m_drop = re.search(r"(?:drop\s*off|dropoff|\uBC18\uB0A9|\uBC18\uB0A9\uC77C|\uBC18\uB0A9\uC77C\uC740)[^\d]*(20\d{2}-\d{1,2}-\d{1,2}|\d{1,2}\s*[/-]\s*\d{1,2}|\d{1,2}\s*\uC6D4\s*\d{1,2}\s*\uC77C)", msg, re.IGNORECASE)
    if m_drop:
        dropoff = _parse_date_ymd(m_drop.group(1)) or dropoff

    # 2) Fallback absolute date scan (first->pickup, second->dropoff).
    dates = []
    for m in re.finditer(r"(20\d{2}-\d{1,2}-\d{1,2}|\d{1,2}\s*[/-]\s*\d{1,2}|\d{1,2}\s*\uC6D4\s*\d{1,2}\s*\uC77C)", msg):
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

    # 2.5) Numeric relative ranges (e.g. "2일뒤에서부터 3일뒤까지", "2주 뒤 ~ 3주 뒤").
    compact_num = re.sub(r"\s+", "", msg)
    rel_pairs = re.findall(r"(\d+)\s*(일|주)\s*(?:뒤|후)", compact_num)
    if rel_pairs:
        now = dt.datetime.now().date()
        if len(rel_pairs) >= 2 and any(k in compact_num for k in ["부터", "까지", "에서", "~", "-", "to"]):
            n1, u1 = rel_pairs[0]
            n2, u2 = rel_pairs[1]
            d1 = now + dt.timedelta(days=int(n1) * (7 if u1 == "주" else 1))
            d2 = now + dt.timedelta(days=int(n2) * (7 if u2 == "주" else 1))
            if d2 <= d1:
                d2 = d1 + dt.timedelta(days=1)
            pickup = pickup or d1.isoformat()
            dropoff = dropoff or d2.isoformat()
        elif len(rel_pairs) == 1:
            n1, u1 = rel_pairs[0]
            d1 = now + dt.timedelta(days=int(n1) * (7 if u1 == "주" else 1))
            pickup = pickup or d1.isoformat()

    # 3) Relative day range fallback (e.g. "?????? ????").
    compact = re.sub(r"\s+", "", msg)
    has_range_connector = any(k in compact for k in ["\uBD80\uD130", "\uAE4C\uC9C0", "\uC5D0\uC11C", "~", "-"]) or ("from" in compact.lower() and "to" in compact.lower())
    token_offsets = {
        "\uC624\uB298": 0,
        "\uB0B4\uC77C": 1,
        "\uB0B4\uC77C\uBAA8\uB808": 2,
        "\uB0B4\uC77C\uBAA8\uB798": 2,
        "\uBAA8\uB808": 2,
        "\uAE00\uD53C": 3,
    }
    token_pat = re.compile(r"\uB0B4\uC77C\uBAA8\uB808|\uB0B4\uC77C\uBAA8\uB798|\uAE00\uD53C|\uBAA8\uB808|\uB0B4\uC77C|\uC624\uB298")
    found = [m.group(0) for m in token_pat.finditer(compact)]
    if found:
        now = dt.datetime.now().date()
        if has_range_connector and len(found) >= 2:
            d1 = now + dt.timedelta(days=token_offsets.get(found[0], 0))
            d2 = now + dt.timedelta(days=token_offsets.get(found[1], token_offsets.get(found[0], 0) + 1))
            if d2 <= d1:
                d2 = d1 + dt.timedelta(days=1)
            pickup = pickup or d1.isoformat()
            dropoff = dropoff or d2.isoformat()
        elif len(found) == 1:
            d1 = now + dt.timedelta(days=token_offsets.get(found[0], 0))
            pickup = pickup or d1.isoformat()

    return pickup, dropoff


def _currency_for_country(country_code: str) -> str:
    # UI requirement: show rental prices in KRW consistently.
    return "KRW"


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


def _normalize_prices_to_krw(cars: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rates = {
        "KRW": 1.0,
        "USD": 1350.0,
        "JPY": 9.0,
        "EUR": 1470.0,
        "GBP": 1720.0,
        "SGD": 1000.0,
        "THB": 38.0,
        "VND": 0.055,
        "TWD": 43.0,
        "AUD": 900.0,
        "AED": 368.0,
    }
    out: list[dict[str, Any]] = []
    for car in cars or []:
        row = dict(car or {})
        ccy = str(row.get("currency") or "KRW").upper()
        price = row.get("price")
        if isinstance(price, (int, float)):
            rate = rates.get(ccy)
            if rate and ccy != "KRW":
                row["price"] = int(round(float(price) * rate))
                row["currency"] = "KRW"
            elif ccy == "KRW":
                row["price"] = int(round(float(price)))
                row["currency"] = "KRW"
            else:
                # Unknown currency: keep numeric value but label KRW for consistency.
                row["price"] = int(round(float(price)))
                row["currency"] = "KRW"
        else:
            row["currency"] = "KRW"
        out.append(row)
    return out


def _rental_cards_html(city_label: str, pickup_date: str, dropoff_date: str, cars: list[dict[str, Any]]) -> str:
    blocks = []
    for i, car in enumerate(cars[:6], 1):
        name = str(car.get("name") or "Rental Car")
        supplier = str(car.get("supplier") or "Rental Partner")
        price = _fmt_money(car.get("price"), str(car.get("currency") or "KRW"))
        specs = " 쨌 ".join([str(x) for x in (car.get("specs") or []) if x]) or "Option info"
        img = str(car.get("image") or "").strip()
        rating = car.get("rating")

        block = [
            "<div style='margin:10px 0;padding:12px;border:1px solid #e5e7eb;border-radius:12px;'>",
            f"<div><b>{i}. {name}</b></div>",
            f"<div style='margin-top:4px;color:#4b5563;'>supplier: {supplier}</div>",
        ]
        if img:
            block.append(
                f"<div style='margin-top:8px;'><img src=\"{img}\" alt=\"\" style='width:100%;max-width:360px;height:160px;object-fit:cover;border-radius:8px;border:1px solid #e5e7eb;'></div>"
            )
        block.append(f"<div style='margin-top:8px;color:#374151;'>options: {specs}</div>")
        if rating is not None:
            block.append(f"<div style='color:#4b5563;'>rating: {rating}</div>")
        block.append(f"<div style='margin-top:6px;font-weight:700;'>price: {price}</div>")
        block.append("</div>")
        blocks.append("".join(block))

    return (
        f"<div><b>{city_label} rental car recommendations</b>"
        f"<div style='margin-top:6px;color:#4b5563;'>pickup {pickup_date} / dropoff {dropoff_date}</div>"
        f"{''.join(blocks)}</div>"
    )


def _rental_cards_html_v2(city_label: str, pickup_date: str, dropoff_date: str, cars: list[dict[str, Any]]) -> str:
    lines: list[str] = []
    for i, car in enumerate(cars[:8], 1):
        name = str(car.get("name") or "Rental Car")
        supplier = str(car.get("supplier") or "Rental Partner")
        price = _fmt_money(car.get("price"), str(car.get("currency") or "KRW"))
        specs = " 쨌 ".join([str(x) for x in (car.get("specs") or []) if x]) or "Option info"
        img = str(car.get("image") or "").strip()
        rating = car.get("rating")

        parts = [
            f"{i}) {name}",
            f"price: {price}",
            f"supplier: {supplier}",
            f"options: {specs}",
            f"pickup: {pickup_date}",
            f"dropoff: {dropoff_date}",
        ]
        if rating is not None:
            parts.append(f"rating: {rating}")
        if img:
            parts.append(f"photo: {img}")
        lines.append(" | ".join(parts))

    return f"<div><b>{city_label} rental car recommendations</b><br>{'<br>'.join(lines)}</div>"


def answer_rentalcar_from_message(message: str, prev_state: Optional[dict[str, Any]] = None) -> tuple[str, dict[str, Any]]:
    prev_state = prev_state or {}
    msg = str(message or "")
    msg_compact = re.sub(r"\s+", "", msg)
    country_code = _detect_country_code(msg, prev_state) or "KR"
    city_query = _parse_city_query(msg, prev_state)
    city_query_norm = _normalize_city_query_for_rental(city_query) or city_query
    pickup_date, dropoff_date = _parse_pickup_dropoff_dates(msg, prev_state)

    has_explicit_date_in_turn = bool(
        re.search(r"\b20\d{2}-\d{1,2}-\d{1,2}\b", msg)
        or re.search(r"\b\d{1,2}[/-]\d{1,2}\b", msg)
        or re.search(r"\d{1,2}\s*월\s*\d{1,2}\s*일", msg)
        or re.search(r"\d+\s*일\s*(뒤|후)", msg)
        or re.search(r"\d+\s*주\s*(뒤|후)", msg)
        or any(tok in msg_compact for tok in ["오늘", "내일", "내일모레", "내일모래", "모레", "글피"])
    )
    has_city_in_turn = bool(re.search(r"([\uAC00-\uD7A3A-Za-z\s]{1,40}?)\uC5D0\uC11C", msg))
    if (not has_explicit_date_in_turn) and has_city_in_turn:
        # New rental request without date must ask for pickup/dropoff; do not reuse stale dates.
        pickup_date = None
        dropoff_date = None

    driver_age = _parse_age(message, prev_state) or 30

    rental_state = {
        "country_code": country_code,
        "city_query": city_query_norm,
        "pickup_date": pickup_date,
        "dropoff_date": dropoff_date,
        "driver_age": driver_age,
    }

    missing = []
    if not city_query_norm:
        missing.append("\uB3C4\uC2DC")
    if not pickup_date:
        missing.append("\uD53D\uC5C5\uC77C")
    if not dropoff_date:
        missing.append("\uBC18\uB0A9\uC77C")
    if missing:
        html = (
            "<div>\uB80C\uD130\uCE74\uB97C \uCC3E\uC73C\uB824\uBA74 "
            + ", ".join(missing)
            + " \uC815\uBCF4\uB97C \uC54C\uB824\uC8FC\uC138\uC694.<br>\uC608: \uB3C4\uCFC4\uC5D0\uC11C \uD53D\uC5C5\uC77C\uC740 3\uC6D4 2\uC77C, \uBC18\uB0A9\uC77C\uC740 3\uC6D4 3\uC77C, \uC6B4\uC804\uC790 \uB098\uC774 25\uC0B4</div>"
        )
        return html, {"rental_context": True, "rental_state": rental_state}

    locs = search_rental_locations(city_query_norm, category="all", limit=5, country_code=country_code)
    if not locs:
        return (
            f"<div>{city_query_norm} \uC9C0\uC5ED\uC758 \uB80C\uD130\uCE74 \uD53D\uC5C5 \uC704\uCE58\uB97C \uCC3E\uC9C0 \uBABB\uD588\uC5B4\uC694. \uB3C4\uC2DC\uBA85/\uACF5\uD56D\uBA85\uC73C\uB85C \uB2E4\uC2DC \uC54C\uB824\uC8FC\uC138\uC694.</div>",
            {"rental_context": True, "rental_state": rental_state},
        )

    loc = locs[0]
    pickup_name = str(loc.get("name") or city_query_norm)
    pickup_lat = loc.get("lat")
    pickup_lon = loc.get("lon")
    if pickup_lat is None or pickup_lon is None:
        return (
            f"<div>{pickup_name} \uC704\uCE58 \uC88C\uD45C\uB97C \uCC3E\uC9C0 \uBABB\uD588\uC5B4\uC694. \uB2E4\uB978 \uB3C4\uC2DC\uBA85/\uACF5\uD56D\uBA85\uC73C\uB85C \uC2DC\uB3C4\uD574 \uC8FC\uC138\uC694.</div>",
            {"rental_context": True, "rental_state": rental_state},
        )

    pickup_at = f"{pickup_date}T10:00:00"
    dropoff_at = f"{dropoff_date}T10:00:00"

    def _search_with_location(name: str, lat: float, lon: float):
        raw_local = search_sky_car_rentals(
            pickup_name=name,
            pickup_lat=float(lat),
            pickup_lon=float(lon),
            dropoff_name=name,
            dropoff_lat=float(lat),
            dropoff_lon=float(lon),
            pickup_at=pickup_at,
            dropoff_at=dropoff_at,
            market=country_code,
            currency=_currency_for_country(country_code),
            locale=_locale_for_country(country_code),
            driver_age=int(driver_age),
        )
        cars_local = parse_sky_car_search_results(raw_local)
        if not cars_local:
            cars_local = parse_rental_search_results(raw_local)
        return raw_local, cars_local

    raw, cars = _search_with_location(pickup_name, float(pickup_lat), float(pickup_lon))

    if not cars:
        msg = str((raw or {}).get("message") or "")
        if "pickUpEntityId resolution failed" in msg:
            for hint in _entity_retry_hints(city_query_norm, country_code):
                try:
                    raw_hint, cars_hint = _search_with_location(hint, float(pickup_lat), float(pickup_lon))
                    if cars_hint:
                        pickup_name = hint
                        raw = raw_hint
                        cars = cars_hint
                        break
                except Exception:
                    continue

        alt_locs = search_rental_locations(city_query_norm, category="airport", limit=5, country_code=country_code)
        for alt in alt_locs:
            try:
                alt_name = str(alt.get("name") or city_query_norm)
                alt_lat = alt.get("lat")
                alt_lon = alt.get("lon")
                if alt_lat is None or alt_lon is None:
                    continue
                raw_alt, cars_alt = _search_with_location(alt_name, float(alt_lat), float(alt_lon))
                if cars_alt:
                    pickup_name = alt_name
                    raw = raw_alt
                    cars = cars_alt
                    break
            except Exception:
                continue

    if not cars:
        msg = ""
        if isinstance(raw, dict):
            msg = str(raw.get("message") or raw.get("errors") or "").strip()
        msg_l = msg.lower()
        detail = " (API\uB294 \uC131\uACF5 \uC751\uB2F5\uC774\uC9C0\uB9CC \uC774\uC6A9 \uAC00\uB2A5\uD55C \uCC28\uB7C9\uC774 \uC5C6\uC5B4\uC694)" if msg_l == "successful" else (f" ({msg})" if msg else "")
        return (
            f"<div>\uB80C\uD130\uCE74 \uAC80\uC0C9 \uACB0\uACFC\uB97C \uCC3E\uC9C0 \uBABB\uD588\uC5B4\uC694. \uB2E4\uB978 \uB3C4\uC2DC/\uB0A0\uC9DC\uB85C \uB2E4\uC2DC \uC2DC\uB3C4\uD574 \uC8FC\uC138\uC694.{detail}</div>",
            {"rental_context": True, "rental_state": rental_state},
        )

    cars = _normalize_prices_to_krw(cars)
    html = _rental_cards_html_v2(pickup_name, pickup_date, dropoff_date, cars)
    return html, {"rental_context": True, "rental_state": rental_state}
