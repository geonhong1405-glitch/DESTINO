from __future__ import annotations

from typing import Any

from app.db.db import SessionLocal
from app.db.models import GroupBuyPost


IMG_PKG_DANANG = "https://images.unsplash.com/photo-1552465011-b4e21bf6e79a?q=80&w=600&auto=format&fit=crop"
IMG_PKG_KYOTO = "https://images.unsplash.com/photo-1493976040374-85c8e12f0c0e?q=80&w=600&auto=format&fit=crop"
IMG_PKG_BANGKOK = "https://images.unsplash.com/photo-1508009603885-50cf7c579365?q=80&w=600&auto=format&fit=crop"
IMG_PKG_TAIPEI = "https://images.unsplash.com/photo-1528164344705-47542687000d?q=80&w=600&auto=format&fit=crop"
IMG_GROUP_DEFAULT = "https://images.unsplash.com/photo-1527631746610-bca00a040d60?q=80&w=800&auto=format&fit=crop"

IMG_TICKET_TOKYO_DISNEY = "https://images.unsplash.com/photo-1575030194417-9d3f7f5f0b0f?q=80&w=800&auto=format&fit=crop"
IMG_TICKET_TOKYO_SKYTREE = "https://images.unsplash.com/photo-1536098561742-ca998e48cbcc?q=80&w=800&auto=format&fit=crop"
IMG_TICKET_USJ = "https://images.unsplash.com/photo-1629794226066-349748040fb0?q=80&w=800&auto=format&fit=crop"
IMG_TICKET_TSX = "https://images.unsplash.com/photo-1534430480872-3498386e7856?q=80&w=800&auto=format&fit=crop"
IMG_TICKET_LIBERTY = "https://images.unsplash.com/photo-1568515387631-8b650bbcdb90?q=80&w=800&auto=format&fit=crop"

PACKAGE_CATALOG: list[dict[str, Any]] = [
    {
        "type": "\uD328\uD0A4\uC9C0",
        "name": "\uB2E4\uB0AD/\uD638\uC774\uC548 5\uC77C",
        "price": 499000,
        "currency": "KRW",
        "location": "\uBCA0\uD2B8\uB0A8 \u00B7 \uB2E4\uB0AD",
        "rating": 4.6,
        "photo": IMG_PKG_DANANG,
    },
    {
        "type": "\uD328\uD0A4\uC9C0",
        "name": "\uAC04\uC0AC\uC774 \uAC10\uC131 4\uC77C",
        "price": 890000,
        "currency": "KRW",
        "location": "\uC77C\uBCF8 \u00B7 \uAD50\uD1A0",
        "rating": 4.5,
        "photo": IMG_PKG_KYOTO,
    },
    {
        "type": "\uD328\uD0A4\uC9C0",
        "name": "\uBC29\uCF55/\uD30C\uD0C0\uC57C 5\uC77C",
        "price": 550000,
        "currency": "KRW",
        "location": "\uD0DC\uAD6D \u00B7 \uBC29\uCF55",
        "rating": 4.4,
        "photo": IMG_PKG_BANGKOK,
    },
    {
        "type": "\uD328\uD0A4\uC9C0",
        "name": "\uD0C0\uC774\uBCA0\uC774 4\uC77C",
        "price": 450000,
        "currency": "KRW",
        "location": "\uB300\uB9CC \u00B7 \uD0C0\uC774\uBCA0\uC774",
        "rating": 4.3,
        "photo": IMG_PKG_TAIPEI,
    },
]

TICKET_CATALOG: list[dict[str, Any]] = [
    {
        "type": "\uD2F0\uCF13",
        "name": "\uB3C4\uCFC4 \uB514\uC988\uB2C8\uB79C\uB4DC 1\uC77C\uAD8C",
        "price": 98000,
        "currency": "KRW",
        "location": "\uC77C\uBCF8 \u00B7 \uB3C4\uCFC4",
        "rating": 4.7,
        "photo": IMG_TICKET_TOKYO_DISNEY,
    },
    {
        "type": "\uD2F0\uCF13",
        "name": "\uB3C4\uCFC4 \uC2A4\uCE74\uC774\uD2B8\uB9AC \uC785\uC7A5\uAD8C",
        "price": 52000,
        "currency": "KRW",
        "location": "\uC77C\uBCF8 \u00B7 \uB3C4\uCFC4",
        "rating": 4.5,
        "photo": IMG_TICKET_TOKYO_SKYTREE,
    },
    {
        "type": "\uD2F0\uCF13",
        "name": "\uC720\uB2C8\uBC84\uC124 \uC2A4\uD29C\uB514\uC624 \uC7AC\uD32C",
        "price": 89000,
        "currency": "KRW",
        "location": "\uC77C\uBCF8 \u00B7 \uC624\uC0AC\uCE74",
        "rating": 4.8,
        "photo": IMG_TICKET_USJ,
    },
    {
        "type": "\uD2F0\uCF13",
        "name": "\uD0C0\uC784\uC2A4\uD018\uC5B4 \uD604\uC9C0 \uD22C\uC5B4",
        "price": 73000,
        "currency": "KRW",
        "location": "\uBBF8\uAD6D \u00B7 \uB274\uC695",
        "rating": 4.5,
        "photo": IMG_TICKET_TSX,
    },
    {
        "type": "\uD2F0\uCF13",
        "name": "\uC790\uC720\uC758 \uC5EC\uC2E0\uC0C1 \uD06C\uB8E8\uC988",
        "price": 68000,
        "currency": "KRW",
        "location": "\uBBF8\uAD6D \u00B7 \uB274\uC695",
        "rating": 4.4,
        "photo": IMG_TICKET_LIBERTY,
    },
]


