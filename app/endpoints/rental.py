import datetime
import os

from fastapi import APIRouter, Query, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from app.api.booking_api import search_car_rentals
from app.api.sky_cars_api import parse_sky_car_search_results, search_sky_car_rentals
from app.api.rental_helper import (
    calc_rental_days,
    parse_rental_search_results,
    search_rental_locations,
)
from app.db.db import SessionLocal
from app.db.models import User
from app.session import get_user_id_from_session


router = APIRouter()

_APP_DIR = os.path.dirname(os.path.dirname(__file__))
templates = Jinja2Templates(directory=os.path.join(_APP_DIR, "templates"))

_RENTAL_COUNTRY_OPTIONS = [
    {"code": "JP", "name": "일본", "currency": "JPY"},
    {"code": "KR", "name": "대한민국", "currency": "KRW"},
    {"code": "US", "name": "미국", "currency": "USD"},
    {"code": "FR", "name": "프랑스", "currency": "EUR"},
    {"code": "AE", "name": "아랍에미리트", "currency": "AED"},
    {"code": "TH", "name": "태국", "currency": "THB"},
    {"code": "VN", "name": "베트남", "currency": "VND"},
    {"code": "SG", "name": "싱가포르", "currency": "SGD"},
    {"code": "TW", "name": "대만", "currency": "TWD"},
]


def _normalize_rental_country(country_code: str | None) -> str:
    code = (country_code or "JP").strip().upper()
    valid = {x["code"] for x in _RENTAL_COUNTRY_OPTIONS}
    return code if code in valid else "JP"


def _currency_for_country(country_code: str) -> str:
    for row in _RENTAL_COUNTRY_OPTIONS:
        if row["code"] == country_code:
            return row["currency"]
    return "JPY"


def _sky_locale_for_country(country_code: str) -> str:
    mapping = {
        "KR": "ko-KR",
        "JP": "ja-JP",
        "US": "en-US",
        "FR": "fr-FR",
        "AE": "en-US",
        "TH": "en-US",
        "VN": "en-US",
        "SG": "en-US",
        "TW": "zh-TW",
    }
    return mapping.get(country_code, "en-US")


def _get_nickname_from_request(request: Request) -> str | None:
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


def _parse_float_param(value: str | None) -> float | None:
    try:
        if value is None or str(value).strip() == "":
            return None
        return float(str(value).strip())
    except Exception:
        return None


def _parse_int_param(value: str | int | None) -> int | None:
    try:
        if value is None:
            return None
        s = str(value).strip()
        if not s:
            return None
        return int(s)
    except Exception:
        return None


def _extract_rental_api_error(raw: dict | None) -> str | None:
    if not isinstance(raw, dict):
        return None
    if raw.get("error"):
        return str(raw.get("error"))
    if isinstance(raw.get("errors"), dict) and raw.get("errors"):
        return f"렌터카 API 요청 파라미터 오류일 수 있습니다. (공급사 응답: {list(raw.get('errors', {}).items())})"

    message = str(raw.get("message") or "").strip()
    status = str(raw.get("status") or "").strip()
    joined = f"{status} {message}".strip().lower()

    if "something went wrong" in joined:
        return "렌터카 API 서비스 일시 오류입니다. 잠시 후 다시 시도해 주세요."
    if any(k in joined for k in ("invalid", "required", "parameter", "validation")):
        detail = message or status
        if detail:
            return f"렌터카 API 요청 파라미터 오류일 수 있습니다. (공급사 응답: {detail})"
        return "렌터카 API 요청 파라미터 오류일 수 있습니다. 잠시 후 다시 시도해 주세요."
    if any(k in joined for k in ("rate limit", "too many requests")):
        return "렌터카 API 호출이 많아 잠시 제한되었습니다. 잠시 후 다시 시도해 주세요."
    return None


@router.get("/api/rental/location-search")
def rental_location_search_api(
    q: str = Query(""),
    category: str = Query("all"),
    country_code: str = Query("JP"),
):
    items = search_rental_locations(
        q,
        category=category,
        limit=12,
        country_code=_normalize_rental_country(country_code),
    )
    return {"items": items}


