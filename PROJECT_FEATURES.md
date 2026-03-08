# DESTINO 프로젝트 기능 문서 ✈️

## 1. 프로젝트 개요 🧭

DESTINO는 여행 상품 탐색, 장바구니/위시리스트 저장, 공동구매, 결제, AI 챗봇 기능을 통합한 여행 웹 서비스입니다.

---

## 2. 기술 스택 🛠️

| 구분                 | 스택                                          |
| -------------------- | --------------------------------------------- |
| Backend              | FastAPI, Python                               |
| Template             | Jinja2                                        |
| ORM/DB               | SQLAlchemy, SQLite(`app.db`)                  |
| Frontend             | HTML, CSS, JavaScript(페이지별 정적 스크립트) |
| Auth                 | 쿠키 기반 세션(`session_token`)               |
| Payment              | Toss Payments API                             |
| AI                   | OpenAI API, RAG 파이프라인                    |
| External Travel APIs | Amadeus, Booking, Google Places, Geoapify     |

---

## 3. 핵심 기능 🌟

- 계정: 회원가입, 로그인/로그아웃, 아이디/비밀번호 찾기
- 마이페이지: 프로필 수정, 예약내역, 위시리스트/장바구니, 공동구매 알림/내 게시물
- 상품 도메인:
  - 항공(검색/상세/결제)
  - 숙소(검색/상세/결제)
  - 렌터카(검색/상세/결제)
  - 패키지(목록/상세/결제)
  - 티켓/투어(목록/상세/결제)
- 저장 기능: 페이지별 Drawer + 통합 저장 API(`/api/saved-items`)
- 공동구매: 모집글 작성/삭제, 참여요청, 수락/거절, 알림함
- AI 챗봇:
  - 채팅 응답(`POST /chat`)
  - 상품 추천 결과 저장 연동
  - 로그인 및 이용권 기반 접근 제어
- 챗봇 이용권:
  - 구매/결제/상태 조회
  - 마이페이지 이용권 탭에서 목록 확인
  - 만료/소진권 삭제

---

## 4. API 엔드포인트(표) 🔌

## 4.1 사용자/인증/프로필 👤

| Method | Path                   | 설명                     | 인증 |
| ------ | ---------------------- | ------------------------ | ---- |
| POST   | `/api/verify-password` | 비밀번호 검증            | 필요 |
| POST   | `/api/update-profile`  | 프로필 수정              | 필요 |
| GET    | `/api/me`              | 내 정보/로그인 상태 조회 | 선택 |
| GET    | `/logout`              | 로그아웃                 | 선택 |

## 4.2 저장/예약 공통 🧺

| Method | Path                         | 설명                                | 인증 |
| ------ | ---------------------------- | ----------------------------------- | ---- |
| GET    | `/api/saved-items`           | 저장 항목 조회(장바구니/위시리스트) | 필요 |
| POST   | `/api/saved-items`           | 저장 항목 추가/토글                 | 필요 |
| DELETE | `/api/saved-items/{item_id}` | 저장 항목 삭제                      | 필요 |
| GET    | `/api/bookings`              | 전체 예약 내역 조회                 | 필요 |

## 4.3 챗봇 이용권 🎫

| Method | Path                                   | 설명                  | 인증 |
| ------ | -------------------------------------- | --------------------- | ---- |
| GET    | `/api/chat-pass/status`                | 이용권 상태/상품 조회 | 필요 |
| GET    | `/api/chat-passes`                     | 내 이용권 목록 조회   | 필요 |
| DELETE | `/api/chat-passes/{pass_id}`           | 만료/소진 이용권 삭제 | 필요 |
| POST   | `/api/chat-pass/checkout`              | 이용권 결제 준비      | 필요 |
| POST   | `/api/payments/toss/chat-pass/confirm` | 이용권 결제 승인      | 필요 |

## 4.4 항공 🛫

| Method | Path                         | 설명                | 인증 |
| ------ | ---------------------------- | ------------------- | ---- |
| GET    | `/api/flight-search`         | 항공 검색           | 선택 |
| POST   | `/api/flight/checkout`       | 항공 결제 준비      | 필요 |
| POST   | `/api/payments/toss/confirm` | 항공 결제 승인      | 필요 |
| GET    | `/api/flight/bookings`       | 항공 예약 내역 조회 | 필요 |

## 4.5 숙소 🏨

| Method | Path                               | 설명           | 인증 |
| ------ | ---------------------------------- | -------------- | ---- |
| POST   | `/api/hotel/checkout`              | 숙소 결제 준비 | 필요 |
| POST   | `/api/payments/toss/hotel/confirm` | 숙소 결제 승인 | 필요 |

## 4.6 렌터카 🚗

| Method | Path                                | 설명             | 인증 |
| ------ | ----------------------------------- | ---------------- | ---- |
| GET    | `/api/rental/location-search`       | 렌터카 위치 검색 | 선택 |
| POST   | `/api/rental/checkout`              | 렌터카 결제 준비 | 필요 |
| POST   | `/api/payments/toss/rental/confirm` | 렌터카 결제 승인 | 필요 |

