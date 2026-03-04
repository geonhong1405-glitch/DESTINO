from typing import Any
import os
import re
import time

import requests

from app.api.booking_hotel_flight_api import (
    recommend_buckets as booking_recommend_buckets,
    search_destination as booking_search_destination,
    search_hotels_by_dest_id,
)
from app.api.google_places import find_hotel_google_place
from app.services.location_alias_service import HOTEL_AREA_CITY_ALIASES

_DEST_CACHE: dict[str, list[dict[str, Any]]] = {}


def _is_rate_limited(exc: Exception) -> bool:
    text = str(exc or "")
    return "429" in text or "Too Many Requests" in text


def _fmt_price(value: Any, currency: str) -> str:
    try:
        if value is None:
            return f"- {currency or '-'}"
        v = float(value)
        if (currency or "").upper() == "KRW":
            return f"{int(round(v)):,} KRW"
        return f"{v:,.2f} {currency or '-'}"
    except Exception:
        return f"{value} {currency or '-'}"


def _rate_limit_response(query: str, checkin: str, checkout: str, adults: int, destination_phase: bool):
    if destination_phase:
        html = (
            "<p>호텔 목적지 조회 요청이 일시적으로 많아(429) 자동 재시도 후에도 실패했어요.</p>"
            "<p>잠시 후 다시 시도해 주세요.</p>"
        )
    else:
        html = (
            "<p>호텔 검색 요청이 일시적으로 많아(429) 자동 재시도 후에도 실패했어요.</p>"
            "<p>잠시 후 다시 시도해 주세요.</p>"
        )
    return html, {
        "hotel_context": True,
        "hotel_query": query,
        "hotel_checkin": checkin,
        "hotel_checkout": checkout,
        "travel_checkin": checkin,
        "travel_checkout": checkout,
        "hotel_adults": adults,
    }


def _link_fallback_response(query: str, checkin: str, checkout: str, adults: int):
    q = str(query or "").strip()
    if not q:
        return None
    try:
        q_enc = requests.utils.quote(q)
    except Exception:
        q_enc = q

    adults_n = max(1, int(adults or 2))
    booking_url = (
        "https://www.booking.com/searchresults.ko.html"
        f"?ss={q_enc}"
        f"&checkin={checkin or ''}"
        f"&checkout={checkout or ''}"
        f"&group_adults={adults_n}"
        "&no_rooms=1&group_children=0"
    )
    maps_url = f"https://www.google.com/maps/search/?api=1&query={q_enc}%20%ED%98%B8%ED%85%94"

    html = (
        f"<div><b>{q} 호텔 추천 (대체 결과)</b><br>"
        "제휴 API 요청량(429)으로 상세 리스트를 바로 가져오지 못했어요.<br>"
        f"Booking 검색: {booking_url}<br>"
        f"Google 지도 검색: {maps_url}<br>"
        f"체크인 {checkin or '-'} | 체크아웃 {checkout or '-'} | 성인 {adults_n}명"
        "</div>"
    )
    return html, {
        "hotel_context": True,
        "hotel_query": q,
        "hotel_checkin": checkin,
        "hotel_checkout": checkout,
        "travel_checkin": checkin,
        "travel_checkout": checkout,
        "hotel_adults": adults_n,
    }


def _google_hotel_fallback_response(query: str, checkin: str, checkout: str, top_k: int = 5):
    api_key = (os.getenv("GOOGLE_PLACES_API_KEY") or "").strip()
    if not api_key:
        return None

    try:
        q = f"{query} 호텔"
        r = requests.get(
            "https://maps.googleapis.com/maps/api/place/textsearch/json",
            params={"query": q, "language": "ko", "key": api_key},
            timeout=15,
        )
        data = r.json() if r.ok else {}
        rows = (data.get("results") or []) if isinstance(data, dict) else []
        if not rows:
            return None

        lines: list[str] = []
        for i, row in enumerate(rows[: max(1, min(int(top_k or 5), 8))], 1):
            name = str(row.get("name") or "-")
            addr = str(row.get("formatted_address") or row.get("vicinity") or "-")
            rating = row.get("rating")
            place_id = str(row.get("place_id") or "")
            maps_url = f"https://www.google.com/maps/place/?q=place_id:{place_id}" if place_id else ""

            photo_url = ""
            photos = row.get("photos") if isinstance(row.get("photos"), list) else []
            if photos:
                pref = str((photos[0] or {}).get("photo_reference") or "")
                if pref:
                    photo_url = (
                        "https://maps.googleapis.com/maps/api/place/photo"
                        f"?maxwidth=1200&photo_reference={pref}&key={api_key}"
                    )

            parts = [f"{i}) {name}", f"주소: {addr}", "출처: Google Places"]
            if isinstance(rating, (int, float)):
                parts.append(f"평점: {float(rating):.1f}")
            if maps_url:
                parts.append(f"지도: {maps_url}")
            if photo_url:
                parts.append(f"사진: {photo_url}")
            if checkin:
                parts.append(f"체크인: {checkin}")
            if checkout:
                parts.append(f"체크아웃: {checkout}")
            lines.append(" | ".join(parts))

        html = f"<div><b>{query} 호텔 추천 (Google 대체) {len(lines)}개</b><br>{'<br>'.join(lines)}</div>"
        return html, {
            "hotel_context": True,
            "hotel_query": query,
            "hotel_checkin": checkin,
            "hotel_checkout": checkout,
            "travel_checkin": checkin,
            "travel_checkout": checkout,
        }
    except Exception:
        return None


