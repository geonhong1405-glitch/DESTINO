import re
from typing import Any, Callable, Optional


def _has_ko(text: str, pattern: str) -> bool:
    try:
        return bool(re.search(pattern, text))
    except re.error:
        return False


def detect_intent(message: str, prev_state: dict[str, Any], *, contains_fn: Callable[[str, list[str]], bool]) -> str:
    m = (message or "").lower()
    msg = str(message or "")

    has_ko_flight = _has_ko(msg, r"(\uD56D\uACF5|\uD56D\uACF5\uD3B8|\uBE44\uD589\uAE30|\uCD9C\uBC1C|\uB3C4\uCC29|\uC9C1\uD56D|\uACBD\uC720)")
    has_ko_hotel = _has_ko(msg, r"(\uD638\uD154|\uC219\uC18C|\uCCB4\uD06C\uC778|\uCCB4\uD06C\uC544\uC6C3)")
    has_ko_rental = _has_ko(msg, r"(\uB80C\uD130\uCE74|\uB80C\uD2B8\uCE74|\uCC28\uB7C9)")
    has_ko_itin = _has_ko(msg, r"(\uC77C\uC815|\uCF54\uC2A4|\uB8E8\uD2B8|\uD50C\uB79C)")
    has_ko_product = _has_ko(msg, r"(\uD328\uD0A4\uC9C0|\uACF5\uB3D9\uAD6C\uB9E4|\uD2F0\uCF13|\uC785\uC7A5\uAD8C|\uD22C\uC5B4)")

    if has_ko_flight and not has_ko_hotel:
        return "flight"
    if has_ko_hotel and not has_ko_flight:
        return "hotel"
    if has_ko_rental and not has_ko_flight and not has_ko_hotel:
        return "rentalcar"
    if has_ko_itin and not has_ko_flight and not has_ko_hotel:
        return "itinerary"
    if has_ko_product and not has_ko_flight and not has_ko_hotel and not has_ko_rental:
        return "product"

    flight_terms = [
        "flight",
        "airfare",
        "round trip",
        "one way",
        "\uD56D\uACF5",
        "\uD56D\uACF5\uAD8C",
        "\uBE44\uD589\uAE30",
        "\uCD9C\uBC1C",
        "\uB3C4\uCC29",
        "\uC9C1\uD56D",
        "\uACBD\uC720",
    ]
    hotel_terms = ["hotel", "\uD638\uD154", "\uC219\uC18C", "\uCCB4\uD06C\uC778", "\uCCB4\uD06C\uC544\uC6C3"]
    rental_terms = ["rental car", "rent car", "car rental", "\uB80C\uD130\uCE74", "\uB80C\uD2B8\uCE74", "\uCC28\uB7C9", "\uB300\uC5EC", "\uBC18\uB0A9"]
    itinerary_terms = ["itinerary", "plan", "route", "\uC77C\uC815", "\uCF54\uC2A4", "\uB8E8\uD2B8", "\uD50C\uB79C"]
    product_terms = ["package", "groupbuy", "group buy", "ticket", "tour", "\uD328\uD0A4\uC9C0", "\uACF5\uB3D9\uAD6C\uB9E4", "\uD2F0\uCF13", "\uD22C\uC5B4"]

    score = {"flight": 0, "hotel": 0, "rentalcar": 0, "itinerary": 0, "product": 0}
    if contains_fn(m, flight_terms):
        score["flight"] += 3
    if contains_fn(m, hotel_terms):
        score["hotel"] += 3
    if contains_fn(m, rental_terms):
        score["rentalcar"] += 3
    if contains_fn(m, itinerary_terms):
        score["itinerary"] += 3
    if contains_fn(m, product_terms):
        score["product"] += 3

    best = max(score, key=score.get)
    if score[best] >= 3:
        return best

    if prev_state.get("last_intent") == "hotel" and not contains_fn(m, flight_terms):
        return "hotel"
    if prev_state.get("last_intent") == "flight" and contains_fn(m, ["\uC655\uBCF5", "\uD3B8\uB3C4", "round trip", "one way"]):
        return "flight"

    has_any_travel_signal = contains_fn(
        m,
        flight_terms + hotel_terms + rental_terms + itinerary_terms + product_terms + ["travel", "trip", "\uC5EC\uD589"],
    )
    if not has_any_travel_signal:
        return "knowledge"
    return "flight"


