import re
from typing import Any, Callable, Optional

from app.services import place_search_service


def answer_food_place_followup(
    message: str,
    context: str,
    prev_state: Optional[dict[str, Any]] = None,
    *,
    extract_food_place_request_with_llm_fn: Callable[..., dict[str, Any]],
    normalize_rag_country_code_fn: Callable[[Any], Optional[str]],
    place_search_radius_m_fn: Callable[[str, Optional[str]], int],
    should_show_place_distance_fn: Callable[[str, Optional[str], Optional[str]], bool],
    rewrite_place_recommendation_fallback_fn: Callable[..., Optional[str]],
):
    parsed = extract_food_place_request_with_llm_fn(message, context, prev_state)
    prev_k = (prev_state or {}).get("knowledge_state", {}) if isinstance(prev_state, dict) else {}
    city_name = parsed.get("city_name") or prev_k.get("city_name")
    country_code = normalize_rag_country_code_fn(prev_k.get("country_code"))
    food_keyword = parsed.get("food_keyword")
    location_query = parsed.get("location_query") if isinstance(parsed, dict) else None

    if not city_name:
        return (
            "<div>어느 도시에서 찾을지 알려주세요. 예: 도쿄, 오사카, 베를린</div>",
            {"knowledge_state": {**(prev_k or {}), "topic": "culture", "subtopic": "dining"}},
        )

    result = place_search_service.search_food_places(
        city_name=city_name,
        food_keyword=food_keyword,
        country_code=country_code,
        top_k=5,
        location_query=location_query,
        radius_m=place_search_radius_m_fn(message, location_query),
    )
    items = result.get("items") or []
    if not items:
        fallback = rewrite_place_recommendation_fallback_fn(
            city_name=city_name,
            category="restaurant",
            keyword=food_keyword,
            message=message,
            context=context,
        )
        if fallback:
            return (
                fallback,
                {"knowledge_state": {**(prev_k or {}), "city_name": city_name, "country_code": country_code, "topic": "culture", "subtopic": "dining"}},
            )
        q = f"{food_keyword} " if food_keyword else ""
        return (
            f"<div>{city_name}에서 {q}맛집 후보를 찾지 못했습니다. 음식명이나 지역명을 더 구체적으로 알려주세요.</div>",
            {"knowledge_state": {**(prev_k or {}), "city_name": city_name, "topic": "culture", "subtopic": "dining"}},
        )

    title_kw = f"{food_keyword} " if food_keyword else ""
    show_distance = should_show_place_distance_fn(message, location_query, city_name)

    def _food_summary(x: dict[str, Any]) -> str:
        parts = []
        if x.get("rating") is not None:
            parts.append(f"평점 {x.get('rating')} 확인")
        if x.get("reviews"):
            parts.append(f"리뷰 {x.get('reviews')}개")
        if show_distance and x.get("distance_m") is not None:
            parts.append(f"약 {int(x.get('distance_m'))}m")
        if x.get("price_level_text"):
            parts.append(f"가격대 {x.get('price_level_text')}")
        if x.get("address"):
            parts.append("주소 확인 가능")
        src = x.get("source")
        if src == "google_places":
            parts.append("Google Places 기준")
        elif src == "geoapify":
            parts.append("Geoapify 기준(거리/주소 오차 가능)")
        return " · ".join(parts) if parts else "현지 식사 후보"

    def _menu_hint() -> str:
        if food_keyword:
            return f"{food_keyword} 중심으로 찾아본 후보예요."
        return "대표 메뉴는 매장마다 달라서 방문 전 메뉴판/리뷰 확인을 권장해요."

    blocks = []
    for i, x in enumerate(items, 1):
        name = x.get("name") or "-"
        rating = x.get("rating")
        address = x.get("address") or "-"
        source = x.get("source") or "-"
        block = [
            "<div style='margin:10px 0 14px 0;padding:10px 12px;border:1px solid #e5e7eb;border-radius:10px;'>",
            f"<div><b>{i}. {name}</b></div>",
        ]
        if x.get("photo_url"):
            block.append(
                f"<div style='margin-top:8px;'><img src=\"{x.get('photo_url')}\" alt=\"\" "
                "style='width:100%;max-width:360px;height:160px;object-fit:cover;border-radius:8px;border:1px solid #e5e7eb;'></div>"
            )
        block += [
            f"<div style='margin-top:6px;color:#374151;'>{_food_summary(x)}</div>",
            f"<div style='margin-top:6px;color:#4b5563;'>대표 메뉴/포인트: {_menu_hint()}</div>",
            f"<div style='margin-top:6px;color:#4b5563;'>주소: {address}</div>",
        ]
        if rating is not None:
            block.append(f"<div style='color:#4b5563;'>평점: {rating}</div>")
        if x.get("reviews"):
            block.append(f"<div style='color:#4b5563;'>리뷰 수: {x.get('reviews')}</div>")
        if x.get("price_level_text"):
            block.append(f"<div style='color:#4b5563;'>가격대: {x.get('price_level_text')}</div>")
        if x.get("open_now") is True:
            block.append("<div style='color:#047857;'>현재 영업 중</div>")
        elif x.get("open_now") is False:
            block.append("<div style='color:#b45309;'>현재 영업 여부 확인 필요(비영업 시간일 수 있음)</div>")
        block.append(f"<div style='color:#6b7280;font-size:12px;'>출처: {source}</div>")
        if x.get("maps_url"):
            block.append(f"<div style='font-size:12px;'><a href=\"{x.get('maps_url')}\" target='_blank' rel='noopener'>지도에서 보기</a></div>")
        block.append("</div>")
        blocks.append("".join(block))

    html = (
        f"<div><b>{city_name} {title_kw}맛집 추천</b>"
        f"<div style='margin-top:6px;color:#4b5563;'>위치/평점/데이터 출처를 기준으로 보기 쉽게 정리했어요.</div>"
        f"{''.join(blocks)}</div>"
    )
    return html, {"knowledge_state": {**(prev_k or {}), "city_name": city_name, "country_code": country_code, "topic": "culture", "subtopic": "dining"}}


