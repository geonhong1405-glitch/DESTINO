import datetime as _dt
import os
import re
import time
from typing import Any

import requests
from dotenv import load_dotenv

load_dotenv()

SKY_RAPIDAPI_KEY = os.getenv("SKY_RAPIDAPI_KEY")
SKY_RAPIDAPI_HOST = os.getenv("SKY_RAPIDAPI_HOST", "flights-sky.p.rapidapi.com")


def _clean_env_token(value: str | None) -> str:
    s = str(value or "").strip()
    if not s:
        return ""
    if "#" in s:
        s = s.split("#", 1)[0].strip()
    return s


def _headers() -> dict[str, str]:
    return {
        "x-rapidapi-key": _clean_env_token(SKY_RAPIDAPI_KEY),
        "x-rapidapi-host": _clean_env_token(SKY_RAPIDAPI_HOST),
    }


def _has_creds() -> bool:
    return bool(_clean_env_token(SKY_RAPIDAPI_KEY) and _clean_env_token(SKY_RAPIDAPI_HOST))


def _timeout_config() -> tuple[float, float]:
    try:
        connect = float(str(os.getenv("SKY_API_CONNECT_TIMEOUT", "3")).strip())
    except Exception:
        connect = 3.0
    try:
        read = float(str(os.getenv("SKY_API_READ_TIMEOUT", "10")).strip())
    except Exception:
        read = 10.0
    return max(1.0, connect), max(3.0, read)


def _retry_config() -> tuple[int, float]:
    try:
        retries = int(str(os.getenv("SKY_API_RETRIES", "2")).strip())
    except Exception:
        retries = 2
    try:
        backoff = float(str(os.getenv("SKY_API_RETRY_BACKOFF_MS", "200")).strip()) / 1000.0
    except Exception:
        backoff = 0.2
    return max(0, retries), max(0.0, backoff)


def _get_with_retries(url: str, headers: dict[str, str], params: dict) -> requests.Response:
    connect_timeout, read_timeout = _timeout_config()
    retries, backoff = _retry_config()
    last_exc: Exception | None = None
    for attempt in range(retries + 1):
        try:
            return requests.get(
                url,
                headers=headers,
                params=params,
                timeout=(connect_timeout, read_timeout),
            )
        except requests.Timeout as e:
            last_exc = e
            if attempt >= retries:
                raise
            if backoff > 0:
                time.sleep(backoff * (attempt + 1))
        except Exception as e:
            last_exc = e
            if attempt >= retries:
                raise
            if backoff > 0:
                time.sleep(backoff * (attempt + 1))
    if last_exc:
        raise last_exc
    raise RuntimeError("Sky request failed")


def _parse_dt(value: str | None) -> _dt.datetime | None:
    s = str(value or "").strip().replace("T", " ")
    if not s:
        return None
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            return _dt.datetime.strptime(s, fmt)
        except Exception:
            pass
    return None


def _date_part(value: str | None) -> str:
    dt = _parse_dt(value)
    if dt:
        return dt.strftime("%Y-%m-%d")
    s = str(value or "").strip().replace("T", " ")
    return s.split(" ")[0] if s else ""


def _time_part(value: str | None) -> str:
    dt = _parse_dt(value)
    if dt:
        return dt.strftime("%H:%M")
    s = str(value or "").strip().replace("T", " ")
    if " " in s:
        t = s.split(" ", 1)[1].strip()
        if len(t) >= 5:
            return t[:5]
    return "10:00"


def _safe_json(resp: requests.Response) -> Any:
    try:
        return resp.json()
    except Exception:
        return {"status": False, "message": (resp.text or "")[:500]}


def _extract_iata(text: str | None) -> str | None:
    s = str(text or "")
    m = re.search(r"\(([A-Z]{3})\)", s)
    if m:
        return m.group(1)
    m = re.search(r"\b([A-Z]{3})\b", s)
    if m:
        return m.group(1)
    return None


