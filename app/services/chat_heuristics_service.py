from typing import Any, Optional


def is_smalltalk_greeting(message: str) -> bool:
    m = (message or "").strip().lower()
    if not m:
        return False
    greetings = [
        "안녕",
        "안녕하세요",
        "하이",
        "ㅎㅇ",
        "hello",
        "hi",
        "hey",
        "반가워",
        "반갑습니다",
    ]
    if m in greetings:
        return True
    if len(m) <= 6 and any(g in m for g in ["안녕", "hello", "hi", "hey"]):
        return True
    return False


def merge_state(prev: dict[str, Any], cur: dict[str, Any], *, slot_keys: list[str]) -> dict[str, Any]:
    out = dict(prev or {})
    for key in slot_keys:
        value = cur.get(key)
        if value is None:
            continue
        if isinstance(value, str) and value.strip().lower() in {"", "null", "none", "unknown", "n/a", "-"}:
            continue
        out[key] = value
    out.setdefault("adults", 1)
    out.setdefault("children", 0)
    out.setdefault("infants", 0)
    return out


def missing_questions(state: dict[str, Any]) -> list[str]:
    q = []
    if not state.get("origin"):
        q.append("출발지를 알려주세요. (예: 서울, 부산, ICN)")
    if not state.get("destination"):
        q.append("도착지를 알려주세요. (예: 도쿄, 부산, NRT)")
    if not state.get("departure_date"):
        q.append("출발일을 알려주세요. (YYYY-MM-DD 또는 예: 3월 15일)")
    if state.get("trip_type") == "round" and not state.get("return_date"):
        q.append("왕복 일정이므로 복귀일을 알려주세요. (YYYY-MM-DD)")
    return q


def knowledge_top_k(message: str, topic: Optional[str], subtopic: Optional[str], *, rag_top_k: int) -> int:
    msg = message or ""
    k = rag_top_k

    if any(x in msg for x in ["특징", "설명", "소개", "정보", "추천"]):
        k = max(k, 8)

    if topic in {"safety", "emergency", "health"}:
        k = max(k, 8)

    if subtopic in {"metro_subway", "ticket_pass", "ic_card", "tipping", "emergency_numbers"}:
        k = min(max(k, 4), 6)

    if topic in {"visa", "money", "connectivity"} and not any(x in msg for x in ["특징", "설명", "소개"]):
        k = min(max(k, 4), 6)

    return max(3, min(k, 10))
