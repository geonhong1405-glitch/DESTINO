import datetime
import os
import re

import requests


def _parse_float(value):
    try:
        if value is None:
            return None
        if isinstance(value, str) and not value.strip():
            return None
        return float(value)
    except Exception:
        return None


def _coerce_number(value):
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        s = value.strip().replace(",", "")
        m = re.search(r"(\d+(?:\.\d+)?)", s)
        if m:
            try:
                return float(m.group(1))
            except Exception:
                return None
    return None


def _normalize_query_alias(text: str | None) -> str:
    s = (text or "").strip().lower()
    alias = {
        "훗카이도": "삿포로",
        "홋카이도": "삿포로",
        "북해도": "삿포로",
        "벳부": "벳푸",
        "벳푸": "벳푸",
        "벳후": "벳푸",
        "벱푸": "벳푸",
        "hokkaido": "삿포로",
        "sapporo": "삿포로",
        "beppu": "벳푸",
        "narita": "나리타",
        "haneda": "하네다",
        "losangeles": "로스앤젤레스",
        "los angeles": "로스앤젤레스",
    }
    return alias.get(s, s)


def _preset_locations() -> list[dict]:
    return [
        {"name": "서울", "sub": "대한민국 서울", "lat": 37.5665, "lon": 126.9780, "category": "city", "country_code": "KR", "aliases": ["서울", "seoul"]},
        {"name": "인천공항 (ICN)", "sub": "대한민국 인천", "lat": 37.4602, "lon": 126.4407, "category": "airport", "country_code": "KR", "aliases": ["인천", "인천공항", "icn"]},
        {"name": "부산", "sub": "대한민국 부산", "lat": 35.1796, "lon": 129.0756, "category": "city", "country_code": "KR", "aliases": ["부산", "busan"]},
        {"name": "김해공항 (PUS)", "sub": "대한민국 부산", "lat": 35.1795, "lon": 128.9382, "category": "airport", "country_code": "KR", "aliases": ["김해", "김해공항", "pus"]},
        {"name": "도쿄", "sub": "일본 도쿄", "lat": 35.6762, "lon": 139.6503, "category": "city", "country_code": "JP", "aliases": ["도쿄", "tokyo", "tyo"]},
        {"name": "나리타 공항 (NRT)", "sub": "일본 치바", "lat": 35.7719, "lon": 140.3929, "category": "airport", "country_code": "JP", "aliases": ["나리타", "나리타공항", "narita", "nrt"]},
        {"name": "하네다 공항 (HND)", "sub": "일본 도쿄", "lat": 35.5494, "lon": 139.7798, "category": "airport", "country_code": "JP", "aliases": ["하네다", "하네다공항", "haneda", "hnd"]},
        {"name": "오사카", "sub": "일본 오사카", "lat": 34.6937, "lon": 135.5023, "category": "city", "country_code": "JP", "aliases": ["오사카", "osaka", "osa"]},
        {"name": "간사이 공항 (KIX)", "sub": "일본 오사카", "lat": 34.4347, "lon": 135.2440, "category": "airport", "country_code": "JP", "aliases": ["간사이", "간사이공항", "kansai", "kix"]},
        {"name": "삿포로", "sub": "일본 홋카이도", "lat": 43.0618, "lon": 141.3545, "category": "city", "country_code": "JP", "aliases": ["삿포로", "홋카이도", "훗카이도", "hokkaido", "sapporo"]},
        {"name": "신치토세 공항 (CTS)", "sub": "일본 홋카이도", "lat": 42.7752, "lon": 141.6923, "category": "airport", "country_code": "JP", "aliases": ["치토세", "신치토세", "cts"]},
        {"name": "후쿠오카", "sub": "일본 후쿠오카", "lat": 33.5902, "lon": 130.4017, "category": "city", "country_code": "JP", "aliases": ["후쿠오카", "fukuoka", "fuk"]},
        {"name": "후쿠오카 공항 (FUK)", "sub": "일본 후쿠오카", "lat": 33.5859, "lon": 130.4507, "category": "airport", "country_code": "JP", "aliases": ["후쿠오카공항", "fuk"]},
        {"name": "벳푸", "sub": "일본 오이타", "lat": 33.2795, "lon": 131.4970, "category": "city", "country_code": "JP", "aliases": ["벳푸", "벳부", "벳후", "beppu"]},
        {"name": "오이타 공항 (OIT)", "sub": "일본 오이타", "lat": 33.4794, "lon": 131.7369, "category": "airport", "country_code": "JP", "aliases": ["오이타", "오이타공항", "oit"]},
        {"name": "로스앤젤레스", "sub": "미국 캘리포니아", "lat": 34.0522, "lon": -118.2437, "category": "city", "country_code": "US", "aliases": ["로스앤젤레스", "la", "los angeles", "losangeles"]},
        {"name": "LAX 공항 (LAX)", "sub": "미국 로스앤젤레스", "lat": 33.9416, "lon": -118.4085, "category": "airport", "country_code": "US", "aliases": ["lax", "lax공항", "로스앤젤레스공항"]},
        {"name": "뉴욕", "sub": "미국 뉴욕", "lat": 40.7128, "lon": -74.0060, "category": "city", "country_code": "US", "aliases": ["뉴욕", "new york", "nyc"]},
        {"name": "JFK 공항 (JFK)", "sub": "미국 뉴욕", "lat": 40.6413, "lon": -73.7781, "category": "airport", "country_code": "US", "aliases": ["jfk", "jfk공항"]},
        {"name": "런던", "sub": "영국 런던", "lat": 51.5072, "lon": -0.1276, "category": "city", "country_code": "GB", "aliases": ["런던", "london"]},
        {"name": "히드로 공항 (LHR)", "sub": "영국 런던", "lat": 51.4700, "lon": -0.4543, "category": "airport", "country_code": "GB", "aliases": ["히드로", "lhr", "heathrow"]},
        {"name": "파리", "sub": "프랑스 파리", "lat": 48.8566, "lon": 2.3522, "category": "city", "country_code": "FR", "aliases": ["파리", "paris"]},
        {"name": "CDG 공항 (CDG)", "sub": "프랑스 파리", "lat": 49.0097, "lon": 2.5479, "category": "airport", "country_code": "FR", "aliases": ["cdg", "샤를드골"]},
        {"name": "로마", "sub": "이탈리아 로마", "lat": 41.9028, "lon": 12.4964, "category": "city", "country_code": "IT", "aliases": ["로마", "rome"]},
        {"name": "피우미치노 공항 (FCO)", "sub": "이탈리아 로마", "lat": 41.8003, "lon": 12.2389, "category": "airport", "country_code": "IT", "aliases": ["fco", "피우미치노"]},
        {"name": "두바이", "sub": "아랍에미리트 두바이", "lat": 25.2048, "lon": 55.2708, "category": "city", "country_code": "AE", "aliases": ["두바이", "dubai"]},
        {"name": "두바이 공항 (DXB)", "sub": "아랍에미리트 두바이", "lat": 25.2532, "lon": 55.3657, "category": "airport", "country_code": "AE", "aliases": ["dxb", "두바이공항"]},
        {"name": "방콕", "sub": "태국 방콕", "lat": 13.7563, "lon": 100.5018, "category": "city", "country_code": "TH", "aliases": ["방콕", "bangkok"]},
        {"name": "수완나품 공항 (BKK)", "sub": "태국 방콕", "lat": 13.6900, "lon": 100.7501, "category": "airport", "country_code": "TH", "aliases": ["수완나품", "bkk"]},
        {"name": "싱가포르", "sub": "싱가포르", "lat": 1.3521, "lon": 103.8198, "category": "city", "country_code": "SG", "aliases": ["싱가포르", "singapore"]},
        {"name": "창이 공항 (SIN)", "sub": "싱가포르", "lat": 1.3644, "lon": 103.9915, "category": "airport", "country_code": "SG", "aliases": ["창이", "sin", "changi"]},
        {"name": "홍콩", "sub": "홍콩", "lat": 22.3193, "lon": 114.1694, "category": "city", "country_code": "HK", "aliases": ["홍콩", "hong kong", "hk"]},
        {"name": "홍콩 공항 (HKG)", "sub": "홍콩", "lat": 22.3080, "lon": 113.9185, "category": "airport", "country_code": "HK", "aliases": ["hkg", "홍콩공항"]},
        {"name": "타이베이", "sub": "대만 타이베이", "lat": 25.0330, "lon": 121.5654, "category": "city", "country_code": "TW", "aliases": ["타이베이", "taipei"]},
        {"name": "타오위안 공항 (TPE)", "sub": "대만 타이베이", "lat": 25.0797, "lon": 121.2342, "category": "airport", "country_code": "TW", "aliases": ["tpe", "타오위안"]},
        {"name": "시드니", "sub": "호주 시드니", "lat": -33.8688, "lon": 151.2093, "category": "city", "country_code": "AU", "aliases": ["시드니", "sydney"]},
        {"name": "시드니 공항 (SYD)", "sub": "호주 시드니", "lat": -33.9399, "lon": 151.1753, "category": "airport", "country_code": "AU", "aliases": ["syd", "시드니공항"]},
    ]


