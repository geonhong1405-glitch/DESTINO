import datetime
import os
import hashlib
import json
import uuid
import base64
import copy
import time
import requests
from concurrent.futures import ThreadPoolExecutor

from fastapi import APIRouter, Query, Request, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from app.api.booking_api import search_car_rentals
from app.api.exchange_rate import get_exchange_rate
from app.api.sky_cars_api import parse_sky_car_search_results, search_sky_car_rentals
from app.api.rental_helper import (
    calc_rental_days,
    parse_rental_search_results,
    search_rental_locations,
)
from app.db.db import SessionLocal
from app.db.models import User
from app.session import get_user_id_from_session
from app.services.booking_history_service import save_booking


router = APIRouter()
PENDING_RENTAL_ORDERS: dict[str, dict] = {}
_RENTAL_RESULT_CACHE: dict[str, dict] = {}
_RENTAL_RESULT_CACHE_TTL_SECONDS = 240

_APP_DIR = os.path.dirname(os.path.dirname(__file__))
templates = Jinja2Templates(directory=os.path.join(_APP_DIR, "templates"))

_RENTAL_COUNTRY_OPTIONS = [
    {"code": "JP", "name": "일본", "currency": "JPY"},
    {"code": "KR", "name": "대한민국", "currency": "KRW"},
    {"code": "US", "name": "미국", "currency": "USD"},
    {"code": "CN", "name": "중국", "currency": "CNY"},
    {"code": "HK", "name": "홍콩", "currency": "HKD"},
    {"code": "MO", "name": "마카오", "currency": "MOP"},
    {"code": "FR", "name": "프랑스", "currency": "EUR"},
    {"code": "AE", "name": "아랍에미리트", "currency": "AED"},
    {"code": "TH", "name": "태국", "currency": "THB"},
    {"code": "VN", "name": "베트남", "currency": "VND"},
    {"code": "SG", "name": "싱가포르", "currency": "SGD"},
    {"code": "TW", "name": "대만", "currency": "TWD"},
]

# Fallback FX table used when live exchange API is unavailable.
# Values are approximate KRW per 1 unit of foreign currency.
_DEFAULT_FX_TO_KRW = {
    "KRW": 1.0,
    "USD": 1350.0,
    "EUR": 1470.0,
    "JPY": 9.0,
    "CNY": 187.0,
    "HKD": 173.0,
    "MOP": 168.0,
    "AED": 368.0,
    "THB": 38.0,
    "VND": 0.053,
    "SGD": 1000.0,
    "TWD": 43.0,
}


class RentalDriverInput(BaseModel):
    last_name: str
    first_name: str
    birth_date: str
    email: str
    phone: str
    license_country: str
    license_number: str


class RentalCheckoutRequest(BaseModel):
    car: dict
    driver: RentalDriverInput


def _normalize_rental_country(country_code: str | None) -> str:
    code = (country_code or "").strip().upper()
    valid = {x["code"] for x in _RENTAL_COUNTRY_OPTIONS}
    if code in valid:
        return code
    if len(code) == 2 and code.isalpha():
        # Allow global 2-letter country codes even when not explicitly listed in UI options.
        return code
    return "JP"


def _currency_for_country(country_code: str) -> str:
    for row in _RENTAL_COUNTRY_OPTIONS:
        if row["code"] == country_code:
            return row["currency"]
    return "USD"


