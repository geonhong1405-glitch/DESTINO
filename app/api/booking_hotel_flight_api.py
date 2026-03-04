
import os
import requests
from dotenv import load_dotenv
from datetime import datetime
import math
import time
from typing import Any, Dict, List, Optional, Tuple

load_dotenv()
BOOKING_RAPIDAPI_KEY = os.getenv("BOOKING_RAPIDAPI_KEY")
BOOKING_RAPIDAPI_HOST = os.getenv("BOOKING_RAPIDAPI_HOST")

LOG_PATH = os.path.join(os.path.dirname(__file__), '../hotel_debug.log')
def log_debug(msg):
    with open(LOG_PATH, 'a', encoding='utf-8') as f:
        f.write(f"[{datetime.now()}] [booking_hotel_flight_api.py] {msg}\n")


def rapid_headers():
    # Reload .env at request time so updated keys are reflected without process restart.
    load_dotenv(override=True)
    key = os.getenv("BOOKING_RAPIDAPI_KEY") or BOOKING_RAPIDAPI_KEY
    host = os.getenv("BOOKING_RAPIDAPI_HOST") or BOOKING_RAPIDAPI_HOST
    return {
        "x-rapidapi-key": key,
        "x-rapidapi-host": host,
    }


def rapid_host() -> str:
    load_dotenv(override=True)
    return os.getenv("BOOKING_RAPIDAPI_HOST") or BOOKING_RAPIDAPI_HOST


def _get_with_retry(
    url: str,
    *,
    headers: dict,
    params: dict,
    timeout: int | tuple[int, int],
    max_attempts: int = 2,
) -> requests.Response:
    """
    Retry transient Booking API failures (especially 429) with short backoff.
    """
    backoff_sec = [0.5, 0.9]
    last_resp: Optional[requests.Response] = None
    last_exc: Optional[Exception] = None
    attempts = max(1, int(max_attempts))
    for i in range(attempts):
        try:
            resp = requests.get(url, headers=headers, params=params, timeout=timeout)
            last_resp = resp
            # Retry on rate-limit or temporary upstream errors.
            if resp.status_code in {429, 500, 502, 503, 504} and i < attempts - 1:
                time.sleep(backoff_sec[min(i, len(backoff_sec) - 1)])
                continue
            return resp
        except requests.RequestException as e:
            last_exc = e
            if i < attempts - 1:
                time.sleep(backoff_sec[min(i, len(backoff_sec) - 1)])
                continue
            raise

    if last_resp is not None:
        return last_resp
    if last_exc is not None:
        raise last_exc
    raise RuntimeError("Booking API request failed without response.")

def search_hotels(city, checkin_date, checkout_date, adults=2, currency_code="KRW", page_number=1, languagecode="ko"):
    # 1. 도시명으로 dest_id 조회
    dest_url = f"https://{BOOKING_RAPIDAPI_HOST}/api/v1/hotels/searchDestination"
    headers = {
        'x-rapidapi-key': BOOKING_RAPIDAPI_KEY,
        'x-rapidapi-host': BOOKING_RAPIDAPI_HOST
    }
    dest_params = {"query": city}
    log_debug(f"searchDestination: url={dest_url}, headers={headers}, params={dest_params}")
    try:
        dest_resp = requests.get(dest_url, headers=headers, params=dest_params)
        dest_resp.encoding = "utf-8"
        log_debug(f"searchDestination response: status={dest_resp.status_code}, text={dest_resp.text[:500]}")
        dest_json = dest_resp.json()
        dest_id = None
        # 공식 응답 구조에 따라 dest_id 추출
        if dest_json and 'data' in dest_json and dest_json['data']:
            dest_id = dest_json['data'][0].get('dest_id')
        elif isinstance(dest_json, list) and len(dest_json) > 0 and 'dest_id' in dest_json[0]:
            dest_id = dest_json[0]['dest_id']
        if not dest_id:
            log_debug(f"No dest_id found for city={city}")
            if dest_resp.status_code >= 400:
                return {"error": f"searchDestination failed ({dest_resp.status_code})", "details": dest_resp.text[:500]}
            return {"error": "No dest_id found"}
    except Exception as e:
        log_debug(f"searchDestination exception: {e}")
        return {"error": str(e)}

    # 2. dest_id 기반 호텔 검색
    url = f"https://{BOOKING_RAPIDAPI_HOST}/api/v1/hotels/searchHotels"
    params = {
        "dest_id": dest_id,
        "search_type": "CITY",
        "arrival_date": checkin_date,
        "departure_date": checkout_date,
        "adults": adults,
        "currency_code": "KRW",
        "page_number": page_number,
        "languagecode": languagecode,
    }
    log_debug(f"search_hotels: url={url}, headers={headers}, params={params}")
    try:
        response = requests.get(url, headers=headers, params=params)
        response.encoding = "utf-8"
        log_debug(f"search_hotels response: status={response.status_code}, text={response.text[:500]}")
        return response.json()
    except Exception as e:
        log_debug(f"search_hotels exception: {e}")
        return {"error": str(e)}