def answer_local_place_followup(
    message: str,
    context: str,
    prev_state: Optional[dict[str, Any]] = None,
    *,
    extract_local_place_request_with_llm_fn: Callable[..., dict[str, Any]],
    normalize_rag_country_code_fn: Callable[[Any], Optional[str]],
    place_search_radius_m_fn: Callable[[str, Optional[str]], int],
    should_show_place_distance_fn: Callable[[str, Optional[str], Optional[str]], bool],
    rewrite_place_recommendation_fallback_fn: Callable[..., Optional[str]],
    contains_fn: Callable[[str, list[str]], bool],
):
    parsed = extract_local_place_request_with_llm_fn(message, context, prev_state)
    prev_k = (prev_state or {}).get("knowledge_state", {}) if isinstance(prev_state, dict) else {}
    city_name = parsed.get("city_name") or prev_k.get("city_name")
    location_query = parsed.get("location_query")
    country_code = normalize_rag_country_code_fn(prev_k.get("country_code"))
    keyword = parsed.get("keyword")
    brand_or_theme = parsed.get("brand_or_theme")
    category = parsed.get("category") or "generic"

    if category == "generic":
        if contains_fn(message or "", ["맛집", "식당", "레스토랑"]):
            category = "restaurant"
        elif contains_fn(message or "", ["명소", "관광지", "놀거리", "가볼만", "즐길만", "핫플"]):
            category = "attraction"
        elif contains_fn(message or "", ["카페"]):
            category = "cafe"
        elif contains_fn(message or "", ["쇼핑", "쇼핑몰", "백화점", "시장", "마켓"]):
            category = "shopping"

    if category == "generic":
        msg_norm = (message or "").lower()
        if any(tok in msg_norm for tok in ["브랜드", "매장", "파는곳", "파는 곳", "판매처", "편집샵", "셀렉트샵", "brand", "store", "shop"]):
            category = "shopping"

    if category == "generic" and brand_or_theme:
        category = "shopping"

    if category == "shopping" and not keyword and brand_or_theme:
        keyword = brand_or_theme

    if not location_query:
        m_loc = re.search(r"(.{1,30}?)(?:에서|근처)\s*", message or "")
        if m_loc:
            candidate = m_loc.group(1).strip(" ,.?")
            if candidate and not contains_fn(candidate, ["여기", "거기", "근처", "주변", "추천", "맛집"]):
                location_query = candidate

    if category == "restaurant" and not keyword:
        cuisine_kws = ["한식", "일식", "중식", "양식", "라멘", "스시", "우동", "야키니쿠", "규카츠", "오마카세", "이자카야"]
        for ck in cuisine_kws:
            if ck in (message or ""):
                keyword = ck
                break
        if not keyword:
            m_food = re.search(r"([A-Za-z가-힣0-9]{1,20})\s*(?:맛집|요리|음식)", message or "")
            if m_food:
                keyword = m_food.group(1).strip()

    if category == "shopping" and not keyword:
        msg_raw = message or ""
        m_brand = re.search(r"([A-Za-z0-9가-힣·&'\-]{1,30})\s*(?:브랜드|매장|파는곳|파는 곳|판매처)", msg_raw)
        if m_brand:
            cand = m_brand.group(1).strip(" ,.?")
            cand = re.sub(r".*(?:에서|근처)\s*", "", cand).strip()
            if cand:
                keyword = cand

    if not city_name and location_query:
        city_name = location_query

    if not city_name:
        return (
            "<div>어느 도시에서 찾을지 알려주세요. 예: 도쿄, 오사카, 베를린</div>",
            {"knowledge_state": {**(prev_k or {}), "topic": "culture", "subtopic": "dining" if category == "restaurant" else "general"}},
        )

    result = place_search_service.search_local_places(
        city_name=city_name,
        keyword=keyword,
        category=category,
        country_code=country_code,
        top_k=5,
        location_query=location_query,
        radius_m=place_search_radius_m_fn(message, location_query),
    )
    items = result.get("items") or []
    if not items:
        label = {"restaurant": "맛집", "attraction": "명소/놀거리", "cafe": "카페", "shopping": "쇼핑 장소", "generic": "장소"}.get(category, "장소")
        fallback = rewrite_place_recommendation_fallback_fn(
            city_name=city_name,
            category=category,
            keyword=keyword,
            message=message,
            context=context,
        )
        if fallback:
            return (
                fallback,
                {"knowledge_state": {**(prev_k or {}), "city_name": city_name, "country_code": country_code, "topic": "culture", "subtopic": "dining" if category == "restaurant" else category}},
            )
        return (
            f"<div>{city_name}에서 {label} 후보를 찾지 못했습니다. 지역명이나 키워드를 더 구체적으로 알려주세요.</div>",
            {"knowledge_state": {**(prev_k or {}), "city_name": city_name, "country_code": country_code}},
        )

    title = {"restaurant": "맛집 추천", "attraction": "명소/놀거리 추천", "cafe": "카페 추천", "shopping": "쇼핑 장소 추천", "generic": "장소 추천"}.get(category, "장소 추천")
    title_kw = f"{keyword} " if keyword else ""
    title_loc = location_query or city_name
    show_distance = should_show_place_distance_fn(message, location_query, city_name)

    category_label = {
        "restaurant": "식사/현지 음식",
        "attraction": "관광/볼거리",
        "cafe": "휴식/카페",
        "shopping": "쇼핑/구매",
        "generic": "여행 장소",
    }.get(category, "여행 장소")

    def _place_summary(x: dict[str, Any]) -> str:
        reasons = [category_label]
        if x.get("rating") is not None:
            reasons.append(f"평점 {x.get('rating')}")
        if x.get("reviews"):
            reasons.append(f"리뷰 {x.get('reviews')}개")
        if show_distance and x.get("distance_m") is not None:
            reasons.append(f"약 {int(x.get('distance_m'))}m")
        if x.get("price_level_text"):
            reasons.append(f"가격대 {x.get('price_level_text')}")
        if x.get("address"):
            reasons.append("주소 확인 가능")
        src = x.get("source")
        if src:
            if str(src) == "geoapify":
                reasons.append("Geoapify 기준(거리/주소 오차 가능)")
            else:
                reasons.append(f"{src} 기준")
        return " · ".join(reasons)

    blocks = []
    for i, x in enumerate(items, 1):
        name = x.get("name") or "-"
        rating = x.get("rating")
        address = x.get("address") or "-"
        source = x.get("source") or "-"
        block = [
            "<div style='margin:10px 0 14px 0;padding:10px 12px;border:1px solid #e5e7eb;border-radius:10px;'>",
            f"<div><b>{i}. {name}</b></div>",
        ]
        if x.get("photo_url"):
            block.append(
                f"<div style='margin-top:8px;'><img src=\"{x.get('photo_url')}\" alt=\"\" "
                "style='width:100%;max-width:360px;height:160px;object-fit:cover;border-radius:8px;border:1px solid #e5e7eb;'></div>"
            )
        block += [
            f"<div style='margin-top:6px;color:#374151;'>{_place_summary(x)}</div>",
            f"<div style='margin-top:6px;color:#4b5563;'>주소: {address}</div>",
        ]
        if rating is not None:
            block.append(f"<div style='color:#4b5563;'>평점: {rating}</div>")
        if x.get("reviews"):
            block.append(f"<div style='color:#4b5563;'>리뷰 수: {x.get('reviews')}</div>")
        if x.get("price_level_text"):
            block.append(f"<div style='color:#4b5563;'>가격대: {x.get('price_level_text')}</div>")
        block.append(f"<div style='color:#6b7280;font-size:12px;'>출처: {source}</div>")
        if x.get("maps_url"):
            block.append(f"<div style='font-size:12px;'><a href=\"{x.get('maps_url')}\" target='_blank' rel='noopener'>지도에서 보기</a></div>")
        block.append("</div>")
        blocks.append("".join(block))

    html = (
        f"<div><b>{title_loc} {title_kw}{title}</b>"
        f"<div style='margin-top:6px;color:#4b5563;'>후보별 핵심 정보만 빠르게 비교할 수 있게 정리했어요.</div>"
        f"{''.join(blocks)}</div>"
    )
    next_subtopic = "dining" if category == "restaurant" else ("shopping" if category == "shopping" else "general")
    next_topic = "money" if category == "shopping" else "culture"
    return html, {"knowledge_state": {**(prev_k or {}), "city_name": city_name, "country_code": country_code, "topic": next_topic, "subtopic": next_subtopic, "location_query": location_query or prev_k.get("location_query")}}
