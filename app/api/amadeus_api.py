import os
from typing import Optional

import requests
from dotenv import load_dotenv
from requests import HTTPError

load_dotenv()

AMADEUS_CLIENT_ID = os.getenv("AMADEUS_CLIENT_ID") or os.getenv("AMADEUS_API_KEY")
AMADEUS_CLIENT_SECRET = os.getenv("AMADEUS_CLIENT_SECRET") or os.getenv("AMADEUS_API_SECRET")
AMADEUS_BASE_URL = os.getenv("AMADEUS_BASE_URL", "https://test.api.amadeus.com").rstrip("/")
LOCATION_ALIASES = {
    "서울": "SEL",
    "인천": "ICN",
    "김포": "GMP",
    "부산": "PUS",
    "제주": "CJU",
    "도쿄": "TYO",
    "오사카": "OSA",
    "후쿠오카": "FUK",
    "삿포로": "SPK",
    "나리타": "NRT",
    "하네다": "HND",
    "뉴욕": "NYC",
    "런던": "LON",
    "파리": "PAR",
    "로마": "ROM",
    "방콕": "BKK",
    "다낭": "DAD",
    "하노이": "HAN",
    "호치민": "SGN",
    "싱가포르": "SIN",
    "시드니": "SYD",
    "멜버른": "MEL",
    "브리즈번": "BNE",
}

COUNTRY_ALIASES = {
    "한국": "SEL",
    "대한민국": "SEL",
    "일본": "TYO",
    "중국": "BJS",
    "대만": "TPE",
    "홍콩": "HKG",
    "미국": "NYC",
    "영국": "LON",
    "프랑스": "PAR",
    "이탈리아": "ROM",
    "태국": "BKK",
    "베트남": "SGN",
    "싱가포르": "SIN",
    "말레이시아": "KUL",
    "인도네시아": "JKT",
    "필리핀": "MNL",
    "호주": "SYD",
    "뉴질랜드": "AKL",
}


def get_amadeus_token() -> str:
    if not AMADEUS_CLIENT_ID or not AMADEUS_CLIENT_SECRET:
        raise RuntimeError("AMADEUS credentials are not configured.")

    response = requests.post(
        f"{AMADEUS_BASE_URL}/v1/security/oauth2/token",
        data={
            "grant_type": "client_credentials",
            "client_id": AMADEUS_CLIENT_ID,
            "client_secret": AMADEUS_CLIENT_SECRET,
        },
        timeout=15,
    )
    response.raise_for_status()
    token = response.json().get("access_token")
    if not token:
        raise RuntimeError("Failed to fetch Amadeus access token.")
    return token


def resolve_location_to_iata(keyword: str, token: Optional[str] = None) -> Optional[str]:
    if not keyword:
        return None

    cleaned = keyword.strip()
    compact = cleaned.replace(" ", "")

    if compact in LOCATION_ALIASES:
        return LOCATION_ALIASES[compact]
    if compact in COUNTRY_ALIASES:
        return COUNTRY_ALIASES[compact]
    if len(cleaned) == 3 and cleaned.isalpha():
        return cleaned.upper()

    access_token = token or get_amadeus_token()
    url = f"{AMADEUS_BASE_URL}/v1/reference-data/locations"
    headers = {"Authorization": f"Bearer {access_token}"}
    params = {"subType": "CITY,AIRPORT", "keyword": cleaned, "page[limit]": 1}

    try:
        response = requests.get(url, headers=headers, params=params, timeout=15)
        response.raise_for_status()
    except HTTPError:
        try:
            params.pop("subType", None)
            response = requests.get(url, headers=headers, params=params, timeout=15)
            response.raise_for_status()
        except HTTPError:
            return None

    items = response.json().get("data", [])
    if not items:
        return None
    return items[0].get("iataCode")


def search_flight_offers_raw(
    origin_code: str,
    destination_code: str,
    departure_date: str,
    return_date: Optional[str] = None,
    adults: int = 1,
    cabin: Optional[str] = None,
    max_results: int = 30,
):
    import logging
    logger = logging.getLogger("flight_search")
    token = get_amadeus_token()
    params = {
        "originLocationCode": origin_code,
        "destinationLocationCode": destination_code,
        "departureDate": departure_date,
        "adults": adults,
        "max": max_results,
    }
    if return_date:
        params["returnDate"] = return_date
    if cabin:
        params["travelClass"] = cabin
    logger.info(f"[amadeus_api] 요청 params: {params}")
    try:
        response = requests.get(
            f"{AMADEUS_BASE_URL}/v2/shopping/flight-offers",
            headers={"Authorization": f"Bearer {token}"},
            params=params,
            timeout=20,
        )
        logger.info(f"[amadeus_api] 응답 status: {response.status_code}")
        try:
            response.raise_for_status()
        except HTTPError as e:
            detail = _extract_amadeus_error_text(response)
            raise RuntimeError(f"Amadeus error {response.status_code}: {detail}") from e
        logger.info(f"[amadeus_api] 응답 json: {response.text}")
        return response.json()
    except Exception as e:
        logger.error(f"[amadeus_api] Exception: {e}, response: {getattr(response, 'text', None)}")
        raise


