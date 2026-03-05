from typing import Any
import re

from app.services import rentalcar_service
from app.services import product_reco_service


def _extract_iso_date_range_quick(message: str) -> tuple[str | None, str | None]:
    t = str(message or "")
    m = re.search(r"(20\d{2}-\d{1,2}-\d{1,2})\s*[~\-]\s*(20\d{2}-\d{1,2}-\d{1,2})", t)
    if not m:
        return None, None
    return m.group(1), m.group(2)


def _is_bundle_reco_query(message: str, contains_fn) -> bool:
    m = str(message or "").lower()
    has_flight = contains_fn(m, ["항공", "항공권", "비행", "flight"])
    has_hotel = contains_fn(m, ["호텔", "숙소", "숙박", "hotel"])
    has_plus = "+" in m or "and" in m or "같이" in m or "한번에" in m
    has_reco = contains_fn(m, ["추천", "계획", "travel", "plan"])
    return bool((has_flight and has_hotel and has_reco) or ("항공+호텔" in m) or (has_plus and has_flight and has_hotel))


def _handle_knowledge_intent(req: Any, prev_state: dict, context: str, SESSION_STATE: dict, sid: str, _answer_knowledge):
    html, delta = _answer_knowledge(req.message, context, prev_state)
    state = dict(prev_state)
    state.update(delta or {})
    state.pop("pending_intent", None)
    state["last_intent"] = "knowledge"
    SESSION_STATE[sid] = state
    return {"response": html}


def _handle_hotel_intent(req: Any, prev_state: dict, context: str, SESSION_STATE: dict, sid: str, _parse_hotel_slots, hotel_service):
    parsed_hotel = _parse_hotel_slots(req.message, context)
    html, delta = hotel_service.answer_hotel_from_parsed(parsed_hotel, prev_state)
    state = dict(prev_state)
    state.update(delta or {})
    state.pop("pending_intent", None)
    state["last_intent"] = "hotel"
    SESSION_STATE[sid] = state
    return {"response": html}


