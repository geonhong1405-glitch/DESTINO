from app.api.booking_hotel_flight_api import search_hotels as booking_search_hotels, search_flights as booking_search_flights
from app.api.booking_api import search_car_rentals
# ...existing code...
from app.session import get_user_id_from_session, create_session, delete_session
from app.db.db import Base, engine, SessionLocal
from fastapi import FastAPI, Query
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
## Amadeus/Google 호텔 제거: Booking.com만 사용
from app.api.geoapify import get_attractions
from fastapi import Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from app.endpoints.routes import router as main_router
from app.endpoints.rag_api import router as rag_router
from sqlalchemy.orm import Session
from app.db.models import User
from fastapi import Depends


app = FastAPI()

# 로그아웃 라우터: 반드시 app = FastAPI() 이후에 선언
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

# Jinja2 템플릿 엔진 설정
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
                 lon: float = Query(None)):
    session_token = request.cookies.get("session_token")
    nickname = None
    user_id = get_user_id_from_session(session_token) if session_token else None
    if user_id:
        db = next(get_db())
        user = db.query(User).filter(User.id == int(user_id)).first()
        if user:
            nickname = user.nickname
    hotels = []
    # Amadeus/Google 호텔 검색 제거: Booking.com만 사용

    # Booking.com 호텔만 사용
    if city and checkin and checkout:
        try:
            booking_result = booking_search_hotels(city, checkin, checkout, adults=2)
            try:
                with open(os.path.join(BASE_DIR, "hotel_debug.log"), "a", encoding="utf-8") as f:
                    import json
                    f.write(f"booking_result: ")
                    f.write(json.dumps(booking_result, ensure_ascii=False)[:2000]+"...\n")
            except Exception as log_e:
                pass
            if booking_result and 'data' in booking_result:
                data = booking_result['data']
                if isinstance(data, dict) and 'hotels' in data:
                    hotels_list = data['hotels']
                else:
                    hotels_list = data
                if isinstance(hotels_list, list):
                    for h in hotels_list:
                        if isinstance(h, dict):
                            # 한글 호텔명 우선 노출 (property.ko_name, ko_name, name 순)
                            hotel_name = h.get('property', {}).get('ko_name') or h.get('ko_name') or h.get('hotel_name') or h.get('name')
                            if not hotel_name:
                                property_obj = h.get('property', {}) if isinstance(h.get('property'), dict) else {}
                                hotel_name = property_obj.get('name')
                            price = h.get('price')
                            if price is None:
                                price = h.get('priceBreakdown', {}).get('grossPrice', {}).get('value')
                            if price is None and h.get('property'):
                                price = h.get('property', {}).get('priceBreakdown', {}).get('grossPrice', {}).get('value')
                            # Booking.com API에서 KRW로 요청하므로 currency는 KRW로 고정
                            currency = 'KRW'
                            image = h.get('main_photo_url')
                            if not image:
                                photo_urls = h.get('photoUrls', [])
                                if isinstance(photo_urls, list) and photo_urls:
                                    image = photo_urls[0]
                            if not image and h.get('property'):
                                photo_urls = h.get('property', {}).get('photoUrls', [])
                                if isinstance(photo_urls, list) and photo_urls:
                                    image = photo_urls[0]
                                main_photo_id = h.get('property', {}).get('mainPhotoId')
                                if not image and main_photo_id:
                                    image = f"https://cf.bstatic.com/xdata/images/hotel/square500/{main_photo_id}.jpg"
                            hotels.append({
                                'name': hotel_name if hotel_name else '이름없음',
                                'address': h.get('address', ''),
                                'price': price,
                                'currency': currency,
                                'image': image,
                                'source': 'Booking.com'
                            })
                        else:
                            hotels.append({'name': f'Booking.com API 데이터 오류: {type(h)}', 'address': '', 'price': None, 'source': 'Booking.com'})
                else:
                    hotels.append({'name': f'Booking.com API 데이터 오류: hotels_list 타입 {type(hotels_list)}', 'address': '', 'price': None, 'source': 'Booking.com'})
            else:
                hotels.append({'name': f'Booking.com API 결과 없음', 'address': '', 'price': None, 'source': 'Booking.com'})
        except Exception as e:
            hotels.append({'name': f'Booking.com API 오류: {e}', 'address': '', 'price': None, 'source': 'Booking.com'})
    # 중복 제거 (이름+주소 기준)
    seen = set()
    unique_hotels = []
    for h in hotels:
        key = (h['name'], h['address'])
        if key not in seen:
            unique_hotels.append(h)
            seen.add(key)
    # 디버깅: 파라미터, Amadeus 응답, 호텔 리스트를 파일로 기록
    try:
        with open(os.path.join(BASE_DIR, "hotel_debug.log"), "a", encoding="utf-8") as f:
            import datetime, json
            f.write(f"\n[{datetime.datetime.now()}] params: city={city}, country={country}, checkin={checkin}, checkout={checkout}, lat={lat}, lon={lon}\n")
            f.write(f"hotels: ")
            f.write(json.dumps(unique_hotels, ensure_ascii=False))
            f.write("\n")
    except Exception as e:
        pass
    return templates.TemplateResponse("gloval-hotel.html", {"request": request, "nickname": nickname, "hotels": unique_hotels})

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


