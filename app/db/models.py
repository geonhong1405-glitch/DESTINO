from sqlalchemy import Column, Integer, String
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