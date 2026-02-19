# 호텔 오퍼(실시간 가격) 조회
def get_hotel_offers(hotel_id, checkin, checkout, adults=2):
    token = get_amadeus_token()
    if not token:
        return None
    url = "https://test.api.amadeus.com/v3/shopping/hotel-offers"
    headers = {"Authorization": f"Bearer {token}"}
    params = {
        "hotelIds": hotel_id,
        "adults": adults,
        "checkInDate": checkin,
        "checkOutDate": checkout,
        "roomQuantity": 1
    }
    response = requests.get(url, headers=headers, params=params)
    if response.status_code == 200:
        return response.json()
    else:
        return None
# 도시명으로 Amadeus 도시코드(IATA) 실시간 조회
def get_city_code_from_amadeus(city_name):
    token = get_amadeus_token()
    if not token:
        return None
    url = "https://test.api.amadeus.com/v1/reference-data/locations"
    headers = {"Authorization": f"Bearer {token}"}
    params = {
        "keyword": city_name,
        "subType": "CITY"
    }
    response = requests.get(url, headers=headers, params=params)
    if response.status_code == 200:
        data = response.json()
        if data.get('data'):
            return data['data'][0]['iataCode']
    return None
import os
import requests
from dotenv import load_dotenv

load_dotenv()
AMADEUS_CLIENT_ID = os.getenv("AMADEUS_CLIENT_ID")
AMADEUS_CLIENT_SECRET = os.getenv("AMADEUS_CLIENT_SECRET")

# Amadeus API 토큰 발급
def get_amadeus_token():
    url = "https://test.api.amadeus.com/v1/security/oauth2/token"
    data = {
        "grant_type": "client_credentials",
        "client_id": AMADEUS_CLIENT_ID,
        "client_secret": AMADEUS_CLIENT_SECRET
    }
    response = requests.post(url, data=data)
    if response.status_code == 200:
        return response.json().get("access_token")
    else:
        return None

# 예시: 항공편 검색
def search_flights(origin, destination, departure_date):
    token = get_amadeus_token()
    if not token:
        return {"error": "Amadeus 토큰 발급 실패"}
    url = "https://test.api.amadeus.com/v2/shopping/flight-offers"
    headers = {"Authorization": f"Bearer {token}"}
    params = {
        "originLocationCode": origin,
        "destinationLocationCode": destination,
        "departureDate": departure_date,
        "adults": 1,
        "max": 5
    }
    response = requests.get(url, headers=headers, params=params)
    return response.json()

# 예시: 호텔 검색
def search_hotels(city_code, check_in, check_out, adults=1):
    token = get_amadeus_token()
    if not token:
        return {"error": "Amadeus 토큰 발급 실패"}
    url = "https://test.api.amadeus.com/v3/reference-data/locations/hotels/by-city"
    headers = {"Authorization": f"Bearer {token}"}
    params = {
        "cityCode": city_code,
        "checkInDate": check_in,
        "checkOutDate": check_out,
        "adults": adults
    }
    response = requests.get(url, headers=headers, params=params)
    return response.json()