def resolve_intent_with_llm(
    message: str,
    context: str,
    prev_state: Optional[dict[str, Any]] = None,
    *,
    llm_json_fn: Callable[[str, str], dict[str, Any]],
    contains_fn: Callable[[str, list[str]], bool],
) -> Optional[str]:
    prev_state = prev_state or {}
    prev_intent = str(prev_state.get("last_intent") or "")
    prompt = (
        "You are a travel intent router. Return JSON only.\n"
        "{"
        '"intent":"flight|hotel|rentalcar|itinerary|product|knowledge|mixed|unknown",'
        '"parts":["flight","hotel","rentalcar","itinerary","product","knowledge"],'
        '"confidence":0.0'
        "}\n"
        f"Previous intent: {prev_intent}\nContext:\n{context}\nUser:\n{message}"
    )
    parsed = llm_json_fn("Travel intent JSON only", prompt)
    if not isinstance(parsed, dict):
        return None
    raw_intent = str(parsed.get("intent") or "").strip().lower()
    parts = parsed.get("parts") if isinstance(parsed.get("parts"), list) else []
    try:
        confidence = float(parsed.get("confidence", 0))
    except Exception:
        confidence = 0.0

    allowed = {"flight", "hotel", "rentalcar", "itinerary", "product", "knowledge"}
    if raw_intent in allowed:
        return raw_intent if confidence >= 0.45 else None
    if raw_intent == "mixed":
        norm_parts = [str(x).strip().lower() for x in parts if str(x).strip().lower() in allowed]
        for cand in ["flight", "hotel", "rentalcar", "itinerary", "product", "knowledge"]:
            if cand in norm_parts and confidence >= 0.4:
                return cand
    return None


def classify_travel_domain_with_llm(message: str, context: str = "", *, llm_json_fn: Callable[[str, str], dict[str, Any]]) -> Optional[dict[str, Any]]:
    prompt = (
        "Classify whether user message is travel-related. Return JSON only.\n"
        '{"is_travel":true,"confidence":0.0,"reason":"short"}\n'
        f"Context:\n{context}\nUser:\n{message}"
    )
    parsed = llm_json_fn("Travel domain classification JSON only", prompt)
    if not isinstance(parsed, dict):
        return None
    try:
        conf = float(parsed.get("confidence", 0))
    except Exception:
        conf = 0.0
    return {
        "is_travel": bool(parsed.get("is_travel")),
        "confidence": max(0.0, min(conf, 1.0)),
        "reason": str(parsed.get("reason") or "").strip(),
    }


def should_ask_intent_clarification(message: str, *, contains_fn: Callable[[str, list[str]], bool]) -> bool:
    m = (message or "").strip().lower()
    if not m:
        return False
    if contains_fn(
        m,
        [
            "\uD56D\uACF5",
            "\uD56D\uACF5\uAD8C",
            "\uBE44\uD589\uAE30",
            "\uD638\uD154",
            "\uC219\uC18C",
            "\uB80C\uD130\uCE74",
            "\uC77C\uC815",
            "\uD328\uD0A4\uC9C0",
            "\uD2F0\uCF13",
            "flight",
            "hotel",
            "rental",
            "itinerary",
            "package",
            "ticket",
        ],
    ):
        return False
    return contains_fn(m, ["\uC5EC\uD589", "\uCD94\uCC9C", "\uBA85\uC18C", "\uB9DB\uC9D1", "travel"])


def is_route_guidance_query(message: str, *, contains_fn: Callable[[str, list[str]], bool]) -> bool:
    m = (message or "").lower()
    route_phrases = ["\uAC00\uB294 \uBC29\uBC95", "\uC774\uB3D9 \uBC29\uBC95", "\uAD50\uD1B5\uD3B8", "how to get", "how do i get"]
    flight_phrases = ["\uD56D\uACF5", "\uD56D\uACF5\uAD8C", "\uBE44\uD589\uAE30", "flight", "airfare"]
    has_route_phrase = contains_fn(m, route_phrases)
    has_place_connector = ("\uC5D0\uC11C" in m and ("\uAC00" in m or "\uAE4C\uC9C0" in m)) or (" from " in m and " to " in m)
    return has_route_phrase and has_place_connector and not contains_fn(m, flight_phrases)


def should_keep_knowledge_followup(
    message: str,
    prev_state: Optional[dict[str, Any]] = None,
    *,
    contains_fn: Callable[[str, list[str]], bool],
) -> bool:
    prev_state = prev_state or {}
    if prev_state.get("last_intent") != "knowledge":
        return False
    prev_k = prev_state.get("knowledge_state") or {}
    if not isinstance(prev_k, dict):
        prev_k = {}
    if not any(prev_k.get(k) for k in ["country_code", "city_name", "location_query", "topic", "subtopic"]):
        return False
    m = (message or "").strip().lower()
    if not m:
        return False
    if contains_fn(
        m,
        [
            "\uD56D\uACF5",
            "\uD56D\uACF5\uAD8C",
            "\uBE44\uD589\uAE30",
            "\uD638\uD154",
            "\uC219\uC18C",
            "\uC77C\uC815",
            "flight",
            "hotel",
            "itinerary",
        ],
    ):
        return False
    short_followup = len(m) <= 40
    followup_tone = contains_fn(
        m,
        [
            "\uADF8\uB7FC",
            "\uC5B4\uB5BB\uAC8C",
            "\uC774\uB3D9",
            "\uBC84\uC2A4",
            "\uC9C0\uD558\uCCA0",
            "\uD0DD\uC2DC",
            "\uAE30\uCC28",
            "\uAC00\uACA9",
            "bus",
            "train",
            "metro",
            "subway",
            "taxi",
            "price",
        ],
    )
    return short_followup and followup_tone
