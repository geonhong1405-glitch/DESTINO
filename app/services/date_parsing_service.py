import re
from datetime import datetime, timedelta
from typing import Any, Callable, Optional


def parse_rel_date(text: str):
    t = re.sub(r"\s+", "", (text or "").lower())
    now = datetime.now()

    if "\uc624\ub298" in t:
        return now.date()
    if "\ub0b4\uc77c" in t and ("\ub0b4\uc77c\ubaa8\ub808" not in t) and ("\ub0b4\uc77c\ubaa8\ub798" not in t):
        return (now + timedelta(days=1)).date()
    if ("\ub0b4\uc77c\ubaa8\ub808" in t) or ("\ub0b4\uc77c\ubaa8\ub798" in t) or ("\ubaa8\ub808" in t):
        return (now + timedelta(days=2)).date()
    if "\uae00\ud53c" in t:
        return (now + timedelta(days=3)).date()
    if any(x in t for x in ["\uc77c\uc8fc\uc77c\ub4a4", "\uc77c\uc8fc\uc77c\ud6c4", "1\uc8fc\uc77c\ub4a4", "1\uc8fc\uc77c\ud6c4"]):
        return (now + timedelta(days=7)).date()
    if ("\ub2e4\uc74c\uc8fc" in t) or ("\ucc28\uc8fc" in t):
        return (now + timedelta(days=7)).date()
    if "\ub2e4\ub2e4\uc74c\uc8fc" in t:
        return (now + timedelta(days=14)).date()

    m = re.search(r"(\d+)\uc77c(?:\ub4a4|\ud6c4)", t)
    if m:
        return (now + timedelta(days=int(m.group(1)))).date()
    m = re.search(r"(\d+)\uc8fc(?:\uc77c)?(?:\ub4a4|\ud6c4)", t)
    if m:
        return (now + timedelta(days=int(m.group(1)) * 7)).date()
    return None


def has_date_signal(text: str, *, contains_fn: Callable[[str, list[str]], bool]) -> bool:
    t = text or ""
    if re.search(r"\b20\d{2}-\d{2}-\d{2}\b", t):
        return True
    if re.search(r"\d{1,2}\s*월\s*\d{1,2}\s*일", t):
        return True
    if re.search(r"\b\d{1,2}[/-]\d{1,2}\b", t):
        return True
    if re.search(r"\d+\s*\uc77c\s*(?:\ub4a4|\ud6c4)", t):
        return True
    if re.search(r"\d+\s*\uc8fc(?:\uc77c)?\s*(?:\ub4a4|\ud6c4)", t):
        return True
    return contains_fn(
        t,
        [
            "\uc624\ub298", "\ub0b4\uc77c", "\ubaa8\ub808", "\uae00\ud53c",
            "\ub2e4\uc74c\uc8fc", "\ub2e4\ub2e4\uc74c\uc8fc", "\uc774\ubc88\uc8fc", "\uc8fc\ub9d0",
            "\uc77c\uc8fc\uc77c\ub4a4", "\uc77c\uc8fc\uc77c\ud6c4", "\uc77c\uc8fc\uc77c \ub4a4", "\uc77c\uc8fc\uc77c \ud6c4",
        ],
    )


