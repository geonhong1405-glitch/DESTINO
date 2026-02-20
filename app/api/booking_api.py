import os
import requests
from dotenv import load_dotenv

load_dotenv()
BOOKING_RAPIDAPI_KEY = os.getenv("BOOKING_RAPIDAPI_KEY")
BOOKING_RAPIDAPI_HOST = os.getenv("BOOKING_RAPIDAPI_HOST")

def search_car_rentals(pick_up_lat, pick_up_lon, drop_off_lat, drop_off_lon, pick_up_time, drop_off_time, driver_age=30, currency_code="USD", location="US"):
    url = f"https://{BOOKING_RAPIDAPI_HOST}/api/v1/cars/searchCarRentals"
    headers = {
        'x-rapidapi-key': BOOKING_RAPIDAPI_KEY,
        'x-rapidapi-host': BOOKING_RAPIDAPI_HOST
    }
    params = {
        "pick_up_latitude": pick_up_lat,
        "pick_up_longitude": pick_up_lon,
        "drop_off_latitude": drop_off_lat,
        "drop_off_longitude": drop_off_lon,
        "pick_up_time": pick_up_time,
        "drop_off_time": drop_off_time,
        "driver_age": driver_age,
        "currency_code": currency_code,
        "location": location
    }
    response = requests.get(url, headers=headers, params=params)
    return response.json()