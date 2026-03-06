import json

from fastapi import APIRouter, HTTPException, Request

from app.db.db import SessionLocal
from app.db.models import GroupBuyPost, UserSavedItem
from app.session import get_user_id_from_session

router = APIRouter(prefix="/api", tags=["saved-items"])

_LIST_TYPES = {"wishlist", "cart"}


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
