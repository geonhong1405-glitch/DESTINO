from app.api.booking_hotel_flight_api import (
    search_destination as booking_search_destination,
    search_hotels as booking_search_hotels,
    search_hotels_by_dest_id as booking_search_hotels_by_dest_id,
    search_flights as booking_search_flights,
)
from app.session import get_user_id_from_session, create_session, delete_session, clear_all_sessions, SESSION_EXPIRE_MINUTES
from app.db.db import Base, engine, SessionLocal
from fastapi import FastAPI, Query, Request, Depends, Form, status, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from app.api.geoapify import get_attractions
from app.api.google_places import find_hotel_google_place, get_google_places
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session

from app.db.models import User, TranslationCache
from app.endpoints.routes import router as main_router
from app.endpoints.rag_api import router as rag_router
from app.endpoints.flight_chat import router as flight_chat_router
from app.endpoints.rental import router as rental_router
from app.endpoints.saved_items import router as saved_items_router
from app.endpoints.group_buy import router as group_buy_router
from app.api.amadeus_api import (
    search_hotels as amadeus_search_hotels,
    resolve_location_to_iata as amadeus_resolve_location_to_iata,
)
from app.services.booking_history_service import save_booking, get_user_bookings

import os
import json
import datetime
import re
import base64
import hashlib
import hmac
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import quote, unquote

_PWD_PREFIX = "pbkdf2_sha256"
_PWD_ITERATIONS = 260000
_PASSWORD_REGEX = re.compile(r"^(?=.*[A-Za-z])(?=.*\d)(?=.*[^\w\s]).{8,}$")
_EMAIL_REGEX = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
_PHONE_REGEX = re.compile(r"^01[0-9]-\d{3,4}-\d{4}$")


def _validate_signup(password: str, email: str, phone: str) -> str | None:
    if not _PASSWORD_REGEX.match(password or ""):
        return "\ube44\ubc00\ubc88\ud638\ub294 \uc601\ubb38/\uc22b\uc790/\ud2b9\uc218\ubb38\uc790 \ud3ec\ud568 8\uc790 \uc774\uc0c1\uc774\uc5b4\uc57c \ud569\ub2c8\ub2e4."
    if not _EMAIL_REGEX.match(email or ""):
        return "\uc774\uba54\uc77c \ud615\uc2dd\uc774 \uc62c\ubc14\ub974\uc9c0 \uc54a\uc2b5\ub2c8\ub2e4."
    if not _PHONE_REGEX.match(phone or ""):
        return "\ud734\ub300\ud3f0 \ubc88\ud638 \ud615\uc2dd\uc774 \uc62c\ubc14\ub974\uc9c0 \uc54a\uc2b5\ub2c8\ub2e4."
    return None


def _validate_password_only(password: str) -> str | None:
    if not _PASSWORD_REGEX.match(password or ""):
        return "비밀번호는 영문/숫자/특수문자 포함 8자 이상이어야 합니다."
    return None



def _hash_password(password: str) -> str:
    salt = base64.b64encode(os.urandom(16)).decode("ascii").rstrip("=")
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), _PWD_ITERATIONS)
    digest = base64.b64encode(dk).decode("ascii").rstrip("=")
    return f"{_PWD_PREFIX}${_PWD_ITERATIONS}${salt}${digest}"


def _verify_password(password: str, stored: str) -> tuple[bool, bool]:
    if not stored:
        return False, False
    if stored.startswith(f"{_PWD_PREFIX}$"):
        try:
            _, iters, salt, digest = stored.split("$", 3)
            dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), int(iters))
            calc = base64.b64encode(dk).decode("ascii").rstrip("=")
            return hmac.compare_digest(calc, digest), False
        except Exception:
            return False, False
    # legacy plaintext fallback; caller may upgrade
    return hmac.compare_digest(password, stored), True


_TRANSLATE_CACHE: dict[str, str] = {}
_TRANSLATE_CACHE_LOADED = False
_TRANSLATE_CACHE_PATH = None
PENDING_HOTEL_ORDERS: dict[str, dict] = {}
PENDING_TOUR_ORDERS: dict[str, dict] = {}
PENDING_PACK_ORDERS: dict[str, dict] = {}


def _env_int(name: str, default: int) -> int:
    try:
        raw = os.getenv(name, str(default))
        return int(str(raw).strip() or str(default))
    except Exception:
        return int(default)


def _contains_korean(text: str) -> bool:
    return bool(re.search(r"[가-힣]", text or ""))


def _log_translate_issue(message: str) -> None:
    try:
        with open(os.path.join(BASE_DIR, "hotel_debug.log"), "a", encoding="utf-8") as f:
            f.write(f"[translate] {message}\n")
    except Exception:
        pass


def _get_translation_from_db(text: str) -> str | None:
    try:
        db = SessionLocal()
        row = db.query(TranslationCache).filter(TranslationCache.source_text == text).first()
        return row.translated_text if row else None
    except Exception as e:
        _log_translate_issue(f"db_get_exception={e}")
        return None
    finally:
        try:
            db.close()
        except Exception:
            pass


def _save_translation_to_db(text: str, translated: str, source_lang: str, target_lang: str) -> None:
    try:
        db = SessionLocal()
        row = db.query(TranslationCache).filter(TranslationCache.source_text == text).first()
        if row:
            row.translated_text = translated
            row.source_lang = source_lang
            row.target_lang = target_lang
        else:
            row = TranslationCache(
                source_text=text,
                translated_text=translated,
                source_lang=source_lang,
                target_lang=target_lang,
            )
            db.add(row)
        db.commit()
    except Exception as e:
        _log_translate_issue(f"db_save_exception={e}")
    finally:
        try:
            db.close()
        except Exception:
            pass


