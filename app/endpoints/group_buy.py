import json
from fastapi import APIRouter, HTTPException, Request
from sqlalchemy import or_

from app.db.db import SessionLocal
from app.db.models import GroupBuyJoinRequest, GroupBuyPost, User, UserSavedItem
from app.session import get_user_id_from_session

router = APIRouter(prefix="/api/group-buy", tags=["group-buy"])
_LINKED_ITEMS_MARKER = "\n\n[[LINKED_ITEMS_JSON]]\n"


def _normalize_linked_items(raw) -> list[dict]:
    if not isinstance(raw, list):
        return []
    out: list[dict] = []
    for item in raw[:20]:
        if not isinstance(item, dict):
            continue
        item_type = str(item.get("item_type") or "").strip().lower()[:40]
        name = str(item.get("name") or "").strip()[:255]
        meta = str(item.get("meta") or "").strip()[:512]
        source = str(item.get("source") or "").strip()[:50]
        payload = item.get("payload")
        if not item_type or not name:
            continue
        clean = {
            "item_type": item_type,
            "name": name,
            "meta": meta,
            "source": source,
            "payload": payload if isinstance(payload, (dict, list, str, int, float, bool)) or payload is None else None,
        }
        out.append(clean)
    return out


def _split_desc_and_linked_items(raw_desc: str | None) -> tuple[str, list[dict]]:
    text = str(raw_desc or "")
    if _LINKED_ITEMS_MARKER not in text:
        return text, []
    desc, linked_blob = text.split(_LINKED_ITEMS_MARKER, 1)
    desc = desc.strip()
    linked_items = []
    try:
        parsed = json.loads(linked_blob.strip())
        linked_items = _normalize_linked_items(parsed)
    except Exception:
        linked_items = []
    return desc, linked_items


def _pack_desc_with_linked_items(desc: str, linked_items: list[dict]) -> str:
    clean_desc = str(desc or "").strip()
    clean_items = _normalize_linked_items(linked_items)
    if not clean_items:
        return clean_desc
    linked_json = json.dumps(clean_items, ensure_ascii=False, separators=(",", ":"))
    return f"{clean_desc}{_LINKED_ITEMS_MARKER}{linked_json}"


def _require_user_id(request: Request) -> int:
    session_token = request.cookies.get("session_token")
    user_id = get_user_id_from_session(session_token) if session_token else None
    if not user_id:
        raise HTTPException(status_code=401, detail="로그인이 필요합니다.")
    return int(user_id)


def _serialize_post(row: GroupBuyPost, me: int | None = None, owner_nickname: str | None = None) -> dict:
    clean_desc, linked_items = _split_desc_and_linked_items(row.description or "")
    return {
        "id": row.id,
        "owner_user_id": row.owner_user_id,
        "owner_nickname": owner_nickname or "",
        "category": row.category or "package",
        "title": row.title,
        "country": row.country,
        "city": row.city or "",
        "start_date": row.start_date,
        "end_date": row.end_date,
        "departure": row.departure or "인천",
        "budget": row.budget or "",
        "description": clean_desc,
        "linked_items": linked_items,
        "status": row.status or "open",
        "current_people": row.current_people or 1,
        "max_people": row.max_people or 4,
        "is_mine": bool(me and int(me) == int(row.owner_user_id)),
        "created_at": str(row.created_at) if row.created_at else None,
    }


def _parse_join_message(raw: str | None) -> tuple[str, str]:
    if not raw:
        return "", ""
    try:
        parsed = json.loads(raw)
        if isinstance(parsed, dict):
            return str(parsed.get("email") or "").strip(), str(parsed.get("detail") or "").strip()
    except Exception:
        pass
    return "", str(raw or "").strip()


def _parse_join_message_payload(raw: str | None) -> dict:
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
        if isinstance(parsed, dict):
            return parsed
    except Exception:
        pass
    return {"detail": str(raw or "").strip()}


def _ensure_linked_items_in_requester_cart(db, requester_user_id: int, linked_items: list[dict]) -> tuple[int, int]:
    created_count = 0
    existed_count = 0
    uid = int(requester_user_id)

    for item in _normalize_linked_items(linked_items):
        item_type = str(item.get("item_type") or "").strip().lower()[:40] or "item"
        name = str(item.get("name") or "").strip()[:255]
        meta = str(item.get("meta") or "").strip()[:512]
        source = str(item.get("source") or "").strip()[:50] or "group-buy"
        payload = item.get("payload")
        if not name:
            continue

        existing = (
            db.query(UserSavedItem)
            .filter(
                UserSavedItem.user_id == uid,
                UserSavedItem.list_type == "cart",
                UserSavedItem.item_type == item_type,
                UserSavedItem.name == name,
                UserSavedItem.meta == meta,
                UserSavedItem.source == source,
            )
            .first()
        )
        if existing:
            existed_count += 1
            continue

        row = UserSavedItem(
            user_id=uid,
            list_type="cart",
            item_type=item_type,
            name=name,
            meta=meta,
            source=source,
            payload_json=json.dumps(payload, ensure_ascii=False) if payload is not None else None,
        )
        db.add(row)
        created_count += 1

    return created_count, existed_count


