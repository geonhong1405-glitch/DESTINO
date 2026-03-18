import os
import requests
from dotenv import load_dotenv
from difflib import SequenceMatcher

load_dotenv()
GOOGLE_PLACES_API_KEY = os.getenv("GOOGLE_PLACES_API_KEY")

def _google_get(url, params):
    response = requests.get(url, params=params, timeout=15)
    if response.status_code == 200:
        return response.json()
    return {"error": response.text, "status_code": response.status_code}

def get_google_places(lat, lon, radius=5000, keyword=None, type=None):
    url = "https://maps.googleapis.com/maps/api/place/nearbysearch/json"
    params = {
        "location": f"{lat},{lon}",
        "radius": radius,
        "key": GOOGLE_PLACES_API_KEY
    }
    if keyword:
        params["keyword"] = keyword
    if type:
        params["type"] = type
    return _google_get(url, params)


def _sim(a: str, b: str) -> float:
    a = (a or "").lower().strip()
    b = (b or "").lower().strip()
    if not a or not b:
        return 0.0
    return SequenceMatcher(None, a, b).ratio()


def _google_photo_url(photo_reference: str, maxwidth: int = 1200) -> str | None:
    if not photo_reference or not GOOGLE_PLACES_API_KEY:
        return None
    return (
        "https://maps.googleapis.com/maps/api/place/photo"
        f"?maxwidth={maxwidth}&photo_reference={photo_reference}&key={GOOGLE_PLACES_API_KEY}"
    )


def google_place_details(place_id: str, language: str = "ko"):
    url = "https://maps.googleapis.com/maps/api/place/details/json"
    fields = ",".join(
        [
            "place_id",
            "name",
            "formatted_address",
            "formatted_phone_number",
            "international_phone_number",
            "website",
            "url",
            "rating",
            "user_ratings_total",
            "opening_hours",
            "geometry",
            "business_status",
            "types",
            "photos",
            "reviews",
            "editorial_summary",
            "price_level",
        ]
    )
    params = {
        "place_id": place_id,
        "fields": fields,
        "language": language,
        "key": GOOGLE_PLACES_API_KEY,
    }
    return _google_get(url, params)


def find_hotel_google_place(
    name: str | None,
    address: str | None = None,
    lat: float | None = None,
    lon: float | None = None,
    language: str = "ko",
):
    if not GOOGLE_PLACES_API_KEY:
        return {"error": "missing_google_places_api_key"}

    query_name = (name or "").strip()
    query_address = (address or "").strip()
    if not query_name and not query_address:
        return {"error": "missing_query"}

    candidates = []

    # Prefer nearby search when coordinates are available.
    if lat is not None and lon is not None:
        nearby = get_google_places(lat, lon, radius=2500, keyword=query_name or query_address, type="lodging")
        for row in nearby.get("results", []) if isinstance(nearby, dict) else []:
            candidates.append(row)

    # Fallback / complement with text search.
    text_url = "https://maps.googleapis.com/maps/api/place/textsearch/json"
    text_query = " ".join([x for x in [query_name, query_address] if x]).strip()
    text_params = {"query": text_query, "language": language, "key": GOOGLE_PLACES_API_KEY}
    text_data = _google_get(text_url, text_params)
    for row in text_data.get("results", []) if isinstance(text_data, dict) else []:
        candidates.append(row)

    if not candidates:
        return {"status": "no_results", "query": text_query}

    # Score candidates by name similarity + distance bias if coords exist.
    best = None
    best_score = -1.0
    seen = set()
    for row in candidates:
        if not isinstance(row, dict):
            continue
        pid = row.get("place_id")
        if pid and pid in seen:
            continue
        if pid:
            seen.add(pid)
        row_name = row.get("name") or ""
        score = _sim(query_name, row_name) * 100
        types = row.get("types") or []
        if isinstance(types, list) and ("lodging" in types or "hotel" in types):
            score += 10
        if lat is not None and lon is not None:
            loc = (((row.get("geometry") or {}).get("location")) or {})
            rlat = loc.get("lat")
            rlon = loc.get("lng")
            try:
                if rlat is not None and rlon is not None:
                    # very rough distance penalty
                    score -= abs(float(rlat) - float(lat)) * 12
                    score -= abs(float(rlon) - float(lon)) * 12
            except Exception:
                pass
        if query_address:
            vicinity = row.get("formatted_address") or row.get("vicinity") or ""
            score += _sim(query_address, vicinity) * 20
        if score > best_score:
            best_score = score
            best = row

    if not best:
        return {"status": "no_match", "query": text_query}

    pid = best.get("place_id")
    details = google_place_details(pid, language=language) if pid else {}
    detail_result = details.get("result", {}) if isinstance(details, dict) else {}

    photo_urls = []
    for p in (detail_result.get("photos") or best.get("photos") or [])[:20]:
        if not isinstance(p, dict):
            continue
        u = _google_photo_url(p.get("photo_reference"), maxwidth=1400)
        if u:
            photo_urls.append(u)

    return {
        "status": "ok",
        "match_score": round(best_score, 2),
        "candidate": {
            "place_id": best.get("place_id"),
            "name": best.get("name"),
            "address": best.get("formatted_address") or best.get("vicinity"),
            "rating": best.get("rating"),
            "user_ratings_total": best.get("user_ratings_total"),
            "types": best.get("types", []),
            "lat": (((best.get("geometry") or {}).get("location")) or {}).get("lat"),
            "lon": (((best.get("geometry") or {}).get("location")) or {}).get("lng"),
        },
        "details": detail_result,
        "photo_urls": photo_urls,
        "query": text_query,
    }