def _sky_locale_for_country(country_code: str) -> str:
    mapping = {
        "KR": "ko-KR",
        "JP": "ja-JP",
        "US": "en-US",
        "CN": "zh-CN",
        "HK": "zh-HK",
        "MO": "zh-HK",
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


def _require_user_id(request: Request) -> int:
    session_token = request.cookies.get("session_token")
    user_id = get_user_id_from_session(session_token) if session_token else None
    if not user_id:
        raise HTTPException(status_code=401, detail="LOGIN_REQUIRED")
    return int(user_id)


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



def _extract_rental_amount_krw(car: dict) -> int:
    try:
        amount = int(round(float(car.get("price"))))
    except Exception:
        amount = 0
    if amount <= 0:
        raise HTTPException(status_code=400, detail="결제 가능한 금액을 확인할 수 없습니다.")
    return amount


def _build_rental_order_name(car: dict) -> str:
    name = str(car.get("name") or "렌터카").strip() or "렌터카"
    pickup = str(car.get("pickup_name") or "").strip()
    dropoff = str(car.get("dropoff_name") or "").strip()
    if pickup and dropoff:
        return f"{name} {pickup}-{dropoff}"
    return name


def _extract_rental_api_error(raw: dict | None) -> str | None:
    if not isinstance(raw, dict):
        return None
    if raw.get("error"):
        return str(raw.get("error"))
    if isinstance(raw.get("errors"), dict) and raw.get("errors"):
        return f"렌터카 API 요청 파라미터가 올바르지 않습니다. (오류 상세: {list(raw.get('errors', {}).items())})"

    message = str(raw.get("message") or "").strip()
    status = str(raw.get("status") or "").strip()
    joined = f"{status} {message}".strip().lower()

    if "something went wrong" in joined:
        return "렌터카 API 서비스 일시 오류입니다. 잠시 후 다시 시도해 주세요."
    if any(k in joined for k in ("invalid", "required", "parameter", "validation")):
        detail = message or status
        if detail:
            return f"렌터카 API 요청 파라미터가 올바르지 않습니다. (오류 상세: {detail})"
        return "렌터카 API 요청 파라미터가 올바르지 않습니다. 잠시 후 다시 시도해 주세요."
    if any(k in joined for k in ("rate limit", "too many requests")):
        return "렌터카 API 요청 한도를 초과했습니다. 잠시 후 다시 시도해 주세요."
    return None

def _clean_provider_detail(detail: str | None) -> str:
    text = str(detail or "").strip()
    if not text:
        return ""
    lowered = text.lower()
    if lowered in {"successful", "success", "ok"}:
        return ""
    text = text.replace("(Successful)", "").replace("(success)", "").strip()
    text = text.replace("(no sky detail)", "").strip()
    text = text.replace("  ", " ").strip()
    if text.endswith("()"):
        text = text[:-2].strip()
    return text


def _public_provider_detail(provider: str | None, detail: str | None) -> str:
    p = str(provider or "").strip().lower()
    d = str(detail or "").strip().lower()
    if not p:
        return ""
    # Never expose raw upstream exception/timeouts to end users.
    if "exceeded the monthly quota" in d or "rate limit" in d or "too many requests" in d:
        return "실시간 렌터카 API 월간 요청 한도를 초과했습니다."
    if "timeout" in d or "httpsconnectionpool" in d or "exception" in d or "traceback" in d:
        d = ""
    if "estimated" in d:
        return "일부 요금은 공급사 응답 지연으로 추정치가 적용되었습니다."
    if p == "local fallback":
        return "실시간 공급사 응답 지연으로 대체 요금을 표시 중입니다."
    if p == "booking fallback":
        return "일부 공급사 응답 지연으로 대체 공급사 결과를 표시 중입니다."
    if p == "provider fallback":
        return "공급사 응답이 일시적으로 불안정해 대체 결과를 표시 중입니다."
    return ""


def _build_public_rental_failure_message(reasons: list[str]) -> str:
    joined = " | ".join(str(x or "") for x in (reasons or []))
    j = joined.lower()
    msgs: list[str] = []
    if "exceeded the monthly quota" in j:
        msgs.append("RapidAPI 월간 요청 한도를 초과했습니다.")
    if "something went wrong" in j:
        msgs.append("Booking 공급사에서 현재 차량 데이터를 반환하지 못하고 있습니다.")
    if "timed out" in j or "httpsconnectionpool" in j:
        msgs.append("Sky Cars 응답 시간이 초과되었습니다.")
    if not msgs:
        return "실시간 렌터카 API 결과를 가져오지 못했습니다. 잠시 후 다시 시도해 주세요."
    return " / ".join(msgs)


def _to_krw_price(value, currency, rate_cache: dict[str, float | None]) -> int | None:
    try:
        if value is None:
            return None
        amount = float(value)
    except Exception:
        return None

    ccy = str(currency or "KRW").strip().upper()
    if not ccy or ccy == "KRW":
        return int(round(amount))

    if ccy not in rate_cache:
        try:
            live_rate = get_exchange_rate(base=ccy, target="KRW")
            rate_cache[ccy] = live_rate if live_rate else _DEFAULT_FX_TO_KRW.get(ccy)
        except Exception:
            rate_cache[ccy] = _DEFAULT_FX_TO_KRW.get(ccy)

    rate = rate_cache.get(ccy)
    if rate is None:
        return None
    try:
        return int(round(amount * float(rate)))
    except Exception:
        return None


_RENTAL_FALLBACK_IMAGES = [
    "https://images.unsplash.com/photo-1493238792000-8113da705763?q=80&w=1200&auto=format&fit=crop",
    "https://images.unsplash.com/photo-1502877338535-766e1452684a?q=80&w=1200&auto=format&fit=crop",
    "https://images.unsplash.com/photo-1553440569-bcc63803a83d?q=80&w=1200&auto=format&fit=crop",
    "https://images.unsplash.com/photo-1544636331-e26879cd4d9b?q=80&w=1200&auto=format&fit=crop",
    "https://images.unsplash.com/photo-1504215680853-026ed2a45def?q=80&w=1200&auto=format&fit=crop",
]


def _build_local_fallback_rental_cars(country_code: str, rental_days: int | None) -> list[dict]:
    # Emergency fallback to keep UI usable when providers are unavailable.
    base_daily_krw_by_country = {
        "US": 78000,
        "JP": 62000,
        "FR": 83000,
        "TH": 42000,
        "VN": 39000,
        "SG": 76000,
        "TW": 51000,
        "AE": 95000,
        "KR": 69000,
    }
    models = [
        ("Toyota Yaris", 5, "automatic"),
        ("Nissan Versa", 5, "automatic"),
        ("Hyundai Elantra", 5, "automatic"),
        ("Kia K5", 5, "automatic"),
        ("Volkswagen Polo", 5, "manual"),
        ("Toyota Corolla", 5, "automatic"),
    ]
    suppliers = [
        "LocalRent",
        "CityCar",
        "AutoPartner",
        "DriveHub",
    ]
    days = max(1, int(rental_days or 1))
    base_daily = base_daily_krw_by_country.get(country_code, 70000)

    cars: list[dict] = []
    for idx, (name, seats, trans) in enumerate(models):
        price_per_day = int(round(base_daily * (0.92 + (idx * 0.06))))
        total_price = int(price_per_day * days)
        supplier = suppliers[idx % len(suppliers)]
        cars.append(
            {
                "name": name,
                "supplier": supplier,
                "price": total_price,
                "currency": "KRW",
                "image": _fallback_image_for_car(name, supplier),
                "specs": [f"{seats}인승", "가방 2", trans],
                "seats": seats,
                "transmission": trans,
                "fuel_policy": None,
                "rating": round(3.8 + (idx % 4) * 0.3, 1),
                "rental_days": days,
                "price_per_day": price_per_day,
                "fx_applied": False,
                "original_currency": "KRW",
                "original_price": total_price,
                "price_unreliable": False,
            }
        )
    return cars


def _apply_estimated_prices_to_cars(cars: list[dict], country_code: str, rental_days: int | None) -> int:
    if not cars:
        return 0
    days = max(1, int(rental_days or 1))
    base_daily_krw_by_country = {
        "US": 78000,
        "JP": 62000,
        "FR": 83000,
        "TH": 42000,
        "VN": 39000,
        "SG": 76000,
        "TW": 51000,
        "AE": 95000,
        "KR": 69000,
    }
    base_daily = int(base_daily_krw_by_country.get(country_code, 70000))
    updated = 0
    for idx, car in enumerate(cars):
        if not isinstance(car, dict):
            continue
        if car.get("price") is not None and not car.get("price_unreliable"):
            continue
        per_day = int(round(base_daily * (0.92 + (idx % 6) * 0.06)))
        total = int(per_day * days)
        car["price"] = total
        car["currency"] = "KRW"
        car["price_per_day"] = per_day
        car["price_unreliable"] = False
        car["price_estimated"] = True
        car["rental_days"] = days
        updated += 1
    return updated


def _is_reasonable_total_price(price: int | float | None, currency: str | None, rental_days: int | None) -> bool:
    if price is None:
        return False
    try:
        amount = float(price)
    except Exception:
        return False

    ccy = str(currency or "KRW").strip().upper() or "KRW"
    days = max(1, int(rental_days or 1))

    # Very conservative lower bounds to block obvious parse noise (e.g. 2, 3, 4).
    min_per_day_by_ccy = {
        "KRW": 5000,
        "JPY": 500,
        "USD": 10,
        "EUR": 10,
        "AED": 30,
        "THB": 300,
        "VND": 100000,
        "SGD": 15,
        "TWD": 300,
    }
    min_total = float(min_per_day_by_ccy.get(ccy, 10)) * float(days)
    return amount >= min_total


def _fallback_image_for_car(name: str | None, supplier: str | None) -> str:
    seed = f"{name or ''}|{supplier or ''}".encode("utf-8")
    digest = hashlib.sha256(seed).hexdigest()
    idx = int(digest[:8], 16) % len(_RENTAL_FALLBACK_IMAGES)
    return _RENTAL_FALLBACK_IMAGES[idx]


def _looks_like_non_vehicle_image_url(url: str | None) -> bool:
    s = str(url or "").strip().lower()
    if not s:
        return False
    # Block explicit vendor/logo/icon assets only.
    if "/vendors/" in s or "/vendor/" in s:
        return True

    bad_tokens = (
        "icon/",
        "/icons/",
        "avatar",
        "bond-street",
        "roundel",
    )
    return any(token in s for token in bad_tokens)

def _is_generic_supplier_car_name(name: str | None, supplier: str | None) -> bool:
    n = str(name or "").strip().lower()
    s = str(supplier or "").strip().lower()
    if not n:
        return True
    if not s:
        # Names ending with generic "rental car" words are not real model names.
        return ("rental car" in n) or n.endswith("rental")
    normalized = n.replace(" ", "")
    supplier_norm = s.replace(" ", "")
    return normalized in {
        supplier_norm,
        f"{supplier_norm}rental",
        f"{supplier_norm}rentalcar",
    }


def _rental_search_cache_key(
    pickup_lat: float | None,
    pickup_lon: float | None,
    dropoff_lat: float | None,
    dropoff_lon: float | None,
    pickup_at: str | None,
    dropoff_at: str | None,
    country_code: str | None,
) -> str:
    payload = "|".join(
        [
            f"{(pickup_lat or 0.0):.4f}",
            f"{(pickup_lon or 0.0):.4f}",
            f"{(dropoff_lat or 0.0):.4f}",
            f"{(dropoff_lon or 0.0):.4f}",
            str(pickup_at or ""),
            str(dropoff_at or ""),
            str(country_code or ""),
        ]
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _get_cached_rental_results(cache_key: str) -> dict | None:
    row = _RENTAL_RESULT_CACHE.get(cache_key)
    if not isinstance(row, dict):
        return None
    ts = row.get("ts")
    if not isinstance(ts, (int, float)):
        _RENTAL_RESULT_CACHE.pop(cache_key, None)
        return None
    if time.time() - ts > _RENTAL_RESULT_CACHE_TTL_SECONDS:
        _RENTAL_RESULT_CACHE.pop(cache_key, None)
        return None
    cars = row.get("cars")
    if not isinstance(cars, list) or not cars:
        return None
    return {
        "provider": str(row.get("provider") or "Cached Fallback"),
        "provider_detail": str(row.get("provider_detail") or "최근 검색 캐시 결과"),
        "cars": copy.deepcopy(cars),
    }


def _set_cached_rental_results(cache_key: str, cars: list[dict], provider: str | None, provider_detail: str | None) -> None:
    if not cache_key or not isinstance(cars, list) or not cars:
        return
    _RENTAL_RESULT_CACHE[cache_key] = {
        "ts": time.time(),
        "provider": str(provider or ""),
        "provider_detail": str(provider_detail or ""),
        "cars": copy.deepcopy(cars),
    }





@router.get("/api/rental/location-search")
def rental_location_search_api(
    q: str = Query(""),
    category: str = Query("all"),
    country_code: str | None = Query(None),
):
    raw_cc = (country_code or "").strip().upper()
    normalized_cc = None if (not raw_cc or raw_cc == "ALL") else _normalize_rental_country(raw_cc)
    items = search_rental_locations(
        q,
        category=category,
        limit=12,
        country_code=normalized_cc,
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
    fallback_reasons: list[str] = []
    fallback_reason_set: set[str] = set()

    def _add_fallback_reason(reason: str) -> None:
        r = str(reason or "").strip()
        if not r or r in fallback_reason_set:
            return
        fallback_reason_set.add(r)
        fallback_reasons.append(r)

    rental_days = calc_rental_days(pickup_at, dropoff_at)
    fx_rate_cache: dict[str, float | None] = {"KRW": 1.0}

    p_lat = _parse_float_param(pickup_lat)
    p_lon = _parse_float_param(pickup_lon)
    d_lat = _parse_float_param(dropoff_lat) if dropoff_lat else p_lat
    d_lon = _parse_float_param(dropoff_lon) if dropoff_lon else p_lon

    if not pickup_at:
        now = datetime.datetime.now().replace(hour=11, minute=0, second=0, microsecond=0)
        pickup_at = now.strftime("%Y-%m-%d %H:%M")
    if not dropoff_at:
        try:
            dt = datetime.datetime.strptime(pickup_at, "%Y-%m-%d %H:%M") + datetime.timedelta(days=1)
            dropoff_at = dt.strftime("%Y-%m-%d %H:%M")
        except Exception:
            dropoff_at = pickup_at

    cache_key = _rental_search_cache_key(
        pickup_lat=p_lat,
        pickup_lon=p_lon,
        dropoff_lat=d_lat,
        dropoff_lon=d_lon,
        pickup_at=pickup_at,
        dropoff_at=dropoff_at,
        country_code=country_code,
    )

    if p_lat is not None and p_lon is not None and d_lat is not None and d_lon is not None and pickup_at and dropoff_at:
        try:
            pickup_api_time = pickup_at.replace(" ", "T") + ":00"
            dropoff_api_time = dropoff_at.replace(" ", "T") + ":00"
            rental_raw = None
            sky_raw = {}
            booking_raw = {}

            # Default: parallel provider search for better response time.
            # Set RENTAL_PARALLEL_PROVIDERS=0 only if strict quota-protection is needed.
            parallel_providers = str(os.getenv("RENTAL_PARALLEL_PROVIDERS", "1") or "1").strip().lower() in {"1", "true", "yes", "on"}
            if parallel_providers:
                with ThreadPoolExecutor(max_workers=2) as ex:
                    sky_future = ex.submit(
                        search_sky_car_rentals,
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
                    booking_future = ex.submit(
                        search_car_rentals,
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
                    try:
                        sky_raw = sky_future.result()
                    except Exception as e:
                        sky_raw = {"status": False, "message": f"sky_exception: {e}"}
                    try:
                        booking_raw = booking_future.result()
                    except Exception as e:
                        booking_raw = {"error": f"booking_exception: {e}"}
            else:
                try:
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
                except Exception as e:
                    sky_raw = {"status": False, "message": f"sky_exception: {e}"}

                sky_probe = parse_sky_car_search_results(sky_raw)
                if not sky_probe:
                    # Retry once with neutral Sky query params to absorb market/currency mismatch noise.
                    try:
                        sky_retry_raw = search_sky_car_rentals(
                            pickup_name=pickup_name or city_hint or "",
                            pickup_lat=p_lat,
                            pickup_lon=p_lon,
                            dropoff_name=dropoff_name or pickup_name or city_hint or "",
                            dropoff_lat=d_lat,
                            dropoff_lon=d_lon,
                            pickup_at=pickup_api_time,
                            dropoff_at=dropoff_api_time,
                            market="US",
                            currency="USD",
                            locale="en-US",
                            driver_age=30,
                        )
                        sky_retry_probe = parse_sky_car_search_results(sky_retry_raw)
                        if sky_retry_probe:
                            sky_raw = sky_retry_raw
                            sky_probe = sky_retry_probe
                    except Exception:
                        pass

                if not sky_probe and country_code == "JP":
                    # JP-specific retry hints: Narita/Haneda/Tokyo often differ by provider entity naming.
                    jp_retry_names: list[str] = []
                    for cand in [
                        pickup_name or "",
                        dropoff_name or "",
                        city_hint or "",
                        "NRT",
                        "Narita Airport",
                        "HND",
                        "Haneda Airport",
                        "Tokyo",
                    ]:
                        c = str(cand or "").strip()
                        if c and c not in jp_retry_names:
                            jp_retry_names.append(c)
                    for alt_name in jp_retry_names:
                        try:
                            sky_jp_raw = search_sky_car_rentals(
                                pickup_name=alt_name,
                                pickup_lat=p_lat,
                                pickup_lon=p_lon,
                                dropoff_name=alt_name,
                                dropoff_lat=d_lat,
                                dropoff_lon=d_lon,
                                pickup_at=pickup_api_time,
                                dropoff_at=dropoff_api_time,
                                market="JP",
                                currency="JPY",
                                locale="en-US",
                                driver_age=30,
                            )
                            sky_jp_probe = parse_sky_car_search_results(sky_jp_raw)
                            if sky_jp_probe:
                                sky_raw = sky_jp_raw
                                sky_probe = sky_jp_probe
                                break
                        except Exception:
                            continue

                if sky_probe:
                    rental_raw = sky_raw
                    rental_cars = sky_probe
                    rental_provider = "Sky Cars"
                    rental_provider_detail = "Sky cars/search"
                    booking_raw = {}
                else:
                    try:
                        booking_raw = search_car_rentals(
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
                    except Exception as e:
                        booking_raw = {"error": f"booking_exception: {e}"}
            sky_cars = parse_sky_car_search_results(sky_raw)
            booking_cars = parse_rental_search_results(booking_raw)

            if sky_cars:
                rental_raw = sky_raw
                rental_cars = sky_cars
                rental_provider = "Sky Cars"
                rental_provider_detail = "Sky cars/search"
            elif booking_cars:
                rental_raw = booking_raw
                rental_cars = booking_cars
                rental_provider = "Booking Fallback"
                rental_provider_detail = "Sky empty/fail -> Booking"
            else:
                sky_msg = None
                if isinstance(sky_raw, dict):
                    sky_msg = str(sky_raw.get("message") or sky_raw.get("errors") or "").strip()
                    if sky_msg:
                        _add_fallback_reason(f"sky={sky_msg}")
                    else:
                        _add_fallback_reason("sky=empty")
                booking_msg = None
                if isinstance(booking_raw, dict):
                    booking_msg = str(booking_raw.get("error") or booking_raw.get("message") or "").strip()
                    if booking_msg:
                        _add_fallback_reason(f"booking={booking_msg}")
                    else:
                        _add_fallback_reason("booking=empty")
                rental_raw = booking_raw if isinstance(booking_raw, dict) else sky_raw
                rental_cars = []
                rental_provider = "Provider Fallback"
                detail_raw = f"Sky empty/fail -> Booking empty/fail ({sky_msg or 'no sky detail'})"
                detail_clean = _clean_provider_detail(detail_raw)
                rental_provider_detail = detail_clean if detail_clean else "Sky empty/fail -> Booking"
                cached = _get_cached_rental_results(cache_key)
                if cached:
                    rental_cars = cached["cars"]
                    rental_provider = "Cached Fallback"
                    rental_provider_detail = cached["provider_detail"] or "최근 검색 캐시 결과"
                    rental_raw = {"status": True, "message": "cached_result"}
            for car in rental_cars:
                if not isinstance(car, dict):
                    continue
                original_currency = str(car.get("currency") or currency_code or "KRW").strip().upper() or "KRW"
                original_price = car.get("price")
                car["original_currency"] = original_currency
                car["original_price"] = original_price

                converted_price = _to_krw_price(original_price, original_currency, fx_rate_cache)
                if converted_price is not None:
                    car["price"] = converted_price
                    car["currency"] = "KRW"
                    car["fx_applied"] = original_currency != "KRW"
                else:
                    car["currency"] = original_currency
                    car["fx_applied"] = False

                # Drop obviously broken parser values (e.g. 2 KRW, 3 KRW).
                if not _is_reasonable_total_price(car.get("price"), car.get("currency"), rental_days):
                    car["price"] = None
                    car["price_per_day"] = None
                    car["price_unreliable"] = True
                    car["price_estimated"] = False
                else:
                    car["price_unreliable"] = False
                    car["price_estimated"] = False

                # Use deterministic fallback image when provider image is missing.
                image_url = str(car.get("image") or "").strip()
                if (
                    not image_url
                    or _looks_like_non_vehicle_image_url(image_url)
                ):
                    # Replace only missing or explicit non-vehicle image URL.
                    car["image"] = _fallback_image_for_car(car.get("name"), car.get("supplier"))

                car["rental_days"] = rental_days
                if rental_days and car.get("price"):
                    try:
                        car["price_per_day"] = int(round(float(car["price"]) / rental_days))
                    except Exception:
                        car["price_per_day"] = None

            if rental_cars and (rental_provider or "").lower() in {"sky cars", "booking fallback"}:
                _set_cached_rental_results(cache_key, rental_cars, rental_provider, rental_provider_detail)

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
                _add_fallback_reason(f"booking={api_error}")
            elif not rental_cars:
                rental_error = "실시간 차량 검색 결과가 없습니다. 날짜/장소를 다시 확인해 주세요."
                _add_fallback_reason("booking=no_cars")

            reliable_count = sum(
                1
                for c in rental_cars
                if c.get("price") is not None and not c.get("price_unreliable")
            )
            if reliable_count == 0 and rental_cars:
                estimated = _apply_estimated_prices_to_cars(rental_cars, country_code, rental_days)
                if estimated > 0:
                    # Treat estimated-fare mode as non-fatal; keep result list visible without red error banner.
                    rental_error = None
                    rental_provider_detail = _public_provider_detail(
                        rental_provider or "Provider Fallback",
                        "estimated fares",
                    )
                else:
                    _add_fallback_reason("filtered=all_unreliable_or_no_price")
                    rental_error = "실시간 차량은 조회되었지만 요금이 불안정해 요금을 표시할 수 없습니다."

            if not rental_cars:
                # Always keep at least fallback inventory visible when provider results are empty.
                rental_cars = _build_local_fallback_rental_cars(country_code, rental_days)
                original_fallback = list(rental_cars)
                filtered_fallback = list(rental_cars)
                if min_seats_value:
                    filtered_fallback = [c for c in filtered_fallback if not c.get("seats") or c.get("seats") >= min_seats_value]
                if transmission and transmission not in {"", "all"}:
                    tneedle = str(transmission).lower()
                    filtered_fallback = [c for c in filtered_fallback if tneedle in str(c.get("transmission") or "").lower()]
                rental_cars = filtered_fallback if filtered_fallback else original_fallback
                if sort == "price_desc":
                    rental_cars.sort(key=lambda x: x.get("price") or -1, reverse=True)
                elif sort == "name":
                    rental_cars.sort(key=lambda x: str(x.get("name") or ""))
                elif sort == "rating":
                    rental_cars.sort(key=lambda x: x.get("rating") or 0, reverse=True)
                else:
                    rental_cars.sort(key=lambda x: x.get("price") or 10**12)

                if rental_cars:
                    rental_provider = "Local Fallback"
                    rental_provider_detail = _public_provider_detail(rental_provider, " / ".join(fallback_reasons))
                    rental_error = None
                else:
                    rental_provider = "API Unavailable"
                    rental_provider_detail = _public_provider_detail(rental_provider, " / ".join(fallback_reasons))
                    rental_error = _build_public_rental_failure_message(fallback_reasons)
        except Exception as e:
            rental_error = f"렌터카 검색 중 오류: {e}"

    rental_provider_detail = _public_provider_detail(rental_provider, rental_provider_detail)

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


@router.get("/rental/detail", response_class=HTMLResponse)
def rental_detail_page(
    request: Request,
    car: str = Query(""),
):
    nickname = _get_nickname_from_request(request)
    car_payload: dict = {}
    if car:
        try:
            loaded = json.loads(car)
            if isinstance(loaded, dict):
                car_payload = loaded
        except Exception:
            car_payload = {}

    if not car_payload:
        car_payload = {
            "name": "렌터카 상품",
            "supplier": "Rental Partner",
            "price": 0,
            "currency": "KRW",
            "image": "https://images.unsplash.com/photo-1541899481282-d53bffe3c35d?q=80&w=1200&auto=format&fit=crop",
            "specs": ["5인승", "가방 2", "automatic"],
            "pickup_name": "",
            "dropoff_name": "",
            "pickup_at": "",
            "dropoff_at": "",
        }

    return templates.TemplateResponse(
        "rental-detail.html",
        {
            "request": request,
            "nickname": nickname,
            "car": car_payload,
        },
    )


@router.post("/api/rental/checkout")
def api_rental_checkout(payload: RentalCheckoutRequest, request: Request):
    user_id = _require_user_id(request)

    amount = _extract_rental_amount_krw(payload.car)
    order_id = f"RNT-{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:8]}"
    order_name = _build_rental_order_name(payload.car)
    toss_client_key = (os.getenv("TOSS_PAYMENTS_CLIENT_KEY") or os.getenv("TOSS_CLIENT_KEY") or "").strip()
    base_url = str(request.base_url).rstrip("/")

    PENDING_RENTAL_ORDERS[order_id] = {
        "user_id": str(user_id),
        "amount": amount,
        "order_name": order_name,
        "car": payload.car,
        "driver": payload.driver.model_dump(),
        "created_at": datetime.datetime.now().isoformat(),
    }

    return {
        "order_id": order_id,
        "order_name": order_name,
        "amount": amount,
        "currency": "KRW",
        "payment_mode": "toss" if toss_client_key else "mock",
        "toss_client_key": toss_client_key,
        "success_url": f"{base_url}/payment/rental/success",
        "fail_url": f"{base_url}/payment/rental/fail",
        "message": "결제 준비가 완료되었습니다." if toss_client_key else "토스 클라이언트 키가 없어 모의 결제 모드로 동작합니다.",
    }


@router.post("/api/payments/toss/rental/confirm")
def api_toss_rental_confirm(payload: dict):
    payment_key = str(payload.get("paymentKey") or "").strip()
    order_id = str(payload.get("orderId") or "").strip()
    amount = int(payload.get("amount") or 0)

    pending = PENDING_RENTAL_ORDERS.get(order_id)
    if not pending:
        raise HTTPException(status_code=404, detail="주문 정보를 찾을 수 없습니다.")
    if int(pending.get("amount") or 0) != amount:
        raise HTTPException(status_code=400, detail="결제 금액 검증에 실패했습니다.")

    secret_key = (os.getenv("TOSS_PAYMENTS_SECRET_KEY") or os.getenv("TOSS_SECRET_KEY") or "").strip()
    if not secret_key:
        pending["status"] = "confirmed_mock"
        pending["payment_key"] = payment_key
        pending["confirmed_at"] = datetime.datetime.now().isoformat()
        save_booking(
            user_id=int(pending.get("user_id") or 0),
            item_type="rental",
            order_id=order_id,
            order_name=str(pending.get("order_name") or "렌터카 예약"),
            amount=amount,
            currency="KRW",
            status="confirmed_mock",
            status_label="예약 확정(모의 결제)",
            route=str(
                (
                    (pending.get("car") or {}).get("pickup_name")
                    or (pending.get("car") or {}).get("dropoff_name")
                    or ""
                )
            ).strip(),
            payment_key=payment_key,
            payload=pending,
            created_at_iso=str(pending.get("created_at") or ""),
            confirmed_at_iso=str(pending.get("confirmed_at") or ""),
        )
        return {
            "status": "confirmed_mock",
            "order_id": order_id,
            "amount": amount,
            "message": "토스 시크릿 키가 없어 모의 승인 처리되었습니다.",
        }

    auth = base64.b64encode(f"{secret_key}:".encode("utf-8")).decode("ascii")
    try:
        res = requests.post(
            "https://api.tosspayments.com/v1/payments/confirm",
            headers={
                "Authorization": f"Basic {auth}",
                "Content-Type": "application/json",
            },
            json={
                "paymentKey": payment_key,
                "orderId": order_id,
                "amount": amount,
            },
            timeout=15,
        )
        data = res.json() if res.content else {}
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"토스 승인 요청 실패: {e}")

    if not res.ok:
        msg = (data or {}).get("message") if isinstance(data, dict) else None
        raise HTTPException(status_code=400, detail=msg or f"토스 승인 실패 ({res.status_code})")

    pending["status"] = "confirmed"
    pending["payment_key"] = payment_key
    pending["confirmed_at"] = datetime.datetime.now().isoformat()
    pending["toss_response"] = data
    save_booking(
        user_id=int(pending.get("user_id") or 0),
        item_type="rental",
        order_id=order_id,
        order_name=str(pending.get("order_name") or "렌터카 예약"),
        amount=amount,
        currency="KRW",
        status="confirmed",
        status_label="예약 확정",
        route=str(
            (
                (pending.get("car") or {}).get("pickup_name")
                or (pending.get("car") or {}).get("dropoff_name")
                or ""
            )
        ).strip(),
        payment_key=payment_key,
        payload=pending,
        created_at_iso=str(pending.get("created_at") or ""),
        confirmed_at_iso=str(pending.get("confirmed_at") or ""),
    )
    return {"status": "confirmed", "order_id": order_id, "amount": amount, "payment": data}


@router.get("/payment/rental/success", response_class=HTMLResponse)
def payment_rental_success_page():
    return """
<!doctype html>
<html lang=\"ko\">
<head>
    <meta charset=\"utf-8\">
    <meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">
    <title>DESTINO | 결제 확인</title>
    <link rel=\"stylesheet\" as=\"style\" crossorigin href=\"https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/static/pretendard.css\" />
    <style>
        :root {
            --primary-blue: #00AEEF;
            --dark-navy: #1A202C;
            --bg-gray: #F8F9FA;
            --text-muted: #718096;
        }
        * { box-sizing: border-box; font-family: 'Pretendard', -apple-system, sans-serif; }
        body {
            background-color: var(--bg-gray);
            display: flex; align-items: center; justify-content: center;
            height: 100vh; margin: 0; color: var(--dark-navy);
        }
        .container {
            background: #fff;
            width: 100%;
            max-width: 480px;
            padding: 40px 24px;
            border-radius: 20px;
            box-shadow: 0 10px 25px rgba(0,0,0,0.05);
            text-align: center;
        }
        .status-icon {
            width: 64px; height: 64px;
            background: #f0f9ff;
            border-radius: 50%;
            display: flex; align-items: center; justify-content: center;
            margin: 0 auto 24px;
        }
        .spinner {
            width: 24px; height: 24px;
            border: 3px solid #e2e8f0;
            border-top-color: var(--primary-blue);
            border-radius: 50%;
            animation: spin 1s linear infinite;
        }
        @keyframes spin { to { transform: rotate(360deg); } }
        h2 { font-size: 24px; font-weight: 700; margin-bottom: 12px; letter-spacing: -0.5px; }
        p { color: var(--text-muted); line-height: 1.6; margin-bottom: 32px; }
        .info-card {
            background: #f8fafc;
            border-radius: 12px;
            padding: 20px;
            margin-bottom: 32px;
            text-align: left;
            display: none;
        }
        .info-row {
            display: flex; justify-content: space-between; margin-bottom: 8px;
            font-size: 14px;
        }
        .info-row span:first-child { color: var(--text-muted); }
        .info-row span:last-child { font-weight: 600; }
        .btn {
            display: block;
            width: 100%;
            padding: 16px;
            border-radius: 12px;
            text-decoration: none;
            font-weight: 600;
            transition: all 0.2s;
        }
        .btn-primary { background-color: var(--primary-blue); color: white; }
        .btn-primary:hover { background-color: #0096ce; }
        .btn-outline { border: 1px solid #e2e8f0; color: var(--text-muted); margin-top: 12px; font-size: 14px; }
    </style>
</head>
<body>
    <div class=\"container\">
        <div class=\"status-icon\" id=\"icon-box\">
            <div class=\"spinner\" id=\"spinner\"></div>
        </div>
        <h2 id=\"title\">결제 확인 중</h2>
        <p id=\"msg\">안전한 결제 승인을 위해 잠시만 기다려 주세요.</p>
        <div class=\"info-card\" id=\"info-card\">
            <div class=\"info-row\">
                <span>주문번호</span>
                <span id=\"res-orderId\">-</span>
            </div>
            <div class=\"info-row\">
                <span>결제금액</span>
                <span id=\"res-amount\">-</span>
            </div>
        </div>
        <a href=\"/rental\" class=\"btn btn-primary\" id=\"main-btn\">렌터카 상품페이지로 돌아가기</a>
        <a href=\"/\" class=\"btn btn-outline\">메인페이지로 이동</a>
    </div>
    <script>
        const qs = new URLSearchParams(location.search);
        const orderId = qs.get('orderId');
        const amount = Number(qs.get('amount') || 0);
        const body = { paymentKey: qs.get('paymentKey'), orderId: orderId, amount: amount };
        fetch('/api/payments/toss/rental/confirm', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(body)
        })
        .then(async r => ({ ok: r.ok, data: await r.json().catch(() => ({})) }))
        .then(x => {
            const iconBox = document.getElementById('icon-box');
            const title = document.getElementById('title');
            const msg = document.getElementById('msg');
            const infoCard = document.getElementById('info-card');
            if (x.ok) {
                iconBox.innerHTML = '✅';
                iconBox.style.fontSize = '32px';
                title.textContent = '결제가 완료되었습니다!';
                msg.textContent = '렌터카 예약이 완료되었습니다. 마이페이지에서 상세 내역을 확인하세요.';
                infoCard.style.display = 'block';
                document.getElementById('res-orderId').textContent = orderId;
                document.getElementById('res-amount').textContent = amount.toLocaleString() + '원';
                document.getElementById('main-btn').textContent = '렌터카 상품 페이지로 돌아가기';
            } else {
                iconBox.innerHTML = '❌';
                iconBox.style.fontSize = '32px';
                title.textContent = '결제에 실패했습니다';
                msg.textContent = x.data?.detail || x.data?.message || '알 수 없는 오류가 발생했습니다.';
            }
        })
        .catch(() => {
            document.getElementById('title').textContent = '오류 발생';
            document.getElementById('msg').textContent = '서버와의 통신 중 문제가 발생했습니다.';
        });
    </script>
</body>
</html>
"""


@router.get("/payment/rental/fail", response_class=HTMLResponse)
def payment_rental_fail_page(code: str | None = Query(None), message: str | None = Query(None)):
    c = (code or "").strip()
    m = (message or "").strip()
    return f"""
<!doctype html>
<html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>렌터카 결제 실패</title>
<style>body{{font-family:Pretendard,sans-serif;padding:24px;background:#f8fafc;color:#0f172a}} .box{{max-width:560px;margin:24px auto;background:#fff;border:1px solid #fecaca;border-radius:12px;padding:18px}} .muted{{color:#64748b;font-size:14px}}</style>
</head><body><div class="box"><h2>결제가 완료되지 않았습니다.</h2><p class="muted">코드: {c or '-'}</p><p class="muted">메시지: {m or '-'}</p><a href="/rental">렌터카 페이지로 돌아가기</a></div></body></html>
"""