def _handle_flight_intent(req: Any, prev_state: dict, context: str, SESSION_STATE: dict, sid: str, NeedMoreInfoError: type, _parse_flight_slots, _has_date_signal, _merge_state, _missing_questions, flight_search_service, chat_renderers):
    parsed = _parse_flight_slots(req.message, context)
    state = _merge_state(prev_state, parsed)
    msg_l = (req.message or "").lower()
    msg_raw = (req.message or "")
    msg_compact = re.sub(r"\s+", "", msg_raw)
    has_round_signal_in_turn = any(k in msg_l for k in ["왕복", "복귀", "돌아", "round trip", "roundtrip"])
    has_stay_nights_signal_in_turn = bool(
        re.search(r"\d+\s*박\s*\d+\s*일", msg_raw)
        or re.search(r"\d+\s*일\s*(?:동안|간)", msg_raw)
    )
    has_two_iso_dates = bool(re.search(r"20\d{2}-\d{1,2}-\d{1,2}.*20\d{2}-\d{1,2}-\d{1,2}", msg_compact))
    has_two_mmdd_dates = bool(re.search(r"\d{1,2}[/-]\d{1,2}.*\d{1,2}[/-]\d{1,2}", msg_compact))
    has_two_kr_md_dates = bool(re.search(r"\d{1,2}\s*월\s*\d{1,2}\s*일.*\d{1,2}\s*월\s*\d{1,2}\s*일", msg_raw))
    has_range_connector = any(k in msg_compact for k in ["~", "-", "부터", "까지", "to"])
    has_relative_range = bool(
        has_range_connector
        and (
            ("내일" in msg_compact and "모레" in msg_compact)
            or ("오늘" in msg_compact and "내일" in msg_compact)
            or ("글피" in msg_compact and ("내일" in msg_compact or "모레" in msg_compact))
        )
    )
    has_explicit_return_date_in_turn = bool(
        has_two_iso_dates
        or has_two_mmdd_dates
        or has_two_kr_md_dates
        or has_relative_range
        or has_stay_nights_signal_in_turn
    )
    has_explicit_return_in_turn = has_explicit_return_date_in_turn
    has_origin_cue_in_turn = bool(
        any(k in msg_l for k in ["異쒕컻", "from", "depart", "departure"])
        or re.search(r"[媛-?즑-zA-Z]{2,}\s*?먯꽌", (req.message or ""))
    )
    origin_same_as_prev = bool(parsed.get("origin")) and str(parsed.get("origin")) == str(prev_state.get("origin") or "")
    destination_present = bool(parsed.get("destination"))
    origin_likely_carried_from_prev = bool(destination_present and origin_same_as_prev and not has_origin_cue_in_turn)
    mentioned_destination_without_origin = bool(parsed.get("destination")) and not bool(parsed.get("origin"))
    origin_changed = bool(parsed.get("origin")) and str(parsed.get("origin")) != str(prev_state.get("origin") or "")
    destination_changed = bool(parsed.get("destination")) and str(parsed.get("destination")) != str(prev_state.get("destination") or "")
    route_changed = origin_changed or destination_changed
    has_explicit_date_in_turn = bool(
        parsed.get("departure_date")
        or parsed.get("return_date")
        or _has_date_signal(req.message)
    )
    route_changed_without_date = bool(route_changed and not has_explicit_date_in_turn)

    # If user changed route but did not specify date this turn, do not silently reuse old dates.
    if route_changed_without_date:
        state.pop("departure_date", None)
        state.pop("return_date", None)

    # If user provided destination but omitted origin in this turn, do not silently reuse old origin.
    # Ask origin first to prevent unintended defaults (e.g., previous ICN).
    if mentioned_destination_without_origin or origin_likely_carried_from_prev:
        state.pop("origin", None)

    if has_round_signal_in_turn:
        state["trip_type"] = "round"

    # If user did not explicitly provide return-date semantics in this turn,
    # clear stale carried return date so we can ask for it.
    if not has_explicit_return_date_in_turn:
        state.pop("return_date", None)

    # Shared travel dates can come from non-flight intents (hotel/rentalcar).
    if (not route_changed_without_date) and (not state.get("departure_date")) and prev_state.get("travel_checkin"):
        state["departure_date"] = prev_state.get("travel_checkin")
    if has_explicit_return_in_turn and (not route_changed_without_date) and (not state.get("return_date")) and prev_state.get("travel_checkout"):
        state["return_date"] = prev_state.get("travel_checkout")
    if state.get("departure_date"):
        state["travel_checkin"] = state.get("departure_date")
    if state.get("return_date"):
        state["travel_checkout"] = state.get("return_date")
    missing = _missing_questions(state)
    if missing:
        # Keep flight slot-filling context for short/date-only follow-up turns.
        state["pending_intent"] = "flight"
        SESSION_STATE[sid] = state
        raise NeedMoreInfoError(missing[0])

    raw = flight_search_service._search_flights(
        origin=state["origin"],
        destination=state["destination"],
        departure_date=state["departure_date"],
        return_date=state.get("return_date"),
        adults=state.get("adults", 1),
        children=state.get("children", 0),
        infants=state.get("infants", 0),
        max_price=state.get("max_price"),
        max_results=30,
    )
    flight_search_service._attach_krw(raw)
    rows = flight_search_service._filter_pref(flight_search_service._simplify(raw), state)
    rows = flight_search_service._sort_flights_for_recommendation(rows, state)
    limit = state.get("limit")
    if not isinstance(limit, int) or limit <= 0:
        limit = 8
    rows = rows[:limit]
    if not rows and raw.get("amadeus_error"):
        err = raw.get("amadeus_error")
        return {"response": (
            f"<p>Amadeus \uc9c1\ud56d\ud68c API \uc9c1\ud56d: {err}</p>"
            "<p>\uc9c1\ud56d\ud68c \uc9c1\ud56d\ud68c \uc9c1\ud56d\ud68c \uc9c1\ud56d\ud68c \uc9c1\ud56d\ud68c \uc9c1\ud56d\uc9c1\ud56d. \uc9c1\ud56d \uc9c1\ud56d\ud68c \uc9c1\ud56d\uc9c1\ud56d .env\ud68c "
            "<code>AMADEUS_BASE_URL=https://api.amadeus.com</code>"
            " \uc9c1\ud56d \ud68c \uc9c1\ud56d\uc9c1\ud56d \uc9c1\ud56d\ud68c.</p>"
        )}
    state.pop("pending_intent", None)
    state["last_intent"] = "flight"
    SESSION_STATE[sid] = state
    return {"response": chat_renderers.flight_html_intro(state, rows) + chat_renderers.flight_html_table(rows, raw.get("meta_query", {}))}



