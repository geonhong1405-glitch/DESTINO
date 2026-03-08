import json

from fastapi import APIRouter, HTTPException, Request

from app.db.db import SessionLocal
from app.db.models import GroupBuyPost, UserSavedItem
from app.session import get_user_id_from_session

router = APIRouter(prefix="/api", tags=["saved-items"])

_LIST_TYPES = {"wishlist", "cart"}


def _flight_logo_url(code: str, name: str) -> str:
    c = str(code or "").strip().upper()
    if not c:
        n = str(name or "").lower()
        if "korean" in n:
            c = "KE"
        elif "asiana" in n:
            c = "OZ"
        elif "tway" in n:
            c = "TW"
        elif "jeju" in n:
            c = "7C"
        elif "jin air" in n or "jinair" in n:
            c = "LJ"
        elif "air busan" in n:
            c = "BX"
        elif "air seoul" in n:
            c = "RS"
    if not c:
        return ""
    return f"https://images.kiwi.com/airlines/64x64/{c}.png"


def _default_groupbuy_image(country: str, city: str) -> str:
    key = f"{country} {city}".lower()
    if "japan" in key or "일본" in key:
        return "https://images.unsplash.com/photo-1493976040374-85c8e12f0c0e?auto=format&fit=crop&w=900&q=80"
    if "thailand" in key or "태국" in key:
        return "https://images.unsplash.com/photo-1508009603885-50cf7c579365?auto=format&fit=crop&w=900&q=80"
    if "vietnam" in key or "베트남" in key:
        return "https://images.unsplash.com/photo-1528127269322-539801943592?auto=format&fit=crop&w=900&q=80"
    if "france" in key or "프랑스" in key:
        return "https://images.unsplash.com/photo-1502602898536-47ad22581b52?auto=format&fit=crop&w=900&q=80"
    if "italy" in key or "이탈리아" in key:
        return "https://images.unsplash.com/photo-1515542622106-78bda8ba0e5b?auto=format&fit=crop&w=900&q=80"
    if "uk" in key or "united kingdom" in key or "영국" in key:
        return "https://images.unsplash.com/photo-1486299267070-83823f5448dd?auto=format&fit=crop&w=900&q=80"
    return "https://images.unsplash.com/photo-1467269204594-9661b134dd2b?auto=format&fit=crop&w=900&q=80"


def _require_user_id(request: Request) -> int:
    session_token = request.cookies.get("session_token")
    user_id = get_user_id_from_session(session_token) if session_token else None
    if not user_id:
        raise HTTPException(status_code=401, detail="로그인이 필요합니다.")
    return int(user_id)


def _safe_text(value, default: str = "") -> str:
    return str(value if value is not None else default).strip()


def _safe_lower(value) -> str:
    return _safe_text(value).lower()


def _coalesce_payload(payload: dict, body: dict) -> dict:
    if not isinstance(payload, dict):
        payload = {}
    merged = dict(payload)
    fallback_keys = (
        "id",
        "name",
        "meta",
        "image",
        "image_url",
        "thumb_url",
        "thumbnail",
        "photo",
        "photo_url",
        "price",
        "price_text",
        "location",
        "country",
        "city",
        "detail_url",
        "source",
        "item_type",
        "airline",
        "airline_code",
        "departure",
        "arrival",
    )
    for key in fallback_keys:
        if merged.get(key) in (None, "") and body.get(key) not in (None, ""):
            merged[key] = body.get(key)
    return merged


def _serialize_row(row: UserSavedItem) -> dict:
    payload = None
    try:
        payload = json.loads(row.payload_json) if row.payload_json else None
    except Exception:
        payload = None
    if isinstance(payload, dict):
        item_type = str(row.item_type or payload.get("item_type") or "").lower()
        source = str(row.source or payload.get("source") or "").lower()
        if item_type in {"groupbuy", "travel-group", "group-buy"} or source == "group-buy":
            has_image = bool(
                payload.get("image")
                or payload.get("image_url")
                or payload.get("thumb_url")
                or payload.get("photo")
                or payload.get("photo_url")
            )
            if not has_image:
                fallback = _default_groupbuy_image(
                    str(payload.get("country") or ""),
                    str(payload.get("city") or ""),
                )
                payload["image"] = fallback
                payload["image_url"] = fallback
        if item_type == "flight":
            has_image = bool(
                payload.get("image")
                or payload.get("image_url")
                or payload.get("thumb_url")
                or payload.get("photo")
                or payload.get("photo_url")
            )
            if not has_image:
                logo = _flight_logo_url(
                    str(payload.get("airline_code") or ""),
                    str(payload.get("airline") or row.name or ""),
                )
                if logo:
                    payload["thumb_url"] = logo
                    payload["image"] = logo
                    payload["image_url"] = logo
    return {
        "id": row.id,
        "list_type": row.list_type,
        "item_type": row.item_type,
        "name": row.name,
        "meta": row.meta or "",
        "source": row.source or "",
        "payload": payload,
        "created_at": str(row.created_at) if row.created_at else None,
    }


