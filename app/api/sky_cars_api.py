import datetime as _dt
import os
import re
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
        resp = requests.get(
            f"https://{SKY_RAPIDAPI_HOST}/cars/auto-complete",
            headers=_headers(),
            params={"query": q},
            timeout=15,
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

    for cand in _entity_query_candidates(q):
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
    do = resolve_sky_car_entity(dropoff_name or pickup_name, dropoff_lat, dropoff_lon) or pu
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
        resp = requests.get(
            f"https://{SKY_RAPIDAPI_HOST}/cars/search",
            headers=_headers(),
            params=params,
            timeout=45,
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
            # Prefer keys that look like price fields.
            for k, v in node.items():
                lk = str(k).lower()
                if any(x in lk for x in ("price", "amount", "total", "fare", "cost", "pay")):
                    n = _first_number(v)
                    if n is not None:
                        return n
            # Fallback: scan nested values.
            for v in node.values():
                n = _first_number(v)
                if n is not None:
                    return n
        if isinstance(node, list):
            for v in node:
                n = _first_number(v)
                if n is not None:
                    return n
        return None

    for car in car_list:
        if not isinstance(car, dict):
            continue
        deals = car.get("deals") if isinstance(car.get("deals"), list) else []
        deal = deals[0] if deals and isinstance(deals[0], dict) else {}

        name = str(
            deal.get("car_name")
            or deal.get("name")
            or car.get("car_name")
            or car.get("name")
            or car.get("vehicle_name")
            or car.get("model")
            or ""
        ).strip() or "Rental Car"
        supplier = str(deal.get("vndr") or "").strip()
        if not supplier:
            prv_id = str(deal.get("prv_id") or "").strip()
            provider_row = providers.get(prv_id) if prv_id else None
            if isinstance(provider_row, dict):
                supplier = str(provider_row.get("provider_name") or "").strip()
        supplier = supplier or "Skyscanner Partner"

        price = deal.get("price")
        if price is None:
            price = car.get("min_price") or car.get("mean_price")
        if price is None:
            price = _first_number(deal)
        if price is None:
            price = _first_number(car)
        try:
            price_num = int(round(float(price))) if price is not None else None
        except Exception:
            price_num = None
        if price_num is not None and price_num < 100:
            price_num = None

        img = str(car.get("img") or deal.get("vndr_img") or "").strip() or None
        trans = str(deal.get("trans") or car.get("trans") or "").strip() or None
        seats = deal.get("seat") or car.get("max_seats")
        bags = deal.get("bags") or car.get("max_bags")
        fuel = str(deal.get("fuel_pol") or deal.get("fuel_type") or car.get("fuel_type") or "").strip() or None

        specs = []
        if seats:
            specs.append(f"{int(seats)}인승" if str(seats).isdigit() else str(seats))
        if bags:
            specs.append(f"가방 {bags}")
        if trans:
            specs.append(trans)
        if fuel:
            specs.append(fuel)

        rating = None
        try:
            rating = float(car.get("rating")) if car.get("rating") is not None else None
        except Exception:
            rating = None

        if name.lower() in {"rental car", "렌터카 옵션"} and supplier:
            name = f"{supplier} 렌터카"

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
                "transmission": trans,
                "fuel_policy": fuel,
                "rating": rating,
            }
        )

    out.sort(key=lambda x: x.get("price") or 10**12)
    return out[:24]
