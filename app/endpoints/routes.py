from fastapi import APIRouter, Query, Body
from app.api.geoapify import get_attractions
from app.api.google_places import get_google_places
from app.api.ai_helper import ask_ai_about_attractions
from app.api.amadeus_api import search_flights

router = APIRouter()

@router.get("/attractions")
def attractions(lat: float = Query(...), lon: float = Query(...), radius: int = 5000, kind: str = "tourist_attraction"):
    """
    Fetch tourist or local attractions from Geoapify API.
    """
    return get_attractions(lat, lon, radius, kind)

@router.post("/recommend")
def recommend_attraction(
    lat: float = Query(...),
    lon: float = Query(...),
    radius: int = 5000,
    kind: str = "tourist_attraction",
    question: str = Body(..., embed=True),
    keyword: str = None,
    origin: str = None,
    destination: str = None,
    departure_date: str = None
):
    """
    AI가 Geoapify, Google Places, Amadeus 항공권 정보를 참고하여 질문에 맞는 추천을 제공합니다.
    """
    flight_keywords = ["비행기", "항공권", "항공편", "flight", "airplane", "plane", "티켓"]
    include_flights = any(word in question for word in flight_keywords)

    # Geoapify 데이터
    data = get_attractions(lat, lon, radius, kind)
    attractions = data.get("features", [])
    geoapify_places = [a.get("properties", {}) for a in attractions]

    # Google Places 데이터
    google_data = get_google_places(lat, lon, radius, keyword=keyword or question)
    google_places = []
    for place in google_data.get("results", []):
        google_places.append({
            "name": place.get("name"),
            "address": place.get("vicinity"),
            "categories": [place.get("types", [])],
            "website": None,
            "opening_hours": place.get("opening_hours", {}).get("weekday_text", "정보 없음")
        })

    # 항공권 데이터
    flight_info = []
    if include_flights and origin and destination and departure_date:
        flight_data = search_flights(origin, destination, departure_date)
        for offer in flight_data.get("data", []):
            segments = offer.get("itineraries", [])[0].get("segments", [])
            for seg in segments:
                flight_info.append({
                    "airline": seg.get("carrierCode"),
                    "flight_number": seg.get("number"),
                    "departure": seg.get("departure", {}).get("at"),
                    "arrival": seg.get("arrival", {}).get("at"),
                    "origin": seg.get("departure", {}).get("iataCode"),
                    "destination": seg.get("arrival", {}).get("iataCode"),
                })

    # 통합 데이터
    all_places = geoapify_places + google_places
    return {"recommendation": ask_ai_about_attractions(question, all_places, flight_info)}