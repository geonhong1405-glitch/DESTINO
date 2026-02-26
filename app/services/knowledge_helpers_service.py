import json
from typing import Any, Optional


def resolve_knowledge_context_with_llm(
    message: str,
    context: str,
    prev_state: Optional[dict[str, Any]] = None,
    *,
    llm_json_fn,
    today_kst_str_fn,
    normalize_rag_country_code_fn,
) -> dict[str, Any]:
    """
    Extract knowledge-Q context: intent/country/city/topic/subtopic/exclude_topics.
    Uses English-only prompt to avoid encoding issues, but allows Korean input.
    """
    today = today_kst_str_fn()
    prev_k = (prev_state or {}).get("knowledge_state", {}) if isinstance(prev_state, dict) else {}

    prompt = (
        f"Today is {today} (Asia/Seoul).\n"
        "You are a travel knowledge context interpreter.\n"
        "Return ONLY JSON with this schema:\n"
        "{"
        "\"intent\":\"knowledge|unknown\","
        "\"country_code\":\"ISO2 like JP|KR|US|GB|FR|TH|VN|SG|MY|PH|AU|IN or null\","
        "\"city_name\":\"English standard city name or null\","
        "\"topic\":\"safety|culture|visa|transport|money|health|emergency|connectivity or null\","
        "\"subtopic\":\"string or null\","
        "\"exclude_topics\":[\"topic\", \"...\"]"
        "}\n"
        "Rules:\n"
        "- If it's a follow-up (e.g. user says 'then what about...'), use conversation context.\n"
        "- subway/train/transport card/pass => topic=transport\n"
        "- etiquette/tips/culture => topic=culture\n"
        "- emergency/police/ambulance/fire => topic=emergency or safety\n"
        "- If user asks in Korean, still output city_name in English.\n"
        "- If unknown, use null.\n\n"
        f"Previous knowledge state (reference): {json.dumps(prev_k, ensure_ascii=False)}\n"
        f"Recent conversation:\n{context}\n\n"
        f"User input:\n{message}\n"
        "Return ONLY the JSON object."
    )

    parsed = llm_json_fn("Return ONLY JSON for travel knowledge context.", prompt)
    if not isinstance(parsed, dict):
        parsed = {}

    out = {
        "intent": parsed.get("intent") or "unknown",
        "country_code": parsed.get("country_code") or None,
        "city_name": parsed.get("city_name") or None,
        "topic": parsed.get("topic") or None,
        "subtopic": parsed.get("subtopic") or None,
        "exclude_topics": parsed.get("exclude_topics") or [],
    }

    if isinstance(out["country_code"], str):
        out["country_code"] = normalize_rag_country_code_fn(out["country_code"])

    if isinstance(out["city_name"], str):
        out["city_name"] = out["city_name"].strip() or None

    if isinstance(out["topic"], str):
        out["topic"] = out["topic"].strip().lower() or None

    if isinstance(out["subtopic"], str):
        out["subtopic"] = out["subtopic"].strip() or None

    if not isinstance(out["exclude_topics"], list):
        out["exclude_topics"] = []

    # Final sanity: only allow known topics
    allowed_topics = {"safety", "culture", "visa", "transport", "money", "health", "emergency", "connectivity"}
    if out["topic"] not in allowed_topics:
        out["topic"] = None

    return out



def build_knowledge_retrieval_query(
    message: str,
    country_code: Optional[str],
    city_name: Optional[str],
    topic: Optional[str],
    subtopic: Optional[str],
) -> str:
    base = (message or "").strip()
    region = city_name or country_code or ""
    msg = message or ""

    # Broad "features" questions should span multiple categories.
    if topic is None and any(k in msg for k in ["\ud2b9\uc9d5", "\uc124\uba85", "\uc18c\uac1c", "\uc815\ubcf4"]):
        q = f"{region} travel overview culture etiquette transport money safety tips {base}".strip()
        if any(k in msg for k in ["\ub9d0\uace0", "\uc81c\uc678"]):
            q += " exclude food cuisine"
        return q

    topic_keywords = {
        "transport": "public transport subway metro train bus pass card ticket transfer station route",
        "safety": "travel safety crime police precautions scams night safety local safety advice",
        "emergency": "emergency numbers police ambulance fire emergency contact 110 119 what to do",
        "culture": "culture etiquette customs manners social norms dining tipping",
        "visa": "visa entry requirements immigration passport stay duration documents",
        "money": "money payment cash card exchange currency atm fees",
        "health": "health medical hospital pharmacy insurance clinic treatment",
        "connectivity": "sim esim wifi pocket wifi internet connectivity mobile data",
    }
    subtopic_keywords = {
        "metro_subway": "subway metro train line station transfer how to use",
        "ticket_pass": "ticket pass day pass 24-hour 48-hour 72-hour fare pass",
        "ic_card": "ic card transport card prepaid card suica pasmo tap in tap out",
        "tipping": "tipping gratuity service charge tip etiquette",
        "emergency_numbers": "emergency numbers police ambulance fire emergency phone number 110 119",
        "medical": "hospital clinic ambulance medical insurance emergency treatment",
    }

    parts = [p for p in [region, topic_keywords.get(topic or ""), subtopic_keywords.get(subtopic or ""), base] if p]
    return " ".join(parts).strip() or base