def _contains_any(text: str, keys: list[str]) -> bool:
    t = str(text or "").lower()
    return any(k in t for k in keys)


def _looks_like_alternative_request(msg: str) -> bool:
    m = str(msg or "").lower().strip()
    if not m:
        return False
    direct_terms = [
        "\uB2E4\uB978",
        "\uB2E4\uC2DC \uCD94\uCC9C",
        "\uC7AC\uCD94\uCC9C",
        "\uB610 \uCD94\uCC9C",
        "\uCD94\uAC00 \uCD94\uCC9C",
        "\uB2E4\uB978 \uAC8C",
        "\uB2E4\uB978 \uAC83",
        "\uB9D0\uACE0",
        "another",
        "other",
        "alternative",
        "more",
    ]
    if _contains_any(m, direct_terms):
        return True

    # Short follow-up utterances often used in chat.
    if any(k in m for k in ["\uC5C6\uC5B4?", "\uC5C6\uB098?", "\uB354 \uC5C6\uC5B4?", "\uB354 \uC5C6\uB098?"]):
        return True
    return False


def _extract_city_hint(message: str) -> str:
    msg = str(message or "").lower()
    city_map = {
        "\uB3C4\uCFC4": "\uB3C4\uCFC4",
        "\uC624\uC0AC\uCE74": "\uC624\uC0AC\uCE74",
        "\uAD50\uD1A0": "\uAD50\uD1A0",
        "\uB274\uC695": "\uB274\uC695",
        "\uD30C\uB9AC": "\uD30C\uB9AC",
        "\uB7F0\uB358": "\uB7F0\uB358",
        "\uB2E4\uB0AD": "\uB2E4\uB0AD",
        "\uBC29\uCF55": "\uBC29\uCF55",
        "\uD0C0\uC774\uBCA0\uC774": "\uD0C0\uC774\uBCA0\uC774",
        "tokyo": "\uB3C4\uCFC4",
        "osaka": "\uC624\uC0AC\uCE74",
        "kyoto": "\uAD50\uD1A0",
        "new york": "\uB274\uC695",
        "nyc": "\uB274\uC695",
        "paris": "\uD30C\uB9AC",
        "london": "\uB7F0\uB358",
        "danang": "\uB2E4\uB0AD",
        "bangkok": "\uBC29\uCF55",
        "taipei": "\uD0C0\uC774\uBCA0\uC774",
    }
    for k, v in city_map.items():
        if k in msg:
            return v
    return ""


def _photo_for_groupbuy(country: str, city: str) -> str:
    key = f"{country} {city}".lower()
    if any(x in key for x in ["\uB2E4\uB0AD", "danang"]):
        return IMG_PKG_DANANG
    if any(x in key for x in ["\uAD50\uD1A0", "kyoto"]):
        return IMG_PKG_KYOTO
    if any(x in key for x in ["\uBC29\uCF55", "bangkok"]):
        return IMG_PKG_BANGKOK
    if any(x in key for x in ["\uD0C0\uC774\uBCA0\uC774", "taipei"]):
        return IMG_PKG_TAIPEI
    return IMG_GROUP_DEFAULT


def _serialize_groupbuy_post(row: GroupBuyPost) -> dict[str, Any]:
    budget_text = str(row.budget or "").strip()
    budget_num = None
    if budget_text:
        digits = "".join(ch for ch in budget_text if ch.isdigit())
        if digits:
            try:
                budget_num = int(digits)
            except Exception:
                budget_num = None

    country = str(row.country or "").strip()
    city = str(row.city or "").strip()
    if country and city:
        location = f"{country} \u00B7 {city}"
    else:
        location = country or city

    people = int(row.current_people or 1)
    return {
        "type": "\uACF5\uB3D9\uAD6C\uB9E4",
        "name": str(row.title or "\uACF5\uB3D9\uAD6C\uB9E4 \uBAA8\uC9D1"),
        "price": budget_num,
        "currency": "KRW",
        "location": location,
        "rating": None,
        "photo": _photo_for_groupbuy(country, city),
        "meta": f"{row.start_date or '-'} ~ {row.end_date or '-'} / {people}\uBA85 \uBAA8\uC9D1\uC911",
    }


