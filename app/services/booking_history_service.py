import json
from datetime import datetime
from typing import Any

from app.db.db import SessionLocal
from app.db.models import UserBooking


def save_booking(
    *,
    user_id: int,
    item_type: str,
    order_id: str,
    order_name: str,
    amount: int,
    currency: str = "KRW",
    status: str = "confirmed",
    status_label: str | None = None,
    route: str | None = None,
    payment_key: str | None = None,
    payload: dict[str, Any] | None = None,
    created_at_iso: str | None = None,
    confirmed_at_iso: str | None = None,
) -> None:
    db = SessionLocal()
    try:
        row = db.query(UserBooking).filter(UserBooking.order_id == str(order_id)).first()
        if row is None:
            row = UserBooking(order_id=str(order_id))
            db.add(row)

        row.user_id = int(user_id)
        row.item_type = str(item_type or "").strip() or "etc"
        row.order_name = str(order_name or "").strip() or "예약 상품"
        row.amount = int(amount or 0)
        row.currency = str(currency or "KRW").strip().upper() or "KRW"
        row.status = str(status or "confirmed").strip() or "confirmed"
        row.status_label = str(status_label).strip() if status_label else None
        row.route = str(route).strip() if route else None
        row.payment_key = str(payment_key).strip() if payment_key else None
        row.payload_json = json.dumps(payload or {}, ensure_ascii=False)

        if created_at_iso:
            try:
                row.created_at = datetime.fromisoformat(str(created_at_iso))
            except Exception:
                pass
        if confirmed_at_iso:
            try:
                row.confirmed_at = datetime.fromisoformat(str(confirmed_at_iso))
            except Exception:
                row.confirmed_at = datetime.utcnow()
        elif not row.confirmed_at:
            row.confirmed_at = datetime.utcnow()

        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def get_user_bookings(user_id: int, limit: int = 100) -> list[dict[str, Any]]:
    db = SessionLocal()
    try:
        rows = (
            db.query(UserBooking)
            .filter(UserBooking.user_id == int(user_id))
            .order_by(UserBooking.confirmed_at.desc(), UserBooking.created_at.desc())
            .limit(int(limit))
            .all()
        )
        out: list[dict[str, Any]] = []
        for row in rows:
            out.append(
                {
                    "item_type": row.item_type or "",
                    "order_id": row.order_id or "",
                    "order_name": row.order_name or "",
                    "amount": int(row.amount or 0),
                    "currency": row.currency or "KRW",
                    "status": row.status or "confirmed",
                    "status_label": row.status_label or "",
                    "route": row.route or "",
                    "created_at": row.created_at.isoformat() if row.created_at else "",
                    "confirmed_at": row.confirmed_at.isoformat() if row.confirmed_at else "",
                }
            )
        return out
    finally:
        db.close()
