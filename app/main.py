from app.api.booking_hotel_flight_api import search_hotels as booking_search_hotels, search_flights as booking_search_flights
from app.api.amadeus_api import search_hotels as amadeus_search_hotels, resolve_location_to_iata as amadeus_resolve_location_to_iata
from app.api.booking_api import search_car_rentals
# ...existing code...
from app.session import get_user_id_from_session, create_session, delete_session
from app.db.db import Base, engine, SessionLocal
from fastapi import FastAPI, Query
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
## Amadeus/Google : Booking.com??
from app.api.geoapify import get_attractions
from fastapi import Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from app.endpoints.routes import router as main_router
from app.endpoints.rag_api import router as rag_router
from app.endpoints.flight_chat import router as flight_chat_router
from sqlalchemy.orm import Session
from app.db.models import User
from fastapi import Depends


app = FastAPI()

# 濡쒓렇?占쎌썐 ?占쎌슦?? 諛섎뱶??app = FastAPI() ?占쏀썑???占쎌뼵
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

# Jinja2 ?占쏀뵆占??占쎌쭊 ?占쎌젙
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
    # Amadeus/Google ?占쏀뀛 寃???占쎄굅: Booking.com占??占쎌슜

    # Booking.com ?占쏀뀛占??占쎌슜
    if city and checkin and checkout:
        try:
            city_code = amadeus_resolve_location_to_iata(city)
            if not city_code:
                hotels.append({"name": f"Amadeus location resolve failed: {city}", "address": "", "price": None, "source": "Amadeus"})
            else:
                amadeus_result = amadeus_search_hotels(city_code, checkin, checkout, adults=2)
                try:
                    with open(os.path.join(BASE_DIR, "hotel_debug.log"), "a", encoding="utf-8") as f:
                        import json
                        f.write("amadeus_result: ")
                        f.write(json.dumps(amadeus_result, ensure_ascii=False)[:2000] + "...\n")
                except Exception:
                    pass

                if amadeus_result and amadeus_result.get("error"):
                    details = amadeus_result.get("details", "")
                    msg = f"Amadeus API error: {amadeus_result.get('error')}"
                    if details:
                        msg += f" | {details[:180]}"
                    hotels.append({"name": msg, "address": "", "price": None, "source": "Amadeus"})
                elif amadeus_result and "data" in amadeus_result:
                    hotels_list = amadeus_result.get("data", [])
                    if isinstance(hotels_list, list):
                        for h in hotels_list:
                            if not isinstance(h, dict):
                                continue
                            hotel_obj = h.get("hotel", {}) if isinstance(h.get("hotel"), dict) else {}
                            hotel_name = (
                                hotel_obj.get("name")
                                or h.get("name")
                                or h.get("hotelName")
                                or "Unnamed hotel"
                            )

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

                            hotels.append({
                                "name": hotel_name,
                                "address": address,
                                "price": price,
                                "currency": currency,
                                "image": image,
                                "source": "Amadeus",
                            })
                    else:
                        hotels.append({"name": "Amadeus API invalid data format", "address": "", "price": None, "source": "Amadeus"})
                else:
                    hotels.append({"name": "Amadeus API returned no results", "address": "", "price": None, "source": "Amadeus"})
        except Exception as e:
            hotels.append({"name": f"Amadeus API error: {e}", "address": "", "price": None, "source": "Amadeus"})
        # Booking.com도 함께 조회
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

    # 以묐났 ?占쎄굅 (?占쎈쫫+二쇱냼 湲곤옙?)
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
    # ?占쎈쾭占? ?占쎈씪誘명꽣, Amadeus ?占쎈떟, ?占쏀뀛 由ъ뒪?占쏙옙? ?占쎌씪占?湲곕줉
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


# 濡쒓렇???占쎌씠吏 ?占쎈뜑占?
@app.get("/login", response_class=HTMLResponse)
def login(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

# ?占쎌썝媛???占쎌씠吏 ?占쎈뜑占?
@app.get("/join", response_class=HTMLResponse)
def join(request: Request):
    return templates.TemplateResponse("join.html", {"request": request})

# ?占쎌씠?占쎈쿋?占쎌뒪 ?占쎌씠占??占쎌꽦
Base.metadata.create_all(bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# ?占쎈찓??濡쒓렇???占쎌씠吏 ?占쎈뜑占?占?濡쒓렇??泥섎━
from fastapi import Form, status
from fastapi.responses import RedirectResponse

@app.get("/signin", response_class=HTMLResponse)
def signin_get(request: Request):
    return templates.TemplateResponse("signin.html", {"request": request})



@app.post("/signin", response_class=HTMLResponse)
def signin_post(request: Request, username: str = Form(...), password: str = Form(...), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.name == username).first()
    if not user:
        return templates.TemplateResponse("signin.html", {"request": request, "error": "議댁옱?占쏙옙? ?占쎈뒗 ?占쎌씠?占쎌엯?占쎈떎."})
    if user.password != password:
        return templates.TemplateResponse("signin.html", {"request": request, "error": "鍮꾬옙?踰덊샇媛 ?占쎈컮瑜댐옙? ?占쎌뒿?占쎈떎."})
    # 濡쒓렇???占쎄났: ?占쎌뀡 ?占쎌꽦 占??占쎌뀡 ?占쏀겙??荑좏궎???占??
    session_token = create_session(user.id)
    response = RedirectResponse(url="/", status_code=status.HTTP_302_FOUND)
    response.set_cookie(key="session_token", value=session_token, httponly=True)
    return response

# ?占쏀뻾 ?占쎈옒???占쎌씠吏 ?占쎈뜑占?
@app.get("/planner", response_class=HTMLResponse)
def planner(request: Request):
    return templates.TemplateResponse("planner.html", {"request": request})

# ?占쎌쇅?占쎌냼 ?占쎌씠吏 ?占쎈뜑占?
@app.get("/gloval", response_class=HTMLResponse)
def gloval(request: Request):
    return templates.TemplateResponse("gloval-hotel.html", {"request": request})

# ??占쏙옙 ?占쎌씠吏 ?占쎈뜑占?
@app.get("/airport", response_class=HTMLResponse)
def airport(request: Request):
    return templates.TemplateResponse("airport.html", {"request": request})

# ?占쎌씠?占쎈쿋?占쎌뒪 ?占쎌씠占??占쎌꽦
Base.metadata.create_all(bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

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