# 로그인 페이지 렌더링
@app.get("/login", response_class=HTMLResponse)
def login(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

# 회원가입 페이지 렌더링
@app.get("/join", response_class=HTMLResponse)
def join(request: Request):
    return templates.TemplateResponse("join.html", {"request": request})



# 데이터베이스 테이블 생성
Base.metadata.create_all(bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# 이메일 로그인 페이지 렌더링 및 로그인 처리
from fastapi import Form, status
from fastapi.responses import RedirectResponse

@app.get("/signin", response_class=HTMLResponse)
def signin_get(request: Request):
    return templates.TemplateResponse("signin.html", {"request": request})



@app.post("/signin", response_class=HTMLResponse)
def signin_post(request: Request, username: str = Form(...), password: str = Form(...), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.name == username).first()
    if not user:
        return templates.TemplateResponse("signin.html", {"request": request, "error": "존재하지 않는 아이디입니다."})
    if user.password != password:
        return templates.TemplateResponse("signin.html", {"request": request, "error": "비밀번호가 올바르지 않습니다."})
    # 로그인 성공: 세션 생성 및 세션 토큰을 쿠키에 저장
    session_token = create_session(user.id)
    response = RedirectResponse(url="/", status_code=status.HTTP_302_FOUND)
    response.set_cookie(key="session_token", value=session_token, httponly=True)
    return response

# 여행 플래너 페이지 렌더링
@app.get("/planner", response_class=HTMLResponse)
def planner(request: Request):
    return templates.TemplateResponse("planner.html", {"request": request})

# 해외숙소 페이지 렌더링
@app.get("/gloval", response_class=HTMLResponse)
def gloval(request: Request):
    return templates.TemplateResponse("gloval-hotel.html", {"request": request})

# 항공 페이지 렌더링
@app.get("/airport", response_class=HTMLResponse)
def airport(request: Request):
    return templates.TemplateResponse("airport.html", {"request": request})

# 데이터베이스 테이블 생성
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
    # 중복 체크
    if db.query(User).filter(User.name == username).first():
        return templates.TemplateResponse("join.html", {"request": request, "error": "이미 사용 중인 아이디입니다."})
    if db.query(User).filter(User.email == email).first():
        return templates.TemplateResponse("join.html", {"request": request, "error": "이미 사용 중인 이메일입니다."})
    if db.query(User).filter(User.phone == phone).first():
        return templates.TemplateResponse("join.html", {"request": request, "error": "이미 사용 중인 휴대폰 번호입니다."})
    if db.query(User).filter(User.nickname == nickname).first():
        return templates.TemplateResponse("join.html", {"request": request, "error": "이미 사용 중인 닉네임입니다."})
    if password != password_confirm:
        return templates.TemplateResponse("join.html", {"request": request, "error": "비밀번호가 일치하지 않습니다."})
    # 회원 생성
    user = User(name=username, password=password, nickname=nickname, email=email, phone=phone)
    db.add(user)
    db.commit()
    db.refresh(user)
    return RedirectResponse(url="/login", status_code=302)
    if password != password_confirm:
        return templates.TemplateResponse("join.html", {"request": request, "error": "비밀번호가 일치하지 않습니다."})
    user = User(name=username, email=email, phone=phone, password=password, nickname=nickname)
    db.add(user)
    db.commit()
    db.refresh(user)
    # 회원가입 성공 시 로그인 화면으로 리다이렉트 (POST-Redirect-GET)
    return RedirectResponse(url="/signin", status_code=303)