def parse_abs_monthday_range(text: str, *, now_dt: datetime) -> dict[str, Optional[str]]:
    s = str(text or "")
    if not s.strip():
        return {"departure_date": None, "return_date": None}
    now_date = now_dt.date()

    def _infer_year(month: int, day: int, year: Optional[int] = None) -> Optional[int]:
        y = int(year) if year else now_date.year
        try:
            cand = datetime(y, month, day).date()
        except Exception:
            return None
        if year is None and cand < (now_date - timedelta(days=1)):
            try:
                cand2 = datetime(y + 1, month, day).date()
            except Exception:
                return None
            return cand2.year
        return cand.year

    def _to_iso(year: Optional[int], month: Optional[int], day: Optional[int]) -> Optional[str]:
        if not year or not month or not day:
            return None
        try:
            return datetime(year, month, day).strftime("%Y-%m-%d")
        except Exception:
            return None

    compact = re.sub(r"\s+", "", s)
    m_iso_range = re.search(r"(20\d{2})[./-](\d{1,2})[./-](\d{1,2}).{0,6}?(20\d{2})[./-](\d{1,2})[./-](\d{1,2})", compact)
    if m_iso_range:
        return {
            "departure_date": _to_iso(int(m_iso_range.group(1)), int(m_iso_range.group(2)), int(m_iso_range.group(3))),
            "return_date": _to_iso(int(m_iso_range.group(4)), int(m_iso_range.group(5)), int(m_iso_range.group(6))),
        }

    m_range = re.search(r"(?:(20\d{2})년?)?(\d{1,2})월(\d{1,2})일(?:부터|에서|~|-|—|–|to)(?:(?:(20\d{2})년?)?(\d{1,2})월)?(\d{1,2})일", compact)
    if m_range:
        y1 = _infer_year(int(m_range.group(2)), int(m_range.group(3)), int(m_range.group(1)) if m_range.group(1) else None)
        m1, d1 = int(m_range.group(2)), int(m_range.group(3))
        m2 = int(m_range.group(5)) if m_range.group(5) else m1
        d2 = int(m_range.group(6))
        y2 = _infer_year(m2, d2, int(m_range.group(4)) if m_range.group(4) else y1)
        return {"departure_date": _to_iso(y1, m1, d1), "return_date": _to_iso(y2, m2, d2)}

    m_single = re.search(r"(?:(20\d{2})년?)?(\d{1,2})월(\d{1,2})일", compact)
    if m_single:
        m1, d1 = int(m_single.group(2)), int(m_single.group(3))
        y1 = _infer_year(m1, d1, int(m_single.group(1)) if m_single.group(1) else None)
        return {"departure_date": _to_iso(y1, m1, d1), "return_date": None}

    m_short_range = re.search(r"(\d{1,2})[/-](\d{1,2}).{0,4}?(?:~|-|—|–|to)(\d{1,2})[/-](\d{1,2})", compact)
    if m_short_range:
        m1, d1 = int(m_short_range.group(1)), int(m_short_range.group(2))
        m2, d2 = int(m_short_range.group(3)), int(m_short_range.group(4))
        y1 = _infer_year(m1, d1, None)
        y2 = _infer_year(m2, d2, y1)
        return {"departure_date": _to_iso(y1, m1, d1), "return_date": _to_iso(y2, m2, d2)}

    return {"departure_date": None, "return_date": None}


def is_date_correction_message(text: str, *, contains_fn: Callable[[str, list[str]], bool], has_date_signal_fn: Callable[[str], bool]) -> bool:
    t = text or ""
    has_correction = contains_fn(t, ["\uc544\ub2c8\ub2e4", "\uc544\ub2c8", "\ucde8\uc18c", "\ubcc0\uacbd", "\ub9d0\uace0"])
    return bool(has_correction and has_date_signal_fn(t))


def parse_rel_date_for_correction(text: str, *, parse_rel_date_fn: Callable[[str], Any]):
    t = text or ""
    markers = ["\ub9d0\uace0", "\uc544\ub2c8\ub2e4", "\uc544\ub2c8", "\ubcc0\uacbd", "\ucde8\uc18c"]
    for marker in markers:
        if marker in t:
            tail = t.split(marker)[-1].strip()
            d = parse_rel_date_fn(tail)
            if d:
                return d
    return parse_rel_date_fn(t)


def coerce_int(v: Any, default: int = 0, lo: int = 0, hi: int = 365) -> int:
    try:
        n = int(v)
    except Exception:
        return default
    if n < lo:
        return lo
    if n > hi:
        return hi
    return n


def normalize_date_semantics(parsed: Any) -> dict[str, Any]:
    if not isinstance(parsed, dict):
        return {"departure": None, "return": None, "stay_nights": 0}

    def norm_one(x: Any) -> Optional[dict[str, Any]]:
        if not isinstance(x, dict):
            return None
        kind = (str(x.get("kind") or "").strip().lower()) or None
        date = (str(x.get("date") or "").strip()) or None
        unit = (str(x.get("unit") or "").strip().lower()) or None
        raw = (str(x.get("raw") or "").strip()) or None
        value = coerce_int(x.get("value"), default=0, lo=0, hi=365)
        if kind not in {"absolute", "relative_offset"}:
            kind = None
        if unit not in {"day", "week"}:
            unit = None
        if kind == "absolute" and not (date and re.fullmatch(r"20\d{2}-\d{2}-\d{2}", date)):
            date = None
        return {"kind": kind, "date": date, "unit": unit, "value": value, "raw": raw}

    return {
        "departure": norm_one(parsed.get("departure")),
        "return": norm_one(parsed.get("return")),
        "stay_nights": coerce_int(parsed.get("stay_nights"), default=0, lo=0, hi=365),
    }


