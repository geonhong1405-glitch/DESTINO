import os
import re
from typing import Any, Optional

from dotenv import load_dotenv
from fastapi import APIRouter, HTTPException, Request

try:
    from openai import OpenAI
except Exception as e:  # pragma: no cover
    OpenAI = None
    _openai_import_error = e
else:
    _openai_import_error = None

try:
    from pinecone import Pinecone
except Exception as e:  # pragma: no cover
    Pinecone = None
    _pinecone_import_error = e
else:
    _pinecone_import_error = None

load_dotenv()

router = APIRouter()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")
PINECONE_INDEX_NAME = os.getenv("PINECONE_INDEX_NAME")
PINECONE_NAMESPACE = os.getenv("PINECONE_NAMESPACE", "travel-knowledge")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")
RAG_TOP_K = int(os.getenv("RAG_TOP_K", "5"))

_client = OpenAI(api_key=OPENAI_API_KEY) if OpenAI and OPENAI_API_KEY else None
_pinecone_index = None


def _get_pinecone_index():
    global _pinecone_index
    if _pinecone_index is not None:
        return _pinecone_index
    if not Pinecone:
        raise RuntimeError(f"pinecone import failed: {_pinecone_import_error}")
    if not PINECONE_API_KEY or not PINECONE_INDEX_NAME:
        raise RuntimeError("PINECONE_API_KEY/PINECONE_INDEX_NAME not configured")
    pc = Pinecone(api_key=PINECONE_API_KEY)
    _pinecone_index = pc.Index(PINECONE_INDEX_NAME)
    return _pinecone_index


def _embed_text(text: str):
    if not _client:
        if _openai_import_error:
            raise RuntimeError(f"openai import failed: {_openai_import_error}")
        raise RuntimeError("OPENAI_API_KEY not configured")
    res = _client.embeddings.create(model=EMBEDDING_MODEL, input=text)
    return res.data[0].embedding


def _build_filter(
    country_code: Optional[str] = None,
    city_name: Optional[str] = None,
    topic: Optional[str] = None,
    subtopic: Optional[str] = None,
    trust_tier_min: Optional[int] = None,
):
    conds = []
    if country_code:
        conds.append({"country_code": {"$eq": str(country_code).upper()}})
    if city_name:
        conds.append({"city_name": {"$eq": str(city_name)}})
    if topic:
        conds.append({"topic": {"$eq": str(topic)}})
    if subtopic:
        conds.append({"subtopic": {"$eq": str(subtopic)}})
    if trust_tier_min is not None:
        try:
            conds.append({"trust_tier": {"$gte": int(trust_tier_min)}})
        except Exception:
            pass
    if not conds:
        return None
    return conds[0] if len(conds) == 1 else {"$and": conds}


def retrieve_rag_chunks(
    query: str,
    top_k: int = RAG_TOP_K,
    namespace: Optional[str] = None,
    country_code: Optional[str] = None,
    city_name: Optional[str] = None,
    topic: Optional[str] = None,
    subtopic: Optional[str] = None,
    trust_tier_min: Optional[int] = None,
) -> list[dict[str, Any]]:
    index = _get_pinecone_index()
    vector = _embed_text(query)
    filter_dict = _build_filter(
        country_code=country_code,
        city_name=city_name,
        topic=topic,
        subtopic=subtopic,
        trust_tier_min=trust_tier_min,
    )
    res = index.query(
        vector=vector,
        top_k=top_k,
        include_metadata=True,
        namespace=namespace or PINECONE_NAMESPACE,
        filter=filter_dict,
    )

    matches = getattr(res, "matches", None)
    if matches is None and isinstance(res, dict):
        matches = res.get("matches", [])

    chunks = []
    for m in (matches or []):
        meta = getattr(m, "metadata", None)
        if meta is None and isinstance(m, dict):
            meta = m.get("metadata", {}) or {}
        score = getattr(m, "score", None)
        if score is None and isinstance(m, dict):
            score = m.get("score")
        text = (meta or {}).get("text") or (meta or {}).get("content")
        if not text:
            continue
        chunks.append(
            {
                "text": text,
                "source": (meta or {}).get("source_url") or (meta or {}).get("source", "unknown"),
                "metadata": meta or {},
                "score": score,
            }
        )
    return chunks


def _detect_answer_language(question: str) -> str:
    return "ko" if re.search(r"[가-힣]", question or "") else "en"


