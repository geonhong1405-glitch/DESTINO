from app.api.booking_hotel_flight_api import search_hotels as booking_search_hotels, search_flights as booking_search_flights
from app.api.booking_api import search_car_rentals
from app.session import get_user_id_from_session, create_session, delete_session
from app.db.db import Base, engine, SessionLocal
from fastapi import FastAPI, Query, Request, Depends, Form, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from app.api.geoapify import get_attractions
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session

from app.session import get_user_id_from_session, create_session, delete_session
from app.db.db import Base, engine, SessionLocal
from app.db.models import User
from app.endpoints.routes import router as main_router
from app.endpoints.rag_api import router as rag_router
from app.endpoints.flight_chat import router as flight_chat_router
from sqlalchemy.orm import Session
from app.db.models import User
from app.api.amadeus_api import (
    search_hotels as amadeus_search_hotels,
    resolve_location_to_iata as amadeus_resolve_location_to_iata,
)
from app.api.booking_hotel_flight_api import search_hotels as booking_search_hotels

import os
import json
import datetime
import re
import base64
import hashlib
import hmac

_PWD_PREFIX = "pbkdf2_sha256"
_PWD_ITERATIONS = 260000
_PASSWORD_REGEX = re.compile(r"^(?=.*[A-Za-z])(?=.*\d)(?=.*[^\w\s]).{8,}$")
_EMAIL_REGEX = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
_PHONE_REGEX = re.compile(r"^01[0-9]-\d{3,4}-\d{4}$")


def _validate_signup(password: str, email: str, phone: str) -> str | None:
    if not _PASSWORD_REGEX.match(password or ""):
        return "\ube44\ubc00\ubc88\ud638\ub294 \uc601\ubb38/\uc22b\uc790/\ud2b9\uc218\ubb38\uc790 \ud3ec\ud568 8\uc790 \uc774\uc0c1\uc774\uc5b4\uc57c \ud569\ub2c8\ub2e4."
    if not _EMAIL_REGEX.match(email or ""):
        return "\uc774\uba54\uc77c \ud615\uc2dd\uc774 \uc62c\ubc14\ub974\uc9c0 \uc54a\uc2b5\ub2c8\ub2e4."
    if not _PHONE_REGEX.match(phone or ""):
        return "\ud734\ub300\ud3f0 \ubc88\ud638 \ud615\uc2dd\uc774 \uc62c\ubc14\ub974\uc9c0 \uc54a\uc2b5\ub2c8\ub2e4."
    return None


def _validate_password_only(password: str) -> str | None:
    if not _PASSWORD_REGEX.match(password or ""):
        return "비밀번호는 영문/숫자/특수문자 포함 8자 이상이어야 합니다."
    return None



def _hash_password(password: str) -> str:
    salt = base64.b64encode(os.urandom(16)).decode("ascii").rstrip("=")
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), _PWD_ITERATIONS)
    digest = base64.b64encode(dk).decode("ascii").rstrip("=")
    return f"{_PWD_PREFIX}${_PWD_ITERATIONS}${salt}${digest}"


def _verify_password(password: str, stored: str) -> tuple[bool, bool]:
    if not stored:
        return False, False
    if stored.startswith(f"{_PWD_PREFIX}$"):
        try:
            _, iters, salt, digest = stored.split("$", 3)
            dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), int(iters))
            calc = base64.b64encode(dk).decode("ascii").rstrip("=")
            return hmac.compare_digest(calc, digest), False
        except Exception:
            return False, False
    # legacy plaintext fallback; caller may upgrade
    return hmac.compare_digest(password, stored), True


