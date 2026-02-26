import os

from dotenv import load_dotenv
from fastapi import APIRouter, Body, HTTPException, Query
from openai import OpenAI

from app.api.booking_hotel_flight_api import (
    recommend_buckets as booking_recommend_buckets,
    search_destination as booking_search_destination,
    search_flights as booking_search_flights,
    search_hotels_by_dest_id,
)
from app.api.geoapify import get_attractions
from app.api.google_places import get_google_places

router = APIRouter()

load_dotenv()
_routes_ai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


def ask_ai_about_attractions(question, attractions, flight_info=None):
    context = "\n".join(
        [
            (
                f"상호명: {a.get('name', 'Unknown')}\n"
                f"주소: {a.get('address', {}).get('formatted', '') if isinstance(a.get('address'), dict) else (a.get('address') or '')}\n"
                f"카테고리: {', '.join(a.get('categories', [])) if isinstance(a.get('categories'), list) else str(a.get('categories', ''))}\n"
                f"웹사이트: {a.get('website', '없음')}\n"
                f"영업시간: {a.get('opening_hours', '정보 없음')}\n"
            )
            for a in attractions
        ]
    )

    flight_context = ""
    if flight_info:
        flight_context = "\n\n항공권 정보:\n" + "\n".join(
            [
                (
                    f"항공사: {f.get('airline', 'Unknown')}, "
                    f"항공편: {f.get('flight_number', 'Unknown')}, "
                    f"출발: {f.get('departure', '')}, 도착: {f.get('arrival', '')}, "
                    f"출발지: {f.get('origin', '')}, 도착지: {f.get('destination', '')}"
                )
                for f in flight_info
            ]
        )

    prompt = (
        f"관광객이 '{question}'이라고 물어봤을 때 아래 명소와 항공권 정보 중에서 "
        f"가장 적합한 정보를 정확하게 추천해줘.\n명소 목록:\n{context}{flight_context}"
    )
    response = _routes_ai_client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "너는 여행지 추천 전문가야."},
            {"role": "user", "content": prompt},
        ],
    )
    return response.choices[0].message.content


@router.get("/attractions")
def attractions(
    lat: float = Query(...),
    lon: float = Query(...),
    radius: int = Query(5000),
    kind: str = Query("tourist_attraction"),
):
    """
    Fetch tourist or local attractions from Geoapify API.
    """
    return get_attractions(lat, lon, radius, kind)


@router.post("/recommend")
def recommend_attraction(
    lat: float = Query(...),
    lon: float = Query(...),
    radius: int = Query(5000),
    kind: str = Query("tourist_attraction"),
    question: str = Body(..., embed=True),
    keyword: str | None = None,
    origin: str | None = None,
    destination: str | None = None,
    departure_date: str | None = None,
):
    """
    Geoapify / Google Places / (선택) 항공권 정보를 바탕으로 AI 추천 결과를 생성합니다.
    """
    flight_keywords = ["비행기", "항공권", "항공편", "flight", "airplane", "plane", "티켓"]
    include_flights = any(word in (question or "") for word in flight_keywords)

    data = get_attractions(lat, lon, radius, kind)
    attractions_data = data.get("features", [])
    geoapify_places = [a.get("properties", {}) for a in attractions_data]

    google_data = get_google_places(lat, lon, radius, keyword=keyword or question)
    google_places = []
    for place in google_data.get("results", []):
        google_places.append(
            {
                "name": place.get("name"),
                "address": place.get("vicinity"),
                "categories": place.get("types", []),
                "website": None,
                "opening_hours": place.get("opening_hours", {}).get("weekday_text", "정보 없음"),
            }
        )

    flight_info = []
    if include_flights and origin and destination and departure_date:
        try:
            booking_flight_data = booking_search_flights(origin, destination, departure_date)
            for offer in booking_flight_data.get("data", []):
                itineraries = offer.get("itineraries", [])
                if not itineraries:
                    continue
                for seg in itineraries[0].get("segments", []):
                    flight_info.append(
                        {
                            "airline": seg.get("carrierCode"),
                            "flight_number": seg.get("number"),
                            "departure": seg.get("departure", {}).get("at"),
                            "arrival": seg.get("arrival", {}).get("at"),
                            "origin": seg.get("departure", {}).get("iataCode"),
                            "destination": seg.get("arrival", {}).get("iataCode"),
                            "source": "Booking.com",
                        }
                    )
        except Exception as e:
            flight_info.append({"airline": "Booking.com API 오류", "flight_number": str(e)})

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