def _load_translate_cache() -> None:
    global _TRANSLATE_CACHE_LOADED, _TRANSLATE_CACHE, _TRANSLATE_CACHE_PATH
    if _TRANSLATE_CACHE_LOADED:
        return
    if _TRANSLATE_CACHE_PATH is None:
        _TRANSLATE_CACHE_PATH = os.path.join(BASE_DIR, "translate_cache.json")
    try:
        if os.path.exists(_TRANSLATE_CACHE_PATH):
            with open(_TRANSLATE_CACHE_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    _TRANSLATE_CACHE = {str(k): str(v) for k, v in data.items()}
    except Exception:
        pass
    _TRANSLATE_CACHE_LOADED = True


def _save_translate_cache() -> None:
    if _TRANSLATE_CACHE_PATH is None:
        return
    try:
        with open(_TRANSLATE_CACHE_PATH, "w", encoding="utf-8") as f:
            json.dump(_TRANSLATE_CACHE, f, ensure_ascii=False)
    except Exception:
        pass


def _translate_to_korean(text: str) -> str | None:
    text = _as_text(text)
    if isinstance(text, str):
        text = text.strip()
    else:
        return None
    if not text or _contains_korean(text):
        return None
    _load_translate_cache()
    cached = _TRANSLATE_CACHE.get(text)
    if cached:
        cached_text = _as_text(cached)
        if isinstance(cached_text, str):
            cached_text = cached_text.strip()
            if cached_text:
                return cached_text
    db_cached = _get_translation_from_db(text)
    if db_cached:
        _TRANSLATE_CACHE[text] = db_cached
        return db_cached

    api_key = os.getenv("RAPIDAPI_KEY") or os.getenv("RAPIDAPI_TRANSLATE_KEY")
    api_host = os.getenv("RAPIDAPI_TRANSLATE_HOST") or os.getenv("RAPIDAPI_HOST_TRANSLATE")
    if not api_key or not api_host:
        _log_translate_issue("missing_api_key_or_host")
        return None

    base_url = os.getenv("RAPIDAPI_TRANSLATE_BASE_URL", f"https://{api_host}").rstrip("/")
    endpoint = os.getenv("RAPIDAPI_TRANSLATE_ENDPOINT", "/google/translate/text")
    if not endpoint.startswith("/"):
        endpoint = "/" + endpoint
    url = f"{base_url}{endpoint}"
    headers = {
        "x-rapidapi-key": api_key,
        "x-rapidapi-host": api_host,
        "Content-Type": "application/json",
    }

    source_lang = "auto"

    def _extract_translated_text(data) -> str | None:
        if not isinstance(data, dict):
            return None
        # Common response shapes from translation APIs / proxies.
        candidates = [
            data.get("translatedText"),
            data.get("translated_text"),
            data.get("translation"),
            ((data.get("data") or {}).get("translatedText") if isinstance(data.get("data"), dict) else None),
            ((data.get("data") or {}).get("translated_text") if isinstance(data.get("data"), dict) else None),
            ((data.get("data") or {}).get("translation") if isinstance(data.get("data"), dict) else None),
        ]
        translations = (data.get("data") or {}).get("translations") if isinstance(data.get("data"), dict) else None
        if isinstance(translations, dict):
            candidates.extend(
                [
                    translations.get("translatedText"),
                    translations.get("translated_text"),
                    translations.get("translation"),
                    (translations.get("text") if isinstance(translations.get("text"), str) else None),
                ]
            )
        elif isinstance(translations, list):
            for item in translations:
                if isinstance(item, dict):
                    candidates.extend(
                        [
                            item.get("translatedText"),
                            item.get("translated_text"),
                            item.get("translation"),
                            item.get("text"),
                        ]
                    )
        for c in candidates:
            c = _as_text(c)
            if isinstance(c, str) and c.strip():
                return c.strip()
        return None

    def _translate_text(payload_text: str, src: str, tgt: str) -> str | None:
        payload_text = _as_text(payload_text)
        if not isinstance(payload_text, str):
            return None
        payload_text = payload_text.strip()
        if not payload_text:
            return None
        payload = {
            "origin_language": src,
            "target_language": tgt,
            "input_text": payload_text,
        }
        words_not_to_translate = os.getenv("RAPIDAPI_TRANSLATE_WORDS_NOT_TO_TRANSLATE", "").strip()
        if words_not_to_translate:
            payload["words_not_to_translate"] = words_not_to_translate
        try:
            resp = requests.post(url, headers=headers, json=payload, timeout=12)
            if resp.status_code >= 400:
                _log_translate_issue(f"status={resp.status_code} text={resp.text[:200]}")
                return None
            data = resp.json()
            translated_text = _extract_translated_text(data)
            if not translated_text:
                _log_translate_issue(f"empty_translation_response={str(data)[:300]}")
                return None
            return translated_text
        except Exception as e:
            _log_translate_issue(f"exception={e}")
            return None

    translated_text = _translate_text(text, source_lang, "ko")
    if translated_text and _contains_korean(translated_text):
        _TRANSLATE_CACHE[text] = translated_text
        _save_translate_cache()
        _save_translation_to_db(text, translated_text, source_lang, "ko")
        return translated_text

    # Fallback: Any language -> English -> Korean
    inter = _translate_text(text, source_lang, "en")
    if inter:
        translated_text = _translate_text(inter, "en", "ko")
        if translated_text:
            _TRANSLATE_CACHE[text] = translated_text
            _save_translate_cache()
            _save_translation_to_db(text, translated_text, source_lang, "ko")
            return translated_text

    return None


def _is_descriptive_hotel_title_for_translate(text: str | None) -> bool:
    text = _as_text(text)
    if not isinstance(text, str) or not text.strip():
        return False
    t = text.lower()
    brand_keywords = ["hotel", "inn", "hostel", "residence", "ryokan", "resort"]
    if any(k in t for k in brand_keywords):
        return False
    desc_hits = sum(
        1
        for k in ["modern", "cozy", "private", "whole", "near", "style", "renovated", "house", "apartment", "villa"]
        if k in t
    )
    return desc_hits >= 2


def _translate_hotel_names_for_page(hotels: list[dict]) -> None:
    enabled = str(os.getenv("HOTEL_ENABLE_NAME_TRANSLATION", "1") or "1").strip().lower() in {"1", "true", "yes", "on"}
    if not enabled or not hotels:
        return

    limit = max(1, min(_env_int("HOTEL_TRANSLATE_VISIBLE_LIMIT", 16), 24))
    max_workers = max(1, min(_env_int("HOTEL_TRANSLATE_WORKERS", 4), 8))

    targets: list[tuple[int, str]] = []
    for idx, h in enumerate(hotels[:limit]):
        if not isinstance(h, dict):
            continue
        if _as_text(h.get("name_ko")):
            continue
        name_en = _as_text(h.get("name_en")) or _as_text(h.get("name"))
        if not name_en or _contains_korean(name_en):
            continue
        if _is_descriptive_hotel_title_for_translate(name_en):
            continue
        targets.append((idx, name_en))

    if not targets:
        return

    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        fut_map = {ex.submit(_translate_to_korean, name_en): idx for idx, name_en in targets}
        for fut in as_completed(fut_map):
            idx = fut_map[fut]
            try:
                translated = fut.result()
            except Exception:
                translated = None
            if translated and isinstance(hotels[idx], dict):
                hotels[idx]["name_ko"] = translated


def _hotel_destination_query_candidates(city: str | None, country: str | None, city_en: str | None = None) -> list[str]:
    city_text = (city or "").strip()
    city_en_text = (city_en or "").strip()
    country_text = (country or "").strip()
    if not city_text and not city_en_text:
        return []

    region_like_country = {
        "\ub3d9\ub0a8\uc544", "\ubbf8\uc8fc", "\uc720\ub7fd", "\uc77c\ubcf8", "\ub0a8\ud0dc\ud3c9\uc591", "\uc911\ub3d9/\uc544\ud504\ub9ac\uce74", "\ud64d\ucf69/\ub9c8\uce74\uc624/\uc911\uad6d",
        "southeast asia", "sea", "europe", "us", "america", "oceania",
    }
    country_is_region = ("/" in country_text) or (country_text.lower() in {x.lower() for x in region_like_country})

    city_alias_en = {
        "\ub098\ud2b8\ub791": "Nha Trang",
        "\ub2e4\ub0ad": "Da Nang",
        "\uc138\ubd80": "Cebu",
        "\ubc1c\ub9ac": "Bali",
        "\ucf54\ud0c0\ud0a4\ub098\ubc1c\ub8e8": "Kota Kinabalu",
        "\ub9c8\ub2d0\ub77c": "Manila",
        "\ud558\ub178\uc774": "Hanoi",
        "\ud638\uce58\ubbfc": "Ho Chi Minh City",
        "\ud478\ucf13": "Phuket",
        "\uc2f1\uac00\ud3ec\ub974": "Singapore",
        "\uad0c": "Guam",
        "\uc0ac\uc774\ud310": "Saipan",
        "\ud558\uc640\uc774": "Honolulu",
        "\ub85c\uc2a4\uc564\uc824\ub808\uc2a4": "Los Angeles",
        "\ub274\uc695": "New York",
        "\ub3c4\ucfc4": "Tokyo",
        "\uc624\uc0ac\uce74": "Osaka",
        "\ud6c4\ucfe0\uc624\uce74": "Fukuoka",
        "\uc0ff\ud3ec\ub85c": "Sapporo",
        "\uc624\ud0a4\ub098\uc640": "Okinawa",
        "\ub098\uace0\uc57c": "Nagoya",
        "\uad50\ud1a0": "Kyoto",
        "\uace0\ubca0": "Kobe",
        "\ubc29\ucf55": "Bangkok",
        "\ud64d\ucf69": "Hong Kong",
        "\ub9c8\uce74\uc624": "Macau",
        "\uc0c1\ud558\uc774": "Shanghai",
        "\ubca0\uc774\uc9d5": "Beijing",
        "\uce6d\ub2e4\uc624": "Qingdao",
        "\uad11\uc800\uc6b0": "Guangzhou",
        "\ud30c\ub9ac": "Paris",
        "\ub7f0\ub358": "London",
        "\ub85c\ub9c8": "Rome",
        "\ubc14\ub974\uc140\ub85c\ub098": "Barcelona",
        "\ud504\ub77c\ud558": "Prague",
        "\uc778\ud130\ub77c\ucf04": "Interlaken",
        "\ubca0\ub124\uce58\uc544": "Venice",
        "\ud53c\ub80c\uccb4": "Florence",
        "\uc2dc\ub4dc\ub2c8": "Sydney",
        "\uc624\ud074\ub79c\ub4dc": "Auckland",
        "\uba5c\ubc84\ub978": "Melbourne",
        "\uace8\ub4dc\ucf54\uc2a4\ud2b8": "Gold Coast",
        "\ub450\ubc14\uc774": "Dubai",
        "\uce74\uc774\ub85c": "Cairo",
        "\ucf00\uc774\ud504\ud0c0\uc6b4": "Cape Town",
        "\uc544\ubd80\ub2e4\ube44": "Abu Dhabi",
    }

    out: list[str] = []

    def _add(q: str | None) -> None:
        s = (q or "").strip()
        if s and s not in out:
            out.append(s)

    if country_text and not country_is_region and city_en_text:
        _add(f"{city_en_text}, {country_text}")
        _add(f"{city_en_text} {country_text}")
    if country_text and not country_is_region:
        _add(f"{city_text}, {country_text}")
        _add(f"{city_text} {country_text}")
    _add(city_en_text)
    _add(city_text)
    _add(city_alias_en.get(city_text))
    if country_text and not country_is_region and city_alias_en.get(city_text):
        _add(f"{city_alias_en.get(city_text)}, {country_text}")

    return out


def _hotel_expected_country_code(city: str | None, city_en: str | None = None) -> str | None:
    city_text = (city or "").strip()
    mapping = {
        "\ub3c4\ucfc4": "JP",
        "\uc624\uc0ac\uce74": "JP",
        "\ud6c4\ucfe0\uc624\uce74": "JP",
        "\uc0ff\ud3ec\ub85c": "JP",
        "\uc624\ud0a4\ub098\uc640": "JP",
        "\ub098\uace0\uc57c": "JP",
        "\uad50\ud1a0": "JP",
        "\uace0\ubca0": "JP",
        "\ubc29\ucf55": "TH",
        "\ub2e4\ub0ad": "VN",
        "\ub098\ud2b8\ub791": "VN",
        "\uc138\ubd80": "PH",
        "\ubc1c\ub9ac": "ID",
        "\uc2f1\uac00\ud3ec\ub974": "SG",
        "\ud478\ucf13": "TH",
        "\ucf54\ud0c0\ud0a4\ub098\ubc1c\ub8e8": "MY",
        "\ub9c8\ub2d0\ub77c": "PH",
        "\ud558\ub178\uc774": "VN",
        "\ud638\uce58\ubbfc": "VN",
        "\ud64d\ucf69": "HK",
        "\ub9c8\uce74\uc624": "MO",
        "\uc0c1\ud558\uc774": "CN",
        "\ubca0\uc774\uc9d5": "CN",
        "\uad11\uc800\uc6b0": "CN",
        "\uce6d\ub2e4\uc624": "CN",
        "\uad0c": "GU",
        "\uc0ac\uc774\ud310": "MP",
        "\uc2dc\ub4dc\ub2c8": "AU",
        "\uc624\ud074\ub79c\ub4dc": "NZ",
        "\uba5c\ubc84\ub978": "AU",
        "\uace8\ub4dc\ucf54\uc2a4\ud2b8": "AU",
        "\ud558\uc640\uc774": "US",
        "\ub274\uc695": "US",
        "\ub85c\uc2a4\uc564\uc824\ub808\uc2a4": "US",
        "\ub77c\uc2a4\ubca0\uc774\uac70\uc2a4": "US",
        "\uc0cc\ud504\ub780\uc2dc\uc2a4\ucf54": "US",
        "\ud30c\ub9ac": "FR",
        "\ub7f0\ub358": "GB",
        "\ub85c\ub9c8": "IT",
        "\ubc14\ub974\uc140\ub85c\ub098": "ES",
        "\ud504\ub77c\ud558": "CZ",
        "\uc778\ud130\ub77c\ucf04": "CH",
        "\ubca0\ub124\uce58\uc544": "IT",
        "\ud53c\ub80c\uccb4": "IT",
        "\ub450\ubc14\uc774": "AE",
        "\uce74\uc774\ub85c": "EG",
        "\ucf00\uc774\ud504\ud0c0\uc6b4": "ZA",
        "\uc544\ubd80\ub2e4\ube44": "AE",
    }
    if city_text in mapping:
        return mapping.get(city_text)

    city_en_map = {
        "dubai": "AE",
        "abu dhabi": "AE",
        "tokyo": "JP",
        "osaka": "JP",
        "fukuoka": "JP",
        "sapporo": "JP",
        "okinawa": "JP",
        "nagoya": "JP",
        "kyoto": "JP",
        "kobe": "JP",
        "bangkok": "TH",
        "da nang": "VN",
        "nha trang": "VN",
        "cebu": "PH",
        "bali": "ID",
        "singapore": "SG",
        "phuket": "TH",
        "kota kinabalu": "MY",
        "manila": "PH",
        "hanoi": "VN",
        "ho chi minh city": "VN",
        "hong kong": "HK",
        "macau": "MO",
        "shanghai": "CN",
        "beijing": "CN",
        "guangzhou": "CN",
        "qingdao": "CN",
        "guam": "GU",
        "saipan": "MP",
        "sydney": "AU",
        "auckland": "NZ",
        "melbourne": "AU",
        "gold coast": "AU",
        "honolulu": "US",
        "new york": "US",
        "los angeles": "US",
        "las vegas": "US",
        "san francisco": "US",
        "paris": "FR",
        "london": "GB",
        "rome": "IT",
        "barcelona": "ES",
        "prague": "CZ",
        "interlaken": "CH",
        "venice": "IT",
        "florence": "IT",
        "cairo": "EG",
        "cape town": "ZA",
    }
    city_en_key = str(city_en or "").strip().lower()
    return city_en_map.get(city_en_key)


def _hotel_country_code_hint(country: str | None) -> str | None:
    c = (country or "").strip().lower()
    if not c:
        return None
    mapping = {
        "uae": "AE",
        "united arab emirates": "AE",
        "dubai": "AE",
        "\uc544\ub78d\uc5d0\ubbf8\ub9ac\ud2b8": "AE",
        "\uc544\ub78d\uc5d0\ubbf8\ub9ac\ud2b8\uc5f0\ud569": "AE",
        "japan": "JP",
        "\uc77c\ubcf8": "JP",
        "korea": "KR",
        "south korea": "KR",
        "\ub300\ud55c\ubbfc\uad6d": "KR",
        "\ud55c\uad6d": "KR",
        "hong kong": "HK",
        "\ud64d\ucf69": "HK",
        "macau": "MO",
        "\ub9c8\uce74\uc624": "MO",
        "china": "CN",
        "\uc911\uad6d": "CN",
        "thailand": "TH",
        "\ud0dc\uad6d": "TH",
        "vietnam": "VN",
        "\ubca0\ud2b8\ub0a8": "VN",
        "singapore": "SG",
        "\uc2f1\uac00\ud3ec\ub974": "SG",
        "indonesia": "ID",
        "\uc778\ub3c4\ub124\uc2dc\uc544": "ID",
        "philippines": "PH",
        "\ud544\ub9ac\ud540": "PH",
        "france": "FR",
        "\ud504\ub791\uc2a4": "FR",
        "uk": "GB",
        "united kingdom": "GB",
        "\uc601\uad6d": "GB",
        "italy": "IT",
        "\uc774\ud0c8\ub9ac\uc544": "IT",
        "spain": "ES",
        "\uc2a4\ud398\uc778": "ES",
        "usa": "US",
        "united states": "US",
        "\ubbf8\uad6d": "US",
        "australia": "AU",
        "\ud638\uc8fc": "AU",
        "new zealand": "NZ",
        "\ub274\uc9c8\ub79c\ub4dc": "NZ",
    }
    return mapping.get(c)


def _hotel_city_match_tokens(city: str | None) -> set[str]:
    city_text = (city or "").strip()
    if not city_text:
        return set()
    tokens: set[str] = set()
    low = city_text.lower()
    tokens.add(low)
    tokens.add(re.sub(r"\s+", " ", low))
    alias_map = {
        "\ub450\ubc14\uc774": "dubai",
        "\ub3c4\ucfc4": "tokyo",
        "\uc624\uc0ac\uce74": "osaka",
        "\ud6c4\ucfe0\uc624\uce74": "fukuoka",
        "\uc0ff\ud3ec\ub85c": "sapporo",
        "\ubc29\ucf55": "bangkok",
        "\ud638\uce58\ubbfc": "ho chi minh city",
        "\ub2e4\ub0ad": "da nang",
        "\ub098\ud2b8\ub791": "nha trang",
        "\uc138\ubd80": "cebu",
        "\ud64d\ucf69": "hong kong",
        "\ub9c8\uce74\uc624": "macau",
        "\uc0c1\ud558\uc774": "shanghai",
        "\ubca0\uc774\uc9d5": "beijing",
        "\uc2f1\uac00\ud3ec\ub974": "singapore",
        "\ud478\ucf13": "phuket",
        "\ud30c\ub9ac": "paris",
        "\ub7f0\ub358": "london",
    }
    alias = alias_map.get(city_text)
    if alias:
        tokens.add(alias.lower())
    return {t for t in tokens if t and len(t) >= 2}


def _pick_best_booking_destination(dest_rows: list[dict], city: str | None, country: str | None = None) -> dict | None:
    if not isinstance(dest_rows, list) or not dest_rows:
        return None
    city_tokens = _hotel_city_match_tokens(city)
    expected_cc = (_hotel_expected_country_code(city, city_en=city) or _hotel_country_code_hint(country) or "").upper()

    def _row_text(row: dict) -> str:
        return " ".join(
            str(row.get(k) or "")
            for k in ("city_name", "name", "label", "dest_name", "region", "country", "search_string")
        ).lower()

    def _row_cc(row: dict) -> str:
        return str(
            row.get("countrycode")
            or row.get("country_code")
            or row.get("cc1")
            or row.get("countryCode")
            or ""
        ).upper()

    best = None
    best_score = -10**9
    for row in dest_rows:
        if not isinstance(row, dict):
            continue
        score = 0
        txt = _row_text(row)
        cc = _row_cc(row)
        matched_city = any(token in txt for token in city_tokens)
        if matched_city:
            score += 14
        if expected_cc and cc == expected_cc:
            score += 18
        elif expected_cc and cc and cc != expected_cc:
            score -= 10
        st = str(row.get("search_type") or "").upper()
        if st == "CITY":
            score += 7
        elif st in {"DISTRICT", "LANDMARK"}:
            score += 2
        elif st == "HOTEL":
            score -= 8
        if not matched_city and expected_cc and cc != expected_cc:
            score -= 4
        if score > best_score:
            best = row
            best_score = score
    return best if isinstance(best, dict) else (dest_rows[0] if isinstance(dest_rows[0], dict) else None)


def _is_plausible_booking_destination(row: dict, city: str | None, country: str | None, city_en: str | None = None) -> bool:
    if not isinstance(row, dict):
        return False
    expected_cc = (_hotel_expected_country_code(city, city_en=city_en) or _hotel_country_code_hint(country) or "").upper()
    row_cc = str(
        row.get("countrycode")
        or row.get("country_code")
        or row.get("cc1")
        or row.get("countryCode")
        or ""
    ).upper()
    if expected_cc and row_cc and row_cc != expected_cc:
        return False

    st = str(row.get("search_type") or "").upper()
    text = " ".join(
        str(row.get(k) or "")
        for k in ("city_name", "name", "label", "dest_name", "region", "country", "search_string")
    ).lower()
    city_tokens = _hotel_city_match_tokens(city) | _hotel_city_match_tokens(city_en)
    token_match = any(tok in text for tok in city_tokens) if city_tokens else False

    # Block unrelated single-hotel hits (common false positive when destination search is noisy).
    if st == "HOTEL" and not token_match:
        return False
    # If expected country is known but row has no country code, at least require city token match.
    if expected_cc and not row_cc and not token_match:
        return False
    return True


app = FastAPI()


@app.on_event("startup")
def _clear_sessions_on_startup():
    # Optional: only clear sessions on startup when explicitly requested.
    if str(os.getenv("CLEAR_SESSIONS_ON_STARTUP", "0")).strip() in {"1", "true", "TRUE", "yes", "on"}:
        clear_all_sessions()


@app.middleware("http")
async def _normalize_localhost(request: Request, call_next):
    # Prevent split login cookies between localhost and 127.0.0.1.
    host = (request.url.hostname or "").strip().lower()
    if host == "localhost":
        port = request.url.port or 8000
        target = f"{request.url.scheme}://127.0.0.1:{port}{request.url.path}"
        if request.url.query:
            target += f"?{request.url.query}"
        return RedirectResponse(url=target, status_code=307)
    return await call_next(request)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_nickname_from_request(request: Request) -> str | None:
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
    if value is None:
        return None
    if isinstance(value, str) and value.strip() == "":
        return None
    try:
        return float(value)
    except Exception:
        return None


def _haversine_meters(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    import math

    r = 6371000.0
    p1 = math.radians(lat1)
    p2 = math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _calc_nights(checkin: str | None, checkout: str | None) -> int | None:
    try:
        if not checkin or not checkout:
            return None
        d1 = datetime.datetime.strptime(checkin, "%Y-%m-%d").date()
        d2 = datetime.datetime.strptime(checkout, "%Y-%m-%d").date()
        nights = (d2 - d1).days
        return nights if nights > 0 else None
    except Exception:
        return None


def _price_per_night(total_price, nights: int | None) -> int | None:
    try:
        if total_price is None or not nights or nights <= 0:
            return None
        return int(round(float(total_price) / nights))
    except Exception:
        return None


def _coerce_number(value):
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        s = value.strip().replace(",", "")
        m = re.search(r"(\d+(?:\.\d+)?)", s)
        if m:
            try:
                return float(m.group(1))
            except Exception:
                return None
    return None


def _extract_room_offers_from_booking_detail(raw, fallback_hotel: dict | None = None) -> list[dict]:
    offers: list[dict] = []
    seen = set()
    room_name_pat = re.compile(
        r"(room|suite|studio|double|twin|single|deluxe|family|queen|king|standard|superior|금연|흡연|블루룸|트윈룸|싱글룸|패밀리룸|스위트|디럭스)",
        re.IGNORECASE,
    )
    amenity_like_pat = re.compile(
        r"(private|모닝콜|공기청정기|콘센트|에어컨|평면\s*tv|헤어드라이어|소파|비데|무료\s*주차)",
        re.IGNORECASE,
    )

    def _pick_price(d: dict) -> tuple[float | None, float | None, str | None]:
        cur = None
        orig = None
        ccy = None
        candidates = []
        if not isinstance(d, dict):
            return None, None, None

        for k in ("priceBreakdown", "price", "pricing", "grossPrice", "compositePriceBreakdown"):
            v = d.get(k)
            if isinstance(v, dict):
                candidates.append(v)

        candidates.append(d)
        for obj in candidates:
            if not isinstance(obj, dict):
                continue
            for key in ("grossPrice", "price", "currentPrice", "discountedPrice", "book", "base"):
                v = obj.get(key)
                if isinstance(v, dict):
                    if cur is None:
                        cur = _coerce_number(v.get("value") or v.get("amount") or v.get("price"))
                    ccy = ccy or v.get("currency")
            if cur is None:
                cur = _coerce_number(
                    obj.get("value")
                    or obj.get("amount")
                    or obj.get("current")
                    or obj.get("current_price")
                    or obj.get("price")
                )
            if orig is None:
                orig = _coerce_number(
                    obj.get("original")
                    or obj.get("originalPrice")
                    or obj.get("strikethrough")
                    or obj.get("wasPrice")
                )
            ccy = ccy or obj.get("currency") or obj.get("currency_code")
        return cur, orig, ccy

    def _collect_texts(value) -> list[str]:
        out = []
        if isinstance(value, str):
            t = value.strip()
            if t:
                out.append(t)
        elif isinstance(value, list):
            for x in value:
                out.extend(_collect_texts(x))
        elif isinstance(value, dict):
            for k in ("text", "label", "name", "title", "description", "benefit", "explanation"):
                if k in value:
                    out.extend(_collect_texts(value.get(k)))
        return out

    def _is_sold_out(node: dict) -> bool | None:
        if not isinstance(node, dict):
            return None
        bool_keys = [
            "isSoldOut", "soldOut", "is_sold_out", "closed", "isClosed", "isAvailable", "available",
        ]
        for k in bool_keys:
            if k in node:
                v = node.get(k)
                if isinstance(v, bool):
                    if k.lower() in ("isavailable", "available"):
                        return not v
                    return v
        joined = " ".join(_collect_texts(node)).lower()
        if any(x in joined for x in ["sold out", "매진", "마감", "판매 완료", "예약 불가"]):
            return True
        return None

    def _collect_photos(node: dict) -> list[str]:
        urls = []
        for key in ("photoUrls", "photos", "images", "gallery"):
            v = node.get(key)
            if isinstance(v, list):
                for item in v:
                    if isinstance(item, str) and item.strip():
                        urls.append(item.strip())
                    elif isinstance(item, dict):
                        for ik in ("url", "uri", "src"):
                            iv = item.get(ik)
                            if isinstance(iv, str) and iv.strip():
                                urls.append(iv.strip())
                                break
        return urls

    def _offer_from_node(node: dict):
        if not isinstance(node, dict):
            return
        name = None
        name_key = None
        for k in ("roomName", "name", "title", "displayName", "productName", "rateName"):
            v = node.get(k)
            if isinstance(v, str) and v.strip():
                name = v.strip()
                name_key = k
                break

        cur, orig, ccy = _pick_price(node)
        sold = _is_sold_out(node)
        has_price_struct = any(k in node for k in ("price", "priceBreakdown", "pricing", "grossPrice", "currentPrice", "discountedPrice", "compositePriceBreakdown"))

        feature_texts = []
        for fk in ("benefits", "facilities", "features", "highlights", "policy", "policies", "tags", "badges"):
            if fk in node:
                feature_texts.extend(_collect_texts(node.get(fk)))
        # Keep unique + short list
        dedup_features = []
        seen_ft = set()
        for t in feature_texts:
            key = re.sub(r"\s+", " ", t).strip().lower()
            if not key or key in seen_ft:
                continue
            seen_ft.add(key)
            dedup_features.append(t)
            if len(dedup_features) >= 6:
                break

        photos = _collect_photos(node)
        room_size = None
        for txt in dedup_features + _collect_texts(node):
            m = re.search(r"(\d+(?:\.\d+)?)\s*(?:㎡|m2|m²)", txt, flags=re.IGNORECASE)
            if m:
                room_size = m.group(1)
                break

        # Only accept nodes that look room/offer-like.
        is_roomish = False
        hay = " ".join([name or ""] + dedup_features + _collect_texts(node)[:10]).lower()
        if any(x in hay for x in ["room", "객실", "금연", "smoking", "침대", "bed", "twin", "double", "suite"]):
            is_roomish = True
        if name and (cur is not None or sold is not None):
            is_roomish = True
        name_is_roomish = bool(name and room_name_pat.search(name))
        name_looks_amenity = bool(name and amenity_like_pat.search(name))
        # Avoid facility/amenity nodes that accidentally contain "bed"/room-like words.
        if name_looks_amenity and cur is None and sold is None and not has_price_struct:
            return
        # Stronger guard: generic "name/title" nodes with no pricing/availability are usually not room offers.
        if name and not name_is_roomish and name_key in ("name", "title") and cur is None and sold is None and not has_price_struct:
            return
        # If a node has no pricing/availability signals, only accept explicit room names.
        if name and cur is None and sold is None and not has_price_struct and not name_is_roomish:
            return
        if not is_roomish:
            return

        # Skip very generic hotel-level nodes.
        if name and fallback_hotel and (name.strip() == str(fallback_hotel.get("name") or "").strip()):
            return
        if name and len(name.strip()) <= 2:
            return

        key = (name or "", int(cur) if cur else None, bool(sold))
        if key in seen:
            return
        seen.add(key)
        offers.append(
            {
                "name": name or "객실 옵션",
                "price": int(cur) if cur is not None else None,
                "price_original": int(orig) if orig is not None else None,
                "currency": ccy or (fallback_hotel or {}).get("currency") or "KRW",
                "sold_out": bool(sold) if sold is not None else False,
                "features": dedup_features,
                "photos": photos[:4],
                "room_size_sqm": room_size,
            }
        )

    def _walk(node):
        if isinstance(node, dict):
            _offer_from_node(node)
            for v in node.values():
                _walk(v)
        elif isinstance(node, list):
            for item in node:
                _walk(item)

    _walk(raw)

    # If parsed nodes exist but none has a price, prefer a small set of likely room names and attach fallback base price.
    priced_count = sum(1 for o in offers if o.get("price"))
    if offers and priced_count == 0 and isinstance(fallback_hotel, dict):
        preferred = [o for o in offers if room_name_pat.search(o.get("name") or "")]
        offers = preferred[:6] if preferred else offers[:4]
        base_price = fallback_hotel.get("price")
        if base_price:
            for i, o in enumerate(offers):
                if not o.get("sold_out"):
                    o["price"] = int(base_price)
                    if fallback_hotel.get("price_original"):
                        o["price_original"] = int(fallback_hotel.get("price_original"))
                    o["is_price_fallback"] = True
                    break

    # Fallback synthetic room summary card if no room-level products were found.
    if not offers and isinstance(fallback_hotel, dict):
        features = []
        rf = fallback_hotel.get("room_facts") or {}
        if rf.get("area_sqm"):
            features.append(f"객실/숙소 크기 {rf['area_sqm']}㎡")
        if rf.get("beds"):
            features.append(f"침대 {rf['beds']}개")
        if rf.get("bedrooms"):
            features.append(f"침실 {rf['bedrooms']}개")
        if rf.get("bathrooms"):
            features.append(f"욕실 {rf['bathrooms']}개")
        for p in (fallback_hotel.get("policy_badges") or [])[:3]:
            if isinstance(p, str):
                features.append(p)
        if fallback_hotel.get("rooms_left"):
            features.append(f"남은 객실/옵션 {fallback_hotel.get('rooms_left')}개")

        offers.append(
            {
                "name": (fallback_hotel.get("property_type") or "객실 옵션"),
                "price": fallback_hotel.get("price"),
                "price_original": fallback_hotel.get("price_original"),
                "currency": fallback_hotel.get("currency") or "KRW",
                "sold_out": False,
                "features": features[:6],
                "photos": (fallback_hotel.get("photo_gallery") or [])[:3],
                "room_size_sqm": rf.get("area_sqm"),
                "is_fallback": True,
            }
        )

    # Sort available first, then cheaper first.
    offers.sort(key=lambda x: (1 if x.get("sold_out") else 0, x.get("price") or 10**12))
    return offers[:12]


def _as_text(value) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        return value
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, list):
        parts = [v for v in value if isinstance(v, str) and v.strip()]
        return " ".join(parts) if parts else None
    if isinstance(value, dict):
        for key in ("name", "label", "title"):
            v = value.get(key)
            if isinstance(v, str) and v.strip():
                return v
    return None


def _clean_hotel_title(text: str | None) -> str | None:
    text = _as_text(text)
    if not text:
        return None
    text = text.replace("\n", " ").strip()
    # Remove common promo prefixes
    promo_patterns = [
        r"\bNEW\s*OPEN\b",
        r"\bOPEN\b",
        r"\bOPEN!\b",
        r"\bHOT\s+DEAL\b",
        r"\bSPECIAL\s+OFFER\b",
    ]
    for pat in promo_patterns:
        text = re.sub(pat, "", text, flags=re.IGNORECASE).strip()

    # Remove leading code-like tokens (e.g., sen1002, A1234)
    tokens = text.split()
    while tokens and re.match(r"^[A-Za-z]{1,6}\d{2,}$", tokens[0]):
        tokens.pop(0)
    text = " ".join(tokens).strip()

    for sep in (" - ", " | ", " 쨌 ", "쨌"):
        if sep in text:
            text = text.split(sep, 1)[0].strip()
    # Trim obvious room/bed descriptors that occasionally leak into property titles.
    text = re.sub(r"(침대\s*\d+\s*개.*)$", "", text, flags=re.IGNORECASE).strip()
    text = re.sub(r"(\b\d+\s*beds?\b.*)$", "", text, flags=re.IGNORECASE).strip()
    text = re.sub(r"(\b(room|private house|whole house|apartment)\b.*)$", "", text, flags=re.IGNORECASE).strip()
    # Trim trailing distance/transport descriptors
    text = re.sub(r"(도보|지하철|역\s*근처).*$", "", text, flags=re.IGNORECASE).strip()
    text = re.sub(r"(walk|minutes?|mins?|station|metro).*$", "", text, flags=re.IGNORECASE).strip()
    if len(text) > 60:
        text = text[:60].rstrip()
    return text or None


def _normalize_dedupe_name(text: str | None) -> str | None:
    text = _clean_hotel_title(text)
    if not text:
        return None
    text = re.sub(r"\b\d{1,4}\b", "", text).strip()
    text = re.sub(r"\s{2,}", " ", text).strip()
    return text or None
def parse_amadeus_hotels(amadeus_result: dict) -> list[dict]:
    hotels = []
    if amadeus_result and amadeus_result.get("error"):
        details = amadeus_result.get("details", "")
        msg = f"Amadeus API error: {amadeus_result.get('error')}"
        if details:
            msg += f" | {details[:180]}"
        hotels.append({"name": msg, "address": "", "price": None, "source": "Amadeus"})
        return hotels

    rows = amadeus_result.get("data", []) if isinstance(amadeus_result, dict) else []
    if not isinstance(rows, list):
        hotels.append({"name": "Amadeus API invalid data format", "address": "", "price": None, "source": "Amadeus"})
        return hotels

    for h in rows:
        if not isinstance(h, dict):
            continue

        hotel_obj = h.get("hotel", {}) if isinstance(h.get("hotel"), dict) else {}
        hotel_name = hotel_obj.get("name") or h.get("name") or h.get("hotelName") or "Unnamed hotel"

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

        hotels.append(
            {
                "name": hotel_name,
                "address": address,
                "price": price,
                "currency": currency,
                "image": image,
                "source": "Amadeus",
            }
        )

    if not hotels:
        hotels.append({"name": "Amadeus API returned no results", "address": "", "price": None, "source": "Amadeus"})
    return hotels


def parse_booking_hotels(booking_result: dict) -> list[dict]:
    hotels = []
    if booking_result and booking_result.get("error"):
        err_text = f"{booking_result.get('error', '')} {booking_result.get('details', '')}".lower()
        if any(k in err_text for k in ("중복 발생", "duplicate", "position", "invalid json", "unexpected token")):
            # Treat malformed upstream payload errors as transient and allow caller fallback path.
            return hotels
        details = booking_result.get("details", "")
        msg = f"Booking API error: {booking_result.get('error')}"
        if details:
            msg += f" | {details[:180]}"
        hotels.append({"name": msg, "address": "", "price": None, "source": "Booking"})
        return hotels

    rows_obj = booking_result.get("data", []) if isinstance(booking_result, dict) else []
    rows = rows_obj.get("hotels", []) if isinstance(rows_obj, dict) else rows_obj
    if not isinstance(rows, list):
        return hotels

    def _num_only(text: str) -> int | None:
        digits = "".join([c for c in text if c.isdigit()])
        return int(digits) if digits else None

    def _extract_prices_from_label(label: str) -> tuple[int | None, int | None]:
        if not label:
            return None, None
        # Example: "Original price 664174 KRW. Current price 478374 KRW."
        original = None
        current = None
        if "Original price" in label and "Current price" in label:
            try:
                seg1 = label.split("Original price", 1)[1]
                original = _num_only(seg1)
                seg2 = label.split("Current price", 1)[1]
                current = _num_only(seg2)
            except Exception:
                return None, None
        return original, current

    def _extract_rooms_left(label: str) -> int | None:
        if not label:
            return None
        patterns = [
            r"Only\s+(\d+)\s+left",
            r"남은\s*(?:객실|옵션)?\s*(\d+)\s*개",
            r"옵션\s*(\d+)\s*개",
            r"残り\s*(\d+)\s*(?:室|件)",
            r"剩余\s*(\d+)\s*(?:间|个)",
        ]
        for pat in patterns:
            match = re.search(pat, label, flags=re.IGNORECASE)
            if not match:
                continue
            try:
                return int(match.group(1))
            except Exception:
                continue
        return None

    def _name_from_accessibility_label(label: str) -> str | None:
        if not label:
            return None
        first_line = label.splitlines()[0].strip() if label.splitlines() else label.strip()
        first_line = first_line.rstrip(".")
        return _clean_hotel_title(first_line)

    def _split_label_lines(label: str) -> list[str]:
        if not label:
            return []
        out = []
        for line in label.replace("\r", "\n").split("\n"):
            line = re.sub(r"\s+", " ", line).strip()
            if line:
                out.append(line)
        return out

    def _is_descriptive_listing_title(text: str | None) -> bool:
        text = _as_text(text)
        if not isinstance(text, str) or not text.strip():
            return False
        t = text.lower()
        brand_keywords = ["hotel", "inn", "hostel", "residence", "ryokan", "resort"]
        if any(k in t for k in brand_keywords):
            return False
        desc_hits = sum(
            1
            for k in ["modern", "cozy", "private", "whole", "near", "style", "renovated", "house", "apartment", "villa"]
            if k in t
        )
        return desc_hits >= 2

    def _collect_photo_urls(hotel_row: dict, prop: dict) -> list[str]:
        urls: list[str] = []
        def _photo_key(u: str) -> str:
            x = (u or "").strip().lower()
            if not x:
                return ""
            x = x.split("?", 1)[0]
            x = re.sub(r"/(?:max|square|crop)\d+(?:x\d+)?/", "/<size>/", x)
            x = re.sub(r"/\d{2,5}x\d{2,5}/", "/<size>/", x)
            return x
        for source in (hotel_row, prop):
            for key in ("photoUrls", "photos", "images"):
                value = source.get(key)
                if isinstance(value, list):
                    for item in value:
                        if isinstance(item, str) and item.strip():
                            urls.append(item.strip())
                        elif isinstance(item, dict):
                            for ik in ("url", "uri", "src"):
                                iv = item.get(ik)
                                if isinstance(iv, str) and iv.strip():
                                    urls.append(iv.strip())
                                    break
        deduped = []
        seen = set()
        for u in urls:
            k = _photo_key(u)
            if not k or k in seen:
                continue
            seen.add(k)
            deduped.append(u)
        return deduped[:12]

    def _extract_label_highlights(label: str) -> list[str]:
        lines = _split_label_lines(label)
        if not lines:
            return []
        highlights: list[str] = []
        skip_patterns = [
            r"^booking\.com",
            r"\bkrw\b",
            r"기존 요금",
            r"현재 요금",
            r"original price",
            r"current price",
            r"남은 옵션",
        ]
        for line in lines[1:]:
            lowered = line.lower()
            try:
                is_skip = any(re.search(p, lowered, flags=re.IGNORECASE) for p in skip_patterns)
            except re.error:
                is_skip = False
            if is_skip:
                continue
            highlights.append(line)
            if len(highlights) >= 6:
                break
        return highlights

    def _extract_room_facts(label: str) -> dict:
        facts = {
            "area_sqm": None,
            "beds": None,
            "bedrooms": None,
            "living_rooms": None,
            "bathrooms": None,
        }
        if not label:
            return facts
        compact = label.replace(",", " ")
        area_match = re.search(r"(\d+(?:\.\d+)?)\s*(?:m²|m2|sqm)", compact, flags=re.IGNORECASE)
        if area_match:
            facts["area_sqm"] = area_match.group(1)
        patterns = {
            "beds": [r"침대\s*(\d+)\s*개", r"(\d+)\s*beds?\b"],
            "bedrooms": [r"침실\s*(\d+)\s*개", r"(\d+)\s*bedrooms?\b"],
            "living_rooms": [r"거실\s*(\d+)\s*개", r"(\d+)\s*living rooms?\b"],
            "bathrooms": [r"욕실\s*(\d+)\s*개", r"(\d+)\s*bathrooms?\b"],
        }
        for key, pats in patterns.items():
            for pat in pats:
                m = re.search(pat, compact, flags=re.IGNORECASE)
                if m:
                    facts[key] = m.group(1)
                    break
        return facts

    def _extract_policy_badges(label: str) -> list[str]:
        if not label:
            return []
        checks = [
            ("무료 취소", [r"무료 취소", r"free cancellation"]),
            ("조식 포함 가능", [r"조식", r"breakfast"]),
            ("사전 결제 불필요", [r"결제 불필요", r"no prepayment"]),
            ("환불 불가 조건", [r"환불 불가", r"non[- ]refundable"]),
            ("무료 Wi-Fi", [r"무료 wi-?fi", r"free wi-?fi"]),
            ("사우나/스파 옵션", [r"사우나", r"\bspa\b"]),
        ]
        found = []
        for label_ko, pats in checks:
            if any(re.search(p, label, flags=re.IGNORECASE) for p in pats):
                found.append(label_ko)
        return found

    def _collect_amenities(hotel_row: dict, prop: dict, pb: dict, label: str) -> list[str]:
        items: list[str] = []
        for badge in (pb.get("benefitBadges") or []):
            if isinstance(badge, dict):
                txt = _as_text(badge.get("text") or badge.get("explanation"))
                if isinstance(txt, str) and txt.strip():
                    items.append(txt.strip())

        candidate_lists = [
            prop.get("mainFacilities"),
            prop.get("facilities"),
            hotel_row.get("facilities"),
            prop.get("facilityTags"),
        ]
        for seq in candidate_lists:
            if not isinstance(seq, list):
                continue
            for x in seq:
                if isinstance(x, str) and x.strip():
                    items.append(x.strip())
                elif isinstance(x, dict):
                    txt = _as_text(x.get("name") or x.get("label") or x.get("text") or x.get("title"))
                    if isinstance(txt, str) and txt.strip():
                        items.append(txt.strip())

        # Label-derived fallback amenities (works even when API schema differs)
        label_amenities = [
            ("무료 Wi-Fi", [r"무료 wi-?fi", r"free wi-?fi"]),
            ("사우나", [r"사우나", r"sauna"]),
            ("스파", [r"\bspa\b"]),
            ("무료 취소", [r"무료 취소", r"free cancellation"]),
            ("조식", [r"조식", r"breakfast"]),
            ("주방", [r"주방", r"kitchen"]),
            ("세탁기", [r"세탁기", r"washing machine"]),
            ("에어컨", [r"에어컨", r"air conditioning"]),
        ]
        for amenity_name, pats in label_amenities:
            if any(re.search(p, label or "", flags=re.IGNORECASE) for p in pats):
                items.append(amenity_name)

        deduped = []
        seen = set()
        for item in items:
            key = re.sub(r"\s+", " ", str(item)).strip().lower()
            if not key or key in seen:
                continue
            seen.add(key)
            deduped.append(str(item).strip())
        return deduped[:18]

    def _extract_property_type(title: str | None, label: str | None) -> str | None:
        text = f"{_as_text(title) or ''} {_as_text(label) or ''}".lower()
        mapping = [
            ("호텔", [" hotel", "호텔"]),
            ("아파트", ["apartment", "아파트"]),
            ("빌라/하우스", ["villa", "house", "민박"]),
            ("게스트하우스", ["guesthouse", "guest house"]),
            ("료칸", ["ryokan", "료칸"]),
        ]
        for label_ko, keys in mapping:
            if any(k.lower() in text for k in keys):
                return label_ko
        return None

    def _format_distance(label: str, dist: str | None) -> str | None:
        if not label:
            return None
        if dist:
            if "m" in dist or "km" in dist:
                return f"{label} · {dist}"
            return f"{label} · {dist}m"
        return label

    for h in rows:
        if not isinstance(h, dict):
            continue
        # Upstream occasionally returns provider error payloads mixed into rows.
        row_err_text = (
            f"{h.get('error', '')} {h.get('message', '')} {h.get('name', '')} {h.get('title', '')}"
        ).lower()
        if any(k in row_err_text for k in ("예약 api 오류", "중복 발생", "duplicate", "position", "invalid json", "unexpected token")):
            continue
        prop = h.get("property", {}) if isinstance(h.get("property"), dict) else {}
        label_text = h.get("accessibilityLabel") if isinstance(h.get("accessibilityLabel"), str) else ""
        label_name = _name_from_accessibility_label(label_text)
        name_ko = _clean_hotel_title(prop.get("ko_name")) or _clean_hotel_title(h.get("ko_name")) or _clean_hotel_title(h.get("name_ko"))
        name_en = (
            _clean_hotel_title(prop.get("name"))
            or _clean_hotel_title(h.get("hotel_name"))
            or _clean_hotel_title(h.get("name"))
        )
        if not name_en and label_name:
            name_en = label_name
        hotel_name = name_ko or name_en or "Unnamed hotel"
        address = h.get("address") or prop.get("wishlistName") or ""

        price = h.get("price")
        if price is None:
            price = h.get("priceBreakdown", {}).get("grossPrice", {}).get("value")
        if price is None:
            price = prop.get("priceBreakdown", {}).get("grossPrice", {}).get("value")

        pb = h.get("priceBreakdown", {}) if isinstance(h.get("priceBreakdown"), dict) else {}
        if not pb:
            pb = prop.get("priceBreakdown", {}) if isinstance(prop.get("priceBreakdown"), dict) else {}
        price_current = pb.get("grossPrice", {}).get("value") if isinstance(pb.get("grossPrice"), dict) else None
        price_original = pb.get("strikethroughPrice", {}).get("value") if isinstance(pb.get("strikethroughPrice"), dict) else None
        if price_original is None:
            price_original = pb.get("strikeThroughPrice", {}).get("value") if isinstance(pb.get("strikeThroughPrice"), dict) else None
        if price_current is None:
            price_current = price

        if price_original is None and label_text:
            label_original, label_current = _extract_prices_from_label(label_text)
            if price_current is None and label_current is not None:
                price_current = label_current
            price_original = label_original

        if price_current is None:
            price_current = price
        discount_percent = None
        if price_original and price_current and price_original > price_current:
            try:
                discount_percent = int(round((price_original - price_current) / price_original * 100))
            except Exception:
                discount_percent = None

        review_score = prop.get("reviewScore") or h.get("reviewScore")
        review_count = prop.get("reviewCount") or h.get("reviewCount")
        review_word = prop.get("reviewScoreWord") or h.get("reviewScoreWord")

        distance = (
            prop.get("distanceToCenter")
            or h.get("distanceToCenter")
            or prop.get("distance_to_cc")
            or h.get("distance_to_cc")
        )

        landmarks = prop.get("landmarks") or h.get("landmarks") or []
        nearby = []
        nearby_points = []
        if isinstance(landmarks, list):
            for idx, lm in enumerate(landmarks[:8]):
                if not isinstance(lm, dict):
                    continue
                label = lm.get("label") or lm.get("name")
                dist = lm.get("distance")
                formatted = _format_distance(label, dist)
                if formatted:
                    if idx < 2:
                        nearby.append(formatted)
                    nearby_points.append({"name": label, "distance": dist, "label": formatted})

        rooms_left = (
            h.get("available_rooms")
            or h.get("roomsLeft")
            or prop.get("availableRooms")
            or prop.get("roomsLeft")
            or _extract_rooms_left(label_text)
        )

        image = h.get("main_photo_url")
        if not image:
            photo_urls = h.get("photoUrls", [])
            if isinstance(photo_urls, list) and photo_urls:
                image = photo_urls[0]
        if not image:
            photo_urls = prop.get("photoUrls", [])
            if isinstance(photo_urls, list) and photo_urls:
                image = photo_urls[0]
        photo_gallery = _collect_photo_urls(h, prop)
        if not image and photo_gallery:
            image = photo_gallery[0]

        hotel_id = h.get("hotel_id") or h.get("hotelId") or prop.get("id")
        checkin_info = prop.get("checkin", {}) if isinstance(prop.get("checkin"), dict) else {}
        checkout_info = prop.get("checkout", {}) if isinstance(prop.get("checkout"), dict) else {}
        hotel_url = (
            h.get("url")
            or h.get("hotel_url")
            or h.get("hotelUrl")
            or prop.get("url")
            or prop.get("hotelUrl")
            or prop.get("checkoutUrl")
        )
        room_facts = _extract_room_facts(label_text)
        highlights = _extract_label_highlights(label_text)
        policy_badges = _extract_policy_badges(label_text)
        amenities = _collect_amenities(h, prop, pb, label_text)
        property_type = _extract_property_type(name_en or hotel_name, label_text)
        title_is_descriptive = _is_descriptive_listing_title(name_en or hotel_name)
        location_score = prop.get("reviewLocationScore") or h.get("reviewLocationScore")
        review_breakdown = prop.get("reviewSubscores") or h.get("reviewSubscores") or []

        hotels.append(
            {
                "hotel_id": hotel_id,
                "name": hotel_name,
                "name_ko": name_ko,
                "name_en": name_en,
                "dedupe_key": _normalize_dedupe_name(hotel_name),
                "address": address,
                "price": price_current,
                "price_original": price_original,
                "discount_percent": discount_percent,
                "currency": "KRW",
                "image": image,
                "source": "Booking",
                "review_score": review_score,
                "review_count": review_count,
                "review_word": review_word,
                "distance": distance,
                "nearby": nearby,
                "nearby_points": nearby_points,
                "rooms_left": rooms_left,
                "stars": prop.get("propertyClass") or prop.get("qualityClass") or h.get("propertyClass"),
                "latitude": prop.get("latitude") or h.get("latitude"),
                "longitude": prop.get("longitude") or h.get("longitude"),
                "checkin_from": checkin_info.get("fromTime"),
                "checkin_until": checkin_info.get("untilTime"),
                "checkout_from": checkout_info.get("fromTime"),
                "checkout_until": checkout_info.get("untilTime"),
                "hotel_url": hotel_url,
                "label_text": label_text,
                "photo_gallery": photo_gallery,
                "highlights": highlights,
                "policy_badges": policy_badges,
                "amenities": amenities,
                "property_type": property_type,
                "room_facts": room_facts,
                "title_is_descriptive": title_is_descriptive,
                "location_score": location_score,
                "review_breakdown": review_breakdown if isinstance(review_breakdown, list) else [],
            }
        )

    return hotels


def dedupe_hotels(hotels: list[dict]) -> list[dict]:
    seen = set()
    out = []
    for h in hotels:
        key = (h.get("dedupe_key") or h.get("name"), h.get("address"), h.get("source"))
        if key in seen:
            continue
        seen.add(key)
        out.append(h)
    return out


def _is_booking_error_row(h: dict) -> bool:
    if not isinstance(h, dict):
        return True
    if str(h.get("source") or "").strip().lower() != "booking":
        return False
    name = str(h.get("name") or "").strip().lower()
    if not name:
        return True
    return (
        name.startswith("booking api error")
        or name.startswith("예약 api 오류")
        or "중복 발생" in name
        or "duplicate" in name
        or "position" in name
        or "destination not found" in name
        or "destination id not found" in name
    )


def _has_real_booking_hotels(rows: list[dict]) -> bool:
    if not isinstance(rows, list):
        return False
    for h in rows:
        if isinstance(h, dict) and not _is_booking_error_row(h):
            return True
    return False


# DB table bootstrap
Base.metadata.create_all(bind=engine)

# Template/static setup
templates = Jinja2Templates(directory="app/templates")
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, "static")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

