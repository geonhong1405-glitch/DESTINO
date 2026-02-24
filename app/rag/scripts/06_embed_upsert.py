import os
import json
import time
import datetime as dt
from pathlib import Path
from typing import List, Dict, Any

from dotenv import load_dotenv
from openai import OpenAI
from pinecone import Pinecone

BASE_DIR = Path(__file__).resolve().parents[1]  # app/rag
CHUNKS_ROOT = BASE_DIR / "chunks"

INDEX_NAME = os.getenv("PINECONE_INDEX_NAME", "travel-knowledge")
EMBED_MODEL = "text-embedding-3-small"  # 1536 dims

# 배치 크기: 너무 크면 타임아웃/레이트리밋, 너무 작으면 느림
EMBED_BATCH = 64
UPSERT_BATCH = 100

KST = dt.timezone(dt.timedelta(hours=9))

load_dotenv()


def latest_chunks_file() -> Path:
    dirs = sorted([p for p in CHUNKS_ROOT.iterdir() if p.is_dir()])
    if not dirs:
        raise FileNotFoundError(f"No chunk dirs in {CHUNKS_ROOT}")
    latest = dirs[-1]
    fp = latest / "chunks.jsonl"
    if not fp.exists():
        raise FileNotFoundError(f"Missing {fp}")
    return fp


def load_jsonl(path: Path) -> List[Dict[str, Any]]:
    rows = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def batch(iterable, n):
    buf = []
    for x in iterable:
        buf.append(x)
        if len(buf) >= n:
            yield buf
            buf = []
    if buf:
        yield buf


def embed_texts(client: OpenAI, texts: List[str]) -> List[List[float]]:
    resp = client.embeddings.create(model=EMBED_MODEL, input=texts)
    return [d.embedding for d in resp.data]


def namespace_for_scope(scope: str) -> str:
    s = (scope or "").strip().lower()
    if s == "city":
        return "city"
    return "country"


def build_vector(rec: Dict[str, Any], embedding: List[float]) -> Dict[str, Any]:
    meta = rec.get("metadata", {}) or {}
    text = rec.get("text", "")
    meta_out = dict(meta)
    # Pinecone metadata는 null(None) 값을 허용하지 않음
    meta_out = {k: v for k, v in meta_out.items() if v is not None}
    meta_out["text"] = text[:4000]
    meta_out["chunk_id"] = rec.get("id")

    return {
        "id": rec["id"],
        "values": embedding,
        "metadata": meta_out,
    }


def main():
    openai_key = os.getenv("OPENAI_API_KEY")
    pinecone_key = os.getenv("PINECONE_API_KEY")
    if not openai_key:
        raise RuntimeError("OPENAI_API_KEY not set")
    if not pinecone_key:
        raise RuntimeError("PINECONE_API_KEY not set")

    chunks_file = latest_chunks_file()
    date_str = chunks_file.parent.name

    print(f"Chunks: {chunks_file}")

    oai = OpenAI(api_key=openai_key)
    pc = Pinecone(api_key=pinecone_key)
    index = pc.Index(INDEX_NAME)

    rows = load_jsonl(chunks_file)
    print(f"Loaded {len(rows)} chunks")

    by_ns = {"country": [], "city": []}
    for r in rows:
        ns = namespace_for_scope(r.get("metadata", {}).get("scope"))
        by_ns[ns].append(r)

    for ns, recs in by_ns.items():
        if not recs:
            continue
        print(f"\n--- Namespace: {ns} | records={len(recs)} ---")

        upserted = 0
        for rec_batch in batch(recs, EMBED_BATCH):
            texts = [rb["text"] for rb in rec_batch]
            embeddings = embed_texts(oai, texts)
            vectors = [build_vector(rec_batch[i], embeddings[i]) for i in range(len(rec_batch))]

            for vec_batch in batch(vectors, UPSERT_BATCH):
                index.upsert(vectors=vec_batch, namespace=ns)
                upserted += len(vec_batch)

            time.sleep(0.2)

        print(f"Upserted {upserted} vectors into namespace '{ns}'")

    print("\nDone.")
    print(f"Index: {INDEX_NAME}")
    print(f"Date: {date_str}")
    print(f"Finished at: {dt.datetime.now(KST).isoformat()}")


if __name__ == "__main__":
    main()
