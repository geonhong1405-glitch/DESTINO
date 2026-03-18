from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from app.db.db import SessionLocal
from app.db.models import UserChatPass


PLAN_CATALOG: dict[str, dict[str, Any]] = {
    "count_30": {
        "code": "count_30",
        "name": "30회 이용권",
        "amount": 2900,
        "currency": "KRW",
        "duration_days": 30,
        "total_uses": 30,
    },
    "day_1": {
        "code": "day_1",
        "name": "하루 이용권",
        "amount": 3900,
        "currency": "KRW",
        "duration_days": 1,
        "total_uses": None,
    },
    "month_1": {
        "code": "month_1",
        "name": "한달 이용권",
        "amount": 11900,
        "currency": "KRW",
        "duration_days": 30,
        "total_uses": None,
    },
}


def _utcnow() -> datetime:
    return datetime.utcnow()


def get_plan_catalog() -> list[dict[str, Any]]:
    return [dict(v) for v in PLAN_CATALOG.values()]


def _status_from_row(row: UserChatPass, now: datetime) -> str:
    if row.status in {"cancelled", "used_up", "expired"}:
        return row.status
    if row.expires_at and row.expires_at <= now:
        return "expired"
    if row.remaining_uses is not None and row.remaining_uses <= 0:
        return "used_up"
    return "active"


def _serialize(row: UserChatPass) -> dict[str, Any]:
    return {
        "id": int(row.id),
        "plan_code": row.plan_code,
        "plan_name": row.plan_name,
        "status": row.status,
        "amount": int(row.amount or 0),
        "currency": row.currency or "KRW",
        "total_uses": row.total_uses,
        "remaining_uses": row.remaining_uses,
        "duration_days": row.duration_days,
        "started_at": row.started_at.isoformat() if row.started_at else None,
        "expires_at": row.expires_at.isoformat() if row.expires_at else None,
        "order_id": row.order_id or "",
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }


def _refresh_statuses_for_user(db, user_id: int) -> None:
    now = _utcnow()
    rows = (
        db.query(UserChatPass)
        .filter(UserChatPass.user_id == int(user_id))
        .order_by(UserChatPass.id.desc())
        .all()
    )
    changed = False
    for row in rows:
        next_status = _status_from_row(row, now)
        if row.status != next_status:
            row.status = next_status
            changed = True
    if changed:
        db.commit()


def _consolidate_count_passes_for_user(db, user_id: int) -> None:
    """
    If multiple active count-based passes exist, merge them into the newest one.
    Older rows are marked used_up so only one active counter remains.
    """
    rows = (
        db.query(UserChatPass)
        .filter(
            UserChatPass.user_id == int(user_id),
            UserChatPass.status == "active",
            UserChatPass.remaining_uses.isnot(None),
        )
        .order_by(UserChatPass.id.desc())
        .all()
    )
    if len(rows) <= 1:
        return

    primary = rows[0]
    merged_total = int(primary.total_uses or 0)
    merged_remaining = int(primary.remaining_uses or 0)
    merged_amount = int(primary.amount or 0)
    merged_expires = primary.expires_at

    changed = False
    for row in rows[1:]:
        merged_total += int(row.total_uses or 0)
        merged_remaining += int(row.remaining_uses or 0)
        merged_amount += int(row.amount or 0)
        if row.expires_at and (not merged_expires or row.expires_at > merged_expires):
            merged_expires = row.expires_at
        row.remaining_uses = 0
        row.status = "used_up"
        changed = True

    primary.total_uses = merged_total
    primary.remaining_uses = merged_remaining
    primary.amount = merged_amount
    primary.expires_at = merged_expires
    changed = True

    if changed:
        db.commit()


def list_user_passes(user_id: int) -> list[dict[str, Any]]:
    db = SessionLocal()
    try:
        _refresh_statuses_for_user(db, int(user_id))
        _consolidate_count_passes_for_user(db, int(user_id))
        rows = (
            db.query(UserChatPass)
            .filter(UserChatPass.user_id == int(user_id))
            .order_by(UserChatPass.id.desc())
            .all()
        )
        return [_serialize(row) for row in rows]
    finally:
        db.close()


