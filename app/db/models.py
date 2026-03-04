from sqlalchemy import Column, Integer, String, DateTime, Text, func
from app.db.db import Base

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(50), index=True)
    email = Column(String(100), unique=True, index=True)
    phone = Column(String(20), index=True)
    password = Column(String(128))
    nickname = Column(String(50), index=True)


class UserSession(Base):
    __tablename__ = "user_sessions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, index=True, nullable=False)
    session_token = Column(String(128), unique=True, index=True, nullable=False)
    expire_at = Column(DateTime, index=True, nullable=False)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, onupdate=func.now(), server_default=func.now())


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


class UserSavedItem(Base):
    __tablename__ = "user_saved_items"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, index=True, nullable=False)
    list_type = Column(String(20), index=True, nullable=False)  # wishlist | cart
    item_type = Column(String(40), index=True, nullable=False)  # flight | hotel | rental | ...
    name = Column(String(255), nullable=False)
    meta = Column(String(512), nullable=True)
    source = Column(String(50), nullable=True)
    payload_json = Column(Text, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, onupdate=func.now(), server_default=func.now())


class GroupBuyPost(Base):
    __tablename__ = "group_buy_posts"

    id = Column(Integer, primary_key=True, index=True)
    owner_user_id = Column(Integer, index=True, nullable=False)
    category = Column(String(30), nullable=True)
    title = Column(String(255), nullable=False)
    country = Column(String(100), nullable=False)
    city = Column(String(100), nullable=True)
    start_date = Column(String(20), nullable=False)  # YYYY-MM-DD
    end_date = Column(String(20), nullable=True)
    departure = Column(String(100), nullable=True)
    budget = Column(String(80), nullable=True)
    description = Column(Text, nullable=True)
    status = Column(String(20), nullable=False, default="open")  # open/closed
    current_people = Column(Integer, nullable=False, default=1)
    max_people = Column(Integer, nullable=False, default=4)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, onupdate=func.now(), server_default=func.now())


class GroupBuyJoinRequest(Base):
    __tablename__ = "group_buy_join_requests"

    id = Column(Integer, primary_key=True, index=True)
    post_id = Column(Integer, index=True, nullable=False)
    post_owner_user_id = Column(Integer, index=True, nullable=False)
    requester_user_id = Column(Integer, index=True, nullable=False)
    message = Column(String(500), nullable=True)
    status = Column(String(20), nullable=False, default="pending")  # pending/accepted/rejected
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, onupdate=func.now(), server_default=func.now())


class UserBooking(Base):
    __tablename__ = "user_bookings"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, index=True, nullable=False)
    item_type = Column(String(20), index=True, nullable=False)  # flight | hotel | rental | tour | pack
    order_id = Column(String(80), unique=True, index=True, nullable=False)
    order_name = Column(String(255), nullable=False)
    amount = Column(Integer, nullable=False, default=0)
    currency = Column(String(10), nullable=False, default="KRW")
    status = Column(String(30), nullable=False, default="confirmed")
    status_label = Column(String(80), nullable=True)
    route = Column(String(255), nullable=True)
    payment_key = Column(String(255), nullable=True)
    payload_json = Column(Text, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    confirmed_at = Column(DateTime, nullable=True)
    updated_at = Column(DateTime, onupdate=func.now(), server_default=func.now())