def _match_preset(query: str, category: str, limit: int, country_code: str | None) -> list[dict]:
    q = _normalize_query_alias(query)
    q = (q or "").strip().lower()
    cc = (country_code or "").strip().upper()
    out: list[dict] = []

    for item in _preset_locations():
        if category in {"airport", "station", "city"} and item.get("category") != category:
            continue
        if cc and item.get("country_code") != cc:
            continue

        hay = " ".join(
            [
                str(item.get("name") or ""),
                str(item.get("sub") or ""),
                " ".join(item.get("aliases") or []),
            ]
        ).lower()
        if q and q not in hay:
            continue

        out.append(
            {
                "name": item.get("name"),
                "sub": item.get("sub"),
                "lat": item.get("lat"),
                "lon": item.get("lon"),
                "category": item.get("category", "all"),
                "country_code": item.get("country_code"),
            }
        )
        if len(out) >= max(1, int(limit or 10)):
            break

    if out:
        return out

    if cc:
        retry = _match_preset(query=query, category=category, limit=limit, country_code=None)
        if retry:
            return retry

    fallback: list[dict] = []
    for item in _preset_locations():
        if category in {"airport", "station", "city"} and item.get("category") != category:
            continue
        if cc and item.get("country_code") != cc:
            continue
        fallback.append(
            {
                "name": item.get("name"),
                "sub": item.get("sub"),
                "lat": item.get("lat"),
                "lon": item.get("lon"),
                "category": item.get("category", "all"),
                "country_code": item.get("country_code"),
            }
        )
        if len(fallback) >= max(1, int(limit or 10)):
            break
    if fallback:
        return fallback

    for item in _preset_locations():
        if category in {"airport", "station", "city"} and item.get("category") != category:
            continue
        fallback.append(
            {
                "name": item.get("name"),
                "sub": item.get("sub"),
                "lat": item.get("lat"),
                "lon": item.get("lon"),
                "category": item.get("category", "all"),
                "country_code": item.get("country_code"),
            }
        )
        if len(fallback) >= max(1, int(limit or 10)):
            break
    return fallback


