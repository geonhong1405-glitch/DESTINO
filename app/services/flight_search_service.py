import json
import re
from datetime import datetime
from typing import Any, Optional

from app.api.amadeus_api import (
    COUNTRY_ALIASES as AMADEUS_COUNTRY_ALIASES,
    LOCATION_ALIASES as AMADEUS_LOCATION_ALIASES,
    resolve_location_to_iata as amadeus_resolve_location_to_iata,
    search_flight_offers_raw,
)
from app.api.booking_hotel_flight_api import search_flights as booking_search_flights
from app.api.exchange_rate import get_exchange_rate

DEFAULT_FX_TO_KRW = {"KRW": 1.0, "USD": 1350.0, "EUR": 1470.0, "JPY": 9.0}
SERVICE_LOCATION_ALIASES = {
    # English aliases commonly produced by LLM parsing
    "seoul": "SEL",
    "incheon": "ICN",
    "gimpo": "GMP",
    "busan": "PUS",
    "jeju": "CJU",
    "tokyo": "TYO",
    "osaka": "OSA",
    "fukuoka": "FUK",
    "sapporo": "SPK",
    "narita": "NRT",
    "haneda": "HND",
    "newyork": "NYC",
    "london": "LON",
    "paris": "PAR",
    "rome": "ROM",
    "bangkok": "BKK",
    "danang": "DAD",
    "hanoi": "HAN",
    "hochiminh": "SGN",
    "hochiminhcity": "SGN",
    "saigon": "SGN",
    "singapore": "SIN",
    "sydney": "SYD",
    "melbourne": "MEL",
    "brisbane": "BNE",
}


def _to_float(v: Any) -> Optional[float]:
    try:
        if v is None:
            return None
        return float(v)
    except Exception:
        return None


def _norm_iata(keyword: str) -> Optional[str]:
    if not keyword:
        return None
    cleaned = str(keyword).strip()
    compact = cleaned.replace(" ", "")
    compact_lower = compact.lower()
    # Service-level aliases: absorb user/LLM English city names during refactor.
    if compact_lower in SERVICE_LOCATION_ALIASES:
        return SERVICE_LOCATION_ALIASES[compact_lower]
    if compact in AMADEUS_LOCATION_ALIASES:
        return AMADEUS_LOCATION_ALIASES[compact]
    if compact in AMADEUS_COUNTRY_ALIASES:
        return AMADEUS_COUNTRY_ALIASES[compact]
    if len(cleaned) == 3 and cleaned.isalpha():
        return cleaned.upper()
    # Retry API lookup with original and title-cased English form.
    resolved = amadeus_resolve_location_to_iata(cleaned)
    if resolved:
        return resolved
    if cleaned and cleaned != cleaned.title():
        return amadeus_resolve_location_to_iata(cleaned.title())
    return None


def _search_flights(
    origin: str,
    destination: str,
    departure_date: str,
    return_date: Optional[str] = None,
    adults: int = 1,
    max_price: Optional[float] = None,
    cabin: Optional[str] = None,
    max_results: int = 30,
) -> dict[str, Any]:
    origin_iata = _norm_iata(origin)
    destination_iata = _norm_iata(destination)
    if not origin_iata or not destination_iata:
        raise ValueError(f"출발/도착지를 공항 코드로 해석하지 못했습니다. origin={origin}, destination={destination}")

    amadeus_error = None
    try:
        data = search_flight_offers_raw(
            origin_code=origin_iata,
            destination_code=destination_iata,
            departure_date=departure_date,
            return_date=return_date,
            adults=adults,
            cabin=cabin,
            max_results=max_results,
        )
    except Exception as e:
        amadeus_error = str(e)
        data = {"data": []}

    try:
        b = booking_search_flights(origin_iata, destination_iata, departure_date, return_date, adults)
        data["booking_reference"] = b.get("data", [])
    except Exception as e:
        data["booking_reference_error"] = str(e)

    if amadeus_error:
        data["amadeus_error"] = amadeus_error

    if max_price is not None:
        data["data"] = [
            x for x in data.get("data", [])
            if _to_float((x.get("price") or {}).get("total")) is not None
            and _to_float((x.get("price") or {}).get("total")) <= float(max_price)
        ]

    data["meta_query"] = {
        "origin": origin_iata,
        "destination": destination_iata,
        "departure_date": departure_date,
        "return_date": return_date,
        "adults": adults,
        "max_price": max_price,
        "cabin": cabin,
    }
    return data


def _attach_krw(raw: dict[str, Any]) -> dict[str, float]:
    rates: dict[str, float] = {}
    for offer in raw.get("data", []):
        cur = str((offer.get("price") or {}).get("currency", "")).upper()
        total = _to_float((offer.get("price") or {}).get("total"))
        if not cur or total is None:
            continue
        if cur not in rates:
            if cur == "KRW":
                rates[cur] = 1.0
            else:
                try:
                    rates[cur] = get_exchange_rate(base=cur, target="KRW") or DEFAULT_FX_TO_KRW.get(cur)
                except Exception:
                    rates[cur] = DEFAULT_FX_TO_KRW.get(cur)
        r = rates.get(cur)
        if r:
            offer.setdefault("price", {})["krwTotal"] = int(round(total * float(r)))
    return rates


