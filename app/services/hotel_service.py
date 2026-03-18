from typing import Any
import html as html_utils
import os
import re
import time
from datetime import datetime

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


def _hidden_meta(label: str, value: Any) -> str:
    v = str(value or "").strip()
    if not v:
        return ""
    return f"<span style='display:none'> | {html_utils.escape(label)}: {html_utils.escape(v)}</span>"


def _coarse_area_label(address: Any, name: Any = None) -> str:
    text = f"{str(address or '')} {str(name or '')}".lower()
    if not text.strip():
        return ""
    area_map = [
        ("shinjuku", "신주쿠"), ("신주쿠", "신주쿠"),
        ("shibuya", "시부야"), ("시부야", "시부야"),
        ("ginza", "긴자"), ("긴자", "긴자"),
        ("ueno", "우에노"), ("우에노", "우에노"),
        ("asakusa", "아사쿠사"), ("아사쿠사", "아사쿠사"),
        ("ikebukuro", "이케부쿠로"), ("이케부쿠로", "이케부쿠로"),
        ("roppongi", "롯폰기"), ("롯폰기", "롯폰기"),
    ]
    for k, v in area_map:
        if k in text:
            return v
    return ""


def _pick_hotel_photo(row: dict[str, Any]) -> str:
    cands = [
        row.get("photo_url"),
        row.get("main_photo_url"),
        row.get("image"),
        row.get("thumbnail"),
    ]
    photos = row.get("photos")
    if isinstance(photos, list):
        for p in photos:
            if isinstance(p, str):
                cands.append(p)
            elif isinstance(p, dict):
                cands.extend([p.get("url"), p.get("image"), p.get("photo_url")])
    for c in cands:
        if not isinstance(c, str):
            continue
        u = c.strip()
        if not u:
            continue
        if u.startswith("//"):
            u = f"https:{u}"
        elif u.startswith("http://"):
            u = "https://" + u[len("http://"):]
        if u.startswith("https://"):
            return u
    return ""


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
    adults_n = max(1, int(adults or 2))
    nights = 1
    try:
        if checkin and checkout:
            d1 = datetime.strptime(str(checkin), "%Y-%m-%d")
            d2 = datetime.strptime(str(checkout), "%Y-%m-%d")
            nights = max(1, (d2 - d1).days)
    except Exception:
        nights = 1

    # 429 fallback: keep visible text concise; keep hidden fields for card parsing.
    seeds = [
        (f"{q} 센트럴 호텔", 8.8, 83000, "신주쿠"),
        (f"{q} 프라임 스테이", 8.5, 76000, "시부야"),
        (f"{q} 비즈니스 호텔", 8.2, 69000, "긴자"),
        (f"{q} 시티 인", 8.0, 64000, "우에노"),
        (f"{q} 레지던스", 8.6, 81000, "이케부쿠로"),
    ]
    google_enabled = bool((os.getenv("GOOGLE_PLACES_API_KEY") or "").strip())
    lines: list[str] = []
    for idx, (name, score, nightly_base, area) in enumerate(seeds[:5], 1):
        per_night = int(nightly_base * max(1.0, min(1.6, adults_n / 2)))
        total = per_night * nights
        item_photo = ""
        item_addr = q
        item_score = score
        if google_enabled:
            try:
                gp = find_hotel_google_place(name=name, address=q)
                if isinstance(gp, dict) and gp.get("status") == "ok":
                    cand = gp.get("candidate") or {}
                    photos = gp.get("photo_urls") or []
                    if isinstance(photos, list) and photos and str(photos[0]).strip():
                        item_photo = str(photos[0]).strip()
                    item_addr = str(cand.get("address") or item_addr)
                    gp_rating = cand.get("rating")
                    if isinstance(gp_rating, (int, float)):
                        item_score = round(float(gp_rating), 1)
            except Exception:
                pass
        area_label = _coarse_area_label(item_addr, name) or area
        visible = " | ".join(
            [
                f"{idx}) {name}",
                "타입: 호텔",
                f"가격: ₩{total:,}",
                f"평점: {item_score}",
                f"지역: {area_label}",
            ]
        )
        hidden = "".join(
            [
                _hidden_meta("사진", item_photo),
                _hidden_meta("체크인", checkin or ""),
                _hidden_meta("체크아웃", checkout or ""),
            ]
        )
        lines.append(f"{visible}{hidden}")

    html = f"<div><b>{q} 호텔 추천 (대체 결과) {len(lines)}개</b><br>{'<br>'.join(lines)}</div>"
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
            photo_url = ""
            photos = row.get("photos") if isinstance(row.get("photos"), list) else []
            if photos:
                pref = str((photos[0] or {}).get("photo_reference") or "")
                if pref:
                    photo_url = (
                        "https://maps.googleapis.com/maps/api/place/photo"
                        f"?maxwidth=1200&photo_reference={pref}&key={api_key}"
                    )
            parts = [f"{i}) {name}", "출처: Google Places"]
            if isinstance(rating, (int, float)):
                parts.append(f"평점: {float(rating):.1f}")
            area_label = _coarse_area_label(addr, name)
            if area_label:
                parts.append(f"지역: {area_label}")
            visible = " | ".join(parts)
            hidden = "".join(
                [
                    _hidden_meta("사진", photo_url),
                    _hidden_meta("체크인", checkin or ""),
                    _hidden_meta("체크아웃", checkout or ""),
                ]
            )
            lines.append(f"{visible}{hidden}")

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
    for token in [
        "근처", "부근", "주변", "숙소", "호텔", "추천", "찾아줘", "찾아 줘", "좀", "알려줘", "알려 줘",
        "오늘", "내일", "모레", "글피", "내일모레", "내일모래",
        "from", "to", "checkin", "checkout", "check-in", "check-out",
        "에서", "부터", "까지",
    ]:
        cleaned = cleaned.replace(token, " ")
    cleaned = re.sub(r"[~\-–—]+", " ", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" ,")

    out: list[str] = []
    for cand in [cleaned, q]:
        if cand and cand not in out:
            out.append(cand)

    q_l = q.lower()
    for area, city in HOTEL_AREA_CITY_ALIASES.items():
        if str(area).lower() in q_l and city not in out:
            out.append(city)

    # Landmark/place-name normalization to improve destination API recall.
    landmark_city_map = {
        # JP
        "오사카성": "오사카", "도쿄타워": "도쿄", "도쿄역": "도쿄", "스카이트리": "도쿄",
        "시부야스크램블": "도쿄", "교토역": "교토", "기요미즈데라": "교토", "후시미이나리": "교토",
        "후쿠오카타워": "후쿠오카", "삿포로역": "삿포로",
        "osaka castle": "osaka", "tokyo tower": "tokyo", "tokyo station": "tokyo", "tokyo skytree": "tokyo",
        "shibuya scramble": "tokyo", "kyoto station": "kyoto", "kiyomizu": "kyoto", "fushimi inari": "kyoto",
        "fukuoka tower": "fukuoka", "sapporo station": "sapporo",
        # KR
        "경복궁": "서울", "남산타워": "서울", "해운대": "부산",
        "gyeongbokgung": "seoul", "n seoul tower": "seoul", "haeundae": "busan",
        # TW/HK/SG/TH/VN
        "타이베이101": "타이베이", "중정기념당": "타이베이", "빅토리아피크": "홍콩",
        "마리나베이샌즈": "싱가포르", "가든스바이더베이": "싱가포르",
        "왓아룬": "방콕", "카오산로드": "방콕", "다낭 미케비치": "다낭", "호안끼엠": "하노이",
        "taipei 101": "taipei", "chiang kai shek memorial": "taipei", "victoria peak": "hong kong",
        "marina bay sands": "singapore", "gardens by the bay": "singapore",
        "wat arun": "bangkok", "khao san": "bangkok", "my khe beach": "danang", "hoan kiem": "hanoi",
        # US/CA
        "타임스스퀘어": "뉴욕", "자유의여신상": "뉴욕", "센트럴파크": "뉴욕", "브루클린브리지": "뉴욕",
        "할리우드사인": "로스앤젤레스", "그리피스천문대": "로스앤젤레스", "금문교": "샌프란시스코",
        "cn타워": "토론토",
        "times square": "new york", "statue of liberty": "new york", "central park": "new york", "brooklyn bridge": "new york",
        "hollywood sign": "los angeles", "griffith observatory": "los angeles", "golden gate bridge": "san francisco",
        "cn tower": "toronto",
        # EU
        "에펠탑": "파리", "루브르": "파리", "콜로세움": "로마", "트레비분수": "로마",
        "사그라다파밀리아": "바르셀로나", "람블라스": "바르셀로나",
        "빅벤": "런던", "타워브리지": "런던", "대영박물관": "런던",
        "담광장": "암스테르담", "프라하성": "프라하", "쇤브룬궁전": "비엔나",
        "eiffel tower": "paris", "louvre": "paris", "colosseum": "rome", "trevi fountain": "rome",
        "sagrada familia": "barcelona", "la rambla": "barcelona",
        "big ben": "london", "tower bridge": "london", "british museum": "london",
        "dam square": "amsterdam", "prague castle": "prague", "schonbrunn": "vienna",
        # Oceania / Middle East
        "오페라하우스": "시드니", "하버브리지": "시드니", "버즈칼리파": "두바이",
        "sydney opera house": "sydney", "harbour bridge": "sydney", "burj khalifa": "dubai",
    }
    q_norm = re.sub(r"\s+", " ", q_l).strip()
    for landmark, city in landmark_city_map.items():
        if landmark in q_norm and city not in out:
            out.append(city)

    # Generic "도시+성"/"city castle" patterns
    for city_ko in ["오사카", "도쿄", "교토", "후쿠오카", "삿포로", "나고야", "서울", "부산", "프라하"]:
        if f"{city_ko}성" in q and city_ko not in out:
            out.append(city_ko)
    for city_en in ["osaka", "tokyo", "kyoto", "fukuoka", "sapporo", "nagoya", "prague"]:
        if f"{city_en} castle" in q_norm and city_en not in out:
            out.append(city_en)

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
    max_price = None
    try:
        if parsed.get("max_price") is not None:
            max_price = int(float(parsed.get("max_price")))
            if max_price <= 0:
                max_price = None
    except Exception:
        max_price = None

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
                return _rate_limit_response(query, checkin, checkout, adults, destination_phase=True)
            continue

    if not cands and last_error:
        if _is_rate_limited(last_error):
            fallback = _google_hotel_fallback_response(query, checkin, checkout, top_k=top_k)
            if fallback:
                return fallback
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
            return _rate_limit_response(query, checkin, checkout, adults, destination_phase=False)
        return f"<pre>호텔 검색 실패: {e}</pre>", {"hotel_context": True}

    if not raw.get("status"):
        msg = str(raw.get("message", "Booking API error"))
        if _is_rate_limited(Exception(msg)):
            fallback = _google_hotel_fallback_response(query, checkin, checkout, top_k=top_k)
            if fallback:
                return fallback
        return f"<pre>호텔 검색 실패: {msg}</pre>", {"hotel_context": True}

    center = (
        float(first.get("latitude") or first.get("lat") or 34.703968),
        float(first.get("longitude") or first.get("lon") or 135.49292),
    )
    rows = booking_recommend_buckets(raw, center=center, top_k=top_k).get(bucket) or []
    original_rows = list(rows)
    if max_price is not None:
        filtered_rows = []
        for h in rows:
            price_obj = h.get("price") or {}
            try:
                v = float(price_obj.get("value"))
                c = str(price_obj.get("currency") or "KRW").upper().strip()
            except Exception:
                continue
            if c == "KRW" and v <= float(max_price):
                filtered_rows.append(h)
        rows = filtered_rows or original_rows
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
        hotel_id = str(h.get("hotel_id") or "").strip()
        parts = [
            f"{i}) {name}",
            f"가격: {_fmt_price(price_obj.get('value'), str(price_obj.get('currency') or ''))}",
        ]

        score = (h.get("review") or {}).get("score")
        if score is not None:
            parts.append(f"평점: {score}")

        photo_url = _pick_hotel_photo(h)

        address_text = ""
        if not photo_url:
            try:
                gp = find_hotel_google_place(name=name, address=query)
                if isinstance(gp, dict) and gp.get("status") == "ok":
                    cand = gp.get("candidate") or {}
                    photo_urls = gp.get("photo_urls") or []
                    if isinstance(photo_urls, list) and photo_urls:
                        photo_url = str(photo_urls[0])
                    address_text = str(cand.get("address") or "")
            except Exception:
                pass

        if address_text:
            parts.append(f"주소: {address_text}")
        area_label = _coarse_area_label(address_text or query, name)
        if area_label:
            parts.append(f"지역: {area_label}")

        dist_m = h.get("distance_m")
        if isinstance(dist_m, (int, float)):
            parts.append(f"거리: {float(dist_m) / 1000:.1f}km")

        stars = h.get("stars")
        if stars:
            parts.append(f"등급: {stars}")

        visible = " | ".join(parts)
        hidden = "".join(
            [
                _hidden_meta("사진", photo_url),
                _hidden_meta("hotel_id", hotel_id),
                _hidden_meta("체크인", checkin),
                _hidden_meta("체크아웃", checkout),
            ]
        )
        lines.append(f"{visible}{hidden}")

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
