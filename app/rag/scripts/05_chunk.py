import csv
import json
import re
import datetime as dt
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]  # app/rag
KST = dt.timezone(dt.timedelta(hours=9))

SOURCES_CSV = BASE_DIR / "sources" / "seed_list.csv"
RAW_ROOT = BASE_DIR / "raw"
CLEAN_ROOT = BASE_DIR / "cleaned"
OUT_ROOT = BASE_DIR / "chunks"


def latest_dir(root: Path) -> Path:
    dirs = sorted([p for p in root.iterdir() if p.is_dir()])
    if not dirs:
        raise FileNotFoundError(f"No dirs in {root}")
    return dirs[-1]


def load_seed_map():
    m = {}
    with open(SOURCES_CSV, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            seed_id = row["seed_id"].strip()
            m[seed_id] = row
    return m


def infer_subtopic(topic, text):
    t = (text or "").lower()
    topic = (topic or "").lower()

    if topic == "transport":
        rules = [
            ("ticket_pass", ["pass", "ticket", "24-hr", "48-hr", "72-hr", "subway ticket", "day pass"]),
            ("ic_card", ["suica", "pasmo", "ic card", "smart card"]),
            ("metro_subway", ["metro", "subway", "underground", "asakusa", "ginza line", "marunouchi"]),
            ("bus", [" bus", "route", "limousine bus", "airport bus"]),
            ("taxi", ["taxi", "cab", "fare", "surcharge"]),
            ("airport_access", ["narita", "haneda", "airport", "limousine bus", "express"]),
            ("ferry", ["ferry", "terminal", "cruise", "boat", "mizube"]),
            ("rideshare", ["ride-sharing", "ridesharing", "uber"]),
            ("walking", ["walk", "on foot"]),
        ]
        for sub, kws in rules:
            if any(k in t for k in kws):
                return sub
        return "general"

    if topic == "culture":
        if any(k in t for k in ["tip", "tipping", "service charge", "gratuity"]):
            return "tipping"
        if any(k in t for k in ["restaurant", "dining", "eat", "food", "cuisine"]):
            return "dining"
        return "general"

    if topic in ["emergency", "safety", "health"]:
        if any(k in t for k in ["110", "119", "112", "ambulance", "police", "fire"]):
            return "emergency_numbers"
        if any(k in t for k in ["hospital", "medical", "insurance"]):
            return "medical"
        return "general"

    return None


def chunk_text(text: str, chunk_size: int = 1400, overlap: int = 250):
    """
    문자 수 기반 슬라이딩 청킹.
    줄바꿈이 있으면 최대한 문단 경계 우선.
    """
    text = text.strip()
    if len(text) <= chunk_size:
        return [text]

    chunks = []
    start = 0
    n = len(text)

    while start < n:
        end = min(start + chunk_size, n)

        # 문단 경계(빈 줄) 근처로 end를 조금 당겨서 자르기
        window = text[start:end]
        cut = None
        for pat in ["\n\n", "\n"]:
            idx = window.rfind(pat)
            if idx != -1 and idx > int(chunk_size * 0.6):
                cut = start + idx
                break
        if cut:
            end = cut

        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)

        if end >= n:
            break

        start = max(0, end - overlap)

    return chunks


def extract_seed_id_from_clean_filename(stem: str):
    # cleaned 파일명: "{seed_id}__YYYYMMDD"
    # seed_id는 "__" 앞
    if "__" in stem:
        return stem.split("__", 1)[0]
    return None


def main():
    raw_dir = latest_dir(RAW_ROOT)  # raw/YYYY-MM-DD
    clean_dir = latest_dir(CLEAN_ROOT)  # cleaned/YYYY-MM-DD
    date_str = clean_dir.name
    yyyymmdd = date_str.replace("-", "")

    cleaned_text_dir = clean_dir / "texts"
    out_dir = OUT_ROOT / date_str
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "chunks.jsonl"

    seed_map = load_seed_map()

    # cleaned txt 파일들
    txt_files = sorted(cleaned_text_dir.glob("*.txt"))
    total_chunks = 0
    total_files = 0

    with open(out_path, "w", encoding="utf-8") as out:
        for fp in txt_files:
            seed_id = extract_seed_id_from_clean_filename(fp.stem)
            if not seed_id or seed_id not in seed_map:
                # seed_id 매칭이 안 되면 스킵
                continue

            meta_row = seed_map[seed_id]
            text = fp.read_text(encoding="utf-8", errors="ignore").strip()
            if len(text) < 300:
                continue

            chunks = chunk_text(text, chunk_size=1400, overlap=250)

            # 메타데이터 구성
            metadata = {
                "scope": meta_row["scope"].strip(),
                "country_code": meta_row["country_code"].strip(),
                "country_name": meta_row["country_name"].strip(),
                "city_name": (meta_row.get("city_name") or "").strip() or None,
                "topic": meta_row["topic"].strip(),
                "subtopic": (meta_row.get("subtopic") or "").strip() or None,
                "source_type": meta_row["source_type"].strip(),
                "trust_tier": int(meta_row["trust_tier"]),
                "freshness_policy": meta_row["freshness_policy"].strip(),
                "source_url": meta_row["url"].strip(),
                "lang": (meta_row.get("lang") or "").strip() or "en",
                "fetched_at": date_str,
            }
            for i, ch in enumerate(chunks, start=1):
                doc_id = f"{seed_id}-{i:03d}-{yyyymmdd}"
                chunk_meta = dict(metadata)
                subtopic = infer_subtopic(chunk_meta["topic"], ch)
                if subtopic is not None:
                    chunk_meta["subtopic"] = subtopic
                rec = {"id": doc_id, "text": ch, "metadata": chunk_meta}
                out.write(json.dumps(rec, ensure_ascii=False) + "\n")
                total_chunks += 1

            total_files += 1

    print(f"Chunk done. files={total_files}, chunks={total_chunks}")
    print(f"Output: {out_path}")


if __name__ == "__main__":
    main()