# Routers
app.include_router(main_router)
app.include_router(rag_router)
app.include_router(flight_chat_router)
app.include_router(rental_router)
app.include_router(saved_items_router)
app.include_router(group_buy_router)




@app.post("/api/verify-password")
def api_verify_password(request: Request, payload: dict, db: Session = Depends(get_db)):
    session_token = request.cookies.get("session_token")
    user_id = get_user_id_from_session(session_token) if session_token else None
    if not user_id:
        return {"ok": False}
    user = db.query(User).filter(User.id == int(user_id)).first()
    if not user:
        return {"ok": False}
    password = (payload or {}).get("password") or ""
    ok, _ = _verify_password(password, user.password)
    return {"ok": bool(ok)}


@app.post("/api/update-profile")
def api_update_profile(request: Request, payload: dict, db: Session = Depends(get_db)):
    session_token = request.cookies.get("session_token")
    user_id = get_user_id_from_session(session_token) if session_token else None
    if not user_id:
        return {"ok": False, "error_code": "NOT_LOGGED_IN", "error": "로그인이 필요합니다."}

    user = db.query(User).filter(User.id == int(user_id)).first()
    if not user:
        return {"ok": False, "error_code": "USER_NOT_FOUND", "error": "사용자를 찾을 수 없습니다."}

    password = (payload or {}).get("password") or ""
    ok, _ = _verify_password(password, user.password)
    if not ok:
        return {"ok": False, "error_code": "PASSWORD_INVALID", "error": "비밀번호가 올바르지 않습니다."}

    nickname = (payload or {}).get("nickname") or user.nickname
    email = (payload or {}).get("email") or user.email
    phone = (payload or {}).get("phone") or user.phone

    if email and email != user.email:
        exists = db.query(User).filter(User.email == email).first()
        if exists:
            return {"ok": False, "error_code": "EMAIL_EXISTS", "error": "이미 사용 중인 이메일입니다."}
    if phone and phone != user.phone:
        exists = db.query(User).filter(User.phone == phone).first()
        if exists:
            return {"ok": False, "error_code": "PHONE_EXISTS", "error": "이미 사용 중인 휴대폰 번호입니다."}

    user.nickname = nickname
    user.email = email
    user.phone = phone
    db.commit()

    return {
        "ok": True,
        "user": {
            "id": user.id,
            "name": user.name,
            "nickname": user.nickname,
            "email": user.email,
            "phone": user.phone,
        },
    }


