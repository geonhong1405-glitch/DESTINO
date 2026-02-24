import csv
import datetime as dt
import hashlib
import json
from pathlib import Path
from urllib.parse import urlparse

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


# app/rag/scripts/03_fetch_raw.py -> app/rag
BASE_DIR = Path(__file__).resolve().parents[1]
SOURCES_CSV = BASE_DIR / "sources" / "seed_list.csv"

# Asia/Seoul 기준 날짜 폴더
KST = dt.timezone(dt.timedelta(hours=9))
TODAY = dt.datetime.now(KST).strftime("%Y-%m-%d")

RAW_DIR = BASE_DIR / "raw" / TODAY
HTML_DIR = RAW_DIR / "html"
PDF_DIR = RAW_DIR / "pdf"
OTHER_DIR = RAW_DIR / "other"
MANIFEST = RAW_DIR / "manifest.jsonl"


for d in (HTML_DIR, PDF_DIR, OTHER_DIR):
    d.mkdir(parents=True, exist_ok=True)


def sha256_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def make_session() -> requests.Session:
    session = requests.Session()
    retries = Retry(
        total=4,
        backoff_factor=0.8,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET"],
        raise_on_status=False,
    )
    adapter = HTTPAdapter(max_retries=retries)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    session.headers.update(
        {
            "User-Agent": "DESTINO-RAG-Bot/1.0 (+contact: your-email@example.com)",
            "Accept": "text/html,application/pdf,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en,ko;q=0.9,ja;q=0.8",
        }
    )
    return session


def detect_ext(content_type: str, url: str) -> str:
    ct = (content_type or "").lower()
    if "application/pdf" in ct:
        return "pdf"
    if "text/html" in ct or "application/xhtml+xml" in ct:
        return "html"

    path = urlparse(url).path.lower()
    for ext in ("pdf", "html", "htm", "txt", "json", "xml"):
        if path.endswith("." + ext):
            return ext
    return "bin"


def choose_dir(ext: str) -> Path:
    if ext in {"html", "htm"}:
        return HTML_DIR
    if ext == "pdf":
        return PDF_DIR
    return OTHER_DIR


def fetch_one(session: requests.Session, row: dict) -> dict:
    seed_id = (row.get("seed_id") or "").strip()
    url = (row.get("url") or "").strip()
    lang = (row.get("lang") or "").strip()

    record = {
        "seed_id": seed_id,
        "url": url,
        "lang": lang,
        "fetched_at": dt.datetime.now(KST).isoformat(),
        "status": "fail",
        "http_code": None,
        "content_type": None,
        "filepath": None,
        "sha256": None,
        "bytes": None,
        "error": None,
    }

    if not seed_id or not url:
        record["error"] = "missing seed_id or url"
        return record

    try:
        response = session.get(url, timeout=(10, 30))
        record["http_code"] = response.status_code
        record["content_type"] = response.headers.get("Content-Type", "")

        if response.status_code >= 400:
            record["error"] = f"HTTP {response.status_code}"
            return record

        content = response.content
        record["bytes"] = len(content)
        record["sha256"] = sha256_bytes(content)

        ext = detect_ext(record["content_type"], url)
        out_dir = choose_dir(ext)
        out_name = f"{seed_id}__{TODAY.replace('-', '')}.{ext}"
        out_path = out_dir / out_name
        out_path.write_bytes(content)

        record["filepath"] = str(out_path)
        record["status"] = "ok"
        return record
    except Exception as e:
        record["error"] = repr(e)
        return record


def main() -> None:
    if not SOURCES_CSV.exists():
        raise FileNotFoundError(f"seed csv not found: {SOURCES_CSV}")

    session = make_session()

    with open(SOURCES_CSV, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    ok = 0
    fail = 0
    with open(MANIFEST, "a", encoding="utf-8") as mf:
        for row in rows:
            notes = (row.get("notes") or "").lower()
            if "skip" in notes:
                continue

            rec = fetch_one(session, row)
            mf.write(json.dumps(rec, ensure_ascii=False) + "\n")

            if rec["status"] == "ok":
                ok += 1
            else:
                fail += 1
                print(f"[FAIL] {rec['seed_id']} -> {rec['error']} ({rec['http_code']})")

    print(f"Done. ok={ok}, fail={fail}")
    print(f"Raw saved to: {RAW_DIR}")
    print(f"Manifest: {MANIFEST}")


if __name__ == "__main__":
    main()
