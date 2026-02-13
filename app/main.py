from fastapi import Query
from app.session import get_user_id_from_session, create_session, delete_session
from app.db.db import Base, engine, SessionLocal
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
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

app.mount("/static", StaticFiles(directory="app/static"), name="static")


app.include_router(main_router)
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
    user = User(name=username, email=email, phone=phone, password=password, nickname=nickname)
    db.add(user)
    db.commit()
    db.refresh(user)
    # 회원가입 성공 시 로그인 화면으로 리다이렉트 (POST-Redirect-GET)
    return RedirectResponse(url="/signin", status_code=303)