app = FastAPI()
from app.api.booking_hotel_flight_api import search_hotels as booking_search_hotels, search_flights as booking_search_flights
from app.api.booking_api import search_car_rentals
from app.session import get_user_id_from_session, create_session, delete_session
from app.db.db import Base, engine, SessionLocal
from fastapi import FastAPI, Query, Request, Depends, Form, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from app.api.geoapify import get_attractions
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from app.endpoints.routes import router as main_router
from app.endpoints.rag_api import router as rag_router
from app.endpoints.flight_chat import router as flight_chat_router
from sqlalchemy.orm import Session
from app.db.models import User


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_nickname_from_request(request: Request) -> str | None:
    session_token = request.cookies.get("session_token")
    user_id = get_user_id_from_session(session_token) if session_token else None
    if not user_id:
        return None

    db = SessionLocal()
    try:
        user = db.query(User).filter(User.id == int(user_id)).first()
        return user.nickname if user else None
    finally:
        db.close()


def parse_amadeus_hotels(amadeus_result: dict) -> list[dict]:
    hotels = []
    if amadeus_result and amadeus_result.get("error"):
        details = amadeus_result.get("details", "")
        msg = f"Amadeus API error: {amadeus_result.get('error')}"
        if details:
            msg += f" | {details[:180]}"
        hotels.append({"name": msg, "address": "", "price": None, "source": "Amadeus"})
        return hotels

    rows = amadeus_result.get("data", []) if isinstance(amadeus_result, dict) else []
    if not isinstance(rows, list):
        hotels.append({"name": "Amadeus API invalid data format", "address": "", "price": None, "source": "Amadeus"})
        return hotels

    for h in rows:
        if not isinstance(h, dict):
            continue

        hotel_obj = h.get("hotel", {}) if isinstance(h.get("hotel"), dict) else {}
        hotel_name = hotel_obj.get("name") or h.get("name") or h.get("hotelName") or "Unnamed hotel"

        address_obj = hotel_obj.get("address", {}) if isinstance(hotel_obj.get("address"), dict) else {}
        if not address_obj:
            address_obj = h.get("address", {}) if isinstance(h.get("address"), dict) else {}
        address_lines = address_obj.get("lines")
        if isinstance(address_lines, list):
            address = ", ".join([line for line in address_lines if isinstance(line, str)])
        else:
            address = ""
        if not address:
            address = address_obj.get("cityName") or hotel_obj.get("cityCode") or h.get("iataCode") or ""

        offers = h.get("offers", []) if isinstance(h.get("offers"), list) else []
        first_offer = offers[0] if offers else {}
        price_obj = first_offer.get("price", {}) if isinstance(first_offer, dict) else {}
        price = price_obj.get("total")
        currency = price_obj.get("currency") or "N/A"

        media = hotel_obj.get("media", []) if isinstance(hotel_obj.get("media"), list) else []
        if not media:
            media = h.get("media", []) if isinstance(h.get("media"), list) else []
        first_media = media[0] if media else {}
        image = None
        if isinstance(first_media, dict):
            image = first_media.get("uri") or first_media.get("url")

        hotels.append(
            {
                "name": hotel_name,
                "address": address,
                "price": price,
                "currency": currency,
                "image": image,
                "source": "Amadeus",
            }
        )

    if not hotels:
        hotels.append({"name": "Amadeus API returned no results", "address": "", "price": None, "source": "Amadeus"})
    return hotels


