
import os
import requests
from dotenv import load_dotenv
from datetime import datetime

load_dotenv()
BOOKING_RAPIDAPI_KEY = os.getenv("BOOKING_RAPIDAPI_KEY")
BOOKING_RAPIDAPI_HOST = os.getenv("BOOKING_RAPIDAPI_HOST")

LOG_PATH = os.path.join(os.path.dirname(__file__), '../hotel_debug.log')
def log_debug(msg):
    with open(LOG_PATH, 'a', encoding='utf-8') as f:
        f.write(f"[{datetime.now()}] [booking_hotel_flight_api.py] {msg}\n")

def search_hotels(city, checkin_date, checkout_date, adults=2, currency_code="KRW"):
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

    # 2. dest_id로 호텔 검색
    url = f"https://{BOOKING_RAPIDAPI_HOST}/api/v1/hotels/searchHotels"
    params = {
        "dest_id": dest_id,
        "search_type": "CITY",
        "arrival_date": checkin_date,
        "departure_date": checkout_date,
        "adults": adults,
        "currency_code": "KRW"
    }
    log_debug(f"search_hotels: url={url}, headers={headers}, params={params}")
    try:
        response = requests.get(url, headers=headers, params=params)
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
    response = requests.get(url, headers=headers, params=params)
    return response.json()