@router.get("/saved-items")
def get_saved_items(request: Request):
    session_token = request.cookies.get("session_token")
    user_id = get_user_id_from_session(session_token) if session_token else None
    if not user_id:
        return {"wishlist": [], "cart": []}
    user_id = int(user_id)
    db = SessionLocal()
    try:
        rows = (
            db.query(UserSavedItem)
            .filter(UserSavedItem.user_id == user_id)
            .order_by(UserSavedItem.created_at.desc(), UserSavedItem.id.desc())
            .all()
        )
        grouped = {"wishlist": [], "cart": []}
        valid_group_post_ids = {
            int(x.id) for x in db.query(GroupBuyPost.id).all() if x and x.id is not None
        }
        stale_ids = []
        for row in rows:
            if str(row.item_type or "").lower() in {"groupbuy", "travel-group"}:
                payload = None
                try:
                    payload = json.loads(row.payload_json) if row.payload_json else None
                except Exception:
                    payload = None
                post_id = payload.get("post_id") if isinstance(payload, dict) else None
                if post_id is not None:
                    try:
                        if int(post_id) not in valid_group_post_ids:
                            stale_ids.append(int(row.id))
                            continue
                    except Exception:
                        pass

            key = row.list_type if row.list_type in grouped else "cart"
            grouped[key].append(_serialize_row(row))
        if stale_ids:
            db.query(UserSavedItem).filter(UserSavedItem.id.in_(stale_ids)).delete(synchronize_session=False)
            db.commit()
        return grouped
    finally:
        db.close()


@router.post("/saved-items")
async def add_saved_item(request: Request):
    user_id = _require_user_id(request)
    body = await request.json()
    if not isinstance(body, dict):
        raise HTTPException(status_code=400, detail="잘못된 요청입니다.")

    list_type = _safe_lower(body.get("list_type"))
    if list_type not in _LIST_TYPES:
        raise HTTPException(status_code=400, detail="list_type은 wishlist/cart만 가능합니다.")

    item_type = _safe_text(body.get("item_type"), "item") or "item"
    name = _safe_text(body.get("name"))
    meta = _safe_text(body.get("meta"))
    source = _safe_text(body.get("source"))
    raw_payload = _coalesce_payload(body.get("payload"), body)
    if not name:
        raise HTTPException(status_code=400, detail="name이 필요합니다.")

    db = SessionLocal()
    try:
        rows = (
            db.query(UserSavedItem)
            .filter(
                UserSavedItem.user_id == user_id,
                UserSavedItem.list_type == list_type,
            )
            .order_by(UserSavedItem.id.desc())
            .all()
        )
        row = next(
            (
                r
                for r in rows
                if _safe_lower(r.item_type) == _safe_lower(item_type)
                and _safe_lower(r.name) == _safe_lower(name)
                and _safe_lower(r.meta) == _safe_lower(meta)
                and _safe_lower(r.source) == _safe_lower(source)
            ),
            None,
        )
        if row:
            if raw_payload and not row.payload_json:
                row.payload_json = json.dumps(raw_payload, ensure_ascii=False)
                db.commit()
                db.refresh(row)
            return {"ok": True, "created": False, "item": _serialize_row(row)}

        row = UserSavedItem(
            user_id=user_id,
            list_type=list_type,
            item_type=item_type,
            name=name,
            meta=meta,
            source=source,
            payload_json=json.dumps(raw_payload, ensure_ascii=False) if raw_payload is not None else None,
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        return {"ok": True, "created": True, "item": _serialize_row(row)}
    finally:
        db.close()


@router.delete("/saved-items/{item_id}")
def delete_saved_item(item_id: int, request: Request):
    user_id = _require_user_id(request)
    db = SessionLocal()
    try:
        row = (
            db.query(UserSavedItem)
            .filter(UserSavedItem.id == int(item_id), UserSavedItem.user_id == user_id)
            .first()
        )
        if not row:
            raise HTTPException(status_code=404, detail="항목을 찾을 수 없습니다.")
        db.delete(row)
        db.commit()
        return {"ok": True}
    finally:
        db.close()
