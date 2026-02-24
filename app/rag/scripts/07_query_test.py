import os

from dotenv import load_dotenv
from openai import OpenAI
from pinecone import Pinecone

load_dotenv()

INDEX_NAME = os.getenv("PINECONE_INDEX_NAME", "travel-knowledge")
EMBED_MODEL = "text-embedding-3-small"


def embed(oai: OpenAI, text: str):
    r = oai.embeddings.create(model=EMBED_MODEL, input=[text])
    return r.data[0].embedding


def run_query(index, oai, query, namespace, flt=None, top_k=5):
    vec = embed(oai, query)
    res = index.query(
        namespace=namespace,
        vector=vec,
        top_k=top_k,
        include_metadata=True,
        filter=flt,
    )
    print(f"\n=== QUERY: {query}")
    print(f"namespace={namespace}, filter={flt}, top_k={top_k}")
    for i, m in enumerate(res.matches, start=1):
        md = m.metadata or {}
        print(f"\n[{i}] score={m.score:.4f} id={m.id}")
        print(f"  country_code={md.get('country_code')} city_name={md.get('city_name')}")
        print(f"  topic={md.get('topic')} trust_tier={md.get('trust_tier')}")
        txt = md.get("text") or ""
        print("  text_preview:", txt[:240] + ("..." if len(txt) > 240 else ""))


def main():
    oai = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    pc = Pinecone(api_key=os.getenv("PINECONE_API_KEY"))
    index = pc.Index(INDEX_NAME)

    run_query(
        index,
        oai,
        query="Tokyo public transport and how to get around",
        namespace="city",
        flt={"country_code": {"$eq": "JP"}, "topic": {"$eq": "transport"}},
        top_k=5,
    )

    run_query(
        index,
        oai,
        query="Is tipping expected in Japan restaurants?",
        namespace="country",
        flt={"country_code": {"$eq": "JP"}, "topic": {"$eq": "culture"}},
        top_k=5,
    )

    run_query(
        index,
        oai,
        query="Japan emergency numbers and what to do in an emergency",
        namespace="country",
        flt={"country_code": {"$eq": "JP"}, "topic": {"$in": ["emergency", "safety", "health"]}},
        top_k=5,
    )


if __name__ == "__main__":
    main()