@router.get("/posts")
def list_posts(request: Request):
    session_token = request.cookies.get("session_token")
    me = get_user_id_from_session(session_token) if session_token else None
    db = SessionLocal()
    try:
        rows = (
            db.query(GroupBuyPost)
            .order_by(GroupBuyPost.created_at.desc(), GroupBuyPost.id.desc())
            .all()
        )
        owner_ids = list({int(r.owner_user_id) for r in rows if r.owner_user_id is not None})
        owners = {}
        if owner_ids:
            for u in db.query(User).filter(User.id.in_(owner_ids)).all():
                owners[int(u.id)] = u.nickname or u.name or ""
        return [_serialize_post(r, int(me) if me else None, owners.get(int(r.owner_user_id), "")) for r in rows]
    finally:
        db.close()


@router.post("/posts")
async def create_post(request: Request):
    user_id = _require_user_id(request)
    payload = await request.json()
    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="잘못된 요청입니다.")

    title = str(payload.get("title") or "").strip()
    country = str(payload.get("country") or "").strip()
    start_date = str(payload.get("start_date") or "").strip()
    linked_items = _normalize_linked_items(payload.get("linked_items"))
    if not title or not country or not start_date:
        raise HTTPException(status_code=400, detail="title/country/start_date는 필수입니다.")

    try:
        max_people = int(payload.get("max_people") or 4)
    except Exception:
        max_people = 4
    max_people = max(2, min(max_people, 999))

    row = GroupBuyPost(
        owner_user_id=user_id,
        category=str(payload.get("category") or "package").strip()[:30],
        title=title[:255],
        country=country[:100],
        city=str(payload.get("city") or "").strip()[:100],
        start_date=start_date[:20],
        end_date=str(payload.get("end_date") or "").strip()[:20] or None,
        departure=str(payload.get("departure") or "인천").strip()[:100],
        budget=str(payload.get("budget") or "").strip()[:80],
        description=_pack_desc_with_linked_items(str(payload.get("description") or "").strip(), linked_items),
        status="open",
        current_people=1,
        max_people=max_people,
    )

    db = SessionLocal()
    try:
        db.add(row)
        db.commit()
        db.refresh(row)
        owner = db.query(User).filter(User.id == int(user_id)).first()
        return {"ok": True, "post": _serialize_post(row, user_id, (owner.nickname if owner else ""))}
    finally:
        db.close()


@router.get("/my-posts")
def my_posts(request: Request):
    user_id = _require_user_id(request)
    db = SessionLocal()
    try:
        rows = (
            db.query(GroupBuyPost)
            .filter(GroupBuyPost.owner_user_id == user_id)
            .order_by(GroupBuyPost.created_at.desc(), GroupBuyPost.id.desc())
            .all()
        )
        owner = db.query(User).filter(User.id == int(user_id)).first()
        owner_name = owner.nickname if owner else ""
        return [_serialize_post(r, user_id, owner_name) for r in rows]
    finally:
        db.close()


@router.delete("/posts/{post_id}")
def delete_post(post_id: int, request: Request):
    user_id = _require_user_id(request)
    db = SessionLocal()
    try:
        post = (
            db.query(GroupBuyPost)
            .filter(GroupBuyPost.id == int(post_id), GroupBuyPost.owner_user_id == user_id)
            .first()
        )
        if not post:
            raise HTTPException(status_code=404, detail="게시글을 찾을 수 없습니다.")

        db.query(GroupBuyJoinRequest).filter(GroupBuyJoinRequest.post_id == int(post_id)).delete()
        # 삭제된 공동구매 글을 참조하던 위시리스트/장바구니 항목도 함께 정리
        post_id_text = str(int(post_id))
        db.query(UserSavedItem).filter(
            UserSavedItem.item_type.in_(["groupbuy", "travel-group"]),
            or_(
                UserSavedItem.payload_json.like(f'%"post_id": {post_id_text}%'),
                UserSavedItem.payload_json.like(f'%"post_id":{post_id_text}%'),
            ),
        ).delete(synchronize_session=False)
        db.delete(post)
        db.commit()
        return {"ok": True}
    finally:
        db.close()