def search_flights(origin, destination, departure_date, return_date=None, adults=1, currency_code="USD"):
    url = f"https://{BOOKING_RAPIDAPI_HOST}/api/v1/flights/searchFlights"
    headers = {
        'x-rapidapi-key': BOOKING_RAPIDAPI_KEY,
        'x-rapidapi-host': BOOKING_RAPIDAPI_HOST
    }
    params = {
        "origin": origin,
        "destination": destination,
        "departure_date": departure_date,
        "adults": adults,
        "currency_code": currency_code
    }
    if return_date:
        params["return_date"] = return_date
    response = requests.get(url, headers=headers, params=params, timeout=(3, 8))
    return response.json()


def search_destination(query: str):
    url = f"https://{rapid_host()}/api/v1/hotels/searchDestination"
    params = {"query": query}
    response = _get_with_retry(url, headers=rapid_headers(), params=params, timeout=(3, 8), max_attempts=2)
    response.raise_for_status()
    return response.json()


def search_hotels_by_dest_id(
    dest_id: str,
    search_type: str,
    checkin_date: str,
    checkout_date: str,
    adults: int = 2,
    room_qty: int = 1,
    currency_code: str = "KRW",
    languagecode: str = "ko",
    page_number: int = 1,
):
    url = f"https://{rapid_host()}/api/v1/hotels/searchHotels"
    params = {
        "dest_id": dest_id,
        "search_type": search_type,
        "arrival_date": checkin_date,
        "departure_date": checkout_date,
        "adults": adults,
        "room_qty": room_qty,
        "currency_code": currency_code,
        "languagecode": languagecode,
        "page_number": page_number,
    }
    response = _get_with_retry(url, headers=rapid_headers(), params=params, timeout=(4, 10), max_attempts=2)
    response.raise_for_status()
    return response.json()


def get_hotel_room_products(
    hotel_id: str,
    checkin_date: str,
    checkout_date: str,
    adults: int = 2,
    room_qty: int = 1,
    currency_code: str = "KRW",
    languagecode: str = "ko",
):
    """
    Best-effort wrapper for booking-com15 hotel detail / room-list style endpoints.
    RapidAPI providers sometimes expose slightly different endpoints/params; this
    function tries common variants and returns the first successful JSON payload.
    """
    endpoint_variants = [
        "/api/v1/hotels/getRoomList",
        "/api/v1/hotels/getHotelDetails",
        "/api/v1/hotels/getDescriptionAndInfo",
    ]
    param_variants = [
        {
            "hotel_id": hotel_id,
            "arrival_date": checkin_date,
            "departure_date": checkout_date,
            "adults": adults,
            "room_qty": room_qty,
            "currency_code": currency_code,
            "languagecode": languagecode,
        },
        {
            "hotel_id": hotel_id,
            "checkin_date": checkin_date,
            "checkout_date": checkout_date,
            "adults": adults,
            "room_qty": room_qty,
            "currency_code": currency_code,
            "languagecode": languagecode,
        },
        {
            "hotel_id": hotel_id,
            "arrival_date": checkin_date,
            "departure_date": checkout_date,
            "adults_number": adults,
            "room_number": room_qty,
            "currency_code": currency_code,
            "languagecode": languagecode,
        },
    ]

    last_error = None
    for endpoint in endpoint_variants:
        url = f"https://{BOOKING_RAPIDAPI_HOST}{endpoint}"
        for params in param_variants:
            try:
                log_debug(f"get_hotel_room_products: url={url}, params={params}")
                resp = requests.get(url, headers=rapid_headers(), params=params, timeout=20)
                text_preview = (resp.text or "")[:400]
                log_debug(f"get_hotel_room_products response: endpoint={endpoint}, status={resp.status_code}, text={text_preview}")
                if resp.status_code >= 400:
                    last_error = {"endpoint": endpoint, "status_code": resp.status_code, "details": text_preview}
                    continue
                data = resp.json()
                # Treat explicit provider errors as unsuccessful and continue trying.
                if isinstance(data, dict) and (data.get("error") or data.get("message") == "Not Found"):
                    last_error = {"endpoint": endpoint, "status_code": resp.status_code, "details": str(data)[:400]}
                    continue
                return {
                    "status": "ok",
                    "endpoint": endpoint,
                    "params": params,
                    "data": data,
                }
            except Exception as e:
                last_error = {"endpoint": endpoint, "error": str(e)}
                log_debug(f"get_hotel_room_products exception: endpoint={endpoint}, err={e}")
                continue

    return {"status": "error", "error": "room_detail_request_failed", "last_error": last_error}