def parse_booking_hotels(booking_result: dict) -> list[dict]:
    hotels = []
    if booking_result and booking_result.get("error"):
        details = booking_result.get("details", "")
        msg = f"Booking API error: {booking_result.get('error')}"
        if details:
            msg += f" | {details[:180]}"
        hotels.append({"name": msg, "address": "", "price": None, "source": "Booking"})
        return hotels

    rows_obj = booking_result.get("data", []) if isinstance(booking_result, dict) else []
    rows = rows_obj.get("hotels", []) if isinstance(rows_obj, dict) else rows_obj
    if not isinstance(rows, list):
        return hotels

    for h in rows:
        if not isinstance(h, dict):
            continue
        prop = h.get("property", {}) if isinstance(h.get("property"), dict) else {}
        hotel_name = (
            prop.get("ko_name")
            or prop.get("name")
            or h.get("ko_name")
            or h.get("hotel_name")
            or h.get("name")
            or "Unnamed hotel"
        )
        address = h.get("address") or prop.get("wishlistName") or ""

        price = h.get("price")
        if price is None:
            price = h.get("priceBreakdown", {}).get("grossPrice", {}).get("value")
        if price is None:
            price = prop.get("priceBreakdown", {}).get("grossPrice", {}).get("value")

        image = h.get("main_photo_url")
        if not image:
            photo_urls = h.get("photoUrls", [])
            if isinstance(photo_urls, list) and photo_urls:
                image = photo_urls[0]
        if not image:
            photo_urls = prop.get("photoUrls", [])
            if isinstance(photo_urls, list) and photo_urls:
                image = photo_urls[0]

        hotels.append(
            {
                "name": hotel_name,
                "address": address,
                "price": price,
                "currency": "KRW",
                "image": image,
                "source": "Booking",
            }
        )

    return hotels


def dedupe_hotels(hotels: list[dict]) -> list[dict]:
    seen = set()
    out = []
    for h in hotels:
        key = (h.get("name"), h.get("address"), h.get("source"))
        if key in seen:
            continue
        seen.add(key)
        out.append(h)
    return out


# DB table bootstrap
Base.metadata.create_all(bind=engine)

# Template/static setup
templates = Jinja2Templates(directory="app/templates")
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, "static")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

# Routers
app.include_router(main_router)
app.include_router(rag_router)
app.include_router(flight_chat_router)




@app.post("/api/verify-password")
def api_verify_password(request: Request, payload: dict, db: Session = Depends(get_db)):
    session_token = request.cookies.get("session_token")
    user_id = get_user_id_from_session(session_token) if session_token else None
    if not user_id:
        return {"ok": False}
    user = db.query(User).filter(User.id == int(user_id)).first()
    if not user:
        return {"ok": False}
    password = (payload or {}).get("password") or ""
    ok, _ = _verify_password(password, user.password)
    return {"ok": bool(ok)}


@app.post("/api/update-profile")
def api_update_profile(request: Request, payload: dict, db: Session = Depends(get_db)):
    session_token = request.cookies.get("session_token")
    user_id = get_user_id_from_session(session_token) if session_token else None
    if not user_id:
        return {"ok": False, "error": "로그인이 필요합니다."}

    user = db.query(User).filter(User.id == int(user_id)).first()
    if not user:
        return {"ok": False, "error": "사용자를 찾을 수 없습니다."}

    password = (payload or {}).get("password") or ""
    ok, _ = _verify_password(password, user.password)
    if not ok:
        return {"ok": False, "error": "비밀번호가 올바르지 않습니다."}

    nickname = (payload or {}).get("nickname") or user.nickname
    email = (payload or {}).get("email") or user.email
    phone = (payload or {}).get("phone") or user.phone

    if email and email != user.email:
        exists = db.query(User).filter(User.email == email).first()
        if exists:
            return {"ok": False, "error": "이미 사용 중인 이메일입니다."}
    if phone and phone != user.phone:
        exists = db.query(User).filter(User.phone == phone).first()
        if exists:
            return {"ok": False, "error": "이미 사용 중인 전화번호입니다."}

    user.nickname = nickname
    user.email = email
    user.phone = phone
    db.commit()

    return {
        "ok": True,
        "user": {
            "id": user.id,
            "name": user.name,
            "nickname": user.nickname,
            "email": user.email,
            "phone": user.phone,
        },
    }
@app.get("/logout")
def logout(request: Request):
    session_token = request.cookies.get("session_token")
    if session_token:
        delete_session(session_token)
    response = RedirectResponse(url="/", status_code=302)
    response.delete_cookie(key="session_token", path="/")
    return response


@app.get("/check-username")
def check_username(username: str = Query(...), db: Session = Depends(get_db)):
    exists = db.query(User).filter(User.name == username).first() is not None
    return {"exists": exists}


