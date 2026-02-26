import requests
import os
from dotenv import load_dotenv

load_dotenv()
GEOAPIFY_API_KEY = os.getenv("GEOAPIFY_API_KEY")

# Example function to fetch attractions from Geoapify
# Geoapify uses category strings like "tourism.sights", "catering.cafe", etc.
def get_attractions(lat, lon, radius=5000, kind="tourism.sights"):
    url = f"https://api.geoapify.com/v2/places"
    params = {
        "categories": kind,
        "filter": f"circle:{lon},{lat},{radius}",
        "apiKey": GEOAPIFY_API_KEY
    }
    response = requests.get(url, params=params)
    if response.status_code == 200:
        return response.json()
    else:
        return {"error": response.text}