def haversine_m(lat1, lon1, lat2, lon2) -> float:
    r = 6371000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    d1 = math.radians(lat2 - lat1)
    d2 = math.radians(lon2 - lon1)
    a = math.sin(d1 / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(d2 / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def to_hotel_dto(h: Dict[str, Any], include_raw: bool = False) -> Optional[Dict[str, Any]]:
    p = h.get("property") or {}
    lat, lon = p.get("latitude"), p.get("longitude")
    if lat is None or lon is None:
        return None

    pb = p.get("priceBreakdown") or {}
    gp = pb.get("grossPrice") or {}
    price_val = gp.get("value")
    price_cur = gp.get("currency")

    badges = []
    for b in (pb.get("benefitBadges") or []):
        text = b.get("text") or b.get("explanation")
        if text:
            badges.append(text)

    dto = {
        "source": "booking-com15",
        "hotel_id": h.get("hotel_id") or p.get("id"),
        "name": p.get("name"),
        "lat": float(lat),
        "lon": float(lon),
        "price": {
            "value": float(price_val) if price_val is not None else None,
            "currency": price_cur,
        },
        "review": {
            "score": p.get("reviewScore"),
            "count": p.get("reviewCount"),
            "word": p.get("reviewScoreWord"),
        },
        "stars": p.get("propertyClass"),
        "photo_url": (p.get("photoUrls") or [None])[0],
        "badges": badges,
        "checkin": {
            "from": (p.get("checkin") or {}).get("fromTime"),
            "until": (p.get("checkin") or {}).get("untilTime"),
        },
        "checkout": {
            "from": (p.get("checkout") or {}).get("fromTime"),
            "until": (p.get("checkout") or {}).get("untilTime"),
        },
    }
    if include_raw:
        dto["raw"] = h
    return dto


def recommend_buckets(raw: Dict[str, Any], center: Tuple[float, float], top_k: int = 5) -> Dict[str, List[Dict[str, Any]]]:
    hotels_raw = ((raw.get("data") or {}).get("hotels") or [])
    dtos = [to_hotel_dto(h) for h in hotels_raw]
    dtos = [d for d in dtos if d is not None]

    c_lat, c_lon = center
    for d in dtos:
        d["distance_m"] = haversine_m(c_lat, c_lon, d["lat"], d["lon"])

    review_top = sorted(
        dtos,
        key=lambda x: (x["review"]["score"] or 0, x["review"]["count"] or 0),
        reverse=True,
    )[:top_k]

    location_top = sorted(dtos, key=lambda x: x["distance_m"])[:top_k]

    prices = [d["price"]["value"] for d in dtos if d["price"]["value"] is not None]
    min_p, max_p = (min(prices), max(prices)) if prices else (0, 0)

    def norm_price(v):
        if v is None or max_p == min_p:
            return 0.5
        return (v - min_p) / (max_p - min_p)

    review_counts = [math.log((d["review"]["count"] or 0) + 1) for d in dtos]
    min_rc, max_rc = (min(review_counts), max(review_counts)) if review_counts else (0, 0)

    def norm_log_reviewcount(d):
        v = math.log((d["review"]["count"] or 0) + 1)
        if max_rc == min_rc:
            return 0.5
        return (v - min_rc) / (max_rc - min_rc)

    def value_score(d):
        price_score = 1 - norm_price(d["price"]["value"])
        review_score = (d["review"]["score"] or 0) / 10.0
        rc_score = norm_log_reviewcount(d)
        return 0.45 * price_score + 0.40 * review_score + 0.15 * rc_score

    value_top = sorted(dtos, key=value_score, reverse=True)[:top_k]

    return {
        "value_top": value_top,
        "review_top": review_top,
        "location_top": location_top,
    }
