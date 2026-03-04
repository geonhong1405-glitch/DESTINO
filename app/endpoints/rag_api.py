import os
import re
from typing import Any, Optional
from typing import Dict, List

from dotenv import load_dotenv
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from app.rag.intent import classify_intent

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


class RagSearchRequest(BaseModel):
    query: str
    namespace: str = "country"
    top_k: int = 5
    filter: Optional[Dict[str, Any]] = None


class RagChunk(BaseModel):
    id: str
    score: float
    metadata: Dict[str, Any]


class RagSearchResponse(BaseModel):
    query: str
    matches: List[RagChunk]


class RagAnswerRequest(BaseModel):
    query: str
    country_code: Optional[str] = None
    city_name: Optional[str] = None
    topics: Optional[List[str]] = None
    namespace: Optional[str] = None
    top_k: int = 6


class RagAnswerResponse(BaseModel):
    intent: str
    answer: str
    citations: List[Dict[str, str]]
    matches: List[RagChunk]


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


def _generate_answer_from_chunks(
    question: str,
    chunks: list[dict[str, Any]],
    conversation_context: Optional[str] = None,
) -> dict[str, Any]:
    if not chunks:
        return {"answer": "관련 문서를 찾지 못했습니다. 질문을 조금 더 구체적으로 입력해 주세요.", "sources": [], "chunks": []}

    context_text = "\n\n".join([f"[문서{i+1}] {c['text']}" for i, c in enumerate(chunks)])
    source_list = sorted(set(c.get("source") or "unknown" for c in chunks))

    if not _client:
        raise RuntimeError("OPENAI client not configured")

    if _detect_answer_language(question) == "ko":
        system_text = "RAG 기반 여행 도우미"
        extra_guide = []
        if "말고" in (question or "") or "제외" in (question or ""):
            extra_guide.append("이전 답변에서 이미 언급한 범주는 반복하지 말고 다른 범주 중심으로 답변하세요.")
        if "특징" in (question or ""):
            extra_guide.append("한 가지 주제(예: 음식)에 치우치지 말고 최소 3개 이상 범주(예: 문화/교통/예절/안전/결제)로 나눠 답변하세요.")
        if any(k in (question or "") for k in ["환율", "환전"]):
            extra_guide.append("환율 질문에서 문맥에 정확한 수치/기준시점이 없으면 숫자를 임의로 말하지 마세요.")
            extra_guide.append("실시간 환율은 변동된다고 안내하고, 환전/결제 팁 위주로 실용적으로 답하세요.")
            extra_guide.append("지폐/동전 종류 설명으로 답변을 채우지 마세요(질문이 화폐 단위 구성일 때만 설명).")
        if any(k in (question or "") for k in ["관람비", "티켓", "입장권", "경기장", "좌석", "예매"]):
            extra_guide.append("티켓/관람비 질문에서 정확한 금액이 문맥에 없으면 자연스럽게 가격 변동 요인(상대팀/좌석/일정/예매시점)을 설명하세요.")
            extra_guide.append("기계적으로 '문맥에 포함되어 있지 않다'라고 말하지 말고, 확인 경로(구단 공식 사이트/티켓 페이지)를 안내하세요.")
            extra_guide.append("질문에 팀/경기장/도시 단서가 있으면 여행자 관점에서 위치/이동 팁도 함께 안내하세요.")
        extra_guide.append("영어 단어는 고유명사/상품명 외에는 되도록 한국어로 풀어써 주세요.")
        extra_guide.append("답변은 정적인 나열보다 여행자가 바로 이해하기 쉽게 핵심 요점 중심으로 써 주세요.")

        prompt = (
            "아래 문맥에 근거해서만 답변하세요. 문맥에 없는 내용은 추측하지 마세요. "
            "한국어 존댓말로 답변하세요. 규정/안전 정보는 모르면 모른다고 답하세요.\n"
            "거절할 때도 '문맥에 포함되어 있지 않습니다' 같은 기계적인 표현은 피하고, 무엇을 추가로 알면 답할 수 있는지 안내하세요.\n"
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
    return _generate_answer_from_chunks(
        question=question,
        chunks=chunks,
        conversation_context=conversation_context,
    )


def _query_pinecone_raw(query: str, namespace: str, top_k: int, filter_dict: Optional[dict] = None):
    index = _get_pinecone_index()
    vector = _embed_text(query)
    return index.query(
        vector=vector,
        top_k=max(1, min(int(top_k), 10)),
        include_metadata=True,
        namespace=namespace,
        filter=filter_dict,
    )


def _matches_to_records(matches_obj) -> list[dict[str, Any]]:
    matches = getattr(matches_obj, "matches", None)
    if matches is None and isinstance(matches_obj, dict):
        matches = matches_obj.get("matches", [])
    out: list[dict[str, Any]] = []
    for m in (matches or []):
        meta = getattr(m, "metadata", None)
        if meta is None and isinstance(m, dict):
            meta = m.get("metadata", {}) or {}
        score = getattr(m, "score", None)
        if score is None and isinstance(m, dict):
            score = m.get("score", 0.0)
        mid = getattr(m, "id", None)
        if mid is None and isinstance(m, dict):
            mid = m.get("id")
        out.append({"id": str(mid or ""), "score": float(score or 0.0), "metadata": meta or {}})
    return out


def _choose_namespace(req: RagAnswerRequest) -> str:
    if req.namespace:
        return req.namespace
    return "city" if req.city_name else "country"


def _build_answer_filter(req: RagAnswerRequest) -> Optional[dict]:
    conds = []
    if req.country_code:
        conds.append({"country_code": {"$eq": req.country_code.upper()}})
    if req.city_name:
        conds.append({"city_name": {"$eq": req.city_name}})
    if req.topics:
        topics = [t.strip() for t in req.topics if isinstance(t, str) and t.strip()]
        if topics:
            conds.append({"topic": {"$in": topics}})
    if not conds:
        return None
    return conds[0] if len(conds) == 1 else {"$and": conds}


def _format_evidence(matches: list[dict[str, Any]]):
    lines = []
    citations: list[dict[str, str]] = []
    for i, m in enumerate(matches, start=1):
        md = m.get("metadata") or {}
        txt = (md.get("text") or md.get("content") or "").strip()
        url = str(md.get("source_url") or md.get("source") or "")
        if txt:
            lines.append(f"{i}. {txt}\n출처: {url}")
        if url:
            citations.append({"n": str(i), "url": url})
    return "\n\n".join(lines), citations


@router.post("/rag/search", response_model=RagSearchResponse)
def rag_search(req: RagSearchRequest):
    try:
        res = _query_pinecone_raw(
            query=req.query,
            namespace=req.namespace or "country",
            top_k=req.top_k,
            filter_dict=req.filter,
        )
        records = _matches_to_records(res)
        return RagSearchResponse(query=req.query, matches=[RagChunk(**r) for r in records])
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"RAG 검색 오류: {e}")


