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


def _preset_locations() -> list[dict]:
    # Broad, key travel hubs used when Google Places key is unavailable.
    return [
        {"name": "Seoul", "sub": "South Korea", "lat": 37.5665, "lon": 126.9780, "category": "city", "country_code": "KR", "aliases": ["서울", "seoul"]},
        {"name": "Incheon Intl Airport (ICN)", "sub": "Incheon, South Korea", "lat": 37.4602, "lon": 126.4407, "category": "airport", "country_code": "KR", "aliases": ["인천", "icn"]},
        {"name": "Busan", "sub": "South Korea", "lat": 35.1796, "lon": 129.0756, "category": "city", "country_code": "KR", "aliases": ["부산", "busan"]},
        {"name": "Gimhae Airport (PUS)", "sub": "Busan, South Korea", "lat": 35.1795, "lon": 128.9382, "category": "airport", "country_code": "KR", "aliases": ["김해", "pus"]},
        {"name": "Tokyo", "sub": "Japan", "lat": 35.6762, "lon": 139.6503, "category": "city", "country_code": "JP", "aliases": ["도쿄", "tokyo"]},
        {"name": "Narita Airport (NRT)", "sub": "Tokyo, Japan", "lat": 35.7719, "lon": 140.3929, "category": "airport", "country_code": "JP", "aliases": ["나리타", "nrt"]},
        {"name": "Haneda Airport (HND)", "sub": "Tokyo, Japan", "lat": 35.5494, "lon": 139.7798, "category": "airport", "country_code": "JP", "aliases": ["하네다", "hnd"]},
        {"name": "Osaka", "sub": "Japan", "lat": 34.6937, "lon": 135.5023, "category": "city", "country_code": "JP", "aliases": ["오사카", "osaka"]},
        {"name": "Kansai Airport (KIX)", "sub": "Osaka, Japan", "lat": 34.4347, "lon": 135.2440, "category": "airport", "country_code": "JP", "aliases": ["간사이", "kix"]},
        {"name": "Sapporo", "sub": "Japan", "lat": 43.0618, "lon": 141.3545, "category": "city", "country_code": "JP", "aliases": ["삿포로", "sapporo"]},
        {"name": "New York", "sub": "United States", "lat": 40.7128, "lon": -74.0060, "category": "city", "country_code": "US", "aliases": ["뉴욕", "new york", "nyc"]},
        {"name": "JFK Airport (JFK)", "sub": "New York, United States", "lat": 40.6413, "lon": -73.7781, "category": "airport", "country_code": "US", "aliases": ["jfk"]},
        {"name": "Los Angeles", "sub": "United States", "lat": 34.0522, "lon": -118.2437, "category": "city", "country_code": "US", "aliases": ["la", "los angeles"]},
        {"name": "LAX Airport (LAX)", "sub": "Los Angeles, United States", "lat": 33.9416, "lon": -118.4085, "category": "airport", "country_code": "US", "aliases": ["lax"]},
        {"name": "London", "sub": "United Kingdom", "lat": 51.5072, "lon": -0.1276, "category": "city", "country_code": "GB", "aliases": ["런던", "london"]},
        {"name": "Heathrow Airport (LHR)", "sub": "London, United Kingdom", "lat": 51.4700, "lon": -0.4543, "category": "airport", "country_code": "GB", "aliases": ["lhr", "heathrow"]},
        {"name": "Paris", "sub": "France", "lat": 48.8566, "lon": 2.3522, "category": "city", "country_code": "FR", "aliases": ["파리", "paris"]},
        {"name": "CDG Airport (CDG)", "sub": "Paris, France", "lat": 49.0097, "lon": 2.5479, "category": "airport", "country_code": "FR", "aliases": ["cdg"]},
        {"name": "Rome", "sub": "Italy", "lat": 41.9028, "lon": 12.4964, "category": "city", "country_code": "IT", "aliases": ["로마", "rome"]},
        {"name": "Fiumicino Airport (FCO)", "sub": "Rome, Italy", "lat": 41.8003, "lon": 12.2389, "category": "airport", "country_code": "IT", "aliases": ["fco"]},
        {"name": "Dubai", "sub": "United Arab Emirates", "lat": 25.2048, "lon": 55.2708, "category": "city", "country_code": "AE", "aliases": ["두바이", "dubai"]},
        {"name": "Dubai Airport (DXB)", "sub": "Dubai, United Arab Emirates", "lat": 25.2532, "lon": 55.3657, "category": "airport", "country_code": "AE", "aliases": ["dxb"]},
        {"name": "Bangkok", "sub": "Thailand", "lat": 13.7563, "lon": 100.5018, "category": "city", "country_code": "TH", "aliases": ["방콕", "bangkok"]},
        {"name": "Suvarnabhumi Airport (BKK)", "sub": "Bangkok, Thailand", "lat": 13.6900, "lon": 100.7501, "category": "airport", "country_code": "TH", "aliases": ["수완나품", "bkk"]},
        {"name": "Singapore", "sub": "Singapore", "lat": 1.3521, "lon": 103.8198, "category": "city", "country_code": "SG", "aliases": ["싱가포르", "singapore"]},
        {"name": "Changi Airport (SIN)", "sub": "Singapore", "lat": 1.3644, "lon": 103.9915, "category": "airport", "country_code": "SG", "aliases": ["sin", "changi"]},
        {"name": "Hong Kong", "sub": "Hong Kong", "lat": 22.3193, "lon": 114.1694, "category": "city", "country_code": "HK", "aliases": ["홍콩", "hong kong", "hk"]},
        {"name": "Hong Kong Intl Airport (HKG)", "sub": "Hong Kong", "lat": 22.3080, "lon": 113.9185, "category": "airport", "country_code": "HK", "aliases": ["hkg"]},
        {"name": "Taipei", "sub": "Taiwan", "lat": 25.0330, "lon": 121.5654, "category": "city", "country_code": "TW", "aliases": ["타이베이", "taipei"]},
        {"name": "Taoyuan Airport (TPE)", "sub": "Taipei, Taiwan", "lat": 25.0797, "lon": 121.2342, "category": "airport", "country_code": "TW", "aliases": ["tpe"]},
        {"name": "Sydney", "sub": "Australia", "lat": -33.8688, "lon": 151.2093, "category": "city", "country_code": "AU", "aliases": ["시드니", "sydney"]},
        {"name": "Sydney Airport (SYD)", "sub": "Sydney, Australia", "lat": -33.9399, "lon": 151.1753, "category": "airport", "country_code": "AU", "aliases": ["syd"]},
    ]