def _google_places_search(query: str, category: str, limit: int, country_code: str | None = None) -> list[dict]:
    api_key = (os.getenv("GOOGLE_PLACES_API_KEY") or "").strip()
    if not api_key:
        return []

    type_hint = None
    if category == "airport":
        type_hint = "airport"
    elif category == "station":
        type_hint = "train_station"

    country_hint_name = {
        "KR": "대한민국",
        "JP": "일본",
        "US": "미국",
        "GB": "영국",
        "FR": "프랑스",
        "IT": "이탈리아",
        "AE": "아랍에미리트",
        "TH": "태국",
        "SG": "싱가포르",
        "HK": "홍콩",
        "TW": "대만",
        "AU": "호주",
    }.get((country_code or "").strip().upper(), "")
    q_norm = _normalize_query_alias(query)
    google_query = f"{q_norm} {country_hint_name}".strip() if country_hint_name else q_norm

    params = {
        "query": google_query,
        "language": "ko",
        "key": api_key,
    }
    if type_hint:
        params["type"] = type_hint

    try:
        resp = requests.get(
            "https://maps.googleapis.com/maps/api/place/textsearch/json",
            params=params,
            timeout=10,
        )
        if resp.status_code >= 400:
            return []
        data = resp.json() if resp.content else {}
    except Exception:
        return []

    out: list[dict] = []
    rows = data.get("results") if isinstance(data, dict) else []
    if not isinstance(rows, list):
        rows = []

    for row in rows:
        if not isinstance(row, dict):
            continue
        loc = ((row.get("geometry") or {}).get("location") or {})
        lat = _parse_float(loc.get("lat"))
        lon = _parse_float(loc.get("lng"))
        if lat is None or lon is None:
            continue

        types = row.get("types") or []
        item_cat = "all"
        if "airport" in types:
            item_cat = "airport"
        elif any(t in types for t in ("train_station", "subway_station", "transit_station")):
            item_cat = "station"
        elif "locality" in types or "administrative_area_level_1" in types:
            item_cat = "city"

        if category in {"airport", "station", "city"} and item_cat != category:
            continue

        out.append(
            {
                "name": (row.get("name") or "").strip(),
                "sub": (row.get("formatted_address") or row.get("vicinity") or "").strip(),
                "lat": lat,
                "lon": lon,
                "category": item_cat,
                "place_id": row.get("place_id"),
            }
        )
        if len(out) >= max(1, int(limit or 10)):
            break
    return out