def rewrite_place_recommendation_fallback(
    city_name: str,
    category: str,
    keyword: Optional[str],
    message: str,
    context: str,
    *,
    client,
) -> Optional[str]:
    """
    API 후보를 못 찾았을 때도 사용자가 끊기지 않도록, 도시/카테고리/키워드 기준의
    일반 여행지식 추천을 LLM으로 생성한다. (실시간 재고/운영정보는 단정 금지)
    """
    try:
        category_ko = {
            "restaurant": "맛집",
            "attraction": "명소/놀거리",
            "cafe": "카페",
            "shopping": "쇼핑",
            "generic": "추천 장소",
        }.get(category, "추천 장소")
        kw = (keyword or "").strip()
        q_hint = f"{city_name} {kw} {category_ko}".strip()
        prompt = (
            "You are a travel recommendation assistant.\n"
            "The place APIs returned no reliable candidates, so provide a helpful fallback answer in Korean.\n"
            "Requirements:\n"
            "- Answer in Korean.\n"
            "- Do NOT pretend you found exact API results.\n"
            "- Give 3-5 practical area/store-type recommendations for the city and query intent.\n"
            "- If query is brand shopping, suggest neighborhoods/department stores/select shops to check.\n"
            "- Keep it readable for customers (short sections/bullets, no markdown ### or **).\n"
            "- Include a short note to verify current availability/hours before visiting.\n\n"
            f"City: {city_name}\n"
            f"Category: {category}\n"
            f"Keyword: {kw or '(none)'}\n"
            f"Query intent hint: {q_hint}\n"
            f"Recent context:\n{context}\n\n"
            f"User message:\n{message}\n"
        )
        r = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "Travel recommendation fallback writer. Output customer-friendly Korean only."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.4,
        )
        out = (r.choices[0].message.content or "").strip()
        if not out:
            return None
        # strip markdown decorations for UI consistency
        out = out.replace("###", "").replace("**", "").replace("`", "")
        return f"<div>{out}</div>"
    except Exception:
        return None



def rewrite_budget_destination_fallback(message: str, context: str, *, client) -> Optional[str]:
    try:
        r = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "\ub108\ub294 \uc5ec\ud589 \uc608\uc0b0 \uc0c1\ub2f4 \ub3c4\uc6b0\ubbf8\ub2e4. RAG \uadfc\uac70\uac00 \ubd80\uc871\ud574\ub3c4 \uc77c\ubc18\uc801\uc778 \uc5ec\ud589 \uc0c1\uc2dd \ubc94\uc704\uc5d0\uc11c \uc2e4\uc6a9\uc801\uc73c\ub85c \ub2f5\ud558\ub77c. "
                        "\uc2e4\uc2dc\uac04 \uac00\uaca9\uc744 \ub2e8\uc815\ud558\uc9c0 \ub9d0\uace0, \uc608\uc0b0 \uae30\uc900\uc774 \ub2ec\ub77c\uc9c8 \uc218 \uc788\uc74c\uc744 \uc9e7\uac8c \ubc1d\ud78c \ub4a4 \ud6c4\ubcf4\uc9c0\ub97c 3~5\uac1c \ucd94\ucc9c\ud558\ub77c. "
                        "\ub2f5\ubcc0\uc740 \ud55c\uad6d\uc5b4\ub85c, \uacfc\ud55c \ub9c8\ud06c\ub2e4\uc6b4(###, ** \ub4f1) \uc5c6\uc774 \uae54\ub054\ud55c \ubb38\uc7a5/\ubc88\ud638 \ubaa9\ub85d\uc73c\ub85c \uc791\uc131\ud558\ub77c. "
                        "\uac01 \ud6c4\ubcf4\ub9c8\ub2e4 \uc65c \uac00\uc131\ube44\uac00 \uc88b\uc740\uc9c0(\ud56d\uacf5/\uc219\uc18c/\ubb3c\uac00/\uc774\ub3d9/\uc2dc\uc98c\uc131)\ub97c \ud55c \uc904\uc529 \uc801\uace0, \ub9c8\uc9c0\ub9c9\uc5d0 \ube44\uc6a9 \uc808\uc57d \ud301 2~3\uac1c\ub97c \ubd99\uc5ec\ub77c."
                    ),
                },
                {
                    "role": "user",
                    "content": f"\ucd5c\uadfc \ub300\ud654:\n{context}\n\n\uc9c8\ubb38: {message}",
                },
            ],
            temperature=0.4,
        )
        return (r.choices[0].message.content or "").strip() or None
    except Exception:
        return None

