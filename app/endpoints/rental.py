import datetime
import os
import hashlib
import json
import uuid
import base64
import requests

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


router = APIRouter()
PENDING_RENTAL_ORDERS: dict[str, dict] = {}

_APP_DIR = os.path.dirname(os.path.dirname(__file__))
templates = Jinja2Templates(directory=os.path.join(_APP_DIR, "templates"))

_RENTAL_COUNTRY_OPTIONS = [
    {"code": "JP", "name": "??", "currency": "JPY"},
    {"code": "KR", "name": "????", "currency": "KRW"},
    {"code": "US", "name": "??", "currency": "USD"},
    {"code": "FR", "name": "???", "currency": "EUR"},
    {"code": "AE", "name": "??????", "currency": "AED"},
    {"code": "TH", "name": "??", "currency": "THB"},
    {"code": "VN", "name": "???", "currency": "VND"},
    {"code": "SG", "name": "????", "currency": "SGD"},
    {"code": "TW", "name": "??", "currency": "TWD"},
]

# Fallback FX table used when live exchange API is unavailable.
# Values are approximate KRW per 1 unit of foreign currency.
_DEFAULT_FX_TO_KRW = {
    "KRW": 1.0,
    "USD": 1350.0,
    "EUR": 1470.0,
    "JPY": 9.0,
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
        return f"??? API ?? ???? ??? ? ????. (??? ??: {list(raw.get('errors', {}).items())})"

    message = str(raw.get("message") or "").strip()
    status = str(raw.get("status") or "").strip()
    joined = f"{status} {message}".strip().lower()

    if "something went wrong" in joined:
        return "??? API ??? ?? ?????. ?? ? ?? ??? ???."
    if any(k in joined for k in ("invalid", "required", "parameter", "validation")):
        detail = message or status
        if detail:
            return f"??? API ?? ???? ??? ? ????. (??? ??: {detail})"
        return "??? API ?? ???? ??? ? ????. ?? ? ?? ??? ???."
    if any(k in joined for k in ("rate limit", "too many requests")):
        return "??? API ??? ?? ?? ???????. ?? ? ?? ??? ???."
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
    fallback_reasons: list[str] = []
    has_live_api_key = bool(
        str(os.getenv("SKY_RAPIDAPI_KEY") or "").strip()
        or str(os.getenv("BOOKING_RAPIDAPI_KEY") or "").strip()
    )
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
            if not sky_cars and isinstance(sky_raw, dict):
                # Sky ?? ???? ?? ??? ??? ?? ??? ? ? ??
                sky_cars = parse_rental_search_results(sky_raw)
            if sky_cars:
                rental_raw = sky_raw
                rental_cars = sky_cars
                rental_provider = "Sky Cars"
                rental_provider_detail = "Sky cars/search"
            else:
                sky_msg = None
                if isinstance(sky_raw, dict):
                    sky_msg = str(sky_raw.get("message") or sky_raw.get("errors") or "").strip()
                    if sky_msg:
                        fallback_reasons.append(f"sky={sky_msg}")
                    else:
                        fallback_reasons.append("sky=empty")
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
                detail_raw = f"Sky empty/fail -> Booking ({sky_msg or 'no sky detail'})"
                detail_clean = _clean_provider_detail(detail_raw)
                rental_provider_detail = detail_clean if detail_clean else "Sky empty/fail -> Booking"
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
                else:
                    car["price_unreliable"] = False

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
                fallback_reasons.append(f"booking={api_error}")
            elif not rental_cars:
                rental_error = "??? ?? ??? ?? ?????. ?? ??/???? ?? ??? ???."
                fallback_reasons.append("booking=no_cars")

            reliable_count = sum(
                1
                for c in rental_cars
                if c.get("price") is not None and not c.get("price_unreliable")
            )
            if reliable_count == 0 and rental_cars:
                # Sky 차량은 왔지만 가격이 전부 불안정하면 Booking 요금으로 한 번 더 재조회한다.
                try:
                    booking_raw_retry = search_car_rentals(
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
                    booking_retry_cars = parse_rental_search_results(booking_raw_retry)
                    for bcar in booking_retry_cars:
                        if not isinstance(bcar, dict):
                            continue
                        b_original_currency = str(bcar.get("currency") or currency_code or "KRW").strip().upper() or "KRW"
                        b_original_price = bcar.get("price")
                        bcar["original_currency"] = b_original_currency
                        bcar["original_price"] = b_original_price
                        b_converted = _to_krw_price(b_original_price, b_original_currency, fx_rate_cache)
                        if b_converted is not None:
                            bcar["price"] = b_converted
                            bcar["currency"] = "KRW"
                            bcar["fx_applied"] = b_original_currency != "KRW"
                        else:
                            bcar["currency"] = b_original_currency
                            bcar["fx_applied"] = False
                        if not _is_reasonable_total_price(bcar.get("price"), bcar.get("currency"), rental_days):
                            bcar["price"] = None
                            bcar["price_per_day"] = None
                            bcar["price_unreliable"] = True
                        else:
                            bcar["price_unreliable"] = False
                        b_image = str(bcar.get("image") or "").strip()
                        if (not b_image) or _looks_like_non_vehicle_image_url(b_image):
                            bcar["image"] = _fallback_image_for_car(bcar.get("name"), bcar.get("supplier"))
                        bcar["rental_days"] = rental_days
                        if rental_days and bcar.get("price"):
                            try:
                                bcar["price_per_day"] = int(round(float(bcar["price"]) / rental_days))
                            except Exception:
                                bcar["price_per_day"] = None

                    booking_reliable = [
                        c for c in booking_retry_cars
                        if c.get("price") is not None and not c.get("price_unreliable")
                    ]
                    if booking_reliable:
                        rental_cars = booking_retry_cars
                        rental_provider = "Booking Fallback"
                        rental_provider_detail = "Sky price unstable -> Booking fares applied"
                        rental_error = None
                    else:
                        fallback_reasons.append("filtered=all_unreliable_or_no_price")
                        rental_error = "실시간 차량은 조회되었지만 요금이 불안정해 일부는 '요금 확인 필요'로 표시됩니다."
                except Exception:
                    fallback_reasons.append("filtered=all_unreliable_or_no_price")
                    rental_error = "실시간 차량은 조회되었지만 요금이 불안정해 일부는 '요금 확인 필요'로 표시됩니다."

            if not rental_cars and not has_live_api_key:
                rental_cars = _build_local_fallback_rental_cars(country_code, rental_days)
                if min_seats_value:
                    rental_cars = [c for c in rental_cars if not c.get("seats") or c.get("seats") >= min_seats_value]
                if transmission and transmission not in {"", "all"}:
                    tneedle = str(transmission).lower()
                    rental_cars = [c for c in rental_cars if tneedle in str(c.get("transmission") or "").lower()]
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
                    if fallback_reasons:
                        rental_provider_detail = " / ".join(fallback_reasons)[:280]
                    else:
                        rental_provider_detail = "Live provider unavailable; showing sample rates"
                    rental_error = None
            elif not rental_cars and has_live_api_key:
                rental_provider = rental_provider or "API Only"
                rental_provider_detail = " / ".join(fallback_reasons)[:280] if fallback_reasons else "Live API returned no valid cars"
                if not rental_error:
                    rental_error = "실시간 API 결과가 없거나 요금 검증에서 제외되었습니다. 검색 조건을 바꿔 다시 시도해 주세요."
        except Exception as e:
            rental_error = f"??? ?? ??: {e}"

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
    _require_user_id(request)

    amount = _extract_rental_amount_krw(payload.car)
    order_id = f"RNT-{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:8]}"
    order_name = _build_rental_order_name(payload.car)
    toss_client_key = (os.getenv("TOSS_PAYMENTS_CLIENT_KEY") or os.getenv("TOSS_CLIENT_KEY") or "").strip()
    base_url = str(request.base_url).rstrip("/")

    PENDING_RENTAL_ORDERS[order_id] = {
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
    return {"status": "confirmed", "order_id": order_id, "amount": amount, "payment": data}


@router.get("/payment/rental/success", response_class=HTMLResponse)
def payment_rental_success_page():
    return """
<!doctype html>
<html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>렌터카 결제 확인 중</title>
<style>body{font-family:Pretendard,sans-serif;padding:24px;background:#f8fafc;color:#0f172a} .box{max-width:560px;margin:24px auto;background:#fff;border:1px solid #e2e8f0;border-radius:12px;padding:18px} .muted{color:#64748b;font-size:14px}</style>
</head><body><div class="box"><h2>결제 확인 중입니다...</h2><p id="msg" class="muted">잠시만 기다려 주세요.</p><a href="/rental">렌터카 페이지로 돌아가기</a></div>
<script>
const qs=new URLSearchParams(location.search);
const body={paymentKey:qs.get('paymentKey'),orderId:qs.get('orderId'),amount:Number(qs.get('amount')||0)};
fetch('/api/payments/toss/rental/confirm',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)})
 .then(async r=>({ok:r.ok,data:await r.json().catch(()=>({}))}))
 .then(x=>{document.getElementById('msg').textContent=x.ok?'결제가 승인되었습니다.':'결제 승인 실패: '+(x.data?.detail||x.data?.message||'알 수 없는 오류');})
 .catch(()=>{document.getElementById('msg').textContent='결제 승인 확인 중 오류가 발생했습니다.'});
</script></body></html>
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