@router.post("/posts/{post_id}/join-requests")
async def create_join_request(post_id: int, request: Request):
    requester_id = _require_user_id(request)
    payload = await request.json()
    email = str((payload or {}).get("email") or "").strip()[:120]
    detail = str((payload or {}).get("detail") or (payload or {}).get("message") or "").strip()[:350]
    message = json.dumps({"email": email, "detail": detail}, ensure_ascii=False)[:500]

    db = SessionLocal()
    try:
        post = db.query(GroupBuyPost).filter(GroupBuyPost.id == int(post_id)).first()
        if not post:
            raise HTTPException(status_code=404, detail="게시글을 찾을 수 없습니다.")
        if int(post.owner_user_id) == int(requester_id):
            raise HTTPException(status_code=400, detail="본인 게시글에는 참여 요청할 수 없습니다.")
        if int(post.current_people or 1) >= int(post.max_people or 4):
            post.status = "closed"
            db.commit()
            raise HTTPException(status_code=400, detail="마감된 게시글입니다.")
        if (post.status or "open") != "open":
            raise HTTPException(status_code=400, detail="마감된 게시글입니다.")

        exists = (
            db.query(GroupBuyJoinRequest)
            .filter(
                GroupBuyJoinRequest.post_id == int(post_id),
                GroupBuyJoinRequest.requester_user_id == int(requester_id),
                GroupBuyJoinRequest.status == "pending",
            )
            .first()
        )
        if exists:
            return {"ok": True, "created": False}

        row = GroupBuyJoinRequest(
            post_id=int(post_id),
            post_owner_user_id=int(post.owner_user_id),
            requester_user_id=int(requester_id),
            message=message or None,
            status="pending",
        )
        db.add(row)
        db.commit()
        return {"ok": True, "created": True}
    finally:
        db.close()


@router.get("/join-requests/inbox")
def inbox_join_requests(request: Request):
    session_token = request.cookies.get("session_token")
    user_id = get_user_id_from_session(session_token) if session_token else None
    if not user_id:
        return []
    user_id = int(user_id)
    db = SessionLocal()
    try:
        inbox_rows = (
            db.query(GroupBuyJoinRequest)
            .filter(GroupBuyJoinRequest.post_owner_user_id == user_id)
            .order_by(GroupBuyJoinRequest.created_at.desc(), GroupBuyJoinRequest.id.desc())
            .all()
        )
        mine_rows = (
            db.query(GroupBuyJoinRequest)
            .filter(
                GroupBuyJoinRequest.requester_user_id == user_id,
                GroupBuyJoinRequest.status.in_(["accepted", "rejected"]),
            )
            .order_by(GroupBuyJoinRequest.created_at.desc(), GroupBuyJoinRequest.id.desc())
            .all()
        )
        if not inbox_rows and not mine_rows:
            return []

        post_ids = list({int(r.post_id) for r in (inbox_rows + mine_rows)})
        requester_ids = list({int(r.requester_user_id) for r in inbox_rows})
        owner_ids = list({int(r.post_owner_user_id) for r in mine_rows})

        posts = {int(p.id): p for p in db.query(GroupBuyPost).filter(GroupBuyPost.id.in_(post_ids)).all()}
        users = {int(u.id): u for u in db.query(User).filter(User.id.in_(requester_ids + owner_ids)).all()}

        result = []
        for r in inbox_rows:
            p = posts.get(int(r.post_id))
            u = users.get(int(r.requester_user_id))
            parsed_email, parsed_detail = _parse_join_message(r.message or "")
            result.append(
                {
                    "id": r.id,
                    "post_id": r.post_id,
                    "post_title": p.title if p else "",
                    "requester_user_id": r.requester_user_id,
                    "requester_name": (u.nickname or u.name) if u else "",
                    "requester_email": parsed_email or (u.email if u else ""),
                    "message": parsed_detail,
                    "status": r.status or "pending",
                    "direction": "incoming",
                    "created_at": str(r.created_at) if r.created_at else None,
                }
            )

        for r in mine_rows:
            p = posts.get(int(r.post_id))
            owner = users.get(int(r.post_owner_user_id))
            status = r.status or "pending"
            msg_payload = _parse_join_message_payload(r.message or "")
            notice = ""
            if status == "accepted":
                notice = str(msg_payload.get("decision_notice") or "").strip() or "수락되었습니다. 장바구니를 확인해주세요."
            elif status == "rejected":
                notice = str(msg_payload.get("decision_notice") or "").strip() or "거절되었습니다."
            result.append(
                {
                    "id": r.id,
                    "post_id": r.post_id,
                    "post_title": p.title if p else "",
                    "requester_user_id": r.requester_user_id,
                    "requester_name": (owner.nickname or owner.name) if owner else "",
                    "requester_email": owner.email if owner else "",
                    "message": notice,
                    "status": status,
                    "direction": "mine",
                    "created_at": str(r.created_at) if r.created_at else None,
                }
            )
        return result
    finally:
        db.close()