# Unicode-safe alias candidates for car entity autocomplete.
def _entity_query_candidates(name: str | None) -> list[str]:
    q = (name or "").strip()
    if not q:
        return []

    out: list[str] = []

    def _add(v: str | None):
        s = str(v or "").strip()
        if s and s not in out:
            out.append(s)

    iata = _extract_iata(q)
    if iata:
        _add(iata.upper())

    _add(q)

    q_compact = re.sub(r"\s+", "", q).lower()

    alias_map: dict[str, list[str]] = {
        # KR
        "\uC778\uCC9C": ["ICN", "Incheon Airport", "Incheon", "Seoul"],
        "\uAE40\uD3EC": ["GMP", "Gimpo Airport", "Gimpo", "Seoul"],
        "\uC11C\uC6B8": ["Seoul", "SEL", "ICN"],
        "\uBD80\uC0B0": ["PUS", "Busan"],
        # JP
        "\uB098\uB9AC\uD0C0": ["NRT", "Narita Airport", "Narita", "Tokyo"],
        "\uD558\uB124\uB2E4": ["HND", "Haneda Airport", "Haneda", "Tokyo"],
        "\uB3C4\uCFC4": ["Tokyo", "TYO", "NRT", "HND"],
        "\uC624\uC0AC\uCE74": ["Osaka", "OSA", "KIX"],
        "\uAC04\uC0AC\uC774": ["KIX", "Kansai Airport", "Osaka"],
        "\uC0BF\uD3EC\uB85C": ["CTS", "Sapporo"],
        "\uD6C4\uCFE0\uC624\uCE74": ["FUK", "Fukuoka"],
        # US
        "\uB274\uC695": ["NYC", "JFK", "EWR", "LGA", "New York"],
        # EU
        "\uB7F0\uB358": ["LON", "LHR", "LGW", "London"],
        "\uD30C\uB9AC": ["PAR", "CDG", "ORY", "Paris"],
        "\uB85C\uB9C8": ["ROM", "FCO", "Rome"],
        # APAC
        "\uBC29\uCF55": ["BKK", "Bangkok"],
        "\uD558\uB178\uC774": ["HAN", "Hanoi"],
        "\uD638\uCE58\uBBFC": ["SGN", "Ho Chi Minh"],
        "\uB2E4\uB0AD": ["DAD", "Da Nang"],
        "\uC2F1\uAC00\uD3EC\uB974": ["SIN", "Singapore"],
        "\uB300\uB9CC": ["TPE", "Taipei"],
        "\uC2DC\uB4DC\uB2C8": ["SYD", "Sydney"],
        "\uBA5C\uBC84\uB978": ["MEL", "Melbourne"],
        "\uB450\uBC14\uC774": ["DXB", "Dubai"],
        # EN / codes
        "jfk": ["JFK", "New York"],
        "ewr": ["EWR", "Newark"],
        "lga": ["LGA", "LaGuardia"],
        "icn": ["ICN", "Incheon"],
        "nrt": ["NRT", "Narita"],
        "hnd": ["HND", "Haneda"],
        "lhr": ["LHR", "London"],
        "cdg": ["CDG", "Paris"],
        "fco": ["FCO", "Rome"],
        "bkk": ["BKK", "Bangkok"],
        "sin": ["SIN", "Singapore"],
        "syd": ["SYD", "Sydney"],
    }

    for k, vals in alias_map.items():
        if k in q_compact:
            for v in vals:
                _add(v)

    if len(q.strip()) == 3 and q.strip().isalpha():
        _add(q.strip().upper())

    return out