@app.get("/api/me")
def api_me(request: Request, db: Session = Depends(get_db)):
    session_token = request.cookies.get("session_token")
    user_id = get_user_id_from_session(session_token) if session_token else None
    if not user_id:
        return {"ok": False, "user": None}
    user = db.query(User).filter(User.id == int(user_id)).first()
    if not user:
        return {"ok": False, "user": None}
    return {
        "ok": True,
        "user": {
            "id": user.id,
            "name": user.name or "",
            "nickname": user.nickname or "",
            "email": user.email or "",
            "phone": user.phone or "",
        },
    }


@app.get("/api/bookings")
def api_bookings(request: Request, limit: int = Query(100, ge=1, le=200)):
    session_token = request.cookies.get("session_token")
    user_id = get_user_id_from_session(session_token) if session_token else None
    if not user_id:
        raise HTTPException(status_code=401, detail="LOGIN_REQUIRED")
    return {"bookings": get_user_bookings(int(user_id), limit=limit)}


@app.post("/api/hotel/checkout")
async def api_hotel_checkout(request: Request):
    session_token = request.cookies.get("session_token")
    user_id = get_user_id_from_session(session_token) if session_token else None
    if not user_id:
        raise HTTPException(status_code=401, detail="LOGIN_REQUIRED")

    body = await request.json()
    if not isinstance(body, dict):
        raise HTTPException(status_code=400, detail="잘못된 요청입니다.")

    hotel = body.get("hotel") if isinstance(body.get("hotel"), dict) else {}
    guest = body.get("guest") if isinstance(body.get("guest"), dict) else {}

    try:
        amount = int(round(float(hotel.get("price") or 0)))
    except Exception:
        amount = 0
    if amount <= 0:
        raise HTTPException(status_code=400, detail="결제 가능한 금액을 확인할 수 없습니다.")

    order_id = f"HTL-{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}-{os.urandom(4).hex()}"
    hotel_name = str(hotel.get("name") or "호텔 예약").strip() or "호텔 예약"
    city = str(hotel.get("city") or "").strip()
    order_name = f"{hotel_name} {city}".strip()
    toss_client_key = (os.getenv("TOSS_PAYMENTS_CLIENT_KEY") or os.getenv("TOSS_CLIENT_KEY") or "").strip()
    if not toss_client_key:
        raise HTTPException(status_code=500, detail="토스 클라이언트 키가 설정되지 않았습니다.")
    base_url = str(request.base_url).rstrip("/")

    PENDING_HOTEL_ORDERS[order_id] = {
        "user_id": str(user_id),
        "amount": amount,
        "order_name": order_name,
        "hotel": hotel,
        "guest": guest,
        "created_at": datetime.datetime.now().isoformat(),
    }

    return {
        "order_id": order_id,
        "order_name": order_name,
        "amount": amount,
        "currency": "KRW",
        "payment_mode": "toss",
        "toss_client_key": toss_client_key,
        "success_url": f"{base_url}/payment/hotel/success",
        "fail_url": f"{base_url}/payment/hotel/fail",
        "message": "결제 준비가 완료되었습니다.",
    }


