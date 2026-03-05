import os
import re
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from typing import Any, Optional

from app.api.amadeus_api import (
    resolve_location_to_iata as amadeus_resolve_location_to_iata,
    reprice_flight_offers,
    search_flight_offers_raw,
)
from app.api.booking_hotel_flight_api import search_flights as booking_search_flights
from app.api.exchange_rate import get_exchange_rate
from app.services.location_alias_service import LOCATION_ALIASES, COUNTRY_ALIASES

DEFAULT_FX_TO_KRW = {"KRW": 1.0, "USD": 1350.0, "EUR": 1470.0, "JPY": 9.0}
LOCATION_ALIASES_NORM = {str(k).replace(" ", "").lower(): v for k, v in LOCATION_ALIASES.items()}
COUNTRY_ALIASES_NORM = {str(k).replace(" ", "").lower(): v for k, v in COUNTRY_ALIASES.items()}


def _to_float(v: Any) -> Optional[float]:
    try:
        if v is None:
            return None
        return float(v)
    except Exception:
        return None


def _format_money_amount(v: float) -> str:
    # Keep string shape stable for downstream renderers while trimming unnecessary zeros.
    s = f"{float(v):.2f}"
    return s.rstrip("0").rstrip(".")


def _sum_traveler_pricing_total(offer: dict[str, Any]) -> tuple[Optional[float], Optional[str]]:
    traveler_pricings = offer.get("travelerPricings") or []
    if not isinstance(traveler_pricings, list) or not traveler_pricings:
        return None, None

    total = 0.0
    currency = None
    counted = 0
    for tp in traveler_pricings:
        if not isinstance(tp, dict):
            continue
        tp_price = tp.get("price") or {}
        tp_total = _to_float(tp_price.get("total"))
        tp_currency = str(tp_price.get("currency") or "").upper().strip()
        if tp_total is None or not tp_currency:
            continue
        if currency is None:
            currency = tp_currency
        elif currency != tp_currency:
            return None, None
        total += tp_total
        counted += 1

    if counted == 0 or currency is None:
        return None, None
    return total, currency


def _normalize_offer_totals_from_travelers(data: dict[str, Any]) -> None:
    for offer in data.get("data", []) or []:
        if not isinstance(offer, dict):
            continue
        summed_total, summed_currency = _sum_traveler_pricing_total(offer)
        if summed_total is None or not summed_currency:
            continue
        price_obj = offer.setdefault("price", {})
        if not isinstance(price_obj, dict):
            continue
        price_obj["total"] = _format_money_amount(summed_total)
        price_obj["currency"] = summed_currency


def _reprice_top_offers(data: dict[str, Any], limit: int = 12) -> None:
    offers = data.get("data") or []
    if not isinstance(offers, list) or not offers:
        return
    n = min(max(0, int(limit or 0)), len(offers))
    if n <= 0:
        return

    try:
        repriced = reprice_flight_offers(offers[:n], chunk_size=4)
    except Exception:
        return

    for idx, priced in enumerate(repriced):
        if idx >= n or not isinstance(priced, dict):
            continue
        priced_price = priced.get("price") or {}
        if not isinstance(priced_price, dict):
            continue
        grand_total = _to_float(priced_price.get("grandTotal") or priced_price.get("total"))
        priced_currency = str(priced_price.get("currency") or "").upper().strip()
        if grand_total is None:
            continue

        offer = offers[idx]
        if not isinstance(offer, dict):
            continue
        offer_price = offer.setdefault("price", {})
        if not isinstance(offer_price, dict):
            continue
        offer_price["total"] = _format_money_amount(grand_total)
        if priced_currency:
            offer_price["currency"] = priced_currency
        offer_price["revalidated"] = True


def _offer_itinerary_signature(offer: dict[str, Any]) -> str:
    itineraries = offer.get("itineraries") or []
    if not isinstance(itineraries, list):
        return ""
    legs = []
    for itin in itineraries:
        if not isinstance(itin, dict):
            continue
        segs = []
        for seg in itin.get("segments", []) or []:
            if not isinstance(seg, dict):
                continue
            dep = seg.get("departure") or {}
            arr = seg.get("arrival") or {}
            segs.append(
                "|".join(
                    [
                        str(seg.get("carrierCode") or ""),
                        str(seg.get("number") or ""),
                        str(dep.get("iataCode") or ""),
                        str(dep.get("at") or ""),
                        str(arr.get("iataCode") or ""),
                        str(arr.get("at") or ""),
                        str(seg.get("duration") or ""),
                    ]
                )
            )
        legs.append(">".join(segs))
    return "||".join(legs)


def _dedupe_offers_by_itinerary(data: dict[str, Any]) -> None:
    offers = data.get("data") or []
    if not isinstance(offers, list) or not offers:
        return

    best: dict[str, tuple[dict[str, Any], float]] = {}
    order: list[str] = []
    for offer in offers:
        if not isinstance(offer, dict):
            continue
        sig = _offer_itinerary_signature(offer) or str(offer.get("id") or id(offer))
        total = _to_float((offer.get("price") or {}).get("total"))
        score = float(total) if total is not None else float("inf")
        if sig not in best:
            best[sig] = (offer, score)
            order.append(sig)
            continue
        if score < best[sig][1]:
            best[sig] = (offer, score)

    data["data"] = [best[s][0] for s in order if s in best]