@router.post("/rag/answer", response_model=RagAnswerResponse)
def rag_answer(req: RagAnswerRequest):
    intent_pack = classify_intent(req.query)
    intent = intent_pack["intent"]
    flags = intent_pack["flags"]
    namespace = _choose_namespace(req)
    flt = _build_answer_filter(req)
    if not flags.get("use_rag_info"):
        return RagAnswerResponse(
            intent=intent,
            answer=(
                f"(의도={intent}) 현재 /rag/answer는 정보(RAG) 답변만 연결되어 있습니다. "
                "항공/숙소/일정 API 라우팅을 연결하면 이 의도는 해당 결과로 응답하도록 확장할 수 있습니다."
            ),
            citations=[],
            matches=[],
        )
    try:
        res = _query_pinecone_raw(req.query, namespace, req.top_k, flt)
        records = _matches_to_records(res)
        if not records:
            return RagAnswerResponse(
                intent=intent,
                answer="관련 문서를 찾지 못했습니다. 질문을 조금 더 구체적으로 입력해 주세요.",
                citations=[],
                matches=[],
            )

        chunks = []
        for r in records:
            md = r.get("metadata") or {}
            txt = (md.get("text") or md.get("content") or "").strip()
            if not txt:
                continue
            chunks.append(
                {
                    "text": txt,
                    "source": md.get("source_url") or md.get("source") or "unknown",
                    "metadata": md,
                    "score": r.get("score"),
                }
            )
        generated = _generate_answer_from_chunks(question=req.query, chunks=chunks, conversation_context=None)
        _, citations = _format_evidence(records)
        answer = generated.get("answer") or ""
        return RagAnswerResponse(
            intent=intent,
            answer=answer,
            citations=citations,
            matches=[RagChunk(**r) for r in records],
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"RAG 답변 생성 오류: {e}")


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
