import os
import re
from typing import Any, Optional

import requests
from dotenv import load_dotenv

from app.api.geoapify import get_attractions
from app.api.google_places import _google_photo_url, get_google_places, google_place_details

load_dotenv()

GEOAPIFY_API_KEY = os.getenv("GEOAPIFY_API_KEY")
GOOGLE_PLACES_API_KEY = os.getenv("GOOGLE_PLACES_API_KEY")


def _is_landmark_like_location_query(location_query: Optional[str]) -> bool:
    q = (location_query or "").lower()
    if not q:
        return False
    return any(k in q for k in ["역", "station", "공항", "airport", "터미널", "terminal"])


def _geocode_place_center_geoapify(
    location_query: str,
    country_code: Optional[str] = None,
    city_name: Optional[str] = None,
) -> Optional[tuple[float, float]]:
    if not GEOAPIFY_API_KEY or not location_query:
        return None
    text = location_query
    extras = []
    if city_name and city_name.lower() not in text.lower():
        extras.append(city_name)
    if country_code and country_code.lower() not in text.lower():
        extras.append(country_code)
    if extras:
        text = f"{location_query}, {', '.join(extras)}"
    try:
        r = requests.get(
            "https://api.geoapify.com/v1/geocode/search",
            params={"text": text, "limit": 1, "apiKey": GEOAPIFY_API_KEY},
            timeout=15,
        )
        if r.status_code != 200:
            return None
        data = r.json() or {}
        feats = data.get("features") or []
        if not feats:
            return None
        coords = ((feats[0] or {}).get("geometry") or {}).get("coordinates") or []
        if len(coords) >= 2:
            lon, lat = float(coords[0]), float(coords[1])
            return (lat, lon)
    except Exception:
        return None
    return None


def _geocode_place_center_google_textsearch(
    location_query: str,
    country_code: Optional[str] = None,
    city_name: Optional[str] = None,
) -> Optional[tuple[float, float]]:
    if not GOOGLE_PLACES_API_KEY or not location_query:
        return None
    q = location_query
    extras = []
    if city_name and city_name.lower() not in q.lower():
        extras.append(city_name)
    if country_code and country_code.lower() not in q.lower():
        extras.append(country_code)
    if extras:
        q = f"{location_query}, {', '.join(extras)}"
    try:
        r = requests.get(
            "https://maps.googleapis.com/maps/api/place/textsearch/json",
            params={"query": q, "key": GOOGLE_PLACES_API_KEY, "language": "ko"},
            timeout=15,
        )
        if r.status_code != 200:
            return None
        data = r.json() or {}
        rows = data.get("results") or []
        if not rows:
            return None
        loc = (((rows[0] or {}).get("geometry") or {}).get("location") or {})
        lat = loc.get("lat")
        lon = loc.get("lng")
        if lat is None or lon is None:
            return None
        return (float(lat), float(lon))
    except Exception:
        return None


def _google_maps_search_url(name: Optional[str], address: Optional[str] = None) -> Optional[str]:
    q = " ".join([x for x in [str(name or "").strip(), str(address or "").strip()] if x]).strip()
    if not q:
        return None
    try:
        return f"https://www.google.com/maps/search/?api=1&query={requests.utils.quote(q)}"
    except Exception:
        return None


def _google_places_text_search(query: str) -> list[dict[str, Any]]:
    if not GOOGLE_PLACES_API_KEY or not query:
        return []
    try:
        r = requests.get(
            "https://maps.googleapis.com/maps/api/place/textsearch/json",
            params={"query": query, "key": GOOGLE_PLACES_API_KEY, "language": "ko"},
            timeout=15,
        )
        if r.status_code != 200:
            return []
        data = r.json() or {}
        return data.get("results") or []
    except Exception:
        return []


def _haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    from math import asin, cos, radians, sin, sqrt

    r = 6371000.0
    p1, p2 = radians(lat1), radians(lat2)
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)
    a = sin(dlat / 2) ** 2 + cos(p1) * cos(p2) * sin(dlon / 2) ** 2
    return 2 * r * asin(sqrt(a))


def _price_level_text(v: Any) -> Optional[str]:
    try:
        n = int(v)
    except Exception:
        return None
    if n <= 0:
        return None
    n = max(1, min(n, 4))
    return "₩" * n