## 4.7 패키지/티켓 🎟️

| Method | Path                              | 설명             | 인증 |
| ------ | --------------------------------- | ---------------- | ---- |
| POST   | `/api/pack/checkout`              | 패키지 결제 준비 | 필요 |
| POST   | `/api/payments/toss/pack/confirm` | 패키지 결제 승인 | 필요 |
| POST   | `/api/tour/checkout`              | 티켓 결제 준비   | 필요 |
| POST   | `/api/payments/toss/tour/confirm` | 티켓 결제 승인   | 필요 |

## 4.8 공동구매 🤝

| Method | Path                                                 | 설명                  | 인증 |
| ------ | ---------------------------------------------------- | --------------------- | ---- |
| GET    | `/api/group-buy/posts`                               | 모집글 목록 조회      | 선택 |
| POST   | `/api/group-buy/posts`                               | 모집글 작성           | 필요 |
| GET    | `/api/group-buy/my-posts`                            | 내 모집글 조회        | 필요 |
| DELETE | `/api/group-buy/posts/{post_id}`                     | 모집글 삭제           | 필요 |
| POST   | `/api/group-buy/posts/{post_id}/join-requests`       | 참여 요청             | 필요 |
| GET    | `/api/group-buy/join-requests/inbox`                 | 참여 요청 알림함 조회 | 필요 |
| POST   | `/api/group-buy/join-requests/{request_id}/decision` | 요청 수락/거절        | 필요 |
| DELETE | `/api/group-buy/join-requests/{request_id}`          | 알림 삭제             | 필요 |

## 4.9 AI/RAG/추천 🤖

| Method | Path                            | 설명             | 인증              |
| ------ | ------------------------------- | ---------------- | ----------------- |
| POST   | `/chat`                         | AI 채팅          | 필요(이용권 필요) |
| GET    | `/attractions`                  | 관광지 조회      | 선택              |
| POST   | `/recommend`                    | 추천 생성        | 선택              |
| GET    | `/v1/hotels/search-destination` | 호텔 목적지 검색 | 선택              |
| GET    | `/v1/hotels/recommend`          | 호텔 추천        | 선택              |
| POST   | `/rag/search`                   | RAG 검색         | 선택              |
| POST   | `/rag/answer`                   | RAG 답변 생성    | 선택              |
| POST   | `/rag/ask`                      | RAG 질의         | 선택              |
| GET    | `/rag/health`                   | RAG 헬스체크     | 선택              |

---

## 5. 화면 라우트(주요) 🖥️

| Path                   | 설명             |
| ---------------------- | ---------------- |
| `/`, `/home`           | 메인             |
| `/airport`             | 항공 검색        |
| `/flight-detail`       | 항공 상세        |
| `/gloval-hotel`        | 숙소 검색        |
| `/gloval-hotel/detail` | 숙소 상세        |
| `/rental`              | 렌터카 검색      |
| `/rental/detail`       | 렌터카 상세      |
| `/package`             | 패키지 목록      |
| `/pack-detail`         | 패키지 상세      |
| `/tour`                | 티켓 목록        |
| `/tour-detail`         | 티켓 상세        |
| `/travelGroup`         | 공동구매         |
| `/planner`             | AI 챗봇          |
| `/mypage`              | 마이페이지       |
| `/chat-pass/purchase`  | 챗봇 이용권 구매 |

---

## 6. 데이터 모델(핵심) 🗃️

| 모델                  | 설명                          |
| --------------------- | ----------------------------- |
| `User`                | 사용자 계정                   |
| `UserSession`         | 로그인 세션                   |
| `UserSavedItem`       | 장바구니/위시리스트 저장 항목 |
| `GroupBuyPost`        | 공동구매 모집글               |
| `GroupBuyJoinRequest` | 공동구매 참여 요청            |
| `UserBooking`         | 결제/예약 이력                |
| `UserChatPass`        | 챗봇 이용권                   |

---

## 7. 프로젝트 구조(Tree) 🌳