@router.get("/rental", response_class=HTMLResponse)
def rental_page(
    request: Request,
    pickup_name: str | None = Query(None),
    pickup_lat: str | None = Query(None),
    pickup_lon: str | None = Query(None),
    dropoff_name: str | None = Query(None),
    dropoff_lat: str | None = Query(None),
    dropoff_lon: str | None = Query(None),
    pickup_at: str | None = Query(None),
    dropoff_at: str | None = Query(None),
    country_code: str | None = Query("JP"),
    city_hint: str | None = Query(None),
    sort: str | None = Query("price_asc"),
    min_seats: str | None = Query(None),
    transmission: str | None = Query(None),
):
    nickname = _get_nickname_from_request(request)
    country_code = _normalize_rental_country(country_code)
    currency_code = _currency_for_country(country_code)
    min_seats_value = _parse_int_param(min_seats)
    rental_cars = []
    rental_error = None
    rental_provider = None
    rental_provider_detail = None
    rental_days = calc_rental_days(pickup_at, dropoff_at)

    p_lat = _parse_float_param(pickup_lat)
    p_lon = _parse_float_param(pickup_lon)
    d_lat = _parse_float_param(dropoff_lat) if dropoff_lat else p_lat
    d_lon = _parse_float_param(dropoff_lon) if dropoff_lon else p_lon

    if not pickup_at:
        now = datetime.datetime.now().replace(minute=0, second=0, microsecond=0)
        pickup_at = now.strftime("%Y-%m-%d %H:%M")
    if not dropoff_at:
        try:
            dt = datetime.datetime.strptime(pickup_at, "%Y-%m-%d %H:%M") + datetime.timedelta(days=3)
            dropoff_at = dt.strftime("%Y-%m-%d %H:%M")
        except Exception:
            dropoff_at = pickup_at

    if p_lat is not None and p_lon is not None and d_lat is not None and d_lon is not None and pickup_at and dropoff_at:
        try:
            pickup_api_time = pickup_at.replace(" ", "T") + ":00"
            dropoff_api_time = dropoff_at.replace(" ", "T") + ":00"
            rental_raw = None
            sky_raw = search_sky_car_rentals(
                pickup_name=pickup_name or city_hint or "",
                pickup_lat=p_lat,
                pickup_lon=p_lon,
                dropoff_name=dropoff_name or pickup_name or city_hint or "",
                dropoff_lat=d_lat,
                dropoff_lon=d_lon,
                pickup_at=pickup_api_time,
                dropoff_at=dropoff_api_time,
                market=country_code,
                currency=currency_code,
                locale=_sky_locale_for_country(country_code),
                driver_age=30,
            )
            sky_cars = parse_sky_car_search_results(sky_raw)
            if sky_cars:
                rental_raw = sky_raw
                rental_cars = sky_cars
                rental_provider = "Sky Cars"
                rental_provider_detail = "Sky cars/search"
            else:
                sky_msg = None
                if isinstance(sky_raw, dict):
                    sky_msg = str(sky_raw.get("message") or sky_raw.get("errors") or "").strip()
                rental_raw = search_car_rentals(
                    pick_up_lat=p_lat,
                    pick_up_lon=p_lon,
                    drop_off_lat=d_lat,
                    drop_off_lon=d_lon,
                    pick_up_time=pickup_api_time,
                    drop_off_time=dropoff_api_time,
                    driver_age=30,
                    currency_code=currency_code,
                    location=country_code,
                )
                rental_cars = parse_rental_search_results(rental_raw)
                rental_provider = "Booking Fallback"
                rental_provider_detail = f"Sky empty/fail -> Booking ({sky_msg or 'no sky detail'})"
            for car in rental_cars:
                if not isinstance(car, dict):
                    continue
                car["rental_days"] = rental_days
                if rental_days and car.get("price"):
                    try:
                        car["price_per_day"] = int(round(float(car["price"]) / rental_days))
                    except Exception:
                        car["price_per_day"] = None

            if min_seats_value:
                rental_cars = [c for c in rental_cars if not c.get("seats") or c.get("seats") >= min_seats_value]
            if transmission and transmission not in {"", "all"}:
                tneedle = str(transmission).lower()
                rental_cars = [c for c in rental_cars if tneedle in str(c.get("transmission") or "").lower()]

            sort = (sort or "price_asc").strip()
            if sort == "price_desc":
                rental_cars.sort(key=lambda x: x.get("price") or -1, reverse=True)
            elif sort == "name":
                rental_cars.sort(key=lambda x: str(x.get("name") or ""))
            elif sort == "rating":
                rental_cars.sort(key=lambda x: x.get("rating") or 0, reverse=True)
            else:
                rental_cars.sort(key=lambda x: x.get("price") or 10**12)

            api_error = _extract_rental_api_error(rental_raw) if isinstance(rental_raw, dict) else None
            if api_error:
                rental_error = api_error
            elif not rental_cars:
                rental_error = "렌터카 검색 결과를 찾지 못했습니다. 다른 지역/시간으로 다시 시도해 주세요."
        except Exception as e:
            rental_error = f"렌터카 검색 실패: {e}"

    return templates.TemplateResponse(
        "rental.html",
        {
            "request": request,
            "nickname": nickname,
            "rental_cars": rental_cars,
            "rental_error": rental_error,
            "pickup_name": pickup_name or "",
            "dropoff_name": dropoff_name or (pickup_name or ""),
            "pickup_lat": pickup_lat or "",
            "pickup_lon": pickup_lon or "",
            "dropoff_lat": dropoff_lat or (pickup_lat or ""),
            "dropoff_lon": dropoff_lon or (pickup_lon or ""),
            "pickup_at": pickup_at or "",
            "dropoff_at": dropoff_at or "",
            "country_code": country_code,
            "city_hint": city_hint or "",
            "rental_country_options": _RENTAL_COUNTRY_OPTIONS,
            "rental_days": rental_days,
            "sort": sort or "price_asc",
            "min_seats": min_seats_value,
            "transmission": transmission or "all",
            "rental_provider": rental_provider or "",
            "rental_provider_detail": rental_provider_detail or "",
        },
    )
