import json
from collections import Counter, defaultdict
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]  # app/rag
clean_root = BASE_DIR / "cleaned"
latest = sorted([p for p in clean_root.iterdir() if p.is_dir()])[-1]
manifest = latest / "clean_manifest.jsonl"

def bucket(err: str) -> str:
    e = (err or "").lower()
    if "too short after cleaning" in e:
        return "too_short"
    if "pdf" in e and ("extract" in e or "pypdf" in e):
        return "pdf_extract_error"
    if "valueerror" in e:
        return "valueerror_other"
    return "other_error"

fails = []
with open(manifest, "r", encoding="utf-8") as f:
    for line in f:
        rec = json.loads(line)
        if rec.get("status") == "fail":
            fails.append(rec)

counts = Counter()
examples = defaultdict(list)

for r in fails:
    b = bucket(r.get("error"))
    counts[b] += 1
    if len(examples[b]) < 5:
        examples[b].append((r.get("input_path"), r.get("error")))

print(f"Manifest: {manifest}")
print(f"Fail count: {len(fails)}\n")
for k, v in counts.most_common():
    print(f"{k}: {v}")

print("\n--- Examples (up to 5 each) ---")
for k, lst in examples.items():
    print(f"\n[{k}]")
    for p, e in lst:
        print("-", p)
        print("  ", e)