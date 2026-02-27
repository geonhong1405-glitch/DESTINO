# app/session.py
import secrets
from datetime import datetime, timedelta

from app.db.db import SessionLocal
from app.db.models import UserSession

SESSION_EXPIRE_MINUTES = 60


def create_session(user_id: int) -> str:
    session_token = secrets.token_urlsafe(32)
    expire_at = datetime.utcnow() + timedelta(minutes=SESSION_EXPIRE_MINUTES)
    db = SessionLocal()
    try:
        db.query(UserSession).filter(UserSession.expire_at < datetime.utcnow()).delete()
        db.add(
            UserSession(
                user_id=int(user_id),
                session_token=session_token,
                expire_at=expire_at,
            )
        )
        db.commit()
    finally:
        db.close()
    return session_token


def get_user_id_from_session(session_token: str) -> int | None:
    if not session_token:
        return None
    db = SessionLocal()
    try:
        row = db.query(UserSession).filter(UserSession.session_token == str(session_token)).first()
        if not row:
            return None
        if row.expire_at < datetime.utcnow():
            db.delete(row)
            db.commit()
            return None
        return int(row.user_id)
    finally:
        db.close()


def delete_session(session_token: str):
    if not session_token:
        return
    db = SessionLocal()
    try:
        db.query(UserSession).filter(UserSession.session_token == str(session_token)).delete()
        db.commit()
    finally:
        db.close()