def _rank_place_items(items: list[dict[str, Any]], center: tuple[float, float], category: str) -> list[dict[str, Any]]:
    c_lat, c_lon = center
    for x in items:
        lat = x.get("lat")
        lon = x.get("lon")
        try:
            if lat is not None and lon is not None:
                x["distance_m"] = int(round(_haversine_m(c_lat, c_lon, float(lat), float(lon))))
            else:
                x["distance_m"] = None
        except Exception:
            x["distance_m"] = None

    distances = [x["distance_m"] for x in items if isinstance(x.get("distance_m"), int)]
    max_d = max(distances) if distances else 1

    def _score(x: dict[str, Any]) -> float:
        rating = float(x.get("rating") or 0.0)
        reviews = int(x.get("reviews") or 0)
        d = x.get("distance_m")
        dist_score = 0.5 if d is None else max(0.0, 1.0 - (float(d) / max(1.0, float(max_d))))
        review_score = min(reviews, 500) / 500.0
        rating_score = rating / 5.0
        if category == "restaurant":
            return 0.45 * rating_score + 0.25 * review_score + 0.30 * dist_score
        if category == "shopping":
            return 0.35 * rating_score + 0.20 * review_score + 0.45 * dist_score
        return 0.40 * rating_score + 0.20 * review_score + 0.40 * dist_score

    return sorted(items, key=_score, reverse=True)


def _enrich_google_place_items(results: list[dict[str, Any]], center: tuple[float, float], category: str, top_k: int) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for p in results[: max(top_k * 2, top_k)]:
        loc = (((p.get("geometry") or {}).get("location")) or {})
        photos = p.get("photos") or []
        photo_url = None
        if photos and isinstance(photos, list):
            ref = (photos[0] or {}).get("photo_reference")
            if ref:
                photo_url = _google_photo_url(ref, maxwidth=800)
        items.append(
            {
                "name": p.get("name"),
                "address": p.get("vicinity") or p.get("formatted_address"),
                "rating": p.get("rating"),
                "reviews": p.get("user_ratings_total"),
                "source": "google_places",
                "place_id": p.get("place_id"),
                "lat": loc.get("lat"),
                "lon": loc.get("lng"),
                "photo_url": photo_url,
                "types": p.get("types") or [],
            }
        )

    items = _rank_place_items(items, center=center, category=category)[:top_k]

    for x in items:
        pid = x.get("place_id")
        if not pid:
            continue
        try:
            d = google_place_details(pid, language="ko") or {}
            result = d.get("result") or {}
            x["price_level"] = result.get("price_level")
            x["price_level_text"] = _price_level_text(result.get("price_level"))
            x["maps_url"] = result.get("url")
            x["website"] = result.get("website")
            oh = result.get("opening_hours") or {}
            if isinstance(oh, dict):
                x["open_now"] = oh.get("open_now")
            if isinstance(result.get("editorial_summary"), dict):
                x["editorial_summary"] = (result.get("editorial_summary") or {}).get("overview")
            else:
                x["editorial_summary"] = None
            if not x.get("photo_url"):
                photos = result.get("photos") or []
                if photos and isinstance(photos, list):
                    ref = (photos[0] or {}).get("photo_reference")
                    if ref:
                        x["photo_url"] = _google_photo_url(ref, maxwidth=800)
        except Exception:
            continue
    return items


