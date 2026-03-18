import datetime as dt
import json
import re
from pathlib import Path

from bs4 import BeautifulSoup
from pypdf import PdfReader
from readability import Document


BASE_DIR = Path(__file__).resolve().parents[1]  # app/rag
RAW_ROOT = BASE_DIR / "raw"
CLEAN_ROOT = BASE_DIR / "cleaned"

KST = dt.timezone(dt.timedelta(hours=9))


def latest_raw_dir() -> Path:
    dirs = sorted([p for p in RAW_ROOT.iterdir() if p.is_dir()])
    if not dirs:
        raise FileNotFoundError(f"No raw dirs in {RAW_ROOT}")
    return dirs[-1]


def normalize_ws(text: str) -> str:
    text = text.replace("\r", "\n")
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"[ \t]{2,}", " ", text)
    return text.strip()


def html_to_text(html_bytes: bytes) -> str:
    html = html_bytes.decode("utf-8", errors="ignore")

    def strip_noise(soup: BeautifulSoup):
        for tag in soup(["script", "style", "noscript"]):
            tag.decompose()
        # 흔한 레이아웃 제거(있으면)
        for tag in soup.find_all(["header", "footer", "nav", "aside"]):
            tag.decompose()
        return soup

    def collect_blocks(soup: BeautifulSoup) -> str:
        parts = []
        # 구조화 페이지는 div/section 안에 p/li가 많음
        for el in soup.find_all(["h1", "h2", "h3", "h4", "p", "li"]):
            t = el.get_text(" ", strip=True)
            if not t:
                continue
            if len(t) < 2:
                continue
            parts.append(t)
        return "\n".join(parts).strip()

    # 1) readability 시도
    text1 = ""
    try:
        doc = Document(html)
        main_html = doc.summary(html_partial=True)
        soup1 = BeautifulSoup(main_html, "lxml")
        soup1 = strip_noise(soup1)
        text1 = collect_blocks(soup1)
        text1 = normalize_ws(text1)
    except Exception:
        text1 = ""

    # readability가 너무 짧으면 fallback
    if len(text1) >= 600:
        return text1

    # 2) 전체 HTML에서 p/li 중심으로 다시 추출
    soup2 = BeautifulSoup(html, "lxml")
    soup2 = strip_noise(soup2)
    text2 = collect_blocks(soup2)
    text2 = normalize_ws(text2)
    if len(text2) >= 600:
        return text2

    # 3) 최후: body 전체 텍스트 덤프(그래도 너무 짧으면 그대로 반환)
    body = soup2.body
    if body:
        text3 = body.get_text("\n", strip=True)
        text3 = normalize_ws(text3)
        return text3

    return normalize_ws(text2 or text1 or "")

def pdf_to_text(pdf_path: Path) -> str:
    reader = PdfReader(str(pdf_path))
    parts = []
    for page in reader.pages:
        try:
            t = page.extract_text() or ""
        except Exception:
            t = ""
        t = t.strip()
        if t:
            parts.append(t)
    return normalize_ws("\n\n".join(parts))


def main():
    raw_dir = latest_raw_dir()
    date_str = raw_dir.name
    out_dir = CLEAN_ROOT / date_str / "texts"
    out_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = CLEAN_ROOT / date_str / "clean_manifest.jsonl"

    inputs = []
    for sub in ["html", "pdf", "other"]:
        d = raw_dir / sub
        if d.exists():
            inputs.extend(sorted(d.glob("*.*")))

    ok, fail = 0, 0
    with open(manifest_path, "a", encoding="utf-8") as mf:
        for fp in inputs:
            rec = {
                "input_path": str(fp),
                "output_path": None,
                "status": "fail",
                "error": None,
                "chars": 0,
                "cleaned_at": dt.datetime.now(KST).isoformat(),
            }
            try:
                ext = fp.suffix.lower()
                if ext in [".html", ".htm"]:
                    text = html_to_text(fp.read_bytes())
                elif ext == ".pdf":
                    text = pdf_to_text(fp)
                else:
                    rec["status"] = "skip"
                    mf.write(json.dumps(rec, ensure_ascii=False) + "\n")
                    continue

                if len(text) < 300:
                    raise ValueError(f"Too short after cleaning ({len(text)} chars)")

                out_name = fp.stem + ".txt"
                out_path = out_dir / out_name
                out_path.write_text(text, encoding="utf-8")

                rec["output_path"] = str(out_path)
                rec["status"] = "ok"
                rec["chars"] = len(text)
                ok += 1
            except Exception as e:
                rec["error"] = repr(e)
                fail += 1

            mf.write(json.dumps(rec, ensure_ascii=False) + "\n")

    print(f"Clean done. ok={ok}, fail={fail}")
    print(f"Cleaned saved to: {out_dir}")
    print(f"Manifest: {manifest_path}")


if __name__ == "__main__":
    main()