def _match_preset(query: str, category: str, limit: int, country_code: str | None) -> list[dict]:
    q = (query or "").strip().lower()
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

    # Relax country filter once to avoid empty UX.
    if cc:
        return _match_preset(query=query, category=category, limit=limit, country_code=None)
    return []


def _google_places_search(query: str, category: str, limit: int) -> list[dict]:
    api_key = (os.getenv("GOOGLE_PLACES_API_KEY") or "").strip()
    if not api_key:
        return []

    type_hint = None
    if category == "airport":
        type_hint = "airport"
    elif category == "station":
        type_hint = "train_station"

    params = {
        "query": query,
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
    if not q:
        return []

    cat = (category or "all").strip().lower()
    if cat not in {"all", "airport", "station", "city"}:
        cat = "all"

    # 1) Try Google Places for broad global coverage when key is configured.
    google_rows = _google_places_search(q, cat, limit)
    if google_rows:
        return google_rows

    # 2) Local preset fallback.
    return _match_preset(q, cat, limit, country_code)


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
            # Skip provider/status metadata nodes that are not actual vehicles.
            lower_keys = {str(k).lower() for k in node.keys()}
            vehicle_key_hints = {
                "car_name", "vehicle_name", "vehicle", "vehicleName", "carModel", "model",
                "seats", "seat_count", "passengers", "transmission", "gearbox",
                "luggage", "baggage", "fuel_policy", "fuelPolicy",
            }
            provider_meta_keys = {"provider_name", "logo", "reviews", "optimised_for_mobile", "in_progress", "errored"}
            if (lower_keys & provider_meta_keys) and not (lower_keys & vehicle_key_hints):
                for v in node.values():
                    _walk(v)
                return

            name = None
            for k in (
                "car_name",
                "name",
                "vehicleName",
                "vehicle_name",
                "carModel",
                "model",
                "title",
                "display_name",
                "vehicle",
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
                "image",
                "image_url",
                "photo_url",
                "thumbnail",
                "photo",
                "img",
                "vndr_img",
                "vehicle_image",
                "car_image",
                "imageUrl",
            ):
                v = node.get(k)
                if isinstance(v, str) and v.strip():
                    image = v.strip()
                    break

            supplier = None
            for k in (
                "supplier_name",
                "provider_name",
                "providerName",
                "vendorName",
                "vendor",
                "company",
                "supplier",
                "merchant_name",
                "vndr",
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
