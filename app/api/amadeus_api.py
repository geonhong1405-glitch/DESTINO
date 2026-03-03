import os
from typing import Optional

import requests
from dotenv import load_dotenv
from requests import HTTPError

load_dotenv(override=True)


def _load_amadeus_config() -> tuple[str | None, str | None, str]:
    # Reload .env each request path so server reflects updated .env reliably.
    load_dotenv(override=True)
    client_id = os.getenv("AMADEUS_CLIENT_ID") or os.getenv("AMADEUS_API_KEY")
    client_secret = os.getenv("AMADEUS_CLIENT_SECRET") or os.getenv("AMADEUS_API_SECRET")
    base_url = (os.getenv("AMADEUS_BASE_URL") or "https://test.api.amadeus.com").rstrip("/")
    return client_id, client_secret, base_url


def get_amadeus_token() -> str:
    amadeus_client_id, amadeus_client_secret, amadeus_base_url = _load_amadeus_config()
    if not amadeus_client_id or not amadeus_client_secret:
        raise RuntimeError("AMADEUS credentials are not configured.")

    response = requests.post(
        f"{amadeus_base_url}/v1/security/oauth2/token",
        data={
            "grant_type": "client_credentials",
            "client_id": amadeus_client_id,
            "client_secret": amadeus_client_secret,
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
    if len(cleaned) == 3 and cleaned.isalpha():
        return cleaned.upper()

    access_token = token or get_amadeus_token()
    _, _, amadeus_base_url = _load_amadeus_config()
    url = f"{amadeus_base_url}/v1/reference-data/locations"
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
    children: int = 0,
    infants: int = 0,
    cabin: Optional[str] = None,
    currency_code: Optional[str] = None,
    max_results: int = 30,
):
    import logging
    logger = logging.getLogger("flight_search")
    token = get_amadeus_token()
    _, _, amadeus_base_url = _load_amadeus_config()
    params = {
        "originLocationCode": origin_code,
        "destinationLocationCode": destination_code,
        "departureDate": departure_date,
        "adults": adults,
        "max": max_results,
    }
    if children and int(children) > 0:
        params["children"] = int(children)
    if infants and int(infants) > 0:
        params["infants"] = int(infants)
    if return_date:
        params["returnDate"] = return_date
    if cabin:
        params["travelClass"] = cabin
    if currency_code:
        params["currencyCode"] = str(currency_code).strip().upper()
    logger.info(f"[amadeus_api] 요청 params: {params}")
    try:
        response = requests.get(
            f"{amadeus_base_url}/v2/shopping/flight-offers",
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


def reprice_flight_offers(
    offers: list[dict],
    chunk_size: int = 4,
) -> list[Optional[dict]]:
    if not offers:
        return []

    token = get_amadeus_token()
    _, _, amadeus_base_url = _load_amadeus_config()
    endpoint = f"{amadeus_base_url}/v1/shopping/flight-offers/pricing"
    out: list[Optional[dict]] = [None] * len(offers)
    safe_chunk = max(1, int(chunk_size or 1))

    for start in range(0, len(offers), safe_chunk):
        chunk = offers[start : start + safe_chunk]
        body = {
            "data": {
                "type": "flight-offers-pricing",
                "flightOffers": chunk,
            }
        }
        try:
            response = requests.post(
                endpoint,
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                    # Some Amadeus environments still expect this override for pricing.
                    "X-HTTP-Method-Override": "GET",
                },
                json=body,
                timeout=20,
            )
            response.raise_for_status()
            payload = response.json() if response.content else {}
            priced = ((payload.get("data") or {}).get("flightOffers") or []) if isinstance(payload, dict) else []
            if not isinstance(priced, list):
                continue
            for i, row in enumerate(priced):
                if i >= len(chunk):
                    break
                if isinstance(row, dict):
                    out[start + i] = row
        except Exception:
            # Best-effort only: keep original search prices when repricing fails.
            continue

    return out


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
    _, _, amadeus_base_url = _load_amadeus_config()
    headers = {"Authorization": f"Bearer {token}"}

    params = {
        "cityCode": city_code,
        "checkInDate": check_in,
        "checkOutDate": check_out,
        "adults": adults,
    }

    # 1) Try cityCode-based offers first.
    response = requests.get(
        f"{amadeus_base_url}/v3/shopping/hotel-offers",
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
        f"{amadeus_base_url}/v1/reference-data/locations/hotels/by-city",
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
            f"{amadeus_base_url}/v3/shopping/hotel-offers",
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