def today_kst_str(*, now_dt: datetime) -> str:
    return now_dt.strftime("%Y-%m-%d")


def extract_date_expr_with_llm(
    message: str,
    context: str = "",
    *,
    llm_json_fn: Callable[[str, str], dict[str, Any]],
    today_str: str,
) -> dict[str, Any]:
    prompt = (
        f"Today is {today_str} (Asia/Seoul).\n"
        "Extract ONLY date semantics from the user input and output JSON ONLY (no extra text).\n"
        "Schema:\n"
        "{"
        "\"departure\": {\"kind\":\"absolute|relative_offset|null\",\"date\":\"YYYY-MM-DD|null\",\"unit\":\"day|week|null\",\"value\":0,\"raw\":\"string|null\"},"
        "\"return\": {\"kind\":\"absolute|relative_offset|null\",\"date\":\"YYYY-MM-DD|null\",\"unit\":\"day|week|null\",\"value\":0,\"raw\":\"string|null\"},"
        "\"stay_nights\": 0"
        "}\n"
        "Rules:\n"
        "- absolute date => kind=absolute and set date\n"
        "- relative date => kind=relative_offset, set unit/value/raw when possible\n"
        "- if missing, set null-like fields\n"
        "- if phrase includes stay length, set stay_nights\n\n"
        f"Recent conversation:\n{context}\n\nUser input:\n{message}\nReturn ONLY the JSON object."
    )
    parsed = llm_json_fn("Return ONLY JSON for date semantics.", prompt)
    return normalize_date_semantics(parsed)


def resolve_date_expr(expr: Any, *, parse_rel_date_fn: Callable[[str], Any], now_dt: datetime) -> Optional[str]:
    if not expr:
        return None
    now_date = now_dt.date()

    if isinstance(expr, dict):
        kind = (str(expr.get("kind") or "").strip().lower()) or None
        if kind == "absolute":
            s_abs = (str(expr.get("date") or "").strip()) or ""
            if re.fullmatch(r"20\d{2}-\d{2}-\d{2}", s_abs):
                try:
                    d_abs = datetime.strptime(s_abs, "%Y-%m-%d").date()
                except Exception:
                    return None
                if d_abs < now_date - timedelta(days=1):
                    return None
                return d_abs.strftime("%Y-%m-%d")
            return None
        if kind == "relative_offset":
            unit = (str(expr.get("unit") or "").strip().lower()) or None
            raw = (str(expr.get("raw") or "").strip()) or ""
            try:
                value = int(expr.get("value"))
            except Exception:
                value = None
            if unit in {"day", "week"} and value is not None and 0 <= value <= 365:
                days = value if unit == "day" else value * 7
                return (now_date + timedelta(days=days)).strftime("%Y-%m-%d")
            if raw:
                d_raw = parse_rel_date_fn(raw)
                if d_raw and (d_raw >= now_date - timedelta(days=1)):
                    return d_raw.strftime("%Y-%m-%d")
            return None
        raw = (str(expr.get("raw") or "").strip()) if isinstance(expr, dict) else ""
        if raw:
            d_raw = parse_rel_date_fn(raw)
            if d_raw and (d_raw >= now_date - timedelta(days=1)):
                return d_raw.strftime("%Y-%m-%d")
        return None

    s_expr = str(expr).strip()
    if not s_expr:
        return None
    if re.fullmatch(r"20\d{2}-\d{2}-\d{2}", s_expr):
        try:
            d = datetime.strptime(s_expr, "%Y-%m-%d").date()
        except Exception:
            return None
        if d < now_date - timedelta(days=1):
            return None
        return d.strftime("%Y-%m-%d")

    d = parse_rel_date_fn(s_expr)
    if not d or d < now_date - timedelta(days=1):
        return None
    return d.strftime("%Y-%m-%d")
