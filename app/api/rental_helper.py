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

    def _normalize_query_alias(text: str) -> str:
        s = (text or "").strip().lower()
        alias = {
            "홋카이도": "삿포로",
            "혹카이도": "삿포로",
            "북해도": "삿포로",
            "벳부": "벳푸",
            "beppu": "벳푸",
            "hokkaido": "삿포로",
            "sapporo": "삿포로",
            "new york": "뉴욕",
            "newyork": "뉴욕",
            "ho chi minh": "호치민",
            "hochiminh": "호치민",
            "hochiminhcity": "호치민",
            "saigon": "호치민",
        }
        return alias.get(s, s)

    q_norm = _normalize_query_alias(q)

    def _preset_locations() -> list[dict]:
        # Country is used only for filtering and removed before return.
        return [
            # Korea
            {"name": "서울", "sub": "대한민국 서울", "lat": 37.5665, "lon": 126.9780, "category": "city", "country": "KR"},
            {"name": "서울역", "sub": "대한민국 서울", "lat": 37.5547, "lon": 126.9706, "category": "station", "country": "KR"},
            {"name": "강남역", "sub": "대한민국 서울", "lat": 37.4979, "lon": 127.0276, "category": "station", "country": "KR"},
            {"name": "김포공항 (GMP)", "sub": "대한민국 서울", "lat": 37.5583, "lon": 126.7906, "category": "airport", "country": "KR"},
            {"name": "인천국제공항 (ICN)", "sub": "대한민국 인천", "lat": 37.4602, "lon": 126.4407, "category": "airport", "country": "KR"},
            {"name": "부산", "sub": "대한민국 부산", "lat": 35.1796, "lon": 129.0756, "category": "city", "country": "KR"},
            {"name": "부산역", "sub": "대한민국 부산", "lat": 35.1151, "lon": 129.0414, "category": "station", "country": "KR"},
            {"name": "김해국제공항 (PUS)", "sub": "대한민국 부산", "lat": 35.1795, "lon": 128.9382, "category": "airport", "country": "KR"},
            {"name": "제주", "sub": "대한민국 제주", "lat": 33.4996, "lon": 126.5312, "category": "city", "country": "KR"},
            {"name": "제주국제공항 (CJU)", "sub": "대한민국 제주", "lat": 33.5104, "lon": 126.4928, "category": "airport", "country": "KR"},
            # Japan
            {"name": "도쿄", "sub": "일본 도쿄", "lat": 35.6762, "lon": 139.6503, "category": "city", "country": "JP"},
            {"name": "도쿄역", "sub": "일본 도쿄", "lat": 35.6812, "lon": 139.7671, "category": "station", "country": "JP"},
            {"name": "하네다공항 (HND)", "sub": "일본 도쿄", "lat": 35.5494, "lon": 139.7798, "category": "airport", "country": "JP"},
            {"name": "나리타공항 (NRT)", "sub": "일본 지바", "lat": 35.7719, "lon": 140.3929, "category": "airport", "country": "JP"},
            {"name": "오사카", "sub": "일본 오사카", "lat": 34.6937, "lon": 135.5023, "category": "city", "country": "JP"},
            {"name": "신오사카역", "sub": "일본 오사카", "lat": 34.7335, "lon": 135.5003, "category": "station", "country": "JP"},
            {"name": "간사이국제공항 (KIX)", "sub": "일본 오사카", "lat": 34.4347, "lon": 135.2440, "category": "airport", "country": "JP"},
            {"name": "삿포로", "sub": "일본 홋카이도", "lat": 43.0618, "lon": 141.3545, "category": "city", "country": "JP"},
            {"name": "삿포로역", "sub": "일본 홋카이도", "lat": 43.0687, "lon": 141.3508, "category": "station", "country": "JP"},
            {"name": "신치토세공항 (CTS)", "sub": "일본 홋카이도", "lat": 42.7752, "lon": 141.6923, "category": "airport", "country": "JP"},
            {"name": "후쿠오카", "sub": "일본 후쿠오카", "lat": 33.5902, "lon": 130.4017, "category": "city", "country": "JP"},
            {"name": "후쿠오카공항 (FUK)", "sub": "일본 후쿠오카", "lat": 33.5859, "lon": 130.4507, "category": "airport", "country": "JP"},
            {"name": "나고야", "sub": "일본 아이치", "lat": 35.1815, "lon": 136.9066, "category": "city", "country": "JP"},
            {"name": "나고야역", "sub": "일본 아이치", "lat": 35.1709, "lon": 136.8815, "category": "station", "country": "JP"},
            {"name": "중부국제공항 (NGO)", "sub": "일본 아이치", "lat": 34.8584, "lon": 136.8054, "category": "airport", "country": "JP"},
            {"name": "교토", "sub": "일본 교토", "lat": 35.0116, "lon": 135.7681, "category": "city", "country": "JP"},
            {"name": "교토역", "sub": "일본 교토", "lat": 34.9855, "lon": 135.7586, "category": "station", "country": "JP"},
            {"name": "벳푸", "sub": "일본 오이타 벳푸", "lat": 33.2795, "lon": 131.4970, "category": "city", "country": "JP"},
            {"name": "벳푸역", "sub": "일본 오이타 벳푸", "lat": 33.2799, "lon": 131.5007, "category": "station", "country": "JP"},
            {"name": "오이타공항 (OIT)", "sub": "일본 오이타", "lat": 33.4794, "lon": 131.7369, "category": "airport", "country": "JP"},
            {"name": "나하", "sub": "일본 오키나와", "lat": 26.2124, "lon": 127.6809, "category": "city", "country": "JP"},
            {"name": "나하공항 (OKA)", "sub": "일본 오키나와", "lat": 26.1958, "lon": 127.6460, "category": "airport", "country": "JP"},
            # USA
            {"name": "뉴욕", "sub": "미국 뉴욕", "lat": 40.7128, "lon": -74.0060, "category": "city", "country": "US"},
            {"name": "JFK 공항 (JFK)", "sub": "미국 뉴욕", "lat": 40.6413, "lon": -73.7781, "category": "airport", "country": "US"},
            {"name": "뉴어크 공항 (EWR)", "sub": "미국 뉴저지", "lat": 40.6895, "lon": -74.1745, "category": "airport", "country": "US"},
            {"name": "LGA 공항 (LGA)", "sub": "미국 뉴욕", "lat": 40.7769, "lon": -73.8740, "category": "airport", "country": "US"},
            # UK/France/Italy
            {"name": "런던", "sub": "영국 런던", "lat": 51.5072, "lon": -0.1276, "category": "city", "country": "GB"},
            {"name": "히드로공항 (LHR)", "sub": "영국 런던", "lat": 51.4700, "lon": -0.4543, "category": "airport", "country": "GB"},
            {"name": "파리", "sub": "프랑스 파리", "lat": 48.8566, "lon": 2.3522, "category": "city", "country": "FR"},
            {"name": "샤를드골공항 (CDG)", "sub": "프랑스 파리", "lat": 49.0097, "lon": 2.5479, "category": "airport", "country": "FR"},
            {"name": "로마", "sub": "이탈리아 로마", "lat": 41.9028, "lon": 12.4964, "category": "city", "country": "IT"},
            {"name": "피우미치노공항 (FCO)", "sub": "이탈리아 로마", "lat": 41.8003, "lon": 12.2389, "category": "airport", "country": "IT"},
            # Southeast Asia / Asia
            {"name": "방콕", "sub": "태국 방콕", "lat": 13.7563, "lon": 100.5018, "category": "city", "country": "TH"},
            {"name": "수완나품공항 (BKK)", "sub": "태국 방콕", "lat": 13.6900, "lon": 100.7501, "category": "airport", "country": "TH"},
            {"name": "하노이", "sub": "베트남 하노이", "lat": 21.0278, "lon": 105.8342, "category": "city", "country": "VN"},
            {"name": "노이바이공항 (HAN)", "sub": "베트남 하노이", "lat": 21.2212, "lon": 105.8072, "category": "airport", "country": "VN"},
            {"name": "호치민", "sub": "베트남 호치민", "lat": 10.8231, "lon": 106.6297, "category": "city", "country": "VN"},
            {"name": "탄손녓공항 (SGN)", "sub": "베트남 호치민", "lat": 10.8188, "lon": 106.6519, "category": "airport", "country": "VN"},
            {"name": "다낭", "sub": "베트남 다낭", "lat": 16.0544, "lon": 108.2022, "category": "city", "country": "VN"},
            {"name": "다낭공항 (DAD)", "sub": "베트남 다낭", "lat": 16.0439, "lon": 108.1993, "category": "airport", "country": "VN"},
            {"name": "싱가포르", "sub": "싱가포르", "lat": 1.3521, "lon": 103.8198, "category": "city", "country": "SG"},
            {"name": "창이공항 (SIN)", "sub": "싱가포르", "lat": 1.3644, "lon": 103.9915, "category": "airport", "country": "SG"},
            {"name": "타이베이", "sub": "대만 타이베이", "lat": 25.0330, "lon": 121.5654, "category": "city", "country": "TW"},
            {"name": "타오위안공항 (TPE)", "sub": "대만 타오위안", "lat": 25.0797, "lon": 121.2342, "category": "airport", "country": "TW"},
            # Australia
            {"name": "시드니", "sub": "호주 시드니", "lat": -33.8688, "lon": 151.2093, "category": "city", "country": "AU"},
            {"name": "시드니공항 (SYD)", "sub": "호주 시드니", "lat": -33.9399, "lon": 151.1753, "category": "airport", "country": "AU"},
            {"name": "멜버른", "sub": "호주 멜버른", "lat": -37.8136, "lon": 144.9631, "category": "city", "country": "AU"},
            {"name": "멜버른공항 (MEL)", "sub": "호주 멜버른", "lat": -37.6690, "lon": 144.8410, "category": "airport", "country": "AU"},
            {"name": "브리즈번", "sub": "호주 브리즈번", "lat": -27.4698, "lon": 153.0251, "category": "city", "country": "AU"},
            {"name": "브리즈번공항 (BNE)", "sub": "호주 브리즈번", "lat": -27.3842, "lon": 153.1175, "category": "airport", "country": "AU"},
            # UAE
            {"name": "두바이", "sub": "아랍에미리트 두바이", "lat": 25.2048, "lon": 55.2708, "category": "city", "country": "AE"},
            {"name": "두바이공항 (DXB)", "sub": "아랍에미리트 두바이", "lat": 25.2532, "lon": 55.3657, "category": "airport", "country": "AE"},
        ]

    def _preset_match() -> list[dict]:
        ql = q_norm.lower()
        out = []
        for item in _preset_locations():
            if country_code and item.get("country") != country_code:
                continue
            if category in {"airport", "station", "city"} and item.get("category") != category:
                continue
            hay = f"{item.get('name', '')} {item.get('sub', '')}".lower()
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
        "GB": "영국",
        "FR": "프랑스",
        "IT": "이탈리아",
        "AE": "아랍에미리트",
        "TH": "태국",
        "VN": "베트남",
        "SG": "싱가포르",
        "TW": "대만",
        "AU": "호주",
    }.get(country_code, "")

    # fallback local candidates = preset pool (already broadened)
    local_candidates = [{k: v for k, v in x.items() if k != "country"} | {"_country": x.get("country")} for x in _preset_locations()]

    def _local_match() -> list[dict]:
        ql = q_norm.lower()
        out = []
        for item in local_candidates:
            if category in {"airport", "station", "city"} and item["category"] != category:
                continue
            hay = f"{item['name']} {item['sub']}".lower()
            if country_code and item.get("_country") != country_code:
                continue
            if country_hint_name and country_hint_name.lower() not in hay and country_code and item.get("_country") != country_code:
                continue
            if ql in hay:
                out.append({k: v for k, v in item.items() if k != "_country"})
            if len(out) >= max(1, limit):
                break
        if out:
            return out
        # relax country filter
        for item in local_candidates:
            if category in {"airport", "station", "city"} and item["category"] != category:
                continue
            hay = f"{item['name']} {item['sub']}".lower()
            if ql in hay:
                out.append({k: v for k, v in item.items() if k != "_country"})
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

    def _first_num(node):
        if isinstance(node, (int, float, str)):
            return _coerce_number(node)
        if isinstance(node, dict):
            for k, v in node.items():
                lk = str(k).lower()
                if any(x in lk for x in ("price", "amount", "value", "total", "cost", "fare", "pay")):
                    n = _first_num(v)
                    if n is not None:
                        return n
        elif isinstance(node, list):
            for x in node:
                n = _first_num(x)
                if n is not None:
                    return n
        return None

    def _pick(node, *keys):
        for k in keys:
            v = node.get(k)
            if isinstance(v, str) and v.strip():
                return v.strip()
        return None

    def _is_generic_rental_name(name_val: str | None, supplier_val: str | None) -> bool:
        n = str(name_val or "").strip().lower()
        if not n:
            return True
        if n in {"rental car", "rental", "렌터카", "렌터카 옵션", "car"}:
            return True
        if n.endswith("렌터카") or n.endswith("rental car") or n.endswith(" rental"):
            s = str(supplier_val or "").strip().lower()
            core = n.replace("렌터카", "").replace("rental car", "").replace("rental", "").strip()
            if not core or (s and core == s):
                return True
        return False

    def _walk(node):
        if isinstance(node, dict):
            name = _pick(
                node,
                "car_name", "name", "vehicleName", "vehicle_name", "carModel", "model", "title",
                "display_name", "vehicle", "category", "vehicle_class", "sipp",
            )

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
                        or obj.get("total_price")
                        or obj.get("base_price")
                    )
                currency = currency or obj.get("currency") or obj.get("currency_code")
            if price is None:
                n = _first_num(node)
                price = int(n) if n is not None else None

            image = _pick(
                node,
                "image", "image_url", "photo_url", "thumbnail", "photo", "img", "vehicle_image",
            )

            supplier = _pick(
                node,
                "supplier_name", "provider_name", "vendorName", "company", "supplier", "vndr",
            )

            specs = []
            seat_count = None
            for k in ("seats", "seat_count", "passengers", "passengerQuantity", "seat"):
                if node.get(k) is not None:
                    seat_count = _num(node.get(k))
                    if seat_count is not None:
                        seat_count = int(seat_count)
                        specs.append(f"{seat_count}\uC778\uC2B9")
                        break

            bags = _num(node.get("bags") or node.get("luggage") or node.get("baggage"))
            if bags is not None:
                specs.append(f"\uAC00\uBC29 {bags}")

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

            if node.get("air_conditioning") is True or node.get("airConditioning") is True:
                specs.append("\uC5D0\uC5B4\uCEE8")

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
                category = _pick(node, "vehicle_class", "category", "car_type", "sipp")
                safe_name = name or category or "\uCC28\uC885 \uC815\uBCF4 \uC5C6\uC74C"
                if _is_generic_rental_name(safe_name, supplier):
                    safe_name = category or "\uCC28\uC885 \uC815\uBCF4 \uC5C6\uC74C"
                key = (safe_name, supplier or "", price or 0)
                if key not in seen:
                    seen.add(key)
                    results.append(
                        {
                            "name": safe_name,
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