@app.post("/api/payments/toss/hotel/confirm")
async def api_toss_hotel_confirm(request: Request):
    body = await request.json()
    payment_key = str(body.get("paymentKey") or "").strip()
    order_id = str(body.get("orderId") or "").strip()
    amount = int(body.get("amount") or 0)

    pending = PENDING_HOTEL_ORDERS.get(order_id)
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
            item_type="hotel",
            order_id=order_id,
            order_name=str(pending.get("order_name") or "호텔 예약"),
            amount=amount,
            currency="KRW",
            status="confirmed_mock",
            status_label="예약 확정(모의 결제)",
            route=str(((pending.get("hotel") or {}).get("city") or "")).strip(),
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
        item_type="hotel",
        order_id=order_id,
        order_name=str(pending.get("order_name") or "호텔 예약"),
        amount=amount,
        currency="KRW",
        status="confirmed",
        status_label="예약 확정",
        route=str(((pending.get("hotel") or {}).get("city") or "")).strip(),
        payment_key=payment_key,
        payload=pending,
        created_at_iso=str(pending.get("created_at") or ""),
        confirmed_at_iso=str(pending.get("confirmed_at") or ""),
    )
    return {"status": "confirmed", "order_id": order_id, "amount": amount, "payment": data}


@app.post("/api/tour/checkout")
async def api_tour_checkout(request: Request):
    session_token = request.cookies.get("session_token")
    user_id = get_user_id_from_session(session_token) if session_token else None
    if not user_id:
        raise HTTPException(status_code=401, detail="LOGIN_REQUIRED")

    body = await request.json()
    if not isinstance(body, dict):
        raise HTTPException(status_code=400, detail="잘못된 요청입니다.")

    tour = body.get("tour") if isinstance(body.get("tour"), dict) else {}
    traveler = body.get("traveler") if isinstance(body.get("traveler"), dict) else {}

    try:
        amount = int(round(float(tour.get("price") or 0)))
    except Exception:
        amount = 0
    if amount <= 0:
        raise HTTPException(status_code=400, detail="결제 가능한 금액을 확인할 수 없습니다.")

    order_id = f"TOUR-{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}-{os.urandom(4).hex()}"
    tour_name = str(tour.get("name") or "투어 예약").strip() or "투어 예약"
    meta = str(tour.get("meta") or "").strip()
    order_name = f"{tour_name} {meta}".strip()
    toss_client_key = (os.getenv("TOSS_PAYMENTS_CLIENT_KEY") or os.getenv("TOSS_CLIENT_KEY") or "").strip()
    if not toss_client_key:
        raise HTTPException(status_code=500, detail="토스 클라이언트 키가 설정되지 않았습니다.")
    base_url = str(request.base_url).rstrip("/")

    PENDING_TOUR_ORDERS[order_id] = {
        "user_id": str(user_id),
        "amount": amount,
        "order_name": order_name,
        "tour": tour,
        "traveler": traveler,
        "created_at": datetime.datetime.now().isoformat(),
    }

    return {
        "order_id": order_id,
        "order_name": order_name,
        "amount": amount,
        "currency": "KRW",
        "payment_mode": "toss",
        "toss_client_key": toss_client_key,
        "success_url": f"{base_url}/payment/tour/success",
        "fail_url": f"{base_url}/payment/tour/fail",
        "message": "결제 준비가 완료되었습니다.",
    }