def _handle_rentalcar_intent(req: Any, prev_state: dict, SESSION_STATE: dict, sid: str):
    html, delta = rentalcar_service.answer_rentalcar_from_message(req.message, prev_state)
    state = dict(prev_state)
    state.update(delta or {})
    rental_state = (delta or {}).get("rental_state") if isinstance(delta, dict) else None
    if isinstance(rental_state, dict):
        if rental_state.get("pickup_date"):
            state["travel_checkin"] = rental_state.get("pickup_date")
        if rental_state.get("dropoff_date"):
            state["travel_checkout"] = rental_state.get("dropoff_date")
    state.pop("pending_intent", None)
    state["last_intent"] = "rentalcar"
    SESSION_STATE[sid] = state
    return {"response": html}




def _handle_product_intent(req: Any, prev_state: dict, SESSION_STATE: dict, sid: str, chat_renderers):
    items = product_reco_service.recommend_products(req.message, prev_state, limit=8)
    html = chat_renderers.product_html_list(items, title="\ucd94\ucc9c \uc0c1\ud488")
    state = dict(prev_state)
    state.pop("pending_intent", None)
    state["last_intent"] = "product"
    state["last_product_names"] = [str(x.get("name") or "") for x in items]
    first_type = str((items[0] or {}).get("type") or "") if items else ""
    state["last_product_type"] = first_type
    SESSION_STATE[sid] = state
    return {"response": html}