def _get_groupbuy_items(limit: int = 8) -> list[dict[str, Any]]:
    db = SessionLocal()
    try:
        rows = (
            db.query(GroupBuyPost)
            .order_by(GroupBuyPost.created_at.desc(), GroupBuyPost.id.desc())
            .limit(max(1, int(limit)))
            .all()
        )
        out: list[dict[str, Any]] = []
        for row in rows:
            status = str(getattr(row, "status", "") or "").lower().strip()
            if status and status != "open":
                continue
            out.append(_serialize_groupbuy_post(row))
        return out
    except Exception:
        return []
    finally:
        db.close()


def recommend_products(message: str, prev_state: dict[str, Any] | None = None, limit: int = 8) -> list[dict[str, Any]]:
    prev_state = prev_state or {}
    msg = str(message or "").lower()
    city_hint = _extract_city_hint(message)
    last_type = str(prev_state.get("last_product_type") or "")

    wants_groupbuy = _contains_any(
        msg,
        [
            "\uACF5\uB3D9\uAD6C\uB9E4",
            "\uACF5\uAD6C",
            "\uBAA8\uC9D1",
            "group buy",
            "groupbuy",
        ],
    )
    wants_ticket = _contains_any(
        msg,
        [
            "\uD2F0\uCF13",
            "\uC785\uC7A5\uAD8C",
            "\uAD00\uB78C\uAD8C",
            "\uC561\uD2F0\uBE44\uD2F0",
            "\uCCB4\uD5D8",
            "\uD22C\uC5B4",
            "ticket",
            "activity",
            "tour",
        ],
    )
    wants_package = _contains_any(
        msg,
        [
            "\uD328\uD0A4\uC9C0",
            "\uD328\uD0A4",
            "\uD328\uD0A4\uCE58",
            "\uC5EC\uD589 \uC0C1\uD488",
            "\uC5EC\uD589\uC0C1\uD488",
            "package",
        ],
    )
    wants_generic_product = _contains_any(
        msg,
        [
            "\uC0C1\uD488",
            "\uCD94\uCC9C",
            "product",
            "products",
            "item",
            "items",
        ],
    )

    def _fallback_pool(exclude_type: str) -> list[dict[str, Any]]:
        pool: list[dict[str, Any]] = []
        if exclude_type != "\uD328\uD0A4\uC9C0":
            pool.extend(list(PACKAGE_CATALOG))
        if exclude_type != "\uD2F0\uCF13":
            pool.extend(list(TICKET_CATALOG))
        if exclude_type != "\uACF5\uB3D9\uAD6C\uB9E4":
            pool.extend(_get_groupbuy_items(limit=50))
        return pool

    wants_alternative = _looks_like_alternative_request(msg)
    seen_names = set(str(x) for x in (prev_state.get("last_product_names") or []) if str(x).strip())
    seen_type = str(prev_state.get("last_product_type") or "")

    if wants_ticket:
        selected = list(TICKET_CATALOG)
        selected_type = "\uD2F0\uCF13"
    elif wants_groupbuy:
        selected = _get_groupbuy_items(limit=50)
        selected_type = "\uACF5\uB3D9\uAD6C\uB9E4"
    elif wants_package:
        selected = list(PACKAGE_CATALOG)
        selected_type = "\uD328\uD0A4\uC9C0"
    elif wants_alternative and last_type in {"\uACF5\uB3D9\uAD6C\uB9E4", "\uD2F0\uCF13", "\uD328\uD0A4\uC9C0"}:
        if last_type == "\uACF5\uB3D9\uAD6C\uB9E4":
            selected = _get_groupbuy_items(limit=50)
        elif last_type == "\uD2F0\uCF13":
            selected = list(TICKET_CATALOG)
        else:
            selected = list(PACKAGE_CATALOG)
        selected_type = last_type
    else:
        selected = list(PACKAGE_CATALOG)
        selected_type = "\uD328\uD0A4\uC9C0"

    if wants_alternative and seen_names and (not seen_type or seen_type == selected_type):
        alt = [x for x in selected if str(x.get("name") or "") not in seen_names]
        if alt:
            selected = alt
        else:
            selected = []

    # If user asks generic "other products" and the current type is exhausted,
    # broaden to other product types instead of returning empty immediately.
    if (
        wants_alternative
        and not selected
        and (
            wants_generic_product
            or wants_package
            or wants_ticket
            or wants_groupbuy
            or last_type in {"\uD328\uD0A4\uC9C0", "\uD2F0\uCF13", "\uACF5\uB3D9\uAD6C\uB9E4"}
        )
    ):
        fallback_items = _fallback_pool(selected_type or last_type)
        if seen_names:
            fallback_items = [x for x in fallback_items if str(x.get("name") or "") not in seen_names]
        selected = fallback_items

    if city_hint:
        filtered = [
            x
            for x in selected
            if city_hint in str(x.get("location") or "")
            or city_hint in str(x.get("name") or "")
            or city_hint in str(x.get("meta") or "")
        ]
        if filtered:
            selected = filtered
        elif selected_type == "\uD2F0\uCF13":
            selected = []

    selected.sort(key=lambda x: (x.get("price") is None, x.get("price") or 10**12))
    return selected[: max(1, int(limit))]