def _search_destination_with_retry(query: str, max_attempts: int = 3, base_delay: float = 0.7):
    q = str(query or "").strip()
    if not q:
        return []

    last_error: Exception | None = None
    for attempt in range(1, max_attempts + 1):
        try:
            dest = booking_search_destination(query=q)
            rows = dest.get("data", []) if isinstance(dest, dict) else []
            if rows:
                _DEST_CACHE[q.lower()] = rows
            return rows
        except Exception as e:
            last_error = e
            if not _is_rate_limited(e):
                raise
            if attempt < max_attempts:
                time.sleep(base_delay * attempt)

    cached = _DEST_CACHE.get(q.lower()) or []
    if cached:
        return cached
    if last_error:
        raise last_error
    return []


def _search_hotels_with_retry(**kwargs):
    max_attempts = 3
    base_delay = 0.8
    last_error: Exception | None = None
    for attempt in range(1, max_attempts + 1):
        try:
            return search_hotels_by_dest_id(**kwargs)
        except Exception as e:
            last_error = e
            if not _is_rate_limited(e):
                raise
            if attempt < max_attempts:
                time.sleep(base_delay * attempt)

    if last_error:
        raise last_error
    return {"status": False, "message": "Unknown hotel search failure"}


def _hotel_destination_candidates(query: str) -> list[str]:
    q = (query or "").strip()
    if not q:
        return []

    cleaned = q
    for token in ["근처", "부근", "주변", "숙소", "호텔", "추천", "찾아줘", "찾아 줘", "좀", "알려줘", "알려 줘"]:
        cleaned = cleaned.replace(token, " ")
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" ,")

    out: list[str] = []
    for cand in [q, cleaned]:
        if cand and cand not in out:
            out.append(cand)

    q_l = q.lower()
    for area, city in HOTEL_AREA_CITY_ALIASES.items():
        if str(area).lower() in q_l and city not in out:
            out.append(city)

    return [x for x in out if x]


def _looks_like_date_only_query(text: str) -> bool:
    t = str(text or "").strip().lower()
    if not t:
        return False

    compact = re.sub(r"\s+", "", t)
    if re.search(r"20\d{2}-\d{2}-\d{2}", compact):
        return True
    if re.search(r"\d{1,2}[./-]\d{1,2}", compact):
        return True

    return any(
        kw in t
        for kw in [
            "today",
            "tomorrow",
            "checkin",
            "check-in",
            "checkout",
            "check-out",
            "오늘",
            "내일",
            "모레",
            "체크인",
            "체크아웃",
            "내일모레",
        ]
    )