def search_flights(origin, destination, departure_date):
    return search_flight_offers_raw(origin, destination, departure_date, adults=1, max_results=5)


def _extract_amadeus_error_text(response: requests.Response) -> str:
    try:
        payload = response.json()
        errors = payload.get("errors") or []
        if errors and isinstance(errors, list):
            first = errors[0] if isinstance(errors[0], dict) else {}
            title = first.get("title") or ""
            detail = first.get("detail") or ""
            code = first.get("code") or ""
            msg = " ".join([x for x in [code, title, detail] if x])
            return msg.strip() or response.text[:400]
        return response.text[:400]
    except Exception:
        return response.text[:400]


def search_hotels(city_code, check_in, check_out, adults=1):
    token = get_amadeus_token()
    headers = {"Authorization": f"Bearer {token}"}

    params = {
        "cityCode": city_code,
        "checkInDate": check_in,
        "checkOutDate": check_out,
        "adults": adults,
    }

    # 1) Try cityCode-based offers first.
    response = requests.get(
        f"{AMADEUS_BASE_URL}/v3/shopping/hotel-offers",
        headers=headers,
        params=params,
        timeout=20,
    )
    seed_data = []
    if response.ok:
        payload = response.json()
        seed_data = payload.get("data", []) if isinstance(payload, dict) else []
        # If enough results are returned, keep fast-path response.
        if len(seed_data) >= 15:
            return payload

    # 2) Expand results: find many hotel IDs in city, then query offers by hotelIds in batches.
    by_city = requests.get(
        f"{AMADEUS_BASE_URL}/v1/reference-data/locations/hotels/by-city",
        headers=headers,
        params={"cityCode": city_code, "radius": 30, "radiusUnit": "KM", "hotelSource": "ALL"},
        timeout=20,
    )
    if not by_city.ok:
        return {
            "error": f"{response.status_code} {response.reason}",
            "details": _extract_amadeus_error_text(response),
            "fallback_error": _extract_amadeus_error_text(by_city),
        }

    by_city_data = by_city.json().get("data", [])
    hotel_ids = []
    for item in by_city_data:
        if not isinstance(item, dict):
            continue
        hotel_id = item.get("hotelId")
        if hotel_id:
            hotel_ids.append(hotel_id)
        if len(hotel_ids) >= 120:
            break

    if not hotel_ids:
        return {"data": seed_data}

    merged = []
    if isinstance(seed_data, list):
        merged.extend(seed_data)

    # Batch query to avoid too-long hotelIds query string.
    chunk_size = 20
    for i in range(0, len(hotel_ids), chunk_size):
        chunk = hotel_ids[i : i + chunk_size]
        offers = requests.get(
            f"{AMADEUS_BASE_URL}/v3/shopping/hotel-offers",
            headers=headers,
            params={
                "hotelIds": ",".join(chunk),
                "checkInDate": check_in,
                "checkOutDate": check_out,
                "adults": adults,
            },
            timeout=20,
        )
        if not offers.ok:
            continue
        payload = offers.json()
        rows = payload.get("data", []) if isinstance(payload, dict) else []
        if isinstance(rows, list):
            merged.extend(rows)

    # De-duplicate by hotelId and keep only requested cityCode when available.
    deduped = []
    seen = set()
    for row in merged:
        if not isinstance(row, dict):
            continue
        hotel_obj = row.get("hotel", {}) if isinstance(row.get("hotel"), dict) else {}
        row_city_code = (hotel_obj.get("cityCode") or row.get("cityCode") or "").upper()
        if row_city_code and row_city_code != str(city_code).upper():
            continue
        hid = hotel_obj.get("hotelId") or row.get("hotelId")
        if hid and hid in seen:
            continue
        if hid:
            seen.add(hid)
        deduped.append(row)

    return {"data": deduped}