@app.get("/check-email")
def check_email(email: str = Query(...), db: Session = Depends(get_db)):
    exists = db.query(User).filter(User.email == email).first() is not None
    return {"exists": exists}


@app.get("/check-phone")
def check_phone(phone: str = Query(...), db: Session = Depends(get_db)):
    exists = db.query(User).filter(User.phone == phone).first() is not None
    return {"exists": exists}


@app.get("/check-nickname")
def check_nickname(nickname: str = Query(...), db: Session = Depends(get_db)):
    exists = db.query(User).filter(User.nickname == nickname).first() is not None
    return {"exists": exists}

templates = Jinja2Templates(directory="app/templates")

@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    nickname = get_nickname_from_request(request)
    return templates.TemplateResponse("home.html", {"request": request, "nickname": nickname})


@app.get("/home", response_class=HTMLResponse)
def home_page(request: Request):
    nickname = get_nickname_from_request(request)
    return templates.TemplateResponse("home.html", {"request": request, "nickname": nickname})


@app.get("/mypage", response_class=HTMLResponse)
def mypage(request: Request):
    session_token = request.cookies.get("session_token")
    nickname = None
    email = None
    name = None
    phone = None
    user_id = get_user_id_from_session(session_token) if session_token else None
    if user_id:
        db = SessionLocal()
        try:
            user = db.query(User).filter(User.id == int(user_id)).first()
            if user:
                nickname = user.nickname
                email = user.email
                name = user.name
                phone = user.phone
        finally:
            db.close()
    return templates.TemplateResponse(
        "mypage.html",
        {"request": request, "nickname": nickname, "email": email, "name": name, "phone": phone},
    )


@app.get("/airport", response_class=HTMLResponse)
def airport(request: Request):
    nickname = get_nickname_from_request(request)
    return templates.TemplateResponse("airport.html", {"request": request, "nickname": nickname})



@app.get("/find-id", response_class=HTMLResponse)
def find_id_get(request: Request):
    return templates.TemplateResponse("find_id.html", {"request": request})


@app.post("/find-id", response_class=HTMLResponse)
def find_id_post(
    request: Request,
    email: str = Form(...),
    phone: str = Form(...),
    db: Session = Depends(get_db),
):
    user = db.query(User).filter(User.email == email, User.phone == phone).first()
    if not user:
        return templates.TemplateResponse(
            "find_id.html",
            {"request": request, "error": "입력한 정보와 일치하는 계정을 찾을 수 없습니다."},
        )
    return templates.TemplateResponse(
        "find_id.html",
        {"request": request, "result": f"아이디: {user.name}"},
    )


@app.get("/find-password", response_class=HTMLResponse)
def find_password_get(request: Request):
    return templates.TemplateResponse("find_password.html", {"request": request})


@app.post("/find-password", response_class=HTMLResponse)
def find_password_post(
    request: Request,
    username: str = Form(...),
    email: str = Form(...),
    phone: str = Form(...),
    new_password: str = Form(...),
    new_password_confirm: str = Form(...),
    db: Session = Depends(get_db),
):
    if new_password != new_password_confirm:
        return templates.TemplateResponse(
            "find_password.html",
            {"request": request, "error": "비밀번호가 일치하지 않습니다."},
        )
    validation_error = _validate_password_only(new_password)
    if validation_error:
        return templates.TemplateResponse(
            "find_password.html",
            {"request": request, "error": validation_error},
        )
    user = db.query(User).filter(User.name == username, User.email == email, User.phone == phone).first()
    if not user:
        return templates.TemplateResponse(
            "find_password.html",
            {"request": request, "error": "입력한 정보와 일치하는 계정을 찾을 수 없습니다."},
        )
    user.password = _hash_password(new_password)
    db.commit()
    return templates.TemplateResponse(
        "find_password.html",
        {"request": request, "result": "비밀번호가 변경되었습니다. 로그인해 주세요."},
    )


