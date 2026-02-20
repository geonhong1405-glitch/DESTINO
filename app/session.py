# app/session.py
import secrets
from datetime import datetime, timedelta

from sqlalchemy.orm import Session
from app.db.models import User

# 세션 저장소 (메모리, 실제 서비스는 DB 권장)
session_store = {}
SESSION_EXPIRE_MINUTES = 60

def create_session(user_id: int) -> str:
    session_token = secrets.token_urlsafe(32)
    expire_at = datetime.utcnow() + timedelta(minutes=SESSION_EXPIRE_MINUTES)
    session_store[session_token] = {"user_id": user_id, "expire_at": expire_at}
    return session_token

def get_user_id_from_session(session_token: str) -> int | None:
    session = session_store.get(session_token)
    if not session:
        return None
    if session["expire_at"] < datetime.utcnow():
        del session_store[session_token]
        return None
    return session["user_id"]

def delete_session(session_token: str):
    session_store.pop(session_token, None)
