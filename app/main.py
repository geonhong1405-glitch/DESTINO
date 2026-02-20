from fastapi import FastAPI, Query, Request, Depends, Form, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session

from app.session import get_user_id_from_session, create_session, delete_session
from app.db.db import Base, engine, SessionLocal
from app.db.models import User
from app.endpoints.routes import router as main_router
from app.endpoints.rag_api import router as rag_router
from app.endpoints.flight_chat import router as flight_chat_router
from app.api.amadeus_api import (
    search_hotels as amadeus_search_hotels,
    resolve_location_to_iata as amadeus_resolve_location_to_iata,
)
from app.api.booking_hotel_flight_api import search_hotels as booking_search_hotels

import os
import json
import datetime


app = FastAPI()


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
    return templates.TemplateResponse("mypage.html", {"request": request})


@app.get("/airport", response_class=HTMLResponse)
def airport(request: Request):
    nickname = get_nickname_from_request(request)
    return templates.TemplateResponse("airport.html", {"request": request, "nickname": nickname})


@app.get("/planner", response_class=HTMLResponse)
def planner(request: Request):
    nickname = get_nickname_from_request(request)
    return templates.TemplateResponse("planner.html", {"request": request, "nickname": nickname})


@app.get("/join", response_class=HTMLResponse)
def join(request: Request):
    return templates.TemplateResponse("join.html", {"request": request})


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
        return templates.TemplateResponse("signin.html", {"request": request, "error": "존재하지 않는 아이디입니다."})
    if user.password != password:
        return templates.TemplateResponse("signin.html", {"request": request, "error": "비밀번호가 올바르지 않습니다."})

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
    return db.query(User).all()


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

    user = User(name=username, password=password, nickname=nickname, email=email, phone=phone)
    db.add(user)
    db.commit()
    db.refresh(user)
    return RedirectResponse(url="/login", status_code=302)
