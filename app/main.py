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

@app.get("/logout")
def logout(request: Request):
    session_token = request.cookies.get("session_token")
    if session_token:
        delete_session(session_token)
    response = RedirectResponse(url="/", status_code=302)
    response.delete_cookie(key="session_token", path="/")
    return response

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

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

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

import os
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, "static")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

app.include_router(main_router)

@app.get("/mypage", response_class=HTMLResponse)
def mypage(request: Request):
    return templates.TemplateResponse("mypage.html", {"request": request})

@app.get("/airport", response_class=HTMLResponse)
def airport(request: Request):
    session_token = request.cookies.get("session_token")
    nickname = None
    user_id = get_user_id_from_session(session_token) if session_token else None
    if user_id:
        db = next(get_db())
        user = db.query(User).filter(User.id == int(user_id)).first()
        if user:
            nickname = user.nickname
    return templates.TemplateResponse("airport.html", {"request": request, "nickname": nickname})

@app.get("/gloval-hotel", response_class=HTMLResponse)
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
    session_token = request.cookies.get("session_token")
    nickname = None
    user_id = get_user_id_from_session(session_token) if session_token else None
    if user_id:
        db = next(get_db())
        user = db.query(User).filter(User.id == int(user_id)).first()
        if user:
            nickname = user.nickname
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

@app.get("/users")
def read_users(db: Session = Depends(get_db)):
    return db.query(User).all()





from fastapi.responses import RedirectResponse

@app.post("/users")
def create_user(
    request: Request,
    nickname: str = Form(...),
    username: str = Form(...),
    password: str = Form(...),
    password_confirm: str = Form(...),
    email: str = Form(...),
    phone: str = Form(...),
    db: Session = Depends(get_db)
):
    # 以묐났 泥댄겕
    if db.query(User).filter(User.name == username).first():
        return templates.TemplateResponse("join.html", {"request": request, "error": "?占쏙옙? ?占쎌슜 以묒씤 ?占쎌씠?占쎌엯?占쎈떎."})
    if db.query(User).filter(User.email == email).first():
        return templates.TemplateResponse("join.html", {"request": request, "error": "?占쏙옙? ?占쎌슜 以묒씤 ?占쎈찓?占쎌엯?占쎈떎."})
    if db.query(User).filter(User.phone == phone).first():
        return templates.TemplateResponse("join.html", {"request": request, "error": "?占쏙옙? ?占쎌슜 以묒씤 ?占쏙옙???踰덊샇?占쎈땲??"})
    if db.query(User).filter(User.nickname == nickname).first():
        return templates.TemplateResponse("join.html", {"request": request, "error": "?占쏙옙? ?占쎌슜 以묒씤 ?占쎈꽕?占쎌엯?占쎈떎."})
    if password != password_confirm:
        return templates.TemplateResponse("join.html", {"request": request, "error": "鍮꾬옙?踰덊샇媛 ?占쎌튂?占쏙옙? ?占쎌뒿?占쎈떎."})
    # ?占쎌썝 ?占쎌꽦
    user = User(name=username, password=password, nickname=nickname, email=email, phone=phone)
    db.add(user)
    db.commit()
    db.refresh(user)
    return RedirectResponse(url="/login", status_code=302)
    if password != password_confirm:
        return templates.TemplateResponse("join.html", {"request": request, "error": "鍮꾬옙?踰덊샇媛 ?占쎌튂?占쏙옙? ?占쎌뒿?占쎈떎."})
    user = User(name=username, email=email, phone=phone, password=password, nickname=nickname)
    db.add(user)
    db.commit()
    db.refresh(user)
    # ?占쎌썝媛???占쎄났 ??濡쒓렇???占쎈㈃?占쎈줈 由щ떎?占쎈젆??(POST-Redirect-GET)
    return RedirectResponse(url="/signin", status_code=303)