@app.get("/gloval-hotel", response_class=HTMLResponse)
def gloval_hotel(request: Request,
                 city: str = Query(None),
                 country: str = Query(None),
                 checkin: str = Query(None),
                 checkout: str = Query(None),
                 lat: float = Query(None),
                 lon: float = Query(None),
                 page: int = Query(1, ge=1)):
    session_token = request.cookies.get("session_token")
    nickname = None
    user_id = get_user_id_from_session(session_token) if session_token else None
    if user_id:
        db = next(get_db())
        user = db.query(User).filter(User.id == int(user_id)).first()
        if user:
            nickname = user.nickname
    hotels = []
    # Booking.com 호텔만 조회
    if city and checkin and checkout:
        try:
            booking_result = booking_search_hotels(city, checkin, checkout, adults=2)
            if booking_result and booking_result.get("error"):
                details = booking_result.get("details", "")
                msg = f"Booking API error: {booking_result.get('error')}"
                if details:
                    msg += f" | {details[:180]}"
                hotels.append({"name": msg, "address": "", "price": None, "source": "Booking"})
            elif booking_result and "data" in booking_result:
                data = booking_result.get("data", [])
                hotels_list = data.get("hotels", []) if isinstance(data, dict) else data
                if isinstance(hotels_list, list):
                    for h in hotels_list:
                        if not isinstance(h, dict):
                            continue
                        prop = h.get("property", {}) if isinstance(h.get("property"), dict) else {}
                        hotel_name = (
                            prop.get("ko_name")
                            or prop.get("name")
                            or h.get("ko_name")
                            or h.get("hotel_name")
                            or h.get("name")
                            or "Unnamed hotel"
                        )
                        address = h.get("address") or prop.get("wishlistName") or ""

                        price = h.get("price")
                        if price is None:
                            price = h.get("priceBreakdown", {}).get("grossPrice", {}).get("value")
                        if price is None:
                            price = prop.get("priceBreakdown", {}).get("grossPrice", {}).get("value")

                        image = h.get("main_photo_url")
                        if not image:
                            photo_urls = h.get("photoUrls", [])
                            if isinstance(photo_urls, list) and photo_urls:
                                image = photo_urls[0]
                        if not image:
                            photo_urls = prop.get("photoUrls", [])
                            if isinstance(photo_urls, list) and photo_urls:
                                image = photo_urls[0]

                        hotels.append(
                            {
                                "name": hotel_name,
                                "address": address,
                                "price": price,
                                "currency": "KRW",
                                "image": image,
                                "source": "Booking",
                            }
                        )
        except Exception as e:
            hotels.append({"name": f"Booking API error: {e}", "address": "", "price": None, "source": "Booking"})

    seen = set()
    unique_hotels = []
    for h in hotels:
        key = (h['name'], h['address'])
        if key not in seen:
            unique_hotels.append(h)
            seen.add(key)

    page_size = 15
    total_hotels = len(unique_hotels)
    total_pages = max((total_hotels + page_size - 1) // page_size, 1)
    if page > total_pages:
        page = total_pages
    start_idx = (page - 1) * page_size
    end_idx = start_idx + page_size
    paged_hotels = unique_hotels[start_idx:end_idx]
    has_prev = page > 1
    has_next = page < total_pages
    try:
        with open(os.path.join(BASE_DIR, "hotel_debug.log"), "a", encoding="utf-8") as f:
            import datetime, json
            f.write(f"\n[{datetime.datetime.now()}] params: city={city}, country={country}, checkin={checkin}, checkout={checkout}, lat={lat}, lon={lon}\n")
            f.write(f"hotels: ")
            f.write(json.dumps(unique_hotels, ensure_ascii=False))
            f.write("\n")
    except Exception as e:
        pass
    return templates.TemplateResponse("gloval-hotel.html", {"request": request, "nickname": nickname, "hotels": paged_hotels, "page": page, "total_pages": total_pages, "has_prev": has_prev, "has_next": has_next, "city": city, "country": country, "checkin": checkin, "checkout": checkout, "lat": lat, "lon": lon})

@app.get("/home", response_class=HTMLResponse)
def home_page(request: Request):
    session_token = request.cookies.get("session_token")
    nickname = None
    user_id = get_user_id_from_session(session_token) if session_token else None
    if user_id:
        db = next(get_db())
        user = db.query(User).filter(User.id == int(user_id)).first()
        if user:
            nickname = user.nickname
    return templates.TemplateResponse("home.html", {"request": request, "nickname": nickname})

@app.get("/planner", response_class=HTMLResponse)
def planner(request: Request):
    nickname = get_nickname_from_request(request)
    return templates.TemplateResponse("planner.html", {"request": request, "nickname": nickname})

@app.get("/travelGroup", response_class=HTMLResponse)
def travelGroup(request: Request):
    nickname = get_nickname_from_request(request)
    return templates.TemplateResponse("travel-group.html", {"request": request, "nickname": nickname})

@app.get("/package", response_class=HTMLResponse)
def package_page(request: Request):
    nickname = get_nickname_from_request(request)
    return templates.TemplateResponse("package.html", {"request": request, "nickname": nickname})


@app.get("/tour", response_class=HTMLResponse)
def tour_page(request: Request):
    nickname = get_nickname_from_request(request)
    return templates.TemplateResponse("tour.html", {"request": request, "nickname": nickname})


@app.get("/rental", response_class=HTMLResponse)
def rental_page(request: Request):
    nickname = get_nickname_from_request(request)
    return templates.TemplateResponse("rental.html", {"request": request, "nickname": nickname})


@app.get("/join", response_class=HTMLResponse)
def join(request: Request):
    return templates.TemplateResponse("join.html", {"request": request})


@app.get("/signin", response_class=HTMLResponse)
def signin_get(request: Request):
    return templates.TemplateResponse("signin.html", {"request": request})
app.include_router(rag_router)
app.include_router(flight_chat_router)


@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    session_token = request.cookies.get("session_token")
    nickname = None
    user_id = get_user_id_from_session(session_token) if session_token else None
    if user_id:
        db = next(get_db())
        user = db.query(User).filter(User.id == int(user_id)).first()
        if user:
            nickname = user.nickname
    return templates.TemplateResponse("home.html", {"request": request, "nickname": nickname})
@app.get("/login", response_class=HTMLResponse)
def login(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})


