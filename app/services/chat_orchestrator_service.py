from typing import Any

from app.services import rentalcar_service


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
    if not _has_date_signal(req.message):
        parsed["departure_date"] = None
        parsed["return_date"] = None
    state = _merge_state(prev_state, parsed)
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
    state["last_intent"] = "rentalcar"
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

        domain = _classify_travel_domain_with_llm(req.message, context)
        if domain and (domain.get("is_travel") is False) and float(domain.get("confidence") or 0) >= 0.6:
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
        history.append({"role": "assistant", "text": f"\uc9c1\ud56d \uc9c1\ud56d \uc9c1\ud56d: {err_text}"})
        return {"response": f"<pre>\uc9c1\ud56d \uc9c1\ud56d \uc9c1\ud56d: {err_text}</pre>"}
