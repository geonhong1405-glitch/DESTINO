import os
import re
import datetime
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


def search_rental_locations(
    query: str | None,
    category: str | None = "all",
    limit: int = 10,
    country_code: str | None = None,
) -> list[dict]:
    q = (query or "").strip()
    if not q:
        return []
    category = (category or "all").strip().lower()
    country_code = (country_code or "").strip().upper()

    # Fast preset matcher: protects destination/location search even if local seed text is mis-encoded.
    def _normalize_query_alias(text: str) -> str:
        s = (text or "").strip().lower()
        alias = {
            "\ud6d7\uce74\uc774\ub3c4": "\uc0bf\ud3ec\ub85c",
            "\ud649\uce74\uc774\ub3c4": "\uc0bf\ud3ec\ub85c",
            "\ubd81\ud574\ub3c4": "\uc0bf\ud3ec\ub85c",
            "\ubcb3\ubd80": "\ubcb3\ud478",
            "\ubcb3\ud478": "\ubcb3\ud478",
            "\ubc43\ubd80": "\ubcb3\ud478",
            "\ubc43\ud478": "\ubcb3\ud478",
            "hokkaido": "\uc0bf\ud3ec\ub85c",
            "sapporo": "\uc0bf\ud3ec\ub85c",
            "beppu": "\ubcb3\ud478",
        }
        return alias.get(s, s)

    q_norm = _normalize_query_alias(q)

    def _preset_locations() -> list[dict]:
        return [
            {"name": "\ub3c4\ucfc4", "sub": "\uc77c\ubcf8 \ub3c4\ucfc4", "lat": 35.6762, "lon": 139.6503, "category": "city", "country": "JP"},
            {"name": "\ub3c4\ucfc4\uc5ed", "sub": "\uc77c\ubcf8 \ub3c4\ucfc4", "lat": 35.6812, "lon": 139.7671, "category": "station", "country": "JP"},
            {"name": "\ud558\ub124\ub2e4\uacf5\ud56d (HND)", "sub": "\uc77c\ubcf8 \ub3c4\ucfc4", "lat": 35.5494, "lon": 139.7798, "category": "airport", "country": "JP"},
            {"name": "\ub098\ub9ac\ud0c0\uacf5\ud56d (NRT)", "sub": "\uc77c\ubcf8 \uce58\ubc14", "lat": 35.7719, "lon": 140.3929, "category": "airport", "country": "JP"},
            {"name": "\uc624\uc0ac\uce74", "sub": "\uc77c\ubcf8 \uc624\uc0ac\uce74", "lat": 34.6937, "lon": 135.5023, "category": "city", "country": "JP"},
            {"name": "\uc2e0\uc624\uc0ac\uce74\uc5ed", "sub": "\uc77c\ubcf8 \uc624\uc0ac\uce74", "lat": 34.7335, "lon": 135.5003, "category": "station", "country": "JP"},
            {"name": "\uac04\uc0ac\uc774\uad6d\uc81c\uacf5\ud56d (KIX)", "sub": "\uc77c\ubcf8 \uc624\uc0ac\uce74", "lat": 34.4347, "lon": 135.2440, "category": "airport", "country": "JP"},
            {"name": "\uc0bf\ud3ec\ub85c", "sub": "\uc77c\ubcf8 \ud64b\uce74\uc774\ub3c4", "lat": 43.0618, "lon": 141.3545, "category": "city", "country": "JP"},
            {"name": "\uc0bf\ud3ec\ub85c\uc5ed", "sub": "\uc77c\ubcf8 \ud64b\uce74\uc774\ub3c4", "lat": 43.0687, "lon": 141.3508, "category": "station", "country": "JP"},
            {"name": "\uc2e0\uce58\ud1a0\uc138\uacf5\ud56d (CTS)", "sub": "\uc77c\ubcf8 \ud64b\uce74\uc774\ub3c4", "lat": 42.7752, "lon": 141.6923, "category": "airport", "country": "JP"},
            {"name": "\ud6c4\ucfe0\uc624\uce74", "sub": "\uc77c\ubcf8 \ud6c4\ucfe0\uc624\uce74", "lat": 33.5902, "lon": 130.4017, "category": "city", "country": "JP"},
            {"name": "\ud6c4\ucfe0\uc624\uce74\uacf5\ud56d (FUK)", "sub": "\uc77c\ubcf8 \ud6c4\ucfe0\uc624\uce74", "lat": 33.5859, "lon": 130.4507, "category": "airport", "country": "JP"},
            {"name": "\ub098\uace0\uc57c", "sub": "\uc77c\ubcf8 \uc544\uc774\uce58", "lat": 35.1815, "lon": 136.9066, "category": "city", "country": "JP"},
            {"name": "\ub098\uace0\uc57c\uc5ed", "sub": "\uc77c\ubcf8 \uc544\uc774\uce58", "lat": 35.1709, "lon": 136.8815, "category": "station", "country": "JP"},
            {"name": "\uc911\ubd80\uad6d\uc81c\uacf5\ud56d (NGO)", "sub": "\uc77c\ubcf8 \uc544\uc774\uce58", "lat": 34.8584, "lon": 136.8054, "category": "airport", "country": "JP"},
            {"name": "\uad50\ud1a0", "sub": "\uc77c\ubcf8 \uad50\ud1a0", "lat": 35.0116, "lon": 135.7681, "category": "city", "country": "JP"},
            {"name": "\uad50\ud1a0\uc5ed", "sub": "\uc77c\ubcf8 \uad50\ud1a0", "lat": 34.9855, "lon": 135.7586, "category": "station", "country": "JP"},
            {"name": "\uace0\ubca0", "sub": "\uc77c\ubcf8 \ud6a8\uace0", "lat": 34.6901, "lon": 135.1955, "category": "city", "country": "JP"},
            {"name": "\ubcb3\ud478", "sub": "\uc77c\ubcf8 \uc624\uc774\ud0c0 \ubcb3\ud478", "lat": 33.2795, "lon": 131.4970, "category": "city", "country": "JP"},
            {"name": "\ubcb3\ud478\uc5ed", "sub": "\uc77c\ubcf8 \uc624\uc774\ud0c0 \ubcb3\ud478", "lat": 33.2799, "lon": 131.5007, "category": "station", "country": "JP"},
            {"name": "\uc624\uc774\ud0c0\uacf5\ud56d (OIT)", "sub": "\uc77c\ubcf8 \uc624\uc774\ud0c0", "lat": 33.4794, "lon": 131.7369, "category": "airport", "country": "JP"},
            {"name": "\ub098\ud558", "sub": "\uc77c\ubcf8 \uc624\ud0a4\ub098\uc640", "lat": 26.2124, "lon": 127.6809, "category": "city", "country": "JP"},
            {"name": "\ub098\ud558\uacf5\ud56d (OKA)", "sub": "\uc77c\ubcf8 \uc624\ud0a4\ub098\uc640", "lat": 26.1958, "lon": 127.6460, "category": "airport", "country": "JP"},
        ]

    def _preset_match() -> list[dict]:
        ql = q_norm.lower()
        out = []
        for item in _preset_locations():
            if country_code and item.get("country") != country_code:
                continue
            if category in {"airport", "station", "city"} and item.get("category") != category:
                continue
            hay = f"{item.get('name','')} {item.get('sub','')}".lower()
            if ql and ql in hay:
                out.append({k: v for k, v in item.items() if k != "country"})
            if len(out) >= max(1, limit):
                break
        return out

    preset = _preset_match()
    if preset:
        return preset

    country_hint_name = {
        "KR": "대한민국",
        "JP": "일본",
        "US": "미국",
        "FR": "프랑스",
        "AE": "아랍에미리트",
        "TH": "태국",
        "VN": "베트남",
        "SG": "싱가포르",
        "TW": "대만",
    }.get(country_code, "")

    local_candidates = [
        {"name": "서울", "sub": "대한민국 서울", "lat": 37.5665, "lon": 126.9780, "category": "city"},
        {"name": "강남역", "sub": "대한민국 서울", "lat": 37.4979, "lon": 127.0276, "category": "station"},
        {"name": "서울역", "sub": "대한민국 서울", "lat": 37.5547, "lon": 126.9706, "category": "station"},
        {"name": "김포국제공항 (GMP)", "sub": "대한민국 서울", "lat": 37.5583, "lon": 126.7906, "category": "airport"},
        {"name": "인천국제공항 (ICN)", "sub": "대한민국 인천", "lat": 37.4602, "lon": 126.4407, "category": "airport"},
        {"name": "제주국제공항 (CJU)", "sub": "대한민국 제주", "lat": 33.5104, "lon": 126.4928, "category": "airport"},
        {"name": "부산역", "sub": "대한민국 부산", "lat": 35.1151, "lon": 129.0414, "category": "station"},
        {"name": "도쿄", "sub": "일본 도쿄", "lat": 35.6762, "lon": 139.6503, "category": "city"},
        {"name": "도쿄역", "sub": "일본 도쿄", "lat": 35.6812, "lon": 139.7671, "category": "station"},
        {"name": "하네다공항 (HND)", "sub": "일본 도쿄", "lat": 35.5494, "lon": 139.7798, "category": "airport"},
        {"name": "나리타공항 (NRT)", "sub": "일본 지바", "lat": 35.7719, "lon": 140.3929, "category": "airport"},
        {"name": "오사카", "sub": "일본 오사카", "lat": 34.6937, "lon": 135.5023, "category": "city"},
        {"name": "신오사카역", "sub": "일본 오사카", "lat": 34.7335, "lon": 135.5003, "category": "station"},
        {"name": "간사이국제공항 (KIX)", "sub": "일본 오사카", "lat": 34.4347, "lon": 135.2440, "category": "airport"},
        {"name": "교토", "sub": "일본 교토", "lat": 35.0116, "lon": 135.7681, "category": "city"},
        {"name": "교토역", "sub": "일본 교토", "lat": 34.9855, "lon": 135.7586, "category": "station"},
        {"name": "나고야", "sub": "일본 아이치", "lat": 35.1815, "lon": 136.9066, "category": "city"},
        {"name": "나고야역", "sub": "일본 아이치", "lat": 35.1709, "lon": 136.8815, "category": "station"},
        {"name": "나고야 사카에", "sub": "일본 아이치 나고야", "lat": 35.1701, "lon": 136.9086, "category": "city"},
        {"name": "주부 센트레아 공항 (NGO)", "sub": "일본 아이치", "lat": 34.8584, "lon": 136.8054, "category": "airport"},
        {"name": "후쿠오카", "sub": "일본 후쿠오카", "lat": 33.5902, "lon": 130.4017, "category": "city"},
        {"name": "후쿠오카공항 (FUK)", "sub": "일본 후쿠오카", "lat": 33.5859, "lon": 130.4507, "category": "airport"},
    ]

    def _local_match() -> list[dict]:
        ql = q.lower()
        out = []
        for item in local_candidates:
            if category in {"airport", "station", "city"} and item["category"] != category:
                continue
            hay = f"{item['name']} {item['sub']}".lower()
            if country_hint_name and country_hint_name.lower() not in hay:
                continue
            if ql in hay:
                out.append(item)
            if len(out) >= max(1, limit):
                break
        if out:
            return out
        # If country filter made local fallback too strict, relax country filtering.
        for item in local_candidates:
            if category in {"airport", "station", "city"} and item["category"] != category:
                continue
            hay = f"{item['name']} {item['sub']}".lower()
            if ql in hay:
                out.append(item)
            if len(out) >= max(1, limit):
                break
        return out

    api_key = os.getenv("GOOGLE_PLACES_API_KEY")
    if not api_key:
        return _local_match()

    type_hint = None
    if category == "airport":
        type_hint = "airport"
    elif category == "station":
        type_hint = "train_station"

    url = "https://maps.googleapis.com/maps/api/place/textsearch/json"
    google_query = f"{q_norm} {country_hint_name}".strip() if country_hint_name else q_norm
    params = {"query": google_query, "language": "ko", "key": api_key}
    if type_hint:
        params["type"] = type_hint
    try:
        resp = requests.get(url, params=params, timeout=12)
        if resp.status_code >= 400:
            return _local_match()
        data = resp.json()
    except Exception:
        return _local_match()

    out = []
    for row in data.get("results", []) if isinstance(data, dict) else []:
        if not isinstance(row, dict):
            continue
        name = (row.get("name") or "").strip()
        if not name:
            continue
        loc = (((row.get("geometry") or {}).get("location")) or {})
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
                "name": name,
                "sub": (row.get("formatted_address") or row.get("vicinity") or "").strip(),
                "lat": lat,
                "lon": lon,
                "category": item_cat,
                "place_id": row.get("place_id"),
            }
        )
        if len(out) >= max(1, limit):
            break
    return out or _local_match()


