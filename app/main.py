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

# 이메일 회원가입(또는 로그인) 페이지 렌더링
@app.get("/signin", response_class=HTMLResponse)
def signin(request: Request):
    return templates.TemplateResponse("signin.html", {"request": request})

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
    return templates.TemplateResponse("home.html", {"request": request})

@app.get("/users")
def read_users(db: Session = Depends(get_db)):
    return db.query(User).all()

@app.post("/users")
def create_user(name: str, email: str, db: Session = Depends(get_db)):
    user = User(name=name, email=email)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user