def _distance_sq(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    return (lat1 - lat2) ** 2 + (lon1 - lon2) ** 2


def sky_cars_autocomplete(query: str, limit: int = 10) -> dict:
    if not _has_creds():
        return {"status": False, "message": "Missing SKY_RAPIDAPI_KEY"}
    q = (query or "").strip()
    if not q:
        return {"status": True, "data": []}
    try:
        resp = _get_with_retries(
            f"https://{SKY_RAPIDAPI_HOST}/cars/auto-complete",
            headers=_headers(),
            params={"query": q},
        )
        data = _safe_json(resp)
        if isinstance(data, dict) and isinstance(data.get("data"), list):
            data["data"] = data["data"][: max(1, limit)]
        return data if isinstance(data, dict) else {"status": False, "message": "Invalid response"}
    except Exception as e:
        return {"status": False, "message": f"Sky cars autocomplete request failed: {e}"}


def resolve_sky_car_entity(
    name: str | None,
    lat: float | None = None,
    lon: float | None = None,
) -> dict | None:
    q = (name or "").strip()
    if not q:
        return None

    def parse_loc(item: dict) -> tuple[float | None, float | None]:
        try:
            loc = str(item.get("location") or "")
            a, b = [x.strip() for x in loc.split(",", 1)]
            return float(a), float(b)
        except Exception:
            return None, None

    for cand in _entity_query_candidates(q)[:4]:
        iata = _extract_iata(cand) or (cand.upper() if len(cand) == 3 and cand.isalpha() else None)
        raw = sky_cars_autocomplete(cand, limit=15)
        items = raw.get("data") if isinstance(raw, dict) else None
        if not isinstance(items, list) or not items:
            continue

        if iata:
            for item in items:
                ename = str(item.get("entity_name") or "")
                if f"({iata})" in ename or str(item.get("iata") or "").upper() == iata:
                    return item

        if lat is not None and lon is not None:
            best = None
            best_d = None
            for item in items:
                ilat, ilon = parse_loc(item)
                if ilat is None or ilon is None:
                    continue
                d = _distance_sq(lat, lon, ilat, ilon)
                if best_d is None or d < best_d:
                    best = item
                    best_d = d
            if best is not None:
                return best

        cand_l = cand.lower()
        wants_airport = ("airport" in cand_l) or bool(iata)
        if wants_airport:
            for item in items:
                if str(item.get("class") or "").lower() == "airport":
                    return item
        for item in items:
            if str(item.get("class") or "").lower() in {"city", "airport"}:
                return item
        return items[0]

    return None


def search_sky_car_rentals(
    pickup_name: str | None,
    pickup_lat: float | None,
    pickup_lon: float | None,
    dropoff_name: str | None,
    dropoff_lat: float | None,
    dropoff_lon: float | None,
    pickup_at: str | None,
    dropoff_at: str | None,
    market: str = "KR",
    currency: str = "KRW",
    locale: str = "ko-KR",
    driver_age: int = 30,
) -> dict:
    if not _has_creds():
        return {"status": False, "message": "Missing SKY_RAPIDAPI_KEY"}

    pu = resolve_sky_car_entity(pickup_name, pickup_lat, pickup_lon)
    same_dropoff = (
        str(dropoff_name or "").strip().lower() == str(pickup_name or "").strip().lower()
        and dropoff_lat == pickup_lat
        and dropoff_lon == pickup_lon
    )
    do = pu if same_dropoff else (resolve_sky_car_entity(dropoff_name or pickup_name, dropoff_lat, dropoff_lon) or pu)
    if not pu:
        return {"status": False, "message": "pickUpEntityId resolution failed"}
    if not do:
        return {"status": False, "message": "dropOffEntityId resolution failed"}

    params = {
        "pickUpEntityId": str(pu.get("entity_id") or ""),
        "dropOffEntityId": str(do.get("entity_id") or pu.get("entity_id") or ""),
        "pickUpDate": _date_part(pickup_at),
        "pickUpTime": _time_part(pickup_at),
        "dropOffDate": _date_part(dropoff_at),
        "dropOffTime": _time_part(dropoff_at),
        "market": market,
        "currency": currency,
        "locale": locale,
        "driverAge": driver_age,
    }
    try:
        resp = _get_with_retries(
            f"https://{SKY_RAPIDAPI_HOST}/cars/search",
            headers=_headers(),
            params=params,
        )
        data = _safe_json(resp)
    except Exception as e:
        return {"status": False, "message": f"Sky cars search request failed: {e}"}

    if not isinstance(data, dict):
        data = {"status": False, "message": "Invalid sky cars response"}
    data.setdefault("meta", {})
    if isinstance(data.get("meta"), dict):
        data["meta"]["resolved_pickup"] = pu
        data["meta"]["resolved_dropoff"] = do
        data["meta"]["_http_status"] = resp.status_code if "resp" in locals() else None
    return data


def parse_sky_car_search_results(raw: dict | None) -> list[dict]:
    if not isinstance(raw, dict):
        return []
    if raw.get("status") is False and not raw.get("data"):
        return []
    data = raw.get("data")
    if not isinstance(data, dict):
        return []

    providers = data.get("providers") if isinstance(data.get("providers"), dict) else {}
    ccy = str(((data.get("query") or {}).get("ccy")) or "KRW")
    car_list = data.get("carList") if isinstance(data.get("carList"), list) else []
    out: list[dict] = []
    seen: set[tuple] = set()

    def _first_number(node: Any) -> float | None:
        if isinstance(node, (int, float)):
            return float(node)
        if isinstance(node, str):
            t = node.strip().replace(",", "")
            m = re.search(r"-?\d+(?:\.\d+)?", t)
            if m:
                try:
                    return float(m.group(0))
                except Exception:
                    return None
            return None
        if isinstance(node, dict):
            for k, v in node.items():
                lk = str(k).lower()
                if any(x in lk for x in ("price", "amount", "total", "fare", "cost", "pay", "value")):
                    n = _first_number(v)
                    if n is not None:
                        return n
        if isinstance(node, list):
            for v in node:
                n = _first_number(v)
                if n is not None:
                    return n
        return None

    def _pick_str(primary: dict, secondary: dict, keys: list[str]) -> str:
        for k in keys:
            v = primary.get(k)
            if isinstance(v, str) and v.strip():
                return v.strip()
        for k in keys:
            v = secondary.get(k)
            if isinstance(v, str) and v.strip():
                return v.strip()
        return ""

    def _is_generic_rental_name(name_val: str, supplier_val: str) -> bool:
        n = str(name_val or "").strip().lower()
        if not n:
            return True
        if n in {"rental car", "rental", "car"}:
            return True
        if n.endswith("rental car") or n.endswith(" rental"):
            s = str(supplier_val or "").strip().lower()
            core = n.replace("rental car", "").replace("rental", "").strip()
            if not core or (s and core == s):
                return True
        return False

    for car in car_list:
        if not isinstance(car, dict):
            continue
        deals = [d for d in (car.get("deals") or []) if isinstance(d, dict)]

        def _deal_price_num(d: dict) -> float | None:
            p = (
                d.get("price")
                or d.get("total_price")
                or d.get("amount")
                or d.get("value")
                or d.get("base_price")
                or d.get("total")
            )
            n = _first_number(p)
            if n is None:
                n = _first_number(d)
            return n

        priced_deals = []
        for d in deals:
            n = _deal_price_num(d)
            if n is not None and n > 0:
                priced_deals.append((n, d))
        if priced_deals:
            priced_deals.sort(key=lambda x: x[0])
            deal = priced_deals[0][1]
        else:
            deal = deals[0] if deals else {}

        supplier = str(
            deal.get("vndr")
            or deal.get("supplier")
            or deal.get("provider_name")
            or deal.get("vendorName")
            or deal.get("company")
            or ""
        ).strip()
        if not supplier:
            prv_id = str(deal.get("prv_id") or "").strip()
            provider_row = providers.get(prv_id) if prv_id else None
            if isinstance(provider_row, dict):
                supplier = str(provider_row.get("provider_name") or "").strip()
        supplier = supplier or "Skyscanner Partner"

        name = _pick_str(
            deal,
            car,
            [
                "car_name",
                "name",
                "vehicle_name",
                "vehicle",
                "vehicleName",
                "display_name",
                "car_type",
                "vehicle_class",
                "category",
                "model",
                "title",
                "sipp",
            ],
        )
        if not name:
            category = _pick_str(deal, car, ["vehicle_class", "category", "car_type"])
            name = category.strip() if category else "\uCC28\uC885 \uC815\uBCF4 \uC5C6\uC74C"
        if _is_generic_rental_name(name, supplier):
            category = _pick_str(deal, car, ["vehicle_class", "category", "car_type", "sipp"])
            name = category.strip() if category else "\uCC28\uC885 \uC815\uBCF4 \uC5C6\uC74C"

        price = (
            deal.get("price")
            or deal.get("total_price")
            or deal.get("amount")
            or deal.get("value")
            or deal.get("base_price")
            or deal.get("total")
            or car.get("min_price")
            or car.get("mean_price")
            or car.get("price")
            or car.get("total")
        )
        if price is None:
            price = _first_number(deal)
        if price is None:
            price = _first_number(car)
        if price is None and priced_deals:
            price = priced_deals[0][0]
        try:
            price_num = int(round(float(price))) if price is not None else None
        except Exception:
            price_num = None
        if price_num is not None and price_num < 100:
            price_num = None
        # Prefer vehicle photo; keep thumbnail as fallback.
        img = _pick_str(
            deal,
            car,
            [
                "vehicle_image",
                "photo",
                "photo_url",
                "image",
                "image_url",
                "img",
                "thumbnail",
            ],
        ) or None

        trans = _pick_str(deal, car, ["trans", "transmission", "gearbox"])
        seats = (
            deal.get("seat")
            or deal.get("seats")
            or deal.get("passengers")
            or deal.get("passengerQuantity")
            or car.get("max_seats")
            or car.get("seats")
            or car.get("passengers")
        )
        bags = deal.get("bags") or deal.get("luggage") or deal.get("baggage") or car.get("max_bags") or car.get("luggage")
        fuel = _pick_str(deal, car, ["fuel_pol", "fuel_type", "fuelPolicy"])

        specs = []
        if seats:
            s = str(seats).strip()
            specs.append(f"{s}\uC778\uC2B9" if s.isdigit() else s)
        if bags:
            specs.append(f"\uAC00\uBC29 {bags}")
        if trans:
            specs.append(trans)
        if fuel:
            specs.append(fuel)

        rating = None
        try:
            rating = float(car.get("rating")) if car.get("rating") is not None else None
        except Exception:
            rating = None

        key = (name, supplier, price_num or 0)
        if key in seen:
            continue
        seen.add(key)
        out.append(
            {
                "name": name,
                "supplier": supplier,
                "price": price_num,
                "currency": ccy,
                "image": img,
                "specs": specs,
                "seats": int(seats) if isinstance(seats, (int, float)) else None,
                "transmission": trans or None,
                "fuel_policy": fuel or None,
                "rating": rating,
            }
        )

    out.sort(key=lambda x: x.get("price") or 10**12)
    return out[:24]