def _norm_iata(keyword: str) -> Optional[str]:
    if not keyword:
        return None
    cleaned = str(keyword).strip()
    compact = cleaned.replace(" ", "")
    compact_lower = compact.lower()
    if compact in LOCATION_ALIASES:
        return LOCATION_ALIASES[compact]
    if compact in COUNTRY_ALIASES:
        return COUNTRY_ALIASES[compact]
    if compact_lower in LOCATION_ALIASES_NORM:
        return LOCATION_ALIASES_NORM[compact_lower]
    if compact_lower in COUNTRY_ALIASES_NORM:
        return COUNTRY_ALIASES_NORM[compact_lower]
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
    children: int = 0,
    infants: int = 0,
    max_price: Optional[float] = None,
    cabin: Optional[str] = None,
    currency_code: str = "KRW",
    max_results: int = 30,
) -> dict[str, Any]:
    adults = int(adults or 1)
    children = int(children or 0)
    infants = int(infants or 0)

    origin_iata = _norm_iata(origin)
    destination_iata = _norm_iata(destination)
    if not origin_iata or not destination_iata:
        raise ValueError(f"출발/도착지를 공항 코드로 해석하지 못했습니다. origin={origin}, destination={destination}")

    amadeus_error = None
    data: dict[str, Any] = {"data": []}

    def _run_amadeus() -> dict[str, Any]:
        return search_flight_offers_raw(
            origin_code=origin_iata,
            destination_code=destination_iata,
            departure_date=departure_date,
            return_date=return_date,
            adults=adults,
            children=children,
            infants=infants,
            cabin=cabin,
            currency_code=currency_code,
            max_results=max_results,
        )

    def _run_booking() -> dict[str, Any]:
        return booking_search_flights(origin_iata, destination_iata, departure_date, return_date, adults)

    with ThreadPoolExecutor(max_workers=2) as ex:
        amadeus_future = ex.submit(_run_amadeus)
        booking_future = ex.submit(_run_booking)

        try:
            data = amadeus_future.result()
        except Exception as e:
            amadeus_error = str(e)
            data = {"data": []}

        try:
            b = booking_future.result()
            data["booking_reference"] = b.get("data", [])
        except Exception as e:
            data["booking_reference_error"] = str(e)

    if amadeus_error:
        data["amadeus_error"] = amadeus_error

    # Normalize total price by summing traveler-level pricing when present.
    _normalize_offer_totals_from_travelers(data)
    # Re-validation is expensive; keep it opt-in to reduce search latency.
    reprice_limit = int(os.getenv("FLIGHT_REPRICE_LIMIT", "0") or 0)
    if reprice_limit > 0:
        _reprice_top_offers(data, limit=reprice_limit)
    _dedupe_offers_by_itinerary(data)

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
        "children": children,
        "infants": infants,
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
        # De-duplicate by rendered itinerary shape (carrier/airports/timestamps/durations),
        # ignoring noisy metadata fields that can differ while the displayed route is identical.
        sig_itins = []
        for itin in itineraries:
            sig_segs = []
            for seg in itin.get("segments", []):
                sig_segs.append(
                    "|".join(
                        [
                            str(seg.get("carrierCode") or ""),
                            str((seg.get("departure") or {}).get("iataCode") or ""),
                            str((seg.get("departure") or {}).get("at") or ""),
                            str((seg.get("arrival") or {}).get("iataCode") or ""),
                            str((seg.get("arrival") or {}).get("at") or ""),
                            str(seg.get("duration") or ""),
                        ]
                    )
                )
            sig_itins.append(">".join(sig_segs))
        key = "||".join(sig_itins)
        if key in seen:
            continue
        seen.add(key)
        segs = []
        itinerary_segments = []
        for itin in itineraries:
            leg_segs = []
            for seg in itin.get("segments", []):
                seg_obj = {
                    "airline": seg.get("carrierCode", "-"),
                    "departure_iata": (seg.get("departure") or {}).get("iataCode", "-"),
                    "arrival_iata": (seg.get("arrival") or {}).get("iataCode", "-"),
                    "departure": (seg.get("departure") or {}).get("at", "-"),
                    "arrival": (seg.get("arrival") or {}).get("at", "-"),
                    "duration": seg.get("duration", "-"),
                }
                segs.append(seg_obj)
                leg_segs.append(seg_obj)
            itinerary_segments.append(leg_segs)
        dur = itineraries[0].get("duration") if itineraries else None
        rows.append(
            {
                "price": (offer.get("price") or {}).get("total"),
                "price_value": _to_float((offer.get("price") or {}).get("total")) or float("inf"),
                "price_krw": (offer.get("price") or {}).get("krwTotal"),
                "currency": (offer.get("price") or {}).get("currency"),
                "segments": segs,
                "itinerary_segments": itinerary_segments,
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
            if w == "midday":
                return 11 <= h < 15
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