def answer_hotel_from_parsed(parsed: dict[str, Any], prev_state: dict[str, Any]):
    parsed_query = str(parsed.get("query") or "").strip()
    prev_query = str(prev_state.get("hotel_query") or "").strip()
    date_explicit = bool(parsed.get("__date_explicit"))

    if parsed_query and prev_query and _looks_like_date_only_query(parsed_query):
        query = prev_query
    else:
        query = (parsed_query or prev_query).strip()

    checkin = parsed.get("checkin_date") or prev_state.get("hotel_checkin") or prev_state.get("travel_checkin")
    checkout = parsed.get("checkout_date") or prev_state.get("hotel_checkout") or prev_state.get("travel_checkout")
    adults = int(parsed.get("adults") or prev_state.get("hotel_adults") or 2)
    top_k = max(1, min(int(parsed.get("top_k") or 5), 20))
    bucket = parsed.get("bucket") or "value_top"

    if not query:
        return "<p>호텔을 찾을 지역을 알려주세요. (예: 오사카 우메다)</p>", {"hotel_context": True, "hotel_adults": adults}

    # 이번 턴에 날짜를 명시하지 않으면 과거 날짜를 재사용하지 않음
    if not date_explicit:
        checkin = None
        checkout = None

    if not checkin or not checkout:
        return "<p>체크인/체크아웃 날짜를 알려주세요. (YYYY-MM-DD)</p>", {
            "hotel_context": True,
            "hotel_query": query,
            "hotel_checkin": checkin,
            "hotel_checkout": checkout,
            "hotel_adults": adults,
        }

    cands = []
    last_error: Exception | None = None
    for dest_query in _hotel_destination_candidates(query):
        try:
            cands = _search_destination_with_retry(dest_query)
            if cands:
                break
        except Exception as e:
            last_error = e
            if _is_rate_limited(e):
                fallback = _google_hotel_fallback_response(query, checkin, checkout, top_k=top_k)
                if fallback:
                    return fallback
                link_fallback = _link_fallback_response(query, checkin, checkout, adults)
                if link_fallback:
                    return link_fallback
                return _rate_limit_response(query, checkin, checkout, adults, destination_phase=True)
            continue

    if not cands and last_error:
        if _is_rate_limited(last_error):
            fallback = _google_hotel_fallback_response(query, checkin, checkout, top_k=top_k)
            if fallback:
                return fallback
            link_fallback = _link_fallback_response(query, checkin, checkout, adults)
            if link_fallback:
                return link_fallback
        return f"<pre>호텔 목적지 검색 실패: {last_error}</pre>", {"hotel_context": True}

    if not cands:
        return "<p>목적지를 찾지 못했어요. 지역명을 조금 더 구체적으로 입력해 주세요.</p>", {"hotel_context": True}

    first = cands[0] if isinstance(cands[0], dict) else {}
    try:
        raw = _search_hotels_with_retry(
            dest_id=str(first.get("dest_id")),
            search_type=str(first.get("search_type") or "CITY"),
            checkin_date=checkin,
            checkout_date=checkout,
            adults=adults,
            room_qty=1,
            currency_code="KRW",
            languagecode="ko",
            page_number=1,
        )
    except Exception as e:
        if _is_rate_limited(e):
            fallback = _google_hotel_fallback_response(query, checkin, checkout, top_k=top_k)
            if fallback:
                return fallback
            link_fallback = _link_fallback_response(query, checkin, checkout, adults)
            if link_fallback:
                return link_fallback
            return _rate_limit_response(query, checkin, checkout, adults, destination_phase=False)
        return f"<pre>호텔 검색 실패: {e}</pre>", {"hotel_context": True}

    if not raw.get("status"):
        msg = str(raw.get("message", "Booking API error"))
        if _is_rate_limited(Exception(msg)):
            fallback = _google_hotel_fallback_response(query, checkin, checkout, top_k=top_k)
            if fallback:
                return fallback
            link_fallback = _link_fallback_response(query, checkin, checkout, adults)
            if link_fallback:
                return link_fallback
        return f"<pre>호텔 검색 실패: {msg}</pre>", {"hotel_context": True}

    center = (
        float(first.get("latitude") or first.get("lat") or 34.703968),
        float(first.get("longitude") or first.get("lon") or 135.49292),
    )
    rows = booking_recommend_buckets(raw, center=center, top_k=top_k).get(bucket) or []
    if not rows:
        return "<p>조건에 맞는 호텔 결과가 없습니다.</p>", {"hotel_context": True}

    bucket_title = {
        "value_top": "가성비 TOP",
        "review_top": "후기 TOP",
        "location_top": "위치 TOP",
    }.get(bucket, "추천 TOP")

    lines: list[str] = []
    for i, h in enumerate(rows, 1):
        price_obj = h.get("price") or {}
        name = h.get("name") or "-"
        parts = [
            f"{i}) {name}",
            f"가격: {_fmt_price(price_obj.get('value'), str(price_obj.get('currency') or ''))}",
        ]

        score = (h.get("review") or {}).get("score")
        if score is not None:
            parts.append(f"평점: {score}")

        photo_url = h.get("photo_url")
        if isinstance(photo_url, str):
            photo_url = photo_url.strip()
            if photo_url.startswith("//"):
                photo_url = f"https:{photo_url}"
            elif photo_url.startswith("http://"):
                photo_url = "https://" + photo_url[len("http://"):]

        maps_url = ""
        address_text = ""
        if not photo_url:
            try:
                gp = find_hotel_google_place(name=name, address=query)
                if isinstance(gp, dict) and gp.get("status") == "ok":
                    cand = gp.get("candidate") or {}
                    details = gp.get("details") or {}
                    photo_urls = gp.get("photo_urls") or []
                    if isinstance(photo_urls, list) and photo_urls:
                        photo_url = str(photo_urls[0])
                    address_text = str(cand.get("address") or "")
                    maps_url = str(details.get("url") or "")
            except Exception:
                pass

        if address_text:
            parts.append(f"주소: {address_text}")
        if maps_url:
            parts.append(f"지도: {maps_url}")
        if photo_url:
            parts.append(f"사진: {photo_url}")

        parts.append(f"체크인: {checkin}")
        parts.append(f"체크아웃: {checkout}")

        dist_m = h.get("distance_m")
        if isinstance(dist_m, (int, float)):
            parts.append(f"거리: {float(dist_m) / 1000:.1f}km")

        stars = h.get("stars")
        if stars:
            parts.append(f"등급: {stars}")

        lines.append(" | ".join(parts))

    html = f"<div><b>{query} 호텔 추천 ({bucket_title}) {len(rows)}개</b><br>{'<br>'.join(lines)}</div>"
    return html, {
        "hotel_context": True,
        "hotel_query": query,
        "hotel_checkin": checkin,
        "hotel_checkout": checkout,
        "travel_checkin": checkin,
        "travel_checkout": checkout,
        "hotel_adults": adults,
    }