def _handle_itinerary_intent(req: Any, prev_state: dict, context: str, SESSION_STATE: dict, sid: str, client, _strip_markdown_decorations):
    msg = str(req.message or "")
    ml = msg.lower()
    state = dict(prev_state)

    dep, ret = _extract_iso_date_range_quick(msg)
    start_date = dep or state.get("travel_checkin") or state.get("departure_date")
    end_date = ret or state.get("travel_checkout") or state.get("return_date")

    adults = int(state.get("adults") or 0)
    m_people = re.search(r"(?:총|인원|성인)?\s*(\d+)\s*(?:명|인|people|pax)", msg, re.IGNORECASE)
    if m_people:
        adults = max(1, int(m_people.group(1)))

    budget_krw = None
    if state.get("max_price") is not None:
        try:
            budget_krw = int(float(state.get("max_price")))
        except Exception:
            budget_krw = None
    if budget_krw is None:
        m_budget_krw = re.search(r"(\d[\d,]*)\s*원", msg)
        if m_budget_krw:
            try:
                budget_krw = int(m_budget_krw.group(1).replace(",", ""))
            except Exception:
                budget_krw = None
    if budget_krw is None:
        m_budget_mw = re.search(r"(\d+(?:\.\d+)?)\s*만\s*원", msg)
        if m_budget_mw:
            try:
                budget_krw = int(float(m_budget_mw.group(1)) * 10000)
            except Exception:
                budget_krw = None

    destination = (
        str(state.get("destination_city") or "").strip()
        or str(state.get("destination") or "").strip()
        or str(state.get("hotel_query") or "").strip()
    )
    if not destination:
        m_dest = re.search(r"([가-힣A-Za-z\s]+?)\s*(?:여행|일정|코스|플랜|trip|travel)", msg, re.IGNORECASE)
        if m_dest:
            destination = m_dest.group(1).strip()
    destination = destination[:60]

    style = None
    if any(k in ml for k in ["미식", "맛집", "food", "먹"]):
        style = "미식 중심"
    elif any(k in ml for k in ["자연", "힐링", "휴양", "relax"]):
        style = "힐링 중심"
    elif any(k in ml for k in ["쇼핑", "shopping"]):
        style = "쇼핑 중심"
    elif any(k in ml for k in ["아이", "가족", "family", "키즈"]):
        style = "가족 친화"
    elif any(k in ml for k in ["커플", "데이트", "honeymoon"]):
        style = "커플/로맨틱"
    elif any(k in ml for k in ["액티비티", "체험", "activity"]):
        style = "액티비티 중심"

    month = None
    if isinstance(start_date, str) and re.match(r"20\d{2}-\d{1,2}-\d{1,2}", start_date):
        try:
            month = int(start_date.split("-")[1])
        except Exception:
            month = None
    if month in (3, 4, 5):
        season = "봄"
    elif month in (6, 7, 8):
        season = "여름"
    elif month in (9, 10, 11):
        season = "가을"
    elif month in (12, 1, 2):
        season = "겨울"
    else:
        season = "현재 시즌"

    missing = []
    if not destination:
        missing.append("여행지")
    if not start_date or not end_date:
        missing.append("여행 날짜")
    if adults <= 0:
        missing.append("인원")
    if budget_krw is None:
        missing.append("총 예산")
    if not style:
        missing.append("원하는 여행 스타일(미식/쇼핑/힐링/액티비티 등)")

    if missing:
        q = (
            "<div><b>일정을 더 정확히 맞추려면 아래 정보를 알려주세요.</b></div>"
            + f"<div style='margin-top:6px;'>누락 항목: {', '.join(missing)}</div>"
            + "<div style='margin-top:6px;'>예: 오사카 2명, 150만원, 2026-04-10~2026-04-13, 미식+쇼핑 위주</div>"
        )
        state["pending_intent"] = "itinerary"
        state["last_intent"] = "itinerary"
        if start_date:
            state["travel_checkin"] = start_date
        if end_date:
            state["travel_checkout"] = end_date
        if adults > 0:
            state["adults"] = adults
        if budget_krw is not None:
            state["max_price"] = budget_krw
        SESSION_STATE[sid] = state
        return {"response": q}

    if start_date:
        state["travel_checkin"] = start_date
    if end_date:
        state["travel_checkout"] = end_date
    if adults > 0:
        state["adults"] = adults
    if budget_krw is not None:
        state["max_price"] = budget_krw

    p = (
        "아래 조건으로 한국어 존댓말 여행 일정안을 HTML로 작성하세요.\n"
        "요구사항:\n"
        "1) <div> 기반으로 가독성 있게 구성하고, 마크다운/코드블록은 금지.\n"
        "2) 섹션은 반드시 다음 순서로: 여행 성향 요약, 예산 배분, 계절 추천 명소, Day별 일정.\n"
        "3) Day별 일정은 실제 여행일 수(입력 날짜 기준)로 만들고, 각 Day마다 오전/오후/저녁 추천 포함.\n"
        "4) 이동 동선이 비효율적이지 않게 같은 권역끼리 묶고, 각 일정 항목에 예상 이동시간(대중교통 기준 범위)을 짧게 표기.\n"
        "5) 예산은 총 예산을 절대 초과하지 않게 제안하고, 과소/과대 금액 추천은 금지.\n"
        f"6) 계절({season}) 특성을 반영한 추천 명소/주의사항(날씨, 혼잡도)을 포함.\n"
        "입력 조건:\n"
        + f"- 여행지: {destination}\n"
        + f"- 기간: {start_date} ~ {end_date}\n"
        + f"- 인원: {adults}명\n"
        + f"- 총 예산: {budget_krw}원\n"
        + f"- 여행 스타일: {style}\n"
        + f"- 최근 대화 참고: {context}\n"
        + f"- 사용자 질문: {msg}\n"
    )
    r = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "system", "content": "여행 일정 도우미"}, {"role": "user", "content": p}],
        temperature=0.3,
    )
    content = _strip_markdown_decorations((r.choices[0].message.content or "").strip())
    state.pop("pending_intent", None)
    state["last_intent"] = "itinerary"
    SESSION_STATE[sid] = state
    return {"response": content if content.startswith("<div") else f"<div>{content}</div>"}


def _resolve_effective_intent(req: Any, context: str, prev_state: dict, _resolve_intent_with_llm, _detect_intent, _has_date_signal, _contains, _should_keep_knowledge_followup, _is_local_place_followup, _is_route_guidance_query):
    llm_intent = _resolve_intent_with_llm(req.message, context, prev_state)
    rule_intent = _detect_intent(req.message, prev_state)
    intent = llm_intent or rule_intent

    if (
        prev_state.get("hotel_context")
        and _has_date_signal(req.message)
        and not _contains((req.message or "").lower(), ["항공", "비행", "flight", "일정", "코스", "itinerary"])
    ):
        intent = "hotel"

    has_hotel_signal = _contains((req.message or "").lower(), ["호텔", "숙소", "숙박", "체크인", "체크아웃"])
    has_flight_signal = _contains((req.message or "").lower(), ["항공", "항공권", "비행", "flight", "출발", "도착", "직항", "경유", "왕복", "편도"])
    if has_hotel_signal and not has_flight_signal:
        intent = "hotel"

    if intent == "flight" and _should_keep_knowledge_followup(req.message, prev_state):
        intent = "knowledge"
    if intent == "flight" and _is_local_place_followup(req.message, prev_state):
        intent = "knowledge"
    if intent == "flight" and _is_route_guidance_query(req.message):
        intent = "knowledge"

    return intent, llm_intent, rule_intent