def _duration_min(v: str) -> int:
    s = str(v or "").strip().upper()
    if not s.startswith("PT"):
        return 10**9
    m = re.match(r"^PT(?:(\d+)H)?(?:(\d+)M)?$", s)
    if not m:
        return 10**9
    try:
        return int(m.group(1) or 0) * 60 + int(m.group(2) or 0)
    except Exception:
        return 10**9


def _is_short_haul_route(origin: Optional[str], destination: Optional[str]) -> bool:
    o = (origin or "").upper()
    d = (destination or "").upper()
    kr = {"ICN", "GMP", "PUS", "CJU", "SEL"}
    jp = {"TYO", "HND", "NRT", "OSA", "KIX", "ITM", "FUK", "SPK"}
    return (o in kr and d in jp) or (o in jp and d in kr)


def _sort_flights_for_recommendation(rows: list[dict[str, Any]], state: dict[str, Any]) -> list[dict[str, Any]]:
    sort_by = state.get("sort_by")
    if sort_by == "price_asc":
        rows.sort(key=lambda x: (x.get("price_value", float("inf")), x.get("duration_min", 10**9), x.get("stops", 99)))
        return rows
    if sort_by == "price_desc":
        rows.sort(key=lambda x: x.get("price_value", float("-inf")), reverse=True)
        return rows
    if sort_by == "earliest_departure":
        rows.sort(key=lambda x: (x.get("first_departure") or "9999-12-31T23:59:59", x.get("stops", 99), x.get("price_value", float("inf"))))
        return rows
    if sort_by in {"fastest", "fastest_cheap"}:
        rows.sort(key=lambda x: (x.get("duration_min", 10**9), x.get("stops", 99), x.get("price_value", float("inf"))))
        return rows

    short_haul = _is_short_haul_route(state.get("origin"), state.get("destination"))
    if short_haul:
        def _key_short(x: dict[str, Any]):
            stops = int(x.get("stops") or 0)
            dur = int(x.get("duration_min") or 10**9)
            price = float(x.get("price_value") or float("inf"))
            long_penalty = 1 if dur > 360 else 0
            very_long_penalty = 1 if dur > 600 else 0
            return (
                stops > 0,
                long_penalty,
                very_long_penalty,
                dur,
                price,
                x.get("first_departure") or "9999-12-31T23:59:59",
            )
        rows.sort(key=_key_short)
        return rows

    rows.sort(key=lambda x: (
        x.get("stops", 99),
        x.get("duration_min", 10**9),
        x.get("price_value", float("inf")),
        x.get("first_departure") or "9999-12-31T23:59:59",
    ))
    return rows


def _simplify(raw: dict[str, Any]) -> list[dict[str, Any]]:
    rows, seen = [], set()
    for offer in raw.get("data", []):
        itineraries = offer.get("itineraries", [])
        key = json.dumps(itineraries, ensure_ascii=False)
        if key in seen:
            continue
        seen.add(key)
        segs = []
        for itin in itineraries:
            for seg in itin.get("segments", []):
                segs.append(
                    {
                        "airline": seg.get("carrierCode", "-"),
                        "departure_iata": (seg.get("departure") or {}).get("iataCode", "-"),
                        "arrival_iata": (seg.get("arrival") or {}).get("iataCode", "-"),
                        "departure": (seg.get("departure") or {}).get("at", "-"),
                        "arrival": (seg.get("arrival") or {}).get("at", "-"),
                        "duration": seg.get("duration", "-"),
                    }
                )
        dur = itineraries[0].get("duration") if itineraries else None
        rows.append(
            {
                "price": (offer.get("price") or {}).get("total"),
                "price_value": _to_float((offer.get("price") or {}).get("total")) or float("inf"),
                "price_krw": (offer.get("price") or {}).get("krwTotal"),
                "currency": (offer.get("price") or {}).get("currency"),
                "segments": segs,
                "itinerary_duration": dur,
                "duration_min": _duration_min(dur),
                "first_departure": segs[0]["departure"] if segs else None,
                "stops": max(len((itineraries[0].get("segments", []) if itineraries else [])) - 1, 0),
                "primary_airline": segs[0]["airline"] if segs else "-",
            }
        )
    return rows


def _filter_pref(rows: list[dict[str, Any]], state: dict[str, Any]) -> list[dict[str, Any]]:
    out = rows
    if state.get("direct_only") is True:
        direct = [x for x in out if x.get("stops", 0) == 0]
        if direct:
            out = direct
    if state.get("departure_window"):
        def _in_window(h: int, w: str) -> bool:
            if w == "morning":
                return 6 <= h < 12
            if w == "afternoon":
                return 12 <= h < 18
            if w == "evening":
                return 18 <= h < 22
            if w == "night":
                return h >= 22 or h < 6
            return True
        tmp = []
        for row in out:
            dep = row.get("first_departure")
            try:
                dep_dt = datetime.fromisoformat(dep) if dep else None
            except Exception:
                dep_dt = None
            if dep_dt and _in_window(dep_dt.hour, state["departure_window"]):
                tmp.append(row)
        if tmp:
            out = tmp
    return out
