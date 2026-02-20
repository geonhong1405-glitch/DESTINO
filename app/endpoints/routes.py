from fastapi import APIRouter, Query, Body, HTTPException
from app.api.geoapify import get_attractions
from app.api.google_places import get_google_places
from app.api.ai_helper import ask_ai_about_attractions
from app.api.amadeus_api import search_flights
from app.api.booking_hotel_flight_api import (
    search_flights as booking_search_flights,
    search_destination as booking_search_destination,
    search_hotels_by_dest_id,
    recommend_buckets as booking_recommend_buckets,
)

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

    # 항공권 데이터 (Booking.com RapidAPI만 사용)
    flight_info = []
    if include_flights and origin and destination and departure_date:
        try:
            booking_flight_data = booking_search_flights(origin, destination, departure_date)
            for offer in booking_flight_data.get("data", []):
                segments = offer.get("itineraries", [])[0].get("segments", [])
                for seg in segments:
                    flight_info.append({
                        "airline": seg.get("carrierCode"),
                        "flight_number": seg.get("number"),
                        "departure": seg.get("departure", {}).get("at"),
                        "arrival": seg.get("arrival", {}).get("at"),
                        "origin": seg.get("departure", {}).get("iataCode"),
                        "destination": seg.get("arrival", {}).get("iataCode"),
                        "source": "Booking.com"
                    })
        except Exception as e:
            flight_info.append({"airline": "Booking.com API 오류", "flight_number": str(e)})

    # 통합 데이터
    all_places = geoapify_places + google_places
    return {"recommendation": ask_ai_about_attractions(question, all_places, flight_info)}


@router.get("/v1/hotels/search-destination")
def search_destination(query: str = Query(...)):
    try:
        return booking_search_destination(query=query)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Booking destination search failed: {e}")


@router.get("/v1/hotels/recommend")
def recommend_hotels(
    dest_id: str = Query(...),
    search_type: str = Query(...),
    checkin_date: str = Query(...),
    checkout_date: str = Query(...),
    adults: int = Query(2),
    room_qty: int = Query(1),
    currency_code: str = Query("KRW"),
    center_lat: float = Query(34.703968),
    center_lon: float = Query(135.49292),
    top_k: int = Query(5, ge=1, le=20),
):
    try:
        raw = search_hotels_by_dest_id(
            dest_id=dest_id,
            search_type=search_type,
            checkin_date=checkin_date,
            checkout_date=checkout_date,
            adults=adults,
            room_qty=room_qty,
            currency_code=currency_code,
            languagecode="ko",
            page_number=1,
        )
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Booking hotel search failed: {e}")

    if not raw.get("status"):
        raise HTTPException(status_code=502, detail=raw.get("message", "Booking API error"))

    buckets = booking_recommend_buckets(raw, center=(center_lat, center_lon), top_k=top_k)
    return {
        "status": True,
        "dest_id": dest_id,
        "search_type": search_type,
        "buckets": buckets,
    }