def search_food_places(
    city_name: str,
    food_keyword: Optional[str],
    country_code: Optional[str] = None,
    top_k: int = 5,
    location_query: Optional[str] = None,
    radius_m: int = 5000,
) -> dict[str, Any]:
    def _normalize_food_keyword(raw_keyword: Optional[str]) -> Optional[str]:
        if not raw_keyword:
            return None
        k = str(raw_keyword).strip()
        if not k:
            return None
        k_l = k.lower()
        generic_food = {
            "맛집", "식당", "레스토랑", "밥집", "먹을만한", "먹을 만한", "추천",
            "restaurant", "restaurants", "food", "eat", "dining", "best",
        }
        compact = re.sub(r"\s+", "", k_l)
        if k in generic_food or k_l in generic_food or compact in {"맛집추천", "식당추천", "레스토랑추천"}:
            return None
        return k

    search_loc = location_query or city_name
    if _is_landmark_like_location_query(location_query):
        center = _geocode_place_center_google_textsearch(search_loc, country_code=country_code, city_name=city_name)
        if not center:
            center = _geocode_place_center_geoapify(search_loc, country_code=country_code, city_name=city_name)
    else:
        center = _geocode_place_center_geoapify(search_loc, country_code=country_code, city_name=city_name)
        if not center:
            center = _geocode_place_center_google_textsearch(search_loc, country_code=country_code, city_name=city_name)
    if not center:
        return {"error": "geocode_failed", "city_name": city_name, "items": []}
    lat, lon = center
    food_keyword = _normalize_food_keyword(food_keyword)
    radius_m = max(800, min(int(radius_m or 5000), 15000))

    try:
        keyword_parts = [x for x in [location_query, food_keyword, "맛집"] if x]
        keyword = " ".join(keyword_parts) if keyword_parts else None
        g = get_google_places(lat, lon, radius=radius_m, keyword=keyword, type="restaurant")
        items = _enrich_google_place_items((g.get("results") or []), center=(lat, lon), category="restaurant", top_k=max(1, min(top_k, 10)))
        if items:
            return {"city_name": city_name, "food_keyword": food_keyword, "location_query": location_query, "items": items}
    except Exception:
        pass

    try:
        q_parts = [x for x in [location_query, city_name, food_keyword, "restaurant"] if x]
        q = " ".join(dict.fromkeys(q_parts))
        rows = _google_places_text_search(q)
        items = _enrich_google_place_items(rows, center=(lat, lon), category="restaurant", top_k=max(1, min(top_k, 10)))
        if items:
            return {"city_name": city_name, "food_keyword": food_keyword, "location_query": location_query, "items": items}
    except Exception:
        pass

    try:
        gg = get_attractions(lat, lon, radius=radius_m, kind="catering.restaurant")
        feats = gg.get("features") or []
        items = []
        fk = (food_keyword or "").lower().strip()
        for f in feats:
            props = f.get("properties") or {}
            name = props.get("name") or props.get("formatted")
            if not name:
                continue
            if fk and fk not in str(name).lower() and fk not in str(props.get("formatted", "")).lower():
                continue
            items.append(
                {
                    "name": name,
                    "address": props.get("formatted"),
                    "rating": props.get("rating"),
                    "reviews": props.get("datasource", {}).get("raw", {}).get("ratings_total") if isinstance(props.get("datasource"), dict) else None,
                    "source": "geoapify",
                    "lat": props.get("lat"),
                    "lon": props.get("lon"),
                    "maps_url": _google_maps_search_url(name, props.get("formatted")),
                }
            )
            if len(items) >= max(1, min(top_k, 10)):
                break
        if items:
            items = _rank_place_items(items, center=(lat, lon), category="restaurant")[: max(1, min(top_k, 10))]
            return {"city_name": city_name, "food_keyword": food_keyword, "location_query": location_query, "items": items}
    except Exception:
        pass

    return {"city_name": city_name, "food_keyword": food_keyword, "location_query": location_query, "items": []}


