from sqlalchemy import Column, Integer, String, DateTime, func
from app.db.db import Base

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(50), index=True)
    email = Column(String(100), unique=True, index=True)
    phone = Column(String(20), index=True)
    password = Column(String(128))
    nickname = Column(String(50), index=True)

class Nickname(Base):
    __tablename__ = "nicknames"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, index=True)
    nickname = Column(String(50), index=True)


class TranslationCache(Base):
    __tablename__ = "translation_cache"
    id = Column(Integer, primary_key=True, index=True)
    source_text = Column(String(512), unique=True, index=True)
    translated_text = Column(String(512))
    source_lang = Column(String(10))
    target_lang = Column(String(10))
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, onupdate=func.now(), server_default=func.now())