def answer_rag_question(
    question: str,
    top_k: int = RAG_TOP_K,
    namespace: Optional[str] = None,
    country_code: Optional[str] = None,
    city_name: Optional[str] = None,
    topic: Optional[str] = None,
    subtopic: Optional[str] = None,
    trust_tier_min: Optional[int] = None,
    conversation_context: Optional[str] = None,
    retrieval_query: Optional[str] = None,
) -> dict[str, Any]:
    chunks = retrieve_rag_chunks(
        query=retrieval_query or question,
        top_k=top_k,
        namespace=namespace,
        country_code=country_code,
        city_name=city_name,
        topic=topic,
        subtopic=subtopic,
        trust_tier_min=trust_tier_min,
    )
    if not chunks:
        return {"answer": "관련 문서를 찾지 못했습니다. 질문을 조금 더 구체적으로 입력해 주세요.", "sources": [], "chunks": []}

    context_text = "\n\n".join([f"[문서{i+1}] {c['text']}" for i, c in enumerate(chunks)])
    source_list = sorted(set(c["source"] for c in chunks))

    if not _client:
        raise RuntimeError("OPENAI client not configured")

    if _detect_answer_language(question) == "ko":
        system_text = "RAG 기반 여행 도우미"
        extra_guide = []
        if "말고" in (question or "") or "제외" in (question or ""):
            extra_guide.append("이전 답변에서 이미 언급한 범주는 반복하지 말고 다른 범주 중심으로 답변하세요.")
        if "특징" in (question or ""):
            extra_guide.append("한 가지 주제(예: 음식)에 치우치지 말고 최소 3개 이상 범주(예: 문화/교통/예절/안전/결제)로 나눠 답변하세요.")
        extra_guide.append("영어 단어는 고유명사/상품명 외에는 되도록 한국어로 풀어써 주세요.")
        extra_guide.append("답변은 정적인 나열보다 여행자가 바로 이해하기 쉽게 핵심 요점 중심으로 써 주세요.")

        prompt = (
            "아래 문맥에 근거해서만 답변하세요. 문맥에 없는 내용은 추측하지 마세요. "
            "한국어 존댓말로 답변하세요. 규정/안전 정보는 모르면 모른다고 답하세요.\n"
            + "\n".join(f"- {x}" for x in extra_guide)
            + "\n\n"
            + (f"최근 대화:\n{conversation_context}\n\n" if conversation_context else "")
            + f"질문: {question}\n\n문맥:\n{context_text}"
        )
    else:
        system_text = "RAG travel assistant"
        prompt = (
            "Answer only using the provided context. Do not guess beyond the context. "
            "Be concise and practical.\n\n"
            f"Question: {question}\n\nContext:\n{context_text}"
        )

    res = _client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": system_text},
            {"role": "user", "content": prompt},
        ],
        temperature=0.2,
    )
    answer = (res.choices[0].message.content or "").strip()
    return {"answer": answer, "sources": source_list, "chunks": chunks}


@router.post("/rag/ask")
async def rag_ask(request: Request):
    try:
        data = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="invalid JSON body")

    question = (data.get("question") or "").strip()
    if not question:
        raise HTTPException(status_code=400, detail="No question provided")

    top_k = data.get("top_k") or RAG_TOP_K
    try:
        top_k = max(1, min(int(top_k), 10))
    except Exception:
        top_k = RAG_TOP_K

    try:
        return answer_rag_question(
            question=question,
            top_k=top_k,
            namespace=(data.get("namespace") or "").strip() or None,
            country_code=(data.get("country_code") or "").strip() or None,
            city_name=(data.get("city_name") or "").strip() or None,
            topic=(data.get("topic") or "").strip() or None,
            subtopic=(data.get("subtopic") or "").strip() or None,
            trust_tier_min=data.get("trust_tier_min"),
            conversation_context=(data.get("conversation_context") or "").strip() or None,
            retrieval_query=(data.get("retrieval_query") or "").strip() or None,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"RAG 처리 실패: {e}")


@router.get("/rag/health")
def rag_health():
    return {
        "openai_configured": bool(OPENAI_API_KEY),
        "pinecone_configured": bool(PINECONE_API_KEY and PINECONE_INDEX_NAME),
        "namespace": PINECONE_NAMESPACE,
        "embedding_model": EMBEDDING_MODEL,
        "top_k": RAG_TOP_K,
    }