@app.post("/api/payments/toss/tour/confirm")
async def api_toss_tour_confirm(request: Request):
    body = await request.json()
    payment_key = str(body.get("paymentKey") or "").strip()
    order_id = str(body.get("orderId") or "").strip()
    amount = int(body.get("amount") or 0)

    pending = PENDING_TOUR_ORDERS.get(order_id)
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
            item_type="tour",
            order_id=order_id,
            order_name=str(pending.get("order_name") or "투어 예약"),
            amount=amount,
            currency="KRW",
            status="confirmed_mock",
            status_label="예약 확정(모의 결제)",
            route=str(((pending.get("tour") or {}).get("meta") or "")).strip(),
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
        item_type="tour",
        order_id=order_id,
        order_name=str(pending.get("order_name") or "투어 예약"),
        amount=amount,
        currency="KRW",
        status="confirmed",
        status_label="예약 확정",
        route=str(((pending.get("tour") or {}).get("meta") or "")).strip(),
        payment_key=payment_key,
        payload=pending,
        created_at_iso=str(pending.get("created_at") or ""),
        confirmed_at_iso=str(pending.get("confirmed_at") or ""),
    )
    return {"status": "confirmed", "order_id": order_id, "amount": amount, "payment": data}


@app.get("/payment/hotel/success", response_class=HTMLResponse)
def payment_hotel_success_page():
    return """
<!doctype html>
<html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>호텔 결제 확인 중</title>
<style>body{font-family:Pretendard,sans-serif;padding:24px;background:#f8fafc;color:#0f172a} .box{max-width:560px;margin:24px auto;background:#fff;border:1px solid #e2e8f0;border-radius:12px;padding:18px} .muted{color:#64748b;font-size:14px}</style>
</head><body><div class="box"><h2>결제 확인 중입니다...</h2><p id="msg" class="muted">잠시만 기다려 주세요.</p><a href="/gloval-hotel">호텔 페이지로 돌아가기</a></div>
<script>
const qs=new URLSearchParams(location.search);
const body={paymentKey:qs.get('paymentKey'),orderId:qs.get('orderId'),amount:Number(qs.get('amount')||0)};
fetch('/api/payments/toss/hotel/confirm',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)})
 .then(async r=>({ok:r.ok,data:await r.json().catch(()=>({}))}))
 .then(x=>{document.getElementById('msg').textContent=x.ok?'결제가 승인되었습니다.':'결제 승인 실패: '+(x.data?.detail||x.data?.message||'알 수 없는 오류');})
 .catch(()=>{document.getElementById('msg').textContent='결제 승인 확인 중 오류가 발생했습니다.'});
</script></body></html>
"""


@app.get("/payment/hotel/fail", response_class=HTMLResponse)
def payment_hotel_fail_page(code: str | None = Query(None), message: str | None = Query(None)):
    c = (code or "").strip()
    m = (message or "").strip()
    return f"""
<!doctype html>
<html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>호텔 결제 실패</title>
<style>body{{font-family:Pretendard,sans-serif;padding:24px;background:#f8fafc;color:#0f172a}} .box{{max-width:560px;margin:24px auto;background:#fff;border:1px solid #fecaca;border-radius:12px;padding:18px}} .muted{{color:#64748b;font-size:14px}}</style>
</head><body><div class="box"><h2>결제가 완료되지 않았습니다.</h2><p class="muted">코드: {c or '-'}</p><p class="muted">메시지: {m or '-'}</p><a href="/gloval-hotel">호텔 페이지로 돌아가기</a></div></body></html>
"""


@app.get("/payment/tour/success", response_class=HTMLResponse)
def payment_tour_success_page():
    return """
<!doctype html>
<html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>투어 결제 확인 중</title>
<style>body{font-family:Pretendard,sans-serif;padding:24px;background:#f8fafc;color:#0f172a} .box{max-width:560px;margin:24px auto;background:#fff;border:1px solid #e2e8f0;border-radius:12px;padding:18px} .muted{color:#64748b;font-size:14px}</style>
</head><body><div class="box"><h2>결제 확인 중입니다...</h2><p id="msg" class="muted">잠시만 기다려 주세요.</p><a href="/tour">투어 페이지로 돌아가기</a></div>
<script>
const qs=new URLSearchParams(location.search);
const body={paymentKey:qs.get('paymentKey'),orderId:qs.get('orderId'),amount:Number(qs.get('amount')||0)};
fetch('/api/payments/toss/tour/confirm',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)})
 .then(async r=>({ok:r.ok,data:await r.json().catch(()=>({}))}))
 .then(x=>{document.getElementById('msg').textContent=x.ok?'결제가 승인되었습니다.':'결제 승인 실패: '+(x.data?.detail||x.data?.message||'알 수 없는 오류');})
 .catch(()=>{document.getElementById('msg').textContent='결제 승인 확인 중 오류가 발생했습니다.'});
</script></body></html>
"""


@app.get("/payment/tour/fail", response_class=HTMLResponse)
def payment_tour_fail_page(code: str | None = Query(None), message: str | None = Query(None)):
    c = (code or "").strip()
    m = (message or "").strip()
    return f"""
<!doctype html>
<html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>투어 결제 실패</title>
<style>body{{font-family:Pretendard,sans-serif;padding:24px;background:#f8fafc;color:#0f172a}} .box{{max-width:560px;margin:24px auto;background:#fff;border:1px solid #fecaca;border-radius:12px;padding:18px}} .muted{{color:#64748b;font-size:14px}}</style>
</head><body><div class="box"><h2>결제가 완료되지 않았습니다.</h2><p class="muted">코드: {c or '-'}</p><p class="muted">메시지: {m or '-'}</p><a href="/tour">투어 페이지로 돌아가기</a></div></body></html>
"""
@app.get("/logout")
def logout(request: Request):
    session_token = request.cookies.get("session_token")
    if session_token:
        delete_session(session_token)
    response = RedirectResponse(url="/", status_code=302)
    response.delete_cookie(key="session_token", path="/")
    return response

# ========== 패키지 상품 결제 전용 엔드포인트 ========== #
from fastapi import Request, HTTPException
import datetime, os

@app.post("/api/pack/checkout")
async def api_pack_checkout(request: Request):
    session_token = request.cookies.get("session_token")
    user_id = get_user_id_from_session(session_token) if session_token else None
    if not user_id:
        raise HTTPException(status_code=401, detail="LOGIN_REQUIRED")

    body = await request.json()
    if not isinstance(body, dict):
        raise HTTPException(status_code=400, detail="잘못된 요청입니다.")

    pack = body.get("tour") if isinstance(body.get("tour"), dict) else {}
    traveler = body.get("traveler") if isinstance(body.get("traveler"), dict) else {}

    try:
        amount = int(round(float(pack.get("price") or 0)))
    except Exception:
        amount = 0
    if amount <= 0:
        raise HTTPException(status_code=400, detail="결제 가능한 금액을 확인할 수 없습니다.")

    order_id = f"PACK-{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}-{os.urandom(4).hex()}"
    pack_name = str(pack.get("name") or "패키지 예약").strip() or "패키지 예약"
    meta = str(pack.get("meta") or "").strip()
    order_name = f"{pack_name} {meta}".strip()
    toss_client_key = (os.getenv("TOSS_PAYMENTS_CLIENT_KEY") or os.getenv("TOSS_CLIENT_KEY") or "").strip()
    if not toss_client_key:
        raise HTTPException(status_code=500, detail="토스 클라이언트 키가 설정되지 않았습니다.")
    base_url = str(request.base_url).rstrip("/")

    PENDING_PACK_ORDERS[order_id] = {
        "user_id": str(user_id),
        "amount": amount,
        "order_name": order_name,
        "pack": pack,
        "traveler": traveler,
        "created_at": datetime.datetime.now().isoformat(),
    }

    return {
        "order_id": order_id,
        "order_name": order_name,
        "amount": amount,
        "currency": "KRW",
        "payment_mode": "toss",
        "toss_client_key": toss_client_key,
        "success_url": f"{base_url}/payment/pack/success",
        "fail_url": f"{base_url}/payment/pack/fail",
        "message": "결제 준비가 완료되었습니다.",
    }


@app.post("/api/payments/toss/pack/confirm")
async def api_toss_pack_confirm(request: Request):
    body = await request.json()
    payment_key = str(body.get("paymentKey") or "").strip()
    order_id = str(body.get("orderId") or "").strip()
    amount = int(body.get("amount") or 0)

    pending = PENDING_PACK_ORDERS.get(order_id)
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
            item_type="pack",
            order_id=order_id,
            order_name=str(pending.get("order_name") or "패키지 예약"),
            amount=amount,
            currency="KRW",
            status="confirmed_mock",
            status_label="예약 확정(모의 결제)",
            route=str(((pending.get("pack") or {}).get("meta") or "")).strip(),
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
        item_type="pack",
        order_id=order_id,
        order_name=str(pending.get("order_name") or "패키지 예약"),
        amount=amount,
        currency="KRW",
        status="confirmed",
        status_label="예약 확정",
        route=str(((pending.get("pack") or {}).get("meta") or "")).strip(),
        payment_key=payment_key,
        payload=pending,
        created_at_iso=str(pending.get("created_at") or ""),
        confirmed_at_iso=str(pending.get("confirmed_at") or ""),
    )
    return {"status": "confirmed", "order_id": order_id, "amount": amount, "payment": data}
# ========== PACK-DETAIL 전용 결제 성공/실패 페이지 ========== #

@app.get("/payment/pack/success", response_class=HTMLResponse)
def payment_pack_success_page():
    return """
<!doctype html>
<html lang=\"ko\"><head><meta charset=\"utf-8\"><meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">
<title>패키지 결제 확인 중</title>
<style>body{font-family:Pretendard,sans-serif;padding:24px;background:#f8fafc;color:#0f172a} .box{max-width:560px;margin:24px auto;background:#fff;border:1px solid #e2e8f0;border-radius:12px;padding:18px} .muted{color:#64748b;font-size:14px}</style>
</head><body><div class=\"box\"><h2>결제 확인 중입니다...</h2><p id=\"msg\" class=\"muted\">잠시만 기다려 주세요.</p><a href=\"/package\">패키지 상품 페이지로 돌아가기</a></div>
<script>
const qs=new URLSearchParams(location.search);
const body={paymentKey:qs.get('paymentKey'),orderId:qs.get('orderId'),amount:Number(qs.get('amount')||0)};
fetch('/api/payments/toss/pack/confirm',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)})
 .then(async r=>({ok:r.ok,data:await r.json().catch(()=>({}))}))
 .then(x=>{document.getElementById('msg').textContent=x.ok?'결제가 승인되었습니다.':'결제 승인 실패: '+(x.data?.detail||x.data?.message||'알 수 없는 오류');})
 .catch(()=>{document.getElementById('msg').textContent='결제 승인 확인 중 오류가 발생했습니다.'});
</script></body></html>
"""

@app.get("/payment/pack/fail", response_class=HTMLResponse)
def payment_pack_fail_page(code: str | None = Query(None), message: str | None = Query(None)):
    c = (code or "").strip()
    m = (message or "").strip()
    return f"""
<!doctype html>
<html lang=\"ko\"><head><meta charset=\"utf-8\"><meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">
<title>패키지 결제 실패</title>
<style>body{{font-family:Pretendard,sans-serif;padding:24px;background:#f8fafc;color:#0f172a}} .box{{max-width:560px;margin:24px auto;background:#fff;border:1px solid #fecaca;border-radius:12px;padding:18px}} .muted{{color:#64748b;font-size:14px}}</style>
</head><body><div class=\"box\"><h2>결제가 완료되지 않았습니다.</h2><p class=\"muted\">코드: {c or '-'}...</p><p class=\"muted\">메시지: {m or '-'}...</p><a href=\"/package\">패키지 상품 페이지로 돌아가기</a></div></body></html>
"""


@app.get("/check-username")
def check_username(username: str = Query(...), db: Session = Depends(get_db)):
    # 아이디 중복 확인은 항상 사용 가능하도록 중복 여부를 노출하지 않음
    return {"exists": False}


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

@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    nickname = get_nickname_from_request(request)
    return templates.TemplateResponse("home.html", {"request": request, "nickname": nickname})


@app.get("/home", response_class=HTMLResponse)
def home_page(request: Request):
    nickname = get_nickname_from_request(request)
    return templates.TemplateResponse("home.html", {"request": request, "nickname": nickname})


@app.get("/mypage", response_class=HTMLResponse)
def mypage(request: Request):
    session_token = request.cookies.get("session_token")
    nickname = None
    email = None
    name = None
    phone = None
    user_id = get_user_id_from_session(session_token) if session_token else None
    if user_id:
        db = SessionLocal()
        try:
            user = db.query(User).filter(User.id == int(user_id)).first()
            if user:
                nickname = user.nickname
                email = user.email
                name = user.name
                phone = user.phone
        finally:
            db.close()
    return templates.TemplateResponse(
        "mypage.html",
        {"request": request, "nickname": nickname, "email": email, "name": name, "phone": phone},
    )


@app.get("/airport", response_class=HTMLResponse)
def airport(request: Request):
    nickname = get_nickname_from_request(request)
    return templates.TemplateResponse("airport.html", {"request": request, "nickname": nickname})

@app.get("/find-id", response_class=HTMLResponse)
def find_id_get(request: Request):
    return templates.TemplateResponse("find_id.html", {"request": request})


