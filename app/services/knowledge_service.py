from typing import Any, Callable, Optional


def answer_knowledge(
    message: str,
    context: str,
    prev_state: Optional[dict[str, Any]] = None,
    *,
    _is_local_place_followup: Callable[..., bool],
    _answer_local_place_followup: Callable[..., tuple[str, dict[str, Any]]],
    _resolve_knowledge_context_with_llm: Callable[..., dict[str, Any]],
    _infer_rag_country_code: Callable[[list[str]], Optional[str]],
    _build_knowledge_retrieval_query: Callable[..., str],
    _knowledge_top_k: Callable[..., int],
    answer_rag_question: Callable[..., dict[str, Any]],
    _strip_markdown_decorations: Callable[[str], str],
):
    msg = message or ""
    if _is_local_place_followup(message, prev_state):
        try:
            return _answer_local_place_followup(message, context, prev_state)
        except Exception:
            pass

    llm_ctx = _resolve_knowledge_context_with_llm(message, context, prev_state)

    country_code = llm_ctx.get("country_code")
    city_name = llm_ctx.get("city_name")
    topic = llm_ctx.get("topic")
    subtopic = llm_ctx.get("subtopic")
    namespace = None

    # Fallback: infer country/city from current message or recent context.
    if not country_code:
        country_code = _infer_rag_country_code([msg, context or ""])

    if not city_name:
        if any(k in msg for k in ["\ub3c4\ucfc4"]) or any(k in (context or "") for k in ["\ub3c4\ucfc4"]):
            city_name = "Tokyo"
        elif any(k in msg for k in ["\uc624\uc0ac\uce74"]) or any(k in (context or "") for k in ["\uc624\uc0ac\uce74"]):
            city_name = "Osaka"

    # Fallback: infer topic/subtopic only when LLM didn't resolve it.
    if topic is None and any(k in msg for k in ["\uad50\ud1b5", "\uc9c0\ud558\ucca0", "\uc804\ucca0", "\ubc84\uc2a4", "\uc774\ub3d9", "\ud328\uc2a4", "\uc2a4\uc774\uce74", "\ud30c\uc2a4\ubaa8"]):
        topic = "transport"
        if any(k in msg for k in ["\uc9c0\ud558\ucca0", "\uc804\ucca0", "\uba54\ud2b8\ub85c", "subway"]):
            subtopic = subtopic or "metro_subway"
        elif any(k in msg for k in ["\ud328\uc2a4", "\ud2f0\ucf13", "\uad50\ud1b5\uce74\ub4dc", "\uc2a4\uc774\uce74", "\ud30c\uc2a4\ubaa8"]):
            subtopic = subtopic or "ticket_pass"
    elif topic is None and any(k in msg for k in ["\uce58\uc548", "\uc548\uc804", "\uc704\ud5d8", "\uc8fc\uc758"]):
        topic = "safety"
    elif topic is None and any(k in msg for k in ["\ube44\uc790", "\uc785\uad6d"]):
        topic = "visa"
    elif topic is None and any(k in msg for k in ["\ubb38\ud654", "\uc608\uc808", "\ud301", "\uc2dd\ub2f9", "\ub808\uc2a4\ud1a0\ub791", "\uc74c\uc2dd", "\uba39\uc744\uac70", "\uc694\ub9ac", "food", "cuisine"]):
        topic = "culture"
        if any(k in msg for k in ["\ud301", "\ud301\ubb38\ud654", "tipping"]):
            subtopic = subtopic or "tipping"
        elif any(k in msg for k in ["\uc74c\uc2dd", "\uba39\uc744\uac70", "\uc694\ub9ac", "food", "cuisine"]):
            subtopic = subtopic or "dining"
    elif topic is None and any(k in msg for k in ["\uc751\uae09", "\uae34\uae09", "\uacbd\ucc30", "\uad6c\uae09\ucc28", "119", "110"]):
        topic = "emergency"
        subtopic = subtopic or "emergency_numbers"

    # Namespace selection (LLM-first, then fallback).
    if topic == "transport":
        namespace = "city" if city_name else "country"
    elif topic in {"culture", "visa", "safety", "emergency", "health", "money", "connectivity"}:
        namespace = "country"
    elif country_code:
        namespace = "country"

    # Country-level knowledge should not carry a city filter unless explicitly city-specific transport context.
    if namespace == "country" and topic != "transport":
        city_name = None

    retrieval_query = _build_knowledge_retrieval_query(
        message=message,
        country_code=country_code,
        city_name=city_name,
        topic=topic,
        subtopic=subtopic,
    )
    top_k = _knowledge_top_k(message, topic, subtopic)

    try:
        result = answer_rag_question(
            question=message,
            top_k=top_k,
            namespace=namespace,
            country_code=country_code,
            city_name=city_name,
            topic=topic,
            subtopic=subtopic,
            trust_tier_min=1,
            conversation_context=context,
            retrieval_query=retrieval_query,
        )

        # Fallback: if strict filters return nothing, relax topic/subtopic/city filters for same country namespace.
        if not result.get("chunks") and country_code:
            result = answer_rag_question(
                question=message,
                top_k=top_k,
                namespace="country",
                country_code=country_code,
                city_name=None,
                topic=None,
                subtopic=None,
                trust_tier_min=1,
                conversation_context=context,
                retrieval_query=retrieval_query,
            )

        content = (result.get("answer") or "").strip()
        # Some safety/emergency queries retrieve weak chunks and the LLM answers with a strict "no context" template.
        # In that case, retry once with broader country-level retrieval focused on safety keywords.
        if (
            topic in {"safety", "emergency"}
            and country_code
            and any(
                x in content
                for x in [
                    "\uad00\ub828 \ubb38\uc11c\ub97c \ucc3e\uc9c0 \ubabb\ud588\uc2b5\ub2c8\ub2e4",
                    "\uc81c\uacf5\ud560 \uc218 \uc5c6\uc2b5\ub2c8\ub2e4",
                    "\ubb38\ub9e5\uc5d0",
                    "\uc8c4\uc1a1\ud558\uc9c0\ub9cc",
                    "\ud655\uc778 \ud544\uc694",
                ]
            )
        ):
            broad_query = _build_knowledge_retrieval_query(
                message=f"{message} \uc548\uc804 \uce58\uc548 \uc8fc\uc758\uc0ac\ud56d \ubc94\uc8c4 \uacbd\ucc30 \uae34\uae09\ubc88\ud638",
                country_code=country_code,
                city_name=None,
                topic=None,
                subtopic=None,
            )
            retry = answer_rag_question(
                question=message,
                top_k=max(top_k, 8),
                namespace="country",
                country_code=country_code,
                city_name=None,
                topic=None,
                subtopic=None,
                trust_tier_min=1,
                conversation_context=context,
                retrieval_query=broad_query,
            )
            if retry.get("answer"):
                result = retry
                content = (retry.get("answer") or "").strip()
        # Money/exchange-rate questions should avoid misleading generic currency descriptions
        # when the retrieved context does not contain a current numeric rate.
        if topic == "money" and any(k in msg for k in ["환율", "환전"]):
            money_noise_markers = ["지폐", "동전", "1,000엔", "10,000엔"]
            if any(x in content for x in money_noise_markers) and "환율" in msg:
                content = (
                    "실시간 환율은 시점에 따라 계속 변동되므로 여기서 정확한 숫자를 단정해 드리기 어렵습니다. "
                    "대신 여행 준비 기준으로는 공항 환전소/은행 환전 수수료와 카드 해외결제 수수료를 함께 비교하시는 게 좋습니다. "
                    "원하시면 현재 환율 조회 기준(원화↔엔화)으로 확인하는 방법도 안내해드릴게요."
                )
        no_context_markers = [
            "문맥에 포함",
            "제공할 수 없습니다",
            "관련 문서를 찾지 못했습니다",
            "정확한 답변을 드릴 수 없습니다",
        ]
        # Tone cleanup: avoid machine-like RAG refusal phrasing for user-facing travel chat.
        if "문맥에 포함되어" in content:
            content = content.replace("문맥에 포함되어 있지 않아", "현재 확보된 정보만으로는").replace("문맥에 포함되어 있지 않습니다", "현재 확보된 정보만으로는 확인되지 않습니다")

        if content and not content.startswith("<div"):
            content = _strip_markdown_decorations(content)
        html = content if content and content.startswith("<div") else (f"<div>{content}</div>" if content else "<div>\uad00\ub828 \uc5ec\ud589 \uc9c0\uc2dd \ub2f5\ubcc0\uc744 \uc0dd\uc131\ud558\uc9c0 \ubabb\ud588\uc2b5\ub2c8\ub2e4.</div>")
        return html, {
            "knowledge_state": {
                "country_code": country_code,
                "city_name": city_name,
                "topic": topic,
                "subtopic": subtopic,
                "namespace": namespace,
            }
        }
    except Exception:
        return "<div>\uc9c0\uc2dd \ub2f5\ubcc0 \uc0dd\uc131 \uc911 \uc624\ub958\uac00 \ubc1c\uc0dd\ud588\uc2b5\ub2c8\ub2e4.</div>", {
            "knowledge_state": {
                "country_code": country_code,
                "city_name": city_name,
                "topic": topic,
                "subtopic": subtopic,
                "namespace": namespace,
            }
        }