def get_active_pass(user_id: int) -> dict[str, Any] | None:
    db = SessionLocal()
    try:
        _refresh_statuses_for_user(db, int(user_id))
        _consolidate_count_passes_for_user(db, int(user_id))
        row = (
            db.query(UserChatPass)
            .filter(UserChatPass.user_id == int(user_id), UserChatPass.status == "active")
            .order_by(UserChatPass.id.desc())
            .first()
        )
        return _serialize(row) if row else None
    finally:
        db.close()


def grant_chat_pass(
    user_id: int,
    plan_code: str,
    *,
    order_id: str = "",
    payment_key: str = "",
) -> dict[str, Any]:
    plan = PLAN_CATALOG.get(str(plan_code))
    if not plan:
        raise ValueError("INVALID_PLAN")
    now = _utcnow()
    duration_days = int(plan["duration_days"]) if plan.get("duration_days") is not None else None
    expires_at = now + timedelta(days=duration_days) if duration_days else None
    total_uses = plan.get("total_uses")
    remaining_uses = total_uses

    db = SessionLocal()
    try:
        _refresh_statuses_for_user(db, int(user_id))
        _consolidate_count_passes_for_user(db, int(user_id))

        # For count-based passes, stack into existing active counter pass.
        if total_uses is not None:
            existing = (
                db.query(UserChatPass)
                .filter(
                    UserChatPass.user_id == int(user_id),
                    UserChatPass.status == "active",
                    UserChatPass.remaining_uses.isnot(None),
                )
                .order_by(UserChatPass.id.desc())
                .first()
            )
            if existing:
                existing.total_uses = int(existing.total_uses or 0) + int(total_uses or 0)
                existing.remaining_uses = int(existing.remaining_uses or 0) + int(total_uses or 0)
                existing.amount = int(existing.amount or 0) + int(plan["amount"])
                if expires_at and (not existing.expires_at or existing.expires_at < expires_at):
                    existing.expires_at = expires_at
                if order_id:
                    existing.order_id = str(order_id)
                if payment_key:
                    existing.payment_key = str(payment_key)
                db.commit()
                db.refresh(existing)
                return _serialize(existing)

        row = UserChatPass(
            user_id=int(user_id),
            plan_code=plan["code"],
            plan_name=plan["name"],
            status="active",
            amount=int(plan["amount"]),
            currency=str(plan.get("currency") or "KRW").upper(),
            total_uses=total_uses,
            remaining_uses=remaining_uses,
            duration_days=duration_days,
            started_at=now,
            expires_at=expires_at,
            order_id=str(order_id or ""),
            payment_key=str(payment_key or ""),
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        return _serialize(row)
    finally:
        db.close()


def consume_for_chat(user_id: int, *, commit: bool = True) -> dict[str, Any]:
    db = SessionLocal()
    try:
        _refresh_statuses_for_user(db, int(user_id))
        _consolidate_count_passes_for_user(db, int(user_id))
        row = (
            db.query(UserChatPass)
            .filter(UserChatPass.user_id == int(user_id), UserChatPass.status == "active")
            .order_by(UserChatPass.id.desc())
            .first()
        )
        if not row:
            latest = (
                db.query(UserChatPass)
                .filter(UserChatPass.user_id == int(user_id))
                .order_by(UserChatPass.id.desc())
                .first()
            )
            reason = "NO_PASS"
            if latest:
                if latest.status == "expired":
                    reason = "PASS_EXPIRED"
                elif latest.status == "used_up":
                    reason = "PASS_EXHAUSTED"
            return {"ok": False, "reason": reason, "active_pass": None}

        if commit and row.remaining_uses is not None:
            row.remaining_uses = max(0, int(row.remaining_uses) - 1)
            if row.remaining_uses <= 0:
                row.status = "used_up"
            db.commit()
            db.refresh(row)
        return {"ok": True, "reason": "", "active_pass": _serialize(row)}
    finally:
        db.close()


def delete_user_pass(user_id: int, pass_id: int) -> bool:
    db = SessionLocal()
    try:
        _refresh_statuses_for_user(db, int(user_id))
        row = (
            db.query(UserChatPass)
            .filter(UserChatPass.id == int(pass_id), UserChatPass.user_id == int(user_id))
            .first()
        )
        if not row:
            return False
        if row.status == "active":
            return False
        db.delete(row)
        db.commit()
        return True
    finally:
        db.close()