@app.post("/find-id", response_class=HTMLResponse)
def find_id_post(
    request: Request,
    email: str = Form(...),
    phone: str = Form(...),
    db: Session = Depends(get_db),
):
    user = db.query(User).filter(User.email == email, User.phone == phone).first()
    if not user:
        return templates.TemplateResponse(
            "find_id.html",
            {"request": request, "error": "입력한 정보와 일치하는 계정을 찾을 수 없습니다."},
        )
    return templates.TemplateResponse(
        "find_id.html",
        {"request": request, "result": f"아이디: {user.name}"},
    )


@app.get("/find-password", response_class=HTMLResponse)
def find_password_get(request: Request):
    return templates.TemplateResponse("find_password.html", {"request": request})


@app.post("/find-password", response_class=HTMLResponse)
def find_password_post(
    request: Request,
    username: str = Form(...),
    email: str = Form(...),
    phone: str = Form(...),
    new_password: str = Form(...),
    new_password_confirm: str = Form(...),
    db: Session = Depends(get_db),
):
    if new_password != new_password_confirm:
        return templates.TemplateResponse(
            "find_password.html",
            {"request": request, "error": "비밀번호가 일치하지 않습니다."},
        )
    validation_error = _validate_password_only(new_password)
    if validation_error:
        return templates.TemplateResponse(
            "find_password.html",
            {"request": request, "error": validation_error},
        )
    user = db.query(User).filter(User.name == username, User.email == email, User.phone == phone).first()
    if not user:
        return templates.TemplateResponse(
            "find_password.html",
            {"request": request, "error": "입력한 정보와 일치하는 계정을 찾을 수 없습니다."},
        )
    user.password = _hash_password(new_password)
    db.commit()
    return templates.TemplateResponse(
        "find_password.html",
        {"request": request, "result": "비밀번호가 변경되었습니다. 로그인해 주세요."},
    )


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


@app.get("/tdetail", response_class=HTMLResponse)
def tdetail(request: Request):
    nickname = get_nickname_from_request(request)
    session_token = request.cookies.get("session_token")
    user_is_authenticated = bool(get_user_id_from_session(session_token)) if session_token else False
    return templates.TemplateResponse(
        "tour-detail.html",
        {"request": request, "nickname": nickname, "user_is_authenticated": user_is_authenticated},
    )

@app.get("/planner", response_class=HTMLResponse)
def planner(request: Request):
    nickname = get_nickname_from_request(request)
    return templates.TemplateResponse("planner.html", {"request": request, "nickname": nickname})

@app.get("/travelGroup", response_class=HTMLResponse)
def travelGroup(request: Request):
    nickname = get_nickname_from_request(request)
    return templates.TemplateResponse("travel-group.html", {"request": request, "nickname": nickname})

@app.get("/package", response_class=HTMLResponse)
def package_page(request: Request):
    nickname = get_nickname_from_request(request)
    return templates.TemplateResponse("package.html", {"request": request, "nickname": nickname})


@app.get("/tour", response_class=HTMLResponse)
def tour_page(request: Request):
    nickname = get_nickname_from_request(request)
    return templates.TemplateResponse("tour.html", {"request": request, "nickname": nickname})

# 신규 투어 상세 페이지 라우트
@app.get("/tour-detail", response_class=HTMLResponse)
def tour_detail(request: Request, tour_id: str = Query(None)):
    nickname = get_nickname_from_request(request)
    session_token = request.cookies.get("session_token")
    user_is_authenticated = bool(get_user_id_from_session(session_token)) if session_token else False
    # TODO: tour_id로 DB에서 투어 정보 조회 후 전달
    return templates.TemplateResponse(
        "tour-detail.html",
        {
            "request": request,
            "nickname": nickname,
            "tour_id": tour_id,
            "user_is_authenticated": user_is_authenticated,
        },
    )


@app.get("/flight-detail", response_class=HTMLResponse)
def flight_detail(
    request: Request,
    airline: str = Query(""),
    dep: str = Query(""),
    arr: str = Query(""),
    route: str = Query(""),
    duration: str = Query(""),
    price: str = Query(""),
    price_base: str = Query(""),
    price_total: str = Query(""),
    price_grand: str = Query(""),
    currency: str = Query("KRW"),
    baggage: str = Query(""),
    baggage_opts: str = Query(""),
    dep_at: str = Query(""),
    arr_at: str = Query(""),
    dep_terminal: str = Query(""),
    arr_terminal: str = Query(""),
    flight_no: str = Query(""),
    aircraft: str = Query(""),
    cabin: str = Query(""),
    ret_route: str = Query(""),
    ret_duration: str = Query(""),
    ret_dep: str = Query(""),
    ret_arr: str = Query(""),
    ret_dep_at: str = Query(""),
    ret_arr_at: str = Query(""),
    ret_dep_terminal: str = Query(""),
    ret_arr_terminal: str = Query(""),
    ret_flight_no: str = Query(""),
    ret_aircraft: str = Query(""),
    ret_cabin: str = Query(""),
    checkout_ref: str = Query(""),
    round: str = Query("0"),
):
    nickname = get_nickname_from_request(request)
    return templates.TemplateResponse(
        "flight-detail.html",
        {
            "request": request,
            "nickname": nickname,
            "airline": airline,
            "dep": dep,
            "arr": arr,
            "route": route,
            "duration": duration,
            "price": price,
            "price_base": price_base,
            "price_total": price_total,
            "price_grand": price_grand,
            "currency": currency,
            "baggage": baggage,
            "baggage_opts": baggage_opts,
            "dep_at": dep_at,
            "arr_at": arr_at,
            "dep_terminal": dep_terminal,
            "arr_terminal": arr_terminal,
            "flight_no": flight_no,
            "aircraft": aircraft,
            "cabin": cabin,
            "ret_route": ret_route,
            "ret_duration": ret_duration,
            "ret_dep": ret_dep,
            "ret_arr": ret_arr,
            "ret_dep_at": ret_dep_at,
            "ret_arr_at": ret_arr_at,
            "ret_dep_terminal": ret_dep_terminal,
            "ret_arr_terminal": ret_arr_terminal,
            "ret_flight_no": ret_flight_no,
            "ret_aircraft": ret_aircraft,
            "ret_cabin": ret_cabin,
            "checkout_ref": checkout_ref,
            "is_round": str(round) == "1",
        },
    )

@app.get("/join", response_class=HTMLResponse)
def join(request: Request):
    return templates.TemplateResponse("join.html", {"request": request})


@app.get("/signin", response_class=HTMLResponse)
def signin_get(request: Request):
    return templates.TemplateResponse("signin.html", {"request": request})
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
@app.get("/login", response_class=HTMLResponse)
def login(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})


@app.get("/signin", response_class=HTMLResponse)
def signin_get(request: Request):
    return templates.TemplateResponse("signin.html", {"request": request})


@app.post("/signin", response_class=HTMLResponse)
def signin_post(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db),
):
    users = (
        db.query(User)
        .filter(User.name == username)
        .order_by(User.id.desc())
        .all()
    )
    if not users:
        return templates.TemplateResponse("signin.html", {"request": request, "error": "아이디 또는 비밀번호가 올바르지 않습니다. 다시 입력해 주세요."})

    matched_user = None
    needs_upgrade = False
    for u in users:
        ok, upgrade = _verify_password(password, u.password)
        if ok:
            matched_user = u
            needs_upgrade = upgrade
            break

    if not matched_user:
        return templates.TemplateResponse("signin.html", {"request": request, "error": "아이디 또는 비밀번호가 올바르지 않습니다. 다시 입력해 주세요."})

    if needs_upgrade:
        matched_user.password = _hash_password(password)
        db.commit()

    session_token = create_session(matched_user.id)
    response = RedirectResponse(url="/", status_code=status.HTTP_302_FOUND)
    response.set_cookie(
        key="session_token",
        value=session_token,
        httponly=True,
        samesite="lax",
        max_age=SESSION_EXPIRE_MINUTES * 60,
        path="/",
    )
    return response