def search_local_places(
    city_name: str,
    keyword: Optional[str],
    category: str,
    country_code: Optional[str] = None,
    top_k: int = 5,
    location_query: Optional[str] = None,
    radius_m: int = 7000,
) -> dict[str, Any]:
    def _normalize_place_keyword(raw_keyword: Optional[str]) -> Optional[str]:
        if not raw_keyword:
            return None
        k = str(raw_keyword).strip()
        if not k:
            return None
        k_l = k.lower()
        generic_tokens = {
            "추천", "추천좀", "추천해줘", "추천해 줘", "어디", "어디가 좋아", "좋은곳", "좋은 곳",
            "명소", "관광지", "놀거리", "가볼만한곳", "가볼만한 곳", "즐길만한곳", "즐길만한 곳",
            "맛집", "식당", "레스토랑", "카페", "장소", "쇼핑", "쇼핑몰", "백화점", "시장", "마켓",
            "recommend", "recommended", "best", "place", "places", "attraction", "attractions",
            "restaurant", "restaurants", "cafe", "cafes", "things to do", "shopping", "mall", "market",
        }
        if k in generic_tokens or k_l in generic_tokens:
            return None
        compact = re.sub(r"\s+", "", k_l)
        if compact in {
            "명소추천", "명소추천좀", "관광지추천", "놀거리추천", "맛집추천", "카페추천", "쇼핑추천", "쇼핑몰추천",
            "attractionrecommend", "restaurantrecommend", "caferecommend", "shoppingrecommend",
        }:
            return None
        return k

    if category == "restaurant":
        return search_food_places(
            city_name=city_name,
            food_keyword=keyword,
            country_code=country_code,
            top_k=top_k,
            location_query=location_query,
            radius_m=radius_m,
        )

    search_loc = location_query or city_name
    if _is_landmark_like_location_query(location_query):
        center = _geocode_place_center_google_textsearch(search_loc, country_code=country_code, city_name=city_name)
        if not center:
            center = _geocode_place_center_geoapify(search_loc, country_code=country_code, city_name=city_name)
    else:
        center = _geocode_place_center_geoapify(search_loc, country_code=country_code, city_name=city_name)
        if not center:
            center = _geocode_place_center_google_textsearch(search_loc, country_code=country_code, city_name=city_name)
    if not center:
        return {"error": "geocode_failed", "city_name": city_name, "items": []}
    lat, lon = center
    top_k = max(1, min(top_k, 10))
    radius_m = max(1000, min(int(radius_m or 7000), 20000))

    google_type = None
    if category == "attraction":
        google_type = "tourist_attraction"
    elif category == "cafe":
        google_type = "cafe"
    elif category == "shopping":
        google_type = "shopping_mall"

    keyword = _normalize_place_keyword(keyword)

    try:
        place_keyword = " ".join([x for x in [location_query, keyword] if x]) or None
        g = get_google_places(lat, lon, radius=radius_m, keyword=place_keyword, type=google_type)
        items = _enrich_google_place_items((g.get("results") or []), center=(lat, lon), category=category, top_k=top_k)
        if not items and category == "shopping" and place_keyword:
            g2 = get_google_places(lat, lon, radius=radius_m, keyword=place_keyword, type=None)
            items = _enrich_google_place_items((g2.get("results") or []), center=(lat, lon), category=category, top_k=top_k)
        if items:
            return {"city_name": city_name, "keyword": keyword, "category": category, "items": items}
    except Exception:
        pass

    try:
        category_q = {
            "attraction": "tourist attraction",
            "cafe": "cafe",
            "shopping": "shopping",
            "generic": "things to do",
        }.get(category, "")
        q_parts = [x for x in [location_query, city_name, keyword, category_q] if x]
        q = " ".join(dict.fromkeys(q_parts))
        rows = _google_places_text_search(q)
        items = _enrich_google_place_items(rows, center=(lat, lon), category=category, top_k=top_k)
        if items:
            return {"city_name": city_name, "keyword": keyword, "category": category, "items": items}
    except Exception:
        pass

    try:
        kind = "tourism.sights"
        if category == "cafe":
            kind = "catering.cafe"
        elif category == "shopping":
            kind = "commercial.shopping_mall"
        elif category == "generic":
            kind = "tourism.sights"
        gg = get_attractions(lat, lon, radius=radius_m, kind=kind)
        feats = gg.get("features") or []
        items = []
        kw = (keyword or "").strip().lower()
        for f in feats:
            props = f.get("properties") or {}
            name = props.get("name") or props.get("formatted")
            if not name:
                continue
            if kw and kw not in str(name).lower() and kw not in str(props.get("formatted", "")).lower():
                continue
            items.append(
                {
                    "name": name,
                    "address": props.get("formatted"),
                    "rating": props.get("rating"),
                    "reviews": props.get("datasource", {}).get("raw", {}).get("ratings_total") if isinstance(props.get("datasource"), dict) else None,
                    "source": "geoapify",
                    "lat": props.get("lat"),
                    "lon": props.get("lon"),
                    "maps_url": _google_maps_search_url(name, props.get("formatted")),
                }
            )
            if len(items) >= top_k:
                break
        if items:
            items = _rank_place_items(items, center=(lat, lon), category=category)[:top_k]
            return {"city_name": city_name, "keyword": keyword, "category": category, "location_query": location_query, "items": items}
    except Exception:
        pass

    return {"city_name": city_name, "keyword": keyword, "category": category, "items": []}