```text
DESTINO/
├─ app/
│  ├─ api/
│  │  ├─ amadeus_api.py
│  │  ├─ booking_api.py
│  │  ├─ booking_hotel_flight_api.py
│  │  ├─ exchange_rate.py
│  │  ├─ geoapify.py
│  │  ├─ google_places.py
│  │  ├─ rental_helper.py
│  │  └─ sky_cars_api.py
│  ├─ db/
│  │  ├─ db.py
│  │  ├─ models.py
│  │  └─ chat_history.py
│  ├─ endpoints/
│  │  ├─ flight_chat.py
│  │  ├─ group_buy.py
│  │  ├─ rag_api.py
│  │  ├─ rental.py
│  │  ├─ routes.py
│  │  └─ saved_items.py
│  ├─ rag/
│  │  ├─ build_index_google_places.py
│  │  ├─ intent.py
│  │  ├─ search_and_respond.py
│  │  ├─ schema.json
│  │  └─ scripts/
│  ├─ services/
│  │  ├─ booking_history_service.py
│  │  ├─ chat_heuristics_service.py
│  │  ├─ chat_orchestrator_service.py
│  │  ├─ chat_parsing_service.py
│  │  ├─ chat_pass_service.py
│  │  ├─ chat_renderers.py
│  │  ├─ date_parsing_service.py
│  │  ├─ flight_search_service.py
│  │  ├─ hotel_service.py
│  │  ├─ intent_router_service.py
│  │  ├─ knowledge_helpers_service.py
│  │  ├─ knowledge_service.py
│  │  ├─ location_alias_service.py
│  │  ├─ place_followup_service.py
│  │  ├─ place_search_service.py
│  │  ├─ product_reco_service.py
│  │  └─ rentalcar_service.py
│  ├─ static/
│  │  ├─ *.css, *.js (페이지별 스크립트/스타일)
│  │  └─ image/
│  ├─ templates/
│  │  ├─ home.html
│  │  ├─ login.html / signin.html / join.html
│  │  ├─ mypage.html
│  │  ├─ planner.html
│  │  ├─ airport.html / flight-detail.html
│  │  ├─ gloval-hotel.html / gloval-hotel-detail.html
│  │  ├─ rental.html / rental-detail.html
│  │  ├─ package.html / pack-detail.html
│  │  ├─ tour.html / tour-detail.html
│  │  ├─ travel-group.html
│  │  └─ chat-pass-purchase.html
│  ├─ main.py
│  └─ session.py
├─ requirements.txt
├─ README.md
├─ PROJECT_FEATURES.md
└─ app.db
```

---

## 8. 기능별 사용 기술 요약 📌

| 기능                 | 사용 기술                                                         | 요약                                                                              |
| -------------------- | ----------------------------------------------------------------- | --------------------------------------------------------------------------------- |
| 로그인/세션 인증     | FastAPI, SQLAlchemy(`UserSession`), 쿠키(`session_token`)         | 로그인 시 세션 토큰을 DB에 저장하고, 요청마다 토큰으로 사용자 인증을 수행합니다.  |
| 회원정보 수정        | FastAPI API, SQLAlchemy(`User`), 프런트 Fetch                     | 마이페이지에서 비밀번호 재확인 후 사용자 프로필을 서버 API로 안전하게 갱신합니다. |
| 페이지 렌더링        | Jinja2 템플릿                                                     | 서버에서 닉네임/로그인 상태 등을 주입해 페이지를 SSR 방식으로 렌더링합니다.       |
| 장바구니/위시리스트  | FastAPI REST, SQLAlchemy(`UserSavedItem`), 페이지별 JS Drawer     | 공통 저장 API를 통해 도메인별 상품을 동일 포맷으로 저장/조회/삭제합니다.          |
| 공동구매             | FastAPI Router, SQLAlchemy(`GroupBuyPost`, `GroupBuyJoinRequest`) | 모집글/참여요청/의사결정(수락·거절) 흐름을 엔드포인트로 분리해 관리합니다.        |
| 항공 검색/상세       | Amadeus API, 서비스 레이어(`flight_search_service`)               | 외부 항공 데이터를 내부 포맷으로 정규화해 검색 결과/상세 화면에 사용합니다.       |
| 숙소 검색/상세       | Booking API, Google Places, Geoapify                              | 숙소 목록과 상세 보강 정보(주소/리뷰/위치)를 결합해 제공합니다.                   |
| 렌터카 검색/결제     | Sky Cars API, FastAPI endpoint(`rental.py`)                       | 위치/일정 기반 렌터카 검색과 결제 연동을 별도 도메인 라우터로 처리합니다.         |
| 패키지/티켓 상품     | 템플릿 + 정적 JS + 결제 API                                       | 카드형 UI에서 선택/저장/결제까지 일관된 UX로 제공합니다.                          |
| 결제 처리            | Toss Payments API, 서버 승인 API, 예약 저장(`UserBooking`)        | 클라이언트 결제 요청 후 서버에서 승인 검증하고 주문 이력을 DB에 확정 저장합니다.  |
| AI 챗봇              | OpenAI API, 오케스트레이션 서비스, FastAPI `/chat`                | 의도 분류/응답 생성/상품 추천을 통합 처리하고, 결과를 UI 카드로 렌더링합니다.     |
| RAG 지식응답         | Pinecone(선택), 임베딩/검색 파이프라인(`app/rag`)                 | 여행 지식 데이터를 인덱싱해 질의 시 검색+답변 결합 방식으로 응답합니다.           |
| 챗봇 이용권          | SQLAlchemy(`UserChatPass`), 결제 API, `/chat` 게이트              | 이용권 상태/만료/횟수 차감을 서버에서 강제해 챗봇 사용 권한을 제어합니다.         |
| 마이페이지 통합 관리 | `mypage.js`, `/api/me`, `/api/bookings`, `/api/chat-passes`       | 예약/저장/알림/이용권 데이터를 한 화면에서 조회·관리하도록 구성했습니다.          |