@app.get("/gloval-hotel", response_class=HTMLResponse)
def gloval_hotel(
    request: Request,
    city: str = Query(None),
    city_en: str | None = Query(None),
    country: str = Query(None),
    checkin: str = Query(None),
    checkout: str = Query(None),
    lat: str | None = Query(None),
    lon: str | None = Query(None),
    page: int = Query(1, ge=1),
):
    nickname = get_nickname_from_request(request)
    lat = _parse_float_param(lat)
    lon = _parse_float_param(lon)
    nights = _calc_nights(checkin, checkout)
    hotels = []

    if (city or city_en) and checkin and checkout:
        try:
            booking_pages = max(1, min(_env_int("HOTEL_BOOKING_PAGES", 1), 2))
            dest_rows = []
            for search_query in _hotel_destination_query_candidates(city, country, city_en):
                try:
                    destination = booking_search_destination(query=search_query)
                    rows = destination.get("data", []) if isinstance(destination, dict) else []
                    if rows:
                        city_match = city if (city and _hotel_expected_country_code(city, city_en=city_en)) else (city_en or city)
                        first_try = _pick_best_booking_destination(rows, city_match, country) or {}
                        if _is_plausible_booking_destination(first_try, city, country, city_en=city_en):
                            dest_rows = rows
                            break
                except Exception:
                    continue

            if dest_rows:
                city_match = city if (city and _hotel_expected_country_code(city)) else city_en
                first = _pick_best_booking_destination(dest_rows, city_match, country) or {}
                dest_id = str(first.get("dest_id") or "").strip()
                search_type = str(first.get("search_type") or "CITY").strip() or "CITY"
                if dest_id:
                    for page_number in range(1, booking_pages + 1):
                        booking_result = booking_search_hotels_by_dest_id(
                            dest_id=dest_id,
                            search_type=search_type,
                            checkin_date=checkin,
                            checkout_date=checkout,
                            adults=2,
                            room_qty=1,
                            currency_code="KRW",
                            languagecode="ko",
                            page_number=page_number,
                        )
                        parsed = parse_booking_hotels(booking_result)
                        hotels.extend(parsed)
                        if len(parsed) < 8:
                            break
                else:
                    hotels.append({"name": "Booking destination id not found", "address": "", "price": None, "source": "Booking"})
            else:
                hotels.append({"name": "Booking destination not found", "address": "", "price": None, "source": "Booking"})
        except Exception as e:
            try:
                _log_translate_issue(f"hotel_search_primary_exception={e}")
            except Exception:
                pass

        # Backup path: if destination-id flow failed or only error cards came back,
        # retry once with legacy city-based search to keep user-facing results alive.
        if not _has_real_booking_hotels(hotels):
            try:
                backup_query = (city_en or city or "").strip()
                backup_raw = booking_search_hotels(backup_query, checkin, checkout, adults=2, page_number=1)
                backup_parsed = parse_booking_hotels(backup_raw)
                backup_real = [h for h in backup_parsed if isinstance(h, dict) and not _is_booking_error_row(h)]
                if backup_real:
                    hotels = backup_real
                else:
                    hotels = []
            except Exception as e:
                try:
                    _log_translate_issue(f"hotel_search_backup_exception={e}")
                except Exception:
                    pass
                hotels = []

        if not hotels:
            hotels.append({
                "name": "검색 가능한 숙소를 찾지 못했습니다. 날짜/도시를 다시 확인해 주세요.",
                "address": "",
                "price": None,
                "source": "Booking",
            })

    unique_hotels = dedupe_hotels(hotels)
    for h in unique_hotels:
        if not isinstance(h, dict):
            continue
        h["nights"] = nights
        h["price_per_night"] = _price_per_night(h.get("price"), nights)
        h["price_original_per_night"] = _price_per_night(h.get("price_original"), nights)

    page_size = 16
    total_hotels = len(unique_hotels)
    total_pages = max((total_hotels + page_size - 1) // page_size, 1)
    page = min(page, total_pages)
    start_idx = (page - 1) * page_size
    end_idx = start_idx + page_size
    paged_hotels = unique_hotels[start_idx:end_idx]
    try:
        _translate_hotel_names_for_page(paged_hotels)
    except Exception as e:
        try:
            _log_translate_issue(f"translate_page_exception={e}")
        except Exception:
            pass
    for h in paged_hotels:
        if not isinstance(h, dict):
            continue
        try:
            h["detail_snapshot"] = quote(
                json.dumps(h, ensure_ascii=False, default=str),
                safe="",
            )
        except Exception:
            h["detail_snapshot"] = ""

    try:
        with open(os.path.join(BASE_DIR, "hotel_debug.log"), "a", encoding="utf-8") as f:
            f.write(
                f"\n[{datetime.datetime.now()}] params: city={city}, city_en={city_en}, country={country}, checkin={checkin}, checkout={checkout}, lat={lat}, lon={lon}\n"
            )
            f.write("hotels: ")
            f.write(json.dumps(unique_hotels, ensure_ascii=False))
            f.write("\n")
    except Exception:
        pass

    return templates.TemplateResponse(
        "gloval-hotel.html",
        {
            "request": request,
            "nickname": nickname,
            "hotels": paged_hotels,
            "page": page,
            "total_pages": total_pages,
            "has_prev": page > 1,
            "has_next": page < total_pages,
            "city": city,
            "city_en": city_en,
            "country": country,
            "checkin": checkin,
            "checkout": checkout,
            "lat": lat,
            "lon": lon,
            "nights": nights,
        },
    )


@app.get("/gloval-hotel/detail", response_class=HTMLResponse)
def gloval_hotel_detail(
    request: Request,
    hotel_id: str = Query(None),
    city: str = Query(None),
    country: str = Query(None),
    checkin: str = Query(None),
    checkout: str = Query(None),
    snapshot: str = Query(None),
):
    nickname = get_nickname_from_request(request)
    nights = _calc_nights(checkin, checkout)
    selected_hotel = None
    error_message = None
    google_place = None
    snapshot_hotel = None
    snapshot_matched = False

    if snapshot:
        try:
            decoded = json.loads(unquote(snapshot))
            if isinstance(decoded, dict):
                snapshot_hotel = decoded
        except Exception:
            snapshot_hotel = None

    if not (hotel_id and city and checkin and checkout):
        error_message = "상세 정보를 표시하려면 호텔/도시/날짜 정보가 필요합니다."
    elif snapshot_hotel and str(snapshot_hotel.get("hotel_id") or "") == str(hotel_id):
        # Fast path: list page already passed a hotel snapshot.
        selected_hotel = snapshot_hotel
        snapshot_matched = True
    else:
        try:
            for page_number in range(1, 4):
                booking_result = booking_search_hotels(city, checkin, checkout, adults=2, page_number=page_number)
                parsed = parse_booking_hotels(booking_result)
                if booking_result and booking_result.get("error"):
                    error_message = "호텔 상세 정보를 불러오지 못했습니다. 잠시 후 다시 시도해 주세요."
                    break
                for hotel in parsed:
                    if str(hotel.get("hotel_id")) == str(hotel_id):
                        selected_hotel = hotel
                        break
                if selected_hotel:
                    break
        except Exception as e:
            error_message = f"호텔 상세 조회 실패: {e}"

    if not selected_hotel and not error_message:
        if snapshot_hotel and (
            not hotel_id or str(snapshot_hotel.get("hotel_id")) == str(hotel_id)
        ):
            selected_hotel = snapshot_hotel
            snapshot_matched = True
        else:
            error_message = "선택한 호텔 정보를 찾지 못했습니다. 검색 결과를 새로고침한 뒤 다시 시도해 주세요."

    # Snapshot detail should render immediately; skip heavy external enrich calls.
    if selected_hotel and snapshot_matched and (
        str(os.getenv("HOTEL_DETAIL_FAST_MODE", "1") or "1").strip().lower() in {"1", "true", "yes", "on"}
    ):
        try:
            selected_hotel["room_offers"] = _extract_room_offers_from_booking_detail(
                None,
                fallback_hotel=selected_hotel,
            )
        except Exception as e:
            try:
                _log_translate_issue(f"detail_fast_room_offer_exception={e}")
            except Exception:
                pass
            selected_hotel["room_offers"] = []
        selected_hotel["nights"] = nights
        selected_hotel["price_per_night"] = _price_per_night(selected_hotel.get("price"), nights)
        selected_hotel["price_original_per_night"] = _price_per_night(selected_hotel.get("price_original"), nights)
        for ro in selected_hotel.get("room_offers") or []:
            if not isinstance(ro, dict):
                continue
            ro["price_per_night"] = _price_per_night(ro.get("price"), nights)
            ro["price_original_per_night"] = _price_per_night(ro.get("price_original"), nights)
        return templates.TemplateResponse(
            "gloval-hotel-detail.html",
            {
                "request": request,
                "nickname": nickname,
                "hotel": selected_hotel,
                "error_message": error_message,
                "city": city,
                "country": country,
                "checkin": checkin,
                "checkout": checkout,
                "nights": nights,
                "google_place": None,
            },
        )

    if selected_hotel:
        try:
            # Best-effort room-level offers (RapidAPI endpoint availability varies by plan/provider).
            try:
                from app.api.booking_hotel_flight_api import get_hotel_room_products

                room_api = get_hotel_room_products(
                    hotel_id=str(selected_hotel.get("hotel_id") or ""),
                    checkin_date=checkin,
                    checkout_date=checkout,
                    adults=2,
                    room_qty=1,
                    currency_code="KRW",
                    languagecode="ko",
                )
                selected_hotel["room_offer_source"] = room_api.get("endpoint") if isinstance(room_api, dict) else None
                if isinstance(room_api, dict) and room_api.get("status") == "ok":
                    selected_hotel["room_offers"] = _extract_room_offers_from_booking_detail(
                        room_api.get("data"),
                        fallback_hotel=selected_hotel,
                    )
                else:
                    selected_hotel["room_offers"] = _extract_room_offers_from_booking_detail(
                        None,
                        fallback_hotel=selected_hotel,
                    )
                    selected_hotel["room_offer_error"] = (room_api or {}).get("error") if isinstance(room_api, dict) else "unknown"
            except Exception as room_e:
                selected_hotel["room_offers"] = _extract_room_offers_from_booking_detail(
                    None,
                    fallback_hotel=selected_hotel,
                )
                selected_hotel["room_offer_error"] = str(room_e)

            selected_hotel["nights"] = nights
            selected_hotel["price_per_night"] = _price_per_night(selected_hotel.get("price"), nights)
            selected_hotel["price_original_per_night"] = _price_per_night(selected_hotel.get("price_original"), nights)
            for ro in selected_hotel.get("room_offers") or []:
                if not isinstance(ro, dict):
                    continue
                ro["price_per_night"] = _price_per_night(ro.get("price"), nights)
                ro["price_original_per_night"] = _price_per_night(ro.get("price_original"), nights)

            def _photo_dedupe_key(url: str) -> str:
                u = (url or "").strip()
                if not u:
                    return ""
                base = u.split("?", 1)[0]
                # Booking image URLs often repeat same asset with size/crop path variants.
                norm = base.lower()
                norm = re.sub(r"/(?:max|square|crop)\d+(?:x\d+)?/", "/<size>/", norm)
                norm = re.sub(r"/\d{2,5}x\d{2,5}/", "/<size>/", norm)
                return norm

            # Deduplicate supplier photos first (some listings repeat identical URLs).
            existing_photos = selected_hotel.get("photo_gallery") or []
            # Merge room-level photos to improve gallery coverage when hotel-level photos are sparse.
            for ro in selected_hotel.get("room_offers") or []:
                if isinstance(ro, dict):
                    for pu in ro.get("photos") or []:
                        if isinstance(pu, str) and pu.strip():
                            existing_photos.append(pu.strip())
            if isinstance(existing_photos, list):
                deduped = []
                seen_photos = set()
                for u in existing_photos:
                    if not isinstance(u, str):
                        continue
                    u = u.strip()
                    k = _photo_dedupe_key(u)
                    if not u or not k or k in seen_photos:
                        continue
                    seen_photos.add(k)
                    deduped.append(u)
                if deduped:
                    selected_hotel["photo_gallery"] = deduped[:12]
                    selected_hotel["image"] = selected_hotel.get("image") or deduped[0]

            g = find_hotel_google_place(
                name=selected_hotel.get("name_en") or selected_hotel.get("name"),
                address=f"{selected_hotel.get('address') or city or ''} {country or ''}".strip(),
                lat=_parse_float_param(selected_hotel.get("latitude")),
                lon=_parse_float_param(selected_hotel.get("longitude")),
                language="ko",
            )
            if isinstance(g, dict) and g.get("status") == "ok":
                google_place = g
                # Prefer Google photos as fallback/augmentation if Booking photos are sparse.
                booking_photos = selected_hotel.get("photo_gallery") or []
                if isinstance(booking_photos, list):
                    merged = []
                    seen = set()
                    google_photos = g.get("photo_urls") or []
                    # If Booking photos are sparse or repetitive, prioritize Google photos first.
                    source_order = (google_photos + booking_photos) if len(booking_photos) <= 3 else (booking_photos + google_photos)
                    for u in source_order:
                        if not isinstance(u, str) or not u.strip():
                            continue
                        key = _photo_dedupe_key(u)
                        if not key or key in seen:
                            continue
                        seen.add(key)
                        merged.append(u)
                    if merged:
                        selected_hotel["photo_gallery"] = merged[:12]
                        selected_hotel["image"] = merged[0]
                details = g.get("details") or {}
                if isinstance(details, dict):
                    selected_hotel["google_place_id"] = details.get("place_id") or (g.get("candidate") or {}).get("place_id")
                    selected_hotel["google_name"] = details.get("name") or (g.get("candidate") or {}).get("name")
                    selected_hotel["google_address"] = details.get("formatted_address") or (g.get("candidate") or {}).get("address")
                    selected_hotel["google_rating"] = details.get("rating") or (g.get("candidate") or {}).get("rating")
                    selected_hotel["google_user_ratings_total"] = details.get("user_ratings_total") or (g.get("candidate") or {}).get("user_ratings_total")

            # Fill nearby landmarks from Google when Booking didn't provide them.
            # Run this even if hotel-place matching failed, as long as coordinates exist.
            if not (selected_hotel.get("nearby_points") or selected_hotel.get("nearby")):
                lat = _parse_float_param(selected_hotel.get("latitude"))
                lon = _parse_float_param(selected_hotel.get("longitude"))
                if lat is not None and lon is not None:
                    google_nearby_points = []
                    seen_poi = set()
                    for poi_type, radius in [
                        ("train_station", 2000),
                        ("subway_station", 1500),
                        ("tourist_attraction", 3000),
                        ("restaurant", 1200),
                        ("convenience_store", 1000),
                    ]:
                        try:
                            nearby_resp = get_google_places(lat, lon, radius=radius, type=poi_type)
                        except Exception:
                            nearby_resp = {}
                        for row in nearby_resp.get("results", []) if isinstance(nearby_resp, dict) else []:
                            if not isinstance(row, dict):
                                continue
                            name = (row.get("name") or "").strip()
                            if not name:
                                continue
                            pid = row.get("place_id") or name
                            if pid in seen_poi:
                                continue
                            seen_poi.add(pid)

                            distance_label = None
                            geom = row.get("geometry") or {}
                            loc = geom.get("location") or {}
                            plat = _parse_float_param(loc.get("lat"))
                            plon = _parse_float_param(loc.get("lng"))
                            if (
                                lat is not None and lon is not None
                                and plat is not None and plon is not None
                            ):
                                try:
                                    meters = _haversine_meters(lat, lon, plat, plon)
                                    distance_label = (
                                        f"{round(meters/1000, 1)}km"
                                        if meters >= 1000
                                        else f"{int(round(meters))}m"
                                    )
                                except Exception:
                                    distance_label = None

                            google_nearby_points.append(
                                {
                                    "name": name,
                                    "distance": distance_label,
                                    "label": f"{name} 쨌 {distance_label}" if distance_label else name,
                                    "source": "google",
                                    "type": poi_type,
                                }
                            )
                            if len(google_nearby_points) >= 10:
                                break
                        if len(google_nearby_points) >= 10:
                            break

                    if google_nearby_points:
                        selected_hotel["nearby_points"] = google_nearby_points
                        selected_hotel["nearby"] = [p.get("label") or p.get("name") for p in google_nearby_points[:2]]
        except Exception as e:
            try:
                _log_translate_issue(f"google_place_enrich_exception={e}")
            except Exception:
                pass

    return templates.TemplateResponse(
        "gloval-hotel-detail.html",
        {
            "request": request,
            "nickname": nickname,
            "hotel": selected_hotel,
            "error_message": error_message,
            "city": city,
            "country": country,
            "checkin": checkin,
            "checkout": checkout,
            "nights": nights,
            "google_place": google_place,
        },
    )


@app.get("/gloval", response_class=HTMLResponse)
def gloval_alias(request: Request):
    # Legacy route alias
    nickname = get_nickname_from_request(request)
    return templates.TemplateResponse("gloval-hotel.html", {"request": request, "nickname": nickname})


@app.get("/users")
def read_users(db: Session = Depends(get_db)):
    return [
        {"id": u.id, "name": u.name, "nickname": u.nickname, "email": u.email, "phone": u.phone}
        for u in db.query(User).all()
    ]


@app.post("/users")
def create_user(
    request: Request,
    nickname: str = Form(...),
    username: str = Form(...),
    password: str = Form(...),
    password_confirm: str = Form(...),
    email: str = Form(...),
    phone: str = Form(...),
    db: Session = Depends(get_db),
):
    if db.query(User).filter(User.email == email).first():
        return templates.TemplateResponse("join.html", {"request": request, "error": "이미 사용 중인 이메일입니다."})
    if db.query(User).filter(User.phone == phone).first():
        return templates.TemplateResponse("join.html", {"request": request, "error": "이미 사용 중인 휴대폰 번호입니다."})
    if db.query(User).filter(User.nickname == nickname).first():
        return templates.TemplateResponse("join.html", {"request": request, "error": "이미 사용 중인 닉네임입니다."})
    if password != password_confirm:
        return templates.TemplateResponse("join.html", {"request": request, "error": "비밀번호가 일치하지 않습니다."})
    validation_error = _validate_signup(password, email, phone)
    if validation_error:
        return templates.TemplateResponse("join.html", {"request": request, "error": validation_error})

    user = User(name=username, password=_hash_password(password), nickname=nickname, email=email, phone=phone)
    db.add(user)
    db.commit()
    db.refresh(user)
    return RedirectResponse(url="/login", status_code=302)

@app.get("/pack-detail", response_class=HTMLResponse)
async def pack_detail(request: Request):
    # 로그인 여부 및 닉네임 추출 (예시)
    session_token = request.cookies.get("session_token")
    user_id = get_user_id_from_session(session_token) if session_token else None
    nickname = None
    user_is_authenticated = False
    if user_id:
        db = SessionLocal()
        try:
            user = db.query(User).filter(User.id == int(user_id)).first()
            if user:
                nickname = user.nickname
                user_is_authenticated = True
        finally:
            db.close()
    return templates.TemplateResponse(
        "pack-detail.html",
        {
            "request": request,
            "user_is_authenticated": user_is_authenticated,
            "nickname": nickname,
        },
    )