def search_rental_locations(
    query: str | None,
    category: str | None = "all",
    limit: int = 10,
    country_code: str | None = None,
) -> list[dict]:
    q = (query or "").strip()

    cat = (category or "all").strip().lower()
    if cat not in {"all", "airport", "station", "city"}:
        cat = "all"

    preset_rows = _match_preset(q, cat, limit, country_code)
    if preset_rows and q:
        return preset_rows

    google_rows = _google_places_search(q, cat, limit, country_code) if q else []
    if google_rows:
        return google_rows

    return preset_rows or _match_preset(q, cat, limit, country_code)


def parse_rental_search_results(raw: dict | None) -> list[dict]:
    if not isinstance(raw, dict):
        return []

    results: list[dict] = []
    seen: set[tuple] = set()

    def _num(v):
        n = _coerce_number(v)
        return int(round(n)) if n is not None else None

    def _first_number(node, prefer_price=True):
        if isinstance(node, (int, float)):
            return float(node)
        if isinstance(node, str):
            s = node.strip().replace(",", "")
            m = re.search(r"-?\d+(?:\.\d+)?", s)
            if m:
                try:
                    return float(m.group(0))
                except Exception:
                    return None
            return None
        if isinstance(node, dict):
            if prefer_price:
                for k, v in node.items():
                    lk = str(k).lower()
                    if any(x in lk for x in ("price", "amount", "total", "fare", "cost", "pay", "value")):
                        n = _first_number(v, prefer_price=False)
                        if n is not None:
                            return n
            for v in node.values():
                n = _first_number(v, prefer_price=False)
                if n is not None:
                    return n
        elif isinstance(node, list):
            for v in node:
                n = _first_number(v, prefer_price=False)
                if n is not None:
                    return n
        return None

    def _walk(node):
        if isinstance(node, dict):
            lower_keys = {str(k).lower() for k in node.keys()}
            vehicle_key_hints = {
                "car_name", "vehicle_name", "vehicle", "vehiclename", "carmodel", "model",
                "seats", "seat_count", "passengers", "transmission", "gearbox",
                "luggage", "baggage", "fuel_policy", "fuelpolicy",
            }
            provider_meta_keys = {"provider_name", "logo", "reviews", "optimised_for_mobile", "in_progress", "errored"}
            if (lower_keys & provider_meta_keys) and not (lower_keys & vehicle_key_hints):
                for v in node.values():
                    _walk(v)
                return

            name = None
            for k in (
                "car_name", "name", "vehicleName", "vehicle_name", "carModel",
                "model", "title", "display_name", "vehicle",
            ):
                v = node.get(k)
                if isinstance(v, str) and v.strip():
                    name = v.strip()
                    break

            price = None
            currency = None
            for obj in [node, node.get("price"), node.get("pricing"), node.get("priceBreakdown"), node.get("quote")]:
                if not isinstance(obj, dict):
                    continue
                if price is None:
                    price = _num(
                        obj.get("amount")
                        or obj.get("value")
                        or obj.get("price")
                        or obj.get("total")
                        or obj.get("minPrice")
                        or obj.get("gross")
                        or obj.get("payable")
                    )
                currency = currency or obj.get("currency") or obj.get("currency_code")

            if price is None:
                n = _first_number(node)
                price = int(round(n)) if n is not None else None

            image = None
            for k in (
                "image", "image_url", "photo_url", "thumbnail", "photo",
                "img", "vndr_img", "vehicle_image", "car_image", "imageUrl",
            ):
                v = node.get(k)
                if isinstance(v, str) and v.strip():
                    image = v.strip()
                    break

            supplier = None
            for k in (
                "supplier_name", "provider_name", "providerName", "vendorName",
                "vendor", "company", "supplier", "merchant_name", "vndr",
            ):
                v = node.get(k)
                if isinstance(v, str) and v.strip():
                    supplier = v.strip()
                    break

            specs = []
            seat_count = None
            for k in ("seats", "seat_count", "passengers", "passengerQuantity", "seat"):
                if node.get(k) is not None:
                    seat_count = _num(node.get(k))
                    if seat_count is not None:
                        seat_count = int(seat_count)
                        specs.append(f"{seat_count}인승")
                        break

            bags = _num(node.get("bags") or node.get("luggage") or node.get("baggage"))
            if bags is not None:
                specs.append(f"가방 {bags}")

            transmission = None
            for k in ("transmission", "gearbox", "transmissionType", "trans"):
                v = node.get(k)
                if isinstance(v, str) and v.strip():
                    transmission = v.strip()
                    break
            if transmission:
                specs.append(transmission)

            fuel_policy = None
            for k in ("fuel_policy", "fuelPolicy", "fuel_type", "fuelType", "fuel_pol"):
                v = node.get(k)
                if isinstance(v, str) and v.strip():
                    fuel_policy = v.strip()
                    break
            if fuel_policy:
                specs.append(fuel_policy)

            vendor_rating = _coerce_number(node.get("supplier_rating") or node.get("providerRating") or node.get("rating"))

            hay = " ".join([name or "", supplier or ""]).lower()
            looks_like_car = any(
                x in hay
                for x in ["toyota", "hyundai", "kia", "nissan", "suv", "sedan", "wagon", "van", "car", "compact", "economy"]
            )
            if name and (price is not None or transmission or seat_count or image):
                looks_like_car = True
            if supplier and (price is not None or image or transmission):
                looks_like_car = True

            if looks_like_car:
                if not name and supplier and price is not None:
                    name = f"{supplier} 렌터카"
                if not name and price is None:
                    for v in node.values():
                        _walk(v)
                    return

                key = (name or "", supplier or "", price or 0)
                if key not in seen:
                    seen.add(key)
                    results.append(
                        {
                            "name": name,
                            "supplier": supplier or "Rental Partner",
                            "price": price,
                            "currency": currency or "KRW",
                            "image": image,
                            "specs": specs,
                            "seats": seat_count,
                            "transmission": transmission,
                            "fuel_policy": fuel_policy,
                            "rating": float(vendor_rating) if vendor_rating is not None else None,
                        }
                    )

            for v in node.values():
                _walk(v)
        elif isinstance(node, list):
            for x in node:
                _walk(x)

    _walk(raw)
    results.sort(key=lambda x: x.get("price") or 10**12)
    return results[:24]


def calc_rental_days(pickup_at: str | None, dropoff_at: str | None) -> int | None:
    try:
        if not pickup_at or not dropoff_at:
            return None
        s = datetime.datetime.strptime(pickup_at, "%Y-%m-%d %H:%M")
        e = datetime.datetime.strptime(dropoff_at, "%Y-%m-%d %H:%M")
        if e <= s:
            return None
        hours = (e - s).total_seconds() / 3600.0
        return max(1, int((hours + 23.9999) // 24))
    except Exception:
        return None
