from typing import Any

from app.services import rentalcar_service
from app.services import product_reco_service


def _handle_knowledge_intent(req: Any, prev_state: dict, context: str, SESSION_STATE: dict, sid: str, _answer_knowledge):
    html, delta = _answer_knowledge(req.message, context, prev_state)
    state = dict(prev_state)
    state.update(delta or {})
    state["last_intent"] = "knowledge"
    SESSION_STATE[sid] = state
    return {"response": html}


def _handle_hotel_intent(req: Any, prev_state: dict, context: str, SESSION_STATE: dict, sid: str, _parse_hotel_slots, hotel_service):
    parsed_hotel = _parse_hotel_slots(req.message, context)
    html, delta = hotel_service.answer_hotel_from_parsed(parsed_hotel, prev_state)
    state = dict(prev_state)
    state.update(delta or {})
    state["last_intent"] = "hotel"
    SESSION_STATE[sid] = state
    return {"response": html}


def _handle_flight_intent(req: Any, prev_state: dict, context: str, SESSION_STATE: dict, sid: str, NeedMoreInfoError: type, _parse_flight_slots, _has_date_signal, _merge_state, _missing_questions, flight_search_service, chat_renderers):
    parsed = _parse_flight_slots(req.message, context)
    state = _merge_state(prev_state, parsed)
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

    # Shared travel dates can come from non-flight intents (hotel/rentalcar).
    if (not route_changed_without_date) and (not state.get("departure_date")) and prev_state.get("travel_checkin"):
        state["departure_date"] = prev_state.get("travel_checkin")
    if (not route_changed_without_date) and (not state.get("return_date")) and prev_state.get("travel_checkout"):
        state["return_date"] = prev_state.get("travel_checkout")
    if state.get("departure_date"):
        state["travel_checkin"] = state.get("departure_date")
    if state.get("return_date"):
        state["travel_checkout"] = state.get("return_date")
    missing = _missing_questions(state)
    if missing:
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
    state["last_intent"] = "rentalcar"
    SESSION_STATE[sid] = state
    return {"response": html}




def _handle_product_intent(req: Any, prev_state: dict, SESSION_STATE: dict, sid: str, chat_renderers):
    items = product_reco_service.recommend_products(req.message, prev_state, limit=8)
    html = chat_renderers.product_html_list(items, title="\ucd94\ucc9c \uc0c1\ud488")
    state = dict(prev_state)
    state["last_intent"] = "product"
    state["last_product_names"] = [str(x.get("name") or "") for x in items]
    first_type = str((items[0] or {}).get("type") or "") if items else ""
    state["last_product_type"] = first_type
    SESSION_STATE[sid] = state
    return {"response": html}


def _handle_itinerary_intent(req: Any, prev_state: dict, context: str, SESSION_STATE: dict, sid: str, client, _strip_markdown_decorations):
    p = f"질문 기반으로 Day1~Day3 여행일정을 한국어 존댓말로 작성. 질문:{req.message}\n대화:{context}"
    r = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "system", "content": "여행 일정 도우미"}, {"role": "user", "content": p}],
        temperature=0.3,
    )
    content = _strip_markdown_decorations((r.choices[0].message.content or "").strip())
    state = dict(prev_state)
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
            return {"response": "<div>여행 관련 질문만 답변할 수 있어요.</div>"}

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
                    "<div>안녕하세요. DESTINO AI 여행 플래너입니다.<br>"
                    "항공편, 숙소, 여행지 정보, 일정 추천까지 도와드릴게요.</div>"
                )
            }

        if (not active_travel_followup) and domain and (domain.get("is_travel") is False) and float(domain.get("confidence") or 0) >= 0.6:
            state = dict(prev_state)
            state["last_intent"] = "knowledge"
            SESSION_STATE[sid] = state
            return {
                "response": (
                    "<div>여행 관련 질문에 집중해서 도와드리고 있어요.<br>"
                    "항공편, 숙소, 여행지 정보, 일정, 맛집/명소 추천처럼 여행 주제로 질문해 주세요.</div>"
                )
            }

        llm_intent = _resolve_intent_with_llm(req.message, context, prev_state)
        rule_intent = _detect_intent(req.message, prev_state)
        intent = llm_intent or rule_intent

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
                    "<div>좋아요. 무엇을 도와드릴지 확인해볼게요.<br>"
                    "원하시는 것은 <b>항공편</b> / <b>숙소</b> / <b>렌터카</b> / <b>여행 일정</b> / "
                    "<b>여행 정보(문화·치안·교통)</b> 중 어느 것인가요?</div>"
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
        return {"response": f"<p>좋아요, 이어서 찾을게요. {e}</p>"}
    except Exception as e:
        sid = (req.session_id or "default").strip() or "default"
        history = SESSION_HISTORY.setdefault(sid, [])
        err_text = str(e)
        if "500 Server Error" in err_text and "amadeus.com/v2/shopping/flight-offers" in err_text:
            msg = "Amadeus \uc9c1\ud56d\ud68c \uc9c1\ud56d\ud68c \uc9c1\ud56d\uc9c1\ud56d\ud68c \uc9c1\ud56d\uc9c1\ud56d\uc9c1\ud56d. \uc9c1\ud56d\ud68c \uc9c1\ud56d \uc9c1\ud56d\ud68c \uc9c1\ud56d\uc9c1\ud56d \uc9c1\ud56d \ud68c \uc9c1\ud56d \uc9c1\ud56d\ud68c \uc9c1\ud56d\ud68c."
            history.append({"role": "assistant", "text": msg})
            return {"response": f"<div>{msg}</div>"}
        history.append({"role": "assistant", "text": f"처리 중 오류: {err_text}"})
        return {"response": f"<pre>처리 중 오류: {err_text}</pre>"}
