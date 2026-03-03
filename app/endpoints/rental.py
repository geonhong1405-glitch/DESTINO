import datetime
import os
import hashlib

from fastapi import APIRouter, Query, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

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
    "https://images.unsplash.com/photo-1549924231-f129b911e442?q=80&w=1200&auto=format&fit=crop",
    "https://images.unsplash.com/photo-1492144534655-ae79c964c9d7?q=80&w=1200&auto=format&fit=crop",
    "https://images.unsplash.com/photo-1503376780353-7e6692767b70?q=80&w=1200&auto=format&fit=crop",
    "https://images.unsplash.com/photo-1552519507-da3b142c6e3d?q=80&w=1200&auto=format&fit=crop",
    "https://images.unsplash.com/photo-1605559424843-9e4c228bf1c2?q=80&w=1200&auto=format&fit=crop",
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


def _is_generic_supplier_car_name(name: str | None, supplier: str | None) -> bool:
    n = str(name or "").strip().lower()
    s = str(supplier or "").strip().lower()
    if not n:
        return True
    if not s:
        # Names ending with the generic word "rental car" are not real model names.
        return "렌터카" in n
    normalized = n.replace(" ", "")
    supplier_norm = s.replace(" ", "")
    return normalized in {
        supplier_norm,
        f"{supplier_norm}렌터카",
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
                if not str(car.get("image") or "").strip():
                    car["image"] = _fallback_image_for_car(car.get("name"), car.get("supplier"))
                elif _is_generic_supplier_car_name(car.get("name"), car.get("supplier")):
                    # Supplier-only placeholder cards often come with non-car or repeated images.
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
            elif not rental_cars:
                rental_error = "??? ?? ??? ?? ?????. ?? ??/???? ?? ??? ???."

            reliable_cars = [
                c
                for c in rental_cars
                if c.get("price") is not None and not c.get("price_unreliable")
            ]
            if reliable_cars:
                rental_cars = reliable_cars
            else:
                rental_cars = []

            if not rental_cars:
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
                    rental_provider_detail = "Live provider unavailable; showing sample rates"
                    rental_error = None
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