@app.get("/signin", response_class=HTMLResponse)
def signin_get(request: Request):
    return templates.TemplateResponse("signin.html", {"request": request})


@app.post("/signin", response_class=HTMLResponse)
def signin_post(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db),
):
    user = db.query(User).filter(User.name == username).first()
    if not user:
        return templates.TemplateResponse("signin.html", {"request": request, "error": "아이디 또는 비밀번호가 올바르지 않습니다. 다시 입력해주세요."})
    ok, needs_upgrade = _verify_password(password, user.password)
    if not ok:
        return templates.TemplateResponse("signin.html", {"request": request, "error": "아이디 또는 비밀번호가 올바르지 않습니다. 다시 입력해주세요."})
    if needs_upgrade:
        user.password = _hash_password(password)
        db.commit()

    session_token = create_session(user.id)
    response = RedirectResponse(url="/", status_code=status.HTTP_302_FOUND)
    response.set_cookie(key="session_token", value=session_token, httponly=True)
    return response


@app.get("/gloval-hotel", response_class=HTMLResponse)
def gloval_hotel(
    request: Request,
    city: str = Query(None),
    country: str = Query(None),
    checkin: str = Query(None),
    checkout: str = Query(None),
    lat: float = Query(None),
    lon: float = Query(None),
    page: int = Query(1, ge=1),
):
    nickname = get_nickname_from_request(request)
    hotels = []

    if city and checkin and checkout:
        try:
            city_code = amadeus_resolve_location_to_iata(city)
            if city_code:
                amadeus_result = amadeus_search_hotels(city_code, checkin, checkout, adults=2)
                hotels.extend(parse_amadeus_hotels(amadeus_result))
            else:
                hotels.append({"name": f"Amadeus location resolve failed: {city}", "address": "", "price": None, "source": "Amadeus"})
        except Exception as e:
            hotels.append({"name": f"Amadeus API error: {e}", "address": "", "price": None, "source": "Amadeus"})

        try:
            booking_result = booking_search_hotels(city, checkin, checkout, adults=2)
            hotels.extend(parse_booking_hotels(booking_result))
        except Exception as e:
            hotels.append({"name": f"Booking API error: {e}", "address": "", "price": None, "source": "Booking"})

    unique_hotels = dedupe_hotels(hotels)

    page_size = 15
    total_hotels = len(unique_hotels)
    total_pages = max((total_hotels + page_size - 1) // page_size, 1)
    page = min(page, total_pages)
    start_idx = (page - 1) * page_size
    end_idx = start_idx + page_size
    paged_hotels = unique_hotels[start_idx:end_idx]

    try:
        with open(os.path.join(BASE_DIR, "hotel_debug.log"), "a", encoding="utf-8") as f:
            f.write(
                f"\n[{datetime.datetime.now()}] params: city={city}, country={country}, checkin={checkin}, checkout={checkout}, lat={lat}, lon={lon}\n"
            )
            f.write("hotels: ")
            f.write(json.dumps(unique_hotels, ensure_ascii=False))
            f.write("\n")
    except Exception:
        pass

    return templates.TemplateResponse(
        "gloval-hotel.html",
        {
            "request": request,
            "nickname": nickname,
            "hotels": paged_hotels,
            "page": page,
            "total_pages": total_pages,
            "has_prev": page > 1,
            "has_next": page < total_pages,
            "city": city,
            "country": country,
            "checkin": checkin,
            "checkout": checkout,
            "lat": lat,
            "lon": lon,
        },
    )


@app.get("/gloval", response_class=HTMLResponse)
def gloval_alias(request: Request):
    # Legacy route alias
    return templates.TemplateResponse("gloval-hotel.html", {"request": request})


@app.get("/users")
def read_users(db: Session = Depends(get_db)):
    return [
        {"id": u.id, "name": u.name, "nickname": u.nickname, "email": u.email, "phone": u.phone}
        for u in db.query(User).all()
    ]


@app.post("/users")
def create_user(
    request: Request,
    nickname: str = Form(...),
    username: str = Form(...),
    password: str = Form(...),
    password_confirm: str = Form(...),
    email: str = Form(...),
    phone: str = Form(...),
    db: Session = Depends(get_db),
):
    if db.query(User).filter(User.name == username).first():
        return templates.TemplateResponse("join.html", {"request": request, "error": "이미 사용 중인 아이디입니다."})
    if db.query(User).filter(User.email == email).first():
        return templates.TemplateResponse("join.html", {"request": request, "error": "이미 사용 중인 이메일입니다."})
    if db.query(User).filter(User.phone == phone).first():
        return templates.TemplateResponse("join.html", {"request": request, "error": "이미 사용 중인 전화번호입니다."})
    if db.query(User).filter(User.nickname == nickname).first():
        return templates.TemplateResponse("join.html", {"request": request, "error": "이미 사용 중인 닉네임입니다."})
    if password != password_confirm:
        return templates.TemplateResponse("join.html", {"request": request, "error": "비밀번호가 일치하지 않습니다."})
    validation_error = _validate_signup(password, email, phone)
    if validation_error:
        return templates.TemplateResponse("join.html", {"request": request, "error": validation_error})

    user = User(name=username, password=_hash_password(password), nickname=nickname, email=email, phone=phone)
    db.add(user)
    db.commit()
    db.refresh(user)
    return RedirectResponse(url="/login", status_code=302)