def parse_rental_search_results(raw: dict | None) -> list[dict]:
    if not isinstance(raw, dict):
        return []
    results = []
    seen = set()

    def _num(v):
        n = _coerce_number(v)
        return int(n) if n is not None else None

    def _walk(node):
        if isinstance(node, dict):
            name = None
            for k in ("car_name", "name", "vehicleName", "carModel", "model", "title"):
                v = node.get(k)
                if isinstance(v, str) and v.strip():
                    name = v.strip()
                    break

            price = None
            currency = None
            for obj in [node, node.get("price"), node.get("pricing"), node.get("priceBreakdown")]:
                if not isinstance(obj, dict):
                    continue
                if price is None:
                    price = _num(obj.get("amount") or obj.get("value") or obj.get("price") or obj.get("total"))
                currency = currency or obj.get("currency") or obj.get("currency_code")

            image = None
            for k in ("image", "image_url", "photo_url", "thumbnail", "photo"):
                v = node.get(k)
                if isinstance(v, str) and v.strip():
                    image = v.strip()
                    break

            supplier = None
            for k in ("supplier_name", "provider_name", "vendorName", "company", "supplier"):
                v = node.get(k)
                if isinstance(v, str) and v.strip():
                    supplier = v.strip()
                    break

            specs = []
            seat_count = None
            for k in ("seats", "seat_count", "passengers", "passengerQuantity"):
                if node.get(k) is not None:
                    seat_count = _num(node.get(k))
                    if seat_count is not None:
                        seat_count = int(seat_count)
                        specs.append(f"{seat_count}인승")
                        break

            transmission = None
            for k in ("transmission", "gearbox", "transmissionType"):
                v = node.get(k)
                if isinstance(v, str) and v.strip():
                    transmission = v.strip()
                    break
            if transmission:
                specs.append(transmission)

            fuel_policy = None
            for k in ("fuel_policy", "fuelPolicy", "fuel_type", "fuelType"):
                v = node.get(k)
                if isinstance(v, str) and v.strip():
                    fuel_policy = v.strip()
                    break
            if fuel_policy:
                specs.append(fuel_policy)

            if node.get("air_conditioning") is True or node.get("airConditioning") is True:
                specs.append("에어컨")

            vendor_rating = _coerce_number(node.get("supplier_rating") or node.get("providerRating") or node.get("rating"))

            looks_like_car = False
            hay = " ".join([name or "", supplier or ""]).lower()
            if any(x in hay for x in ["toyota", "hyundai", "kia", "nissan", "suv", "sedan", "wagon", "van", "car", "compact", "economy"]):
                looks_like_car = True
            if name and price is not None:
                looks_like_car = True

            if looks_like_car:
                key = (name or "", supplier or "", price or 0)
                if key not in seen:
                    seen.add(key)
                    results.append(
                        {
                            "name": name or "렌터카 옵션",
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