@router.post("/join-requests/{request_id}/decision")
async def decide_join_request(request_id: int, request: Request):
    user_id = _require_user_id(request)
    payload = await request.json()
    action = str((payload or {}).get("action") or "").strip().lower()
    if action not in {"accept", "reject"}:
        raise HTTPException(status_code=400, detail="action은 accept/reject만 가능합니다.")

    db = SessionLocal()
    try:
        added_count = 0
        existed_count = 0
        row = (
            db.query(GroupBuyJoinRequest)
            .filter(
                GroupBuyJoinRequest.id == int(request_id),
                GroupBuyJoinRequest.post_owner_user_id == user_id,
            )
            .first()
        )
        if not row:
            raise HTTPException(status_code=404, detail="요청을 찾을 수 없습니다.")
        if row.status != "pending":
            return {"ok": True, "updated": False}

        row.status = "accepted" if action == "accept" else "rejected"
        join_payload = _parse_join_message_payload(row.message or "")

        if action == "accept":
            post = db.query(GroupBuyPost).filter(GroupBuyPost.id == int(row.post_id)).first()
            owner_user = db.query(User).filter(User.id == int(row.post_owner_user_id or 0)).first()
            owner_email = str(owner_user.email or "").strip() if owner_user else ""
            if post:
                if int(post.current_people or 1) >= int(post.max_people or 4):
                    post.status = "closed"
                    row.status = "rejected"
                    join_payload["decision_notice"] = "정원이 마감되어 자동 거절되었습니다."
                    row.message = json.dumps(join_payload, ensure_ascii=False)[:500]
                    db.commit()
                    return {"ok": True, "updated": False, "reason": "FULL"}
                next_people = int(post.current_people or 0) + 1
                post.current_people = min(next_people, int(post.max_people or 4))
                if int(post.current_people) >= int(post.max_people or 4):
                    post.status = "closed"

                _, linked_items = _split_desc_and_linked_items(post.description or "")
                added_count, existed_count = _ensure_linked_items_in_requester_cart(
                    db=db,
                    requester_user_id=int(row.requester_user_id),
                    linked_items=linked_items,
                )
                if added_count > 0:
                    email_msg = f" 작성자 이메일: {owner_email}." if owner_email else ""
                    join_payload["decision_notice"] = f"수락되었습니다.{email_msg} 연결 상품 {added_count}개가 장바구니에 담겼습니다."
                elif existed_count > 0:
                    email_msg = f" 작성자 이메일: {owner_email}." if owner_email else ""
                    join_payload["decision_notice"] = f"수락되었습니다.{email_msg} 연결 상품은 이미 장바구니에 있어 중복 추가되지 않았습니다. (기존 {existed_count}개)"
                else:
                    email_msg = f" 작성자 이메일: {owner_email}." if owner_email else ""
                    join_payload["decision_notice"] = f"수락되었습니다.{email_msg} 연결된 상품이 없어 장바구니 추가는 없습니다."
            else:
                join_payload["decision_notice"] = "수락되었습니다."
        else:
            join_payload["decision_notice"] = "거절되었습니다."

        row.message = json.dumps(join_payload, ensure_ascii=False)[:500]

        db.commit()
        return {
            "ok": True,
            "updated": True,
            "cart_added_count": int(added_count),
            "cart_existing_count": int(existed_count),
        }
    finally:
        db.close()


@router.delete("/join-requests/{request_id}")
def delete_join_request_alert(request_id: int, request: Request):
    user_id = _require_user_id(request)
    db = SessionLocal()
    try:
        row = (
            db.query(GroupBuyJoinRequest)
            .filter(GroupBuyJoinRequest.id == int(request_id))
            .first()
        )
        if not row:
            raise HTTPException(status_code=404, detail="요청을 찾을 수 없습니다.")

        is_requester = int(row.requester_user_id or 0) == int(user_id)
        is_post_owner = int(row.post_owner_user_id or 0) == int(user_id)
        if not (is_requester or is_post_owner):
            raise HTTPException(status_code=403, detail="권한이 없습니다.")

        db.delete(row)
        db.commit()
        return {"ok": True}
    finally:
        db.close()