def _should_return_intent_clarification(req: Any, prev_state: dict, intent: str, llm_intent, rule_intent, _is_local_place_followup, _should_ask_intent_clarification, _contains) -> bool:
    return (
        not _is_local_place_followup(req.message, prev_state)
        and _should_ask_intent_clarification(req.message, prev_state)
        and (
            (llm_intent is None and rule_intent == "flight")
            or (
                intent == "knowledge"
                and not _contains(
                    (req.message or "").lower(),
                    ["치안", "비자", "교통", "환율", "환전", "맛집", "명소", "카페", "쇼핑", "일정", "렌터카", "렌트카"],
                )
            )
        )
    )


def handle_chat_request(
    req: Any,
    *,
    SESSION_HISTORY: dict,
    SESSION_STATE: dict,
    NeedMoreInfoError: type,
    _build_context,
    _is_smalltalk_greeting,
    _classify_travel_domain_with_llm,
    _resolve_intent_with_llm,
    _detect_intent,
    _has_date_signal,
    _contains,
    _should_keep_knowledge_followup,
    _is_local_place_followup,
    _is_route_guidance_query,
    _should_ask_intent_clarification,
    _answer_knowledge,
    _parse_hotel_slots,
    hotel_service,
    client,
    _strip_markdown_decorations,
    _parse_flight_slots,
    _merge_state,
    _missing_questions,
    flight_search_service,
    chat_renderers,
):
    try:
        sid = (req.session_id or "default").strip() or "default"
        history = SESSION_HISTORY.setdefault(sid, [])
        history.append({"role": "user", "text": req.message})
        context = _build_context(history)
        prev_state = SESSION_STATE.get(sid, {})
        # Persist last mentioned country so short follow-up turns like
        # "?≫떚鍮꾪떚 ?쒕룞" can inherit country scope from previous turn.
        try:
            country_hint = product_reco_service.infer_country_hint(req.message, prev_state)
        except Exception:
            country_hint = ""
        if country_hint:
            seeded_state = dict(prev_state)
            seeded_state["country_hint"] = country_hint
            prev_state = seeded_state
            SESSION_STATE[sid] = seeded_state

        # Hard gate: ignore non-travel queries unless we are clearly in an active travel slot-filling flow.
        msg_l = (req.message or "").lower()
        has_travel_signal = _contains(
            msg_l,
            [
                "여행", "trip", "travel",
                "항공", "항공권", "비행", "flight", "출발", "도착", "직항", "경유",
                "호텔", "숙소", "숙박", "hotel", "체크인", "체크아웃",
                "렌터카", "렌트카", "rental", "car",
                "package", "groupbuy", "group buy", "ticket", "activity", "tour",
                "\uC5EC\uD589", "\uC561\uD2F0\uBE44\uD2F0", "\uD22C\uC5B4", "\uCD94\uCC9C",
                "\uD638\uD154", "\uC219\uC18C", "\uD56D\uACF5", "\uBE44\uD589", "\uD2F0\uCF13",
                "\uCF54\uC2A4", "\uC77C\uC815", "\uAD00\uAD11", "\uBA85\uC18C", "\uB9DB\uC9D1",
                "일정", "코스", "itinerary", "plan",
                "맛집", "명소", "관광", "교통", "비자", "환전", "치안",
            ],
        )
        has_core_travel_product_signal = _contains(
            msg_l,
            [
                "항공", "항공권", "비행", "flight", "출발", "도착", "직항", "경유",
                "호텔", "숙소", "숙박", "hotel", "체크인", "체크아웃",
                "렌터카", "렌트카", "rental", "pickup", "dropoff",
                "package", "groupbuy", "group buy", "ticket", "activity", "tour",
                "\uC561\uD2F0\uBE44\uD2F0", "\uD22C\uC5B4", "\uD2F0\uCF13",
                "\uD638\uD154", "\uC219\uC18C", "\uC77C\uC815", "\uCF54\uC2A4", "\uAD00\uAD11",
                "일정", "코스", "itinerary", "plan", "day",
                "맛집", "명소", "관광", "교통", "비자", "환전", "치안",
            ],
        )
        has_non_travel_entertainment_topic = _contains(
            msg_l,
            [
                "노래", "음악", "뮤직", "music", "song", "playlist", "플레이리스트",
                "영화", "드라마", "예능", "웹툰", "게임", "축구", "야구",
            ],
        )
        active_travel_followup = bool(
            prev_state.get("hotel_context")
            or prev_state.get("pending_intent") in {"flight", "hotel", "rentalcar", "itinerary", "product"}
            or prev_state.get("last_intent") in {"flight", "hotel", "rentalcar", "itinerary", "product"}
        )
        domain = _classify_travel_domain_with_llm(req.message, context)
        domain_is_non_travel = bool(domain and (domain.get("is_travel") is False))
        try:
            domain_conf = float((domain or {}).get("confidence") or 0)
        except Exception:
            domain_conf = 0.0
        if (
            (not active_travel_followup)
            and (
                (domain_is_non_travel and (domain_conf >= 0.45 or not has_travel_signal))
                or (has_non_travel_entertainment_topic and not has_core_travel_product_signal)
            )
        ):
            state = dict(prev_state)
            state["last_intent"] = "knowledge"
            SESSION_STATE[sid] = state
            return {"response": "<div>?ы뻾 愿??吏덈Ц留??듬??????덉뼱??</div>"}

        # Persist shared travel dates across intents (not only flight flow).
        # If a user mentions dates in any turn, keep them for later hotel/itinerary follow-ups.
        if _has_date_signal(req.message):
            try:
                parsed_for_dates = _parse_flight_slots(req.message, context) or {}
            except Exception:
                parsed_for_dates = {}
            dep = parsed_for_dates.get("departure_date")
            ret = parsed_for_dates.get("return_date")
            if dep or ret:
                seeded = dict(prev_state)
                if dep:
                    seeded["departure_date"] = dep
                    seeded["travel_checkin"] = dep
                if ret:
                    seeded["return_date"] = ret
                    seeded["travel_checkout"] = ret
                prev_state = seeded
                SESSION_STATE[sid] = seeded

        if _is_smalltalk_greeting(req.message):
            state = dict(prev_state)
            state["last_intent"] = "knowledge"
            SESSION_STATE[sid] = state
            return {
                "response": (
                    "<div>?덈뀞?섏꽭?? DESTINO AI ?ы뻾 ?뚮옒?덉엯?덈떎.<br>"
                    "??났?? ?숈냼, ?ы뻾吏 ?뺣낫, ?쇱젙 異붿쿇源뚯? ?꾩??쒕┫寃뚯슂.</div>"
                )
            }

        if (not active_travel_followup) and domain and (domain.get("is_travel") is False) and float(domain.get("confidence") or 0) >= 0.6 and (not has_travel_signal):
            state = dict(prev_state)
            state["last_intent"] = "knowledge"
            SESSION_STATE[sid] = state
            return {
                "response": (
                    "<div>?ы뻾 愿??吏덈Ц??吏묒쨷?댁꽌 ?꾩??쒕━怨??덉뼱??<br>"
                    "??났?? ?숈냼, ?ы뻾吏 ?뺣낫, ?쇱젙, 留쏆쭛/紐낆냼 異붿쿇泥섎읆 ?ы뻾 二쇱젣濡?吏덈Ц??二쇱꽭??</div>"
                )
            }

        # Bundle flow: one prompt for flight + hotel (+ optional itinerary)
        if _is_bundle_reco_query(req.message, _contains):
            seeded_state = dict(prev_state)
            try:
                parsed_for_bundle = _parse_flight_slots(req.message, context) or {}
            except Exception:
                parsed_for_bundle = {}
            seeded_state = _merge_state(seeded_state, parsed_for_bundle)
            if not seeded_state.get("origin"):
                seeded_state["origin"] = "ICN"
            dep_q, ret_q = _extract_iso_date_range_quick(req.message)
            if dep_q and not seeded_state.get("departure_date"):
                seeded_state["departure_date"] = dep_q
                seeded_state["travel_checkin"] = dep_q
            if ret_q and not seeded_state.get("return_date"):
                seeded_state["return_date"] = ret_q
                seeded_state["travel_checkout"] = ret_q

            flight_res = _handle_flight_intent(
                req,
                seeded_state,
                context,
                SESSION_STATE,
                sid,
                NeedMoreInfoError,
                _parse_flight_slots,
                _has_date_signal,
                _merge_state,
                _missing_questions,
                flight_search_service,
                chat_renderers,
            )
            state_after_flight = dict(SESSION_STATE.get(sid, seeded_state))
            hotel_res = _handle_hotel_intent(
                req,
                state_after_flight,
                context,
                SESSION_STATE,
                sid,
                _parse_hotel_slots,
                hotel_service,
            )

            msg_l2 = (req.message or "").lower()
            wants_itinerary = _contains(msg_l2, ["?쇱젙", "肄붿뒪", "猷⑦듃", "itinerary", "plan"])
            itinerary_html = ""
            if wants_itinerary:
                state_after_hotel = dict(SESSION_STATE.get(sid, state_after_flight))
                itinerary_res = _handle_itinerary_intent(
                    req,
                    state_after_hotel,
                    context,
                    SESSION_STATE,
                    sid,
                    client,
                    _strip_markdown_decorations,
                )
                itinerary_html = str(itinerary_res.get("response") or "")

            return {
                "response": (
                    "<div><b>?ы뻾 珥덉븞 異붿쿇</b></div>"
                    "<div style='margin-top:8px;'><b>??났沅?異붿쿇</b></div>"
                    + str(flight_res.get("response") or "")
                    + "<div style='margin-top:12px;'><b>?숈냼 異붿쿇</b></div>"
                    + str(hotel_res.get("response") or "")
                    + (f"<div style='margin-top:12px;'><b>?쇱젙 異붿쿇</b></div>{itinerary_html}" if itinerary_html else "")
                )
            }

        llm_intent = _resolve_intent_with_llm(req.message, context, prev_state)
        rule_intent = _detect_intent(req.message, prev_state)
        intent = llm_intent or rule_intent

        # Flight follow-up guard: when we are waiting for missing flight slots,
        # keep routing short/date-only replies to flight.
        if (
            str(prev_state.get("pending_intent") or "") == "flight"
            and not prev_state.get("hotel_context")
            and str(prev_state.get("last_intent") or "") != "hotel"
            and not _contains(
                (req.message or "").lower(),
                [
                    "hotel", "rental", "rent car", "car rental", "itinerary", "plan",
                    "package", "groupbuy", "group buy", "ticket",
                    "\uD638\uD154", "\uC219\uC18C", "\uB80C\uD130\uCE74", "\uB80C\uD2B8\uCE74",
                    "\uC77C\uC815", "\uCF54\uC2A4", "\uD328\uD0A4\uC9C0", "\uACF5\uB3D9\uAD6C\uB9E4",
                    "\uD2F0\uCF13",
                ],
            )
            and (
                _has_date_signal(req.message)
                or len((req.message or "").strip()) <= 24
            )
        ):
            intent = "flight"

        # Itinerary follow-up guard: keep short preference/budget/date replies in itinerary flow.
        if (
            str(prev_state.get("pending_intent") or "") == "itinerary"
            and not _contains(
                (req.message or "").lower(),
                ["flight", "hotel", "rental", "ticket", "package", "항공", "호텔", "렌터카", "티켓", "패키지"],
            )
            and len((req.message or "").strip()) <= 80
        ):
            intent = "itinerary"

        # Hotel follow-up guard: date-only replies after hotel prompts should stay in hotel flow,
        # not jump to itinerary.
        if (
            prev_state.get("hotel_context")
            and _has_date_signal(req.message)
            and not _contains((req.message or "").lower(), ["항공", "비행", "flight", "일정", "코스", "itinerary"])
        ):
            intent = "hotel"

        # Rental follow-up guard: date/location-only replies after rental prompts
        # should continue rental flow instead of falling to knowledge.
        if (
            prev_state.get("rental_context")
            and not _contains((req.message or "").lower(), ["flight", "hotel", "itinerary", "schedule", "plan"])
            and (
                _has_date_signal(req.message)
                or _contains((req.message or "").lower(), ["pickup", "dropoff", "rental", "rent car", "car rental"])
                or ("에서" in (req.message or ""))
            )
        ):
            intent = "rentalcar"

        # Deterministic override: explicit hotel requests should not be swallowed by LLM flight guesses.
        has_hotel_signal = _contains((req.message or "").lower(), ["호텔", "숙소", "숙박", "체크인", "체크아웃"])
        has_flight_signal = _contains((req.message or "").lower(), ["항공", "항공권", "비행", "flight", "출발", "도착", "직항", "경유", "왕복", "편도"])
        if has_hotel_signal and not has_flight_signal:
            intent = "hotel"

        # Deterministic override: explicit product requests should route to product.
        has_product_signal = _contains(
            (req.message or "").lower(),
            [
                "package", "groupbuy", "group buy", "ticket",
                "\uD328\uD0A4\uC9C0", "\uACF5\uB3D9\uAD6C\uB9E4", "\uD2F0\uCF13", "\uC785\uC7A5\uAD8C", "\uAD00\uB78C\uAD8C", "\uC561\uD2F0\uBE44\uD2F0", "\uCCB4\uD5D8", "\uD22C\uC5B4",
            ],
        )
        if has_product_signal and not has_flight_signal and not has_hotel_signal:
            intent = "product"

        # Keep contextual knowledge follow-ups out of the flight default path.
        if intent == "flight" and _should_keep_knowledge_followup(req.message, prev_state):
            intent = "knowledge"

        # Local recommendation queries (shopping/spots/food/cafe) should not fall into flight search.
        if intent == "flight" and _is_local_place_followup(req.message, prev_state):
            intent = "knowledge"

        # Route place-to-place guidance questions to travel info (transport) unless flights are explicit.
        if intent == "flight" and _is_route_guidance_query(req.message):
            intent = "knowledge"
        if _should_return_intent_clarification(
            req,
            prev_state,
            intent,
            llm_intent,
            rule_intent,
            _is_local_place_followup,
            _should_ask_intent_clarification,
            _contains,
        ):
            state = dict(prev_state)
            state["last_intent"] = "knowledge"
            SESSION_STATE[sid] = state
            return {
                "response": (
                    "<div>醫뗭븘?? 臾댁뾿???꾩??쒕┫吏 ?뺤씤?대낵寃뚯슂.<br>"
                    "?먰븯?쒕뒗 寃껋? <b>??났??/b> / <b>?숈냼</b> / <b>?뚰꽣移?/b> / <b>?ы뻾 ?쇱젙</b> / "
                    "<b>?ы뻾 ?뺣낫(臾명솕쨌移섏븞쨌援먰넻)</b> 以??대뒓 寃껋씤媛??</div>"
                )
            }

        if intent == "knowledge":
            return _handle_knowledge_intent(req, prev_state, context, SESSION_STATE, sid, _answer_knowledge)

        if intent == "hotel":
            return _handle_hotel_intent(req, prev_state, context, SESSION_STATE, sid, _parse_hotel_slots, hotel_service)
        if intent == "rentalcar":
            return _handle_rentalcar_intent(req, prev_state, SESSION_STATE, sid)
        if intent == "itinerary":
            return _handle_itinerary_intent(req, prev_state, context, SESSION_STATE, sid, client, _strip_markdown_decorations)
        if intent == "product":
            return _handle_product_intent(req, prev_state, SESSION_STATE, sid, chat_renderers)

        return _handle_flight_intent(
            req,
            prev_state,
            context,
            SESSION_STATE,
            sid,
            NeedMoreInfoError,
            _parse_flight_slots,
            _has_date_signal,
            _merge_state,
            _missing_questions,
            flight_search_service,
            chat_renderers,
        )
    except NeedMoreInfoError as e:
        return {"response": f"<p>醫뗭븘?? ?댁뼱??李얠쓣寃뚯슂. {e}</p>"}
    except Exception as e:
        sid = (req.session_id or "default").strip() or "default"
        history = SESSION_HISTORY.setdefault(sid, [])
        err_text = str(e)
        if "500 Server Error" in err_text and "amadeus.com/v2/shopping/flight-offers" in err_text:
            msg = "Amadeus \uc9c1\ud56d\ud68c \uc9c1\ud56d\ud68c \uc9c1\ud56d\uc9c1\ud56d\ud68c \uc9c1\ud56d\uc9c1\ud56d\uc9c1\ud56d. \uc9c1\ud56d\ud68c \uc9c1\ud56d \uc9c1\ud56d\ud68c \uc9c1\ud56d\uc9c1\ud56d \uc9c1\ud56d \ud68c \uc9c1\ud56d \uc9c1\ud56d\ud68c \uc9c1\ud56d\ud68c."
            history.append({"role": "assistant", "text": msg})
            return {"response": f"<div>{msg}</div>"}
        history.append({"role": "assistant", "text": f"泥섎━ 以??ㅻ쪟: {err_text}"})
        return {"response": f"<pre>泥섎━ 以??ㅻ쪟: {err_text}</pre>"}

