import os
import datetime as _dt
import time as _time

import requests
from dotenv import load_dotenv

load_dotenv()
BOOKING_RAPIDAPI_KEY = os.getenv("BOOKING_RAPIDAPI_KEY")
BOOKING_RAPIDAPI_HOST = os.getenv("BOOKING_RAPIDAPI_HOST")


def _clean_env_token(value):
    s = str(value or "").strip()
    if not s:
        return ""
    # .env 값 뒤 주석(#...)이 붙어도 실제 토큰만 사용
    if "#" in s:
        s = s.split("#", 1)[0].strip()
    return s


def _ascii_header_value(value):
    s = _clean_env_token(value)
    if not s:
        return ""
    return s.encode("ascii", "ignore").decode("ascii").strip()


def _safe_country_location(value, default="US"):
    s = str(value or "").strip().upper()
    s = "".join(ch for ch in s if "A" <= ch <= "Z")
    if len(s) == 2:
        return s
    return default


def _parse_booking_datetime(value):
    s = str(value or "").strip()
    if not s:
        return None
    s = s.replace("T", " ")
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            return _dt.datetime.strptime(s, fmt)
        except Exception:
            pass
    return None


def _booking_date_part(value):
    dt = _parse_booking_datetime(value)
    if dt:
        return dt.strftime("%Y-%m-%d")
    s = str(value or "").strip().replace("T", " ")
    return s.split(" ")[0] if s else ""


def _booking_time_part(value, include_seconds=True):
    dt = _parse_booking_datetime(value)
    if dt:
        return dt.strftime("%H:%M:%S" if include_seconds else "%H:%M")
    s = str(value or "").strip().replace("T", " ")
    if " " in s:
        t = s.split(" ", 1)[1].strip()
        if len(t) == 5:
            return t if not include_seconds else f"{t}:00"
        if len(t) == 8 and not include_seconds:
            return t[:5]
        return t
    return "10:00:00" if include_seconds else "10:00"


def _safe_json(response):
    try:
        return response.json()
    except Exception:
        return {"message": (response.text or "")[:300]}


def _is_generic_provider_failure(data):
    if not isinstance(data, dict):
        return False
    joined = f"{data.get('message') or ''} {data.get('error') or ''}".lower()
    return "something went wrong" in joined


def _finalize_error(data, status_code):
    if not isinstance(data, dict):
        return {"error": "렌터카 API 응답 형식이 올바르지 않습니다."}

    msg = str(data.get("message") or "").strip()
    if msg and "something went wrong" in msg.lower():
        data["error"] = "렌터카 API 서비스 일시 오류입니다. 잠시 후 다시 시도해 주세요."
    if status_code >= 400 and not data.get("error"):
        data["error"] = f"렌터카 API 오류 (HTTP {status_code})"
    return data


def search_car_rentals(
    pick_up_lat,
    pick_up_lon,
    drop_off_lat,
    drop_off_lon,
    pick_up_time,
    drop_off_time,
    driver_age=30,
    currency_code="USD",
    location="US",
):
    rapidapi_host = _ascii_header_value(BOOKING_RAPIDAPI_HOST)
    rapidapi_key = _ascii_header_value(BOOKING_RAPIDAPI_KEY)
    if not rapidapi_host or not rapidapi_key:
        return {"error": "렌터카 API 설정이 올바르지 않습니다. 관리자에게 문의해 주세요."}

    url = f"https://{rapidapi_host}/api/v1/cars/searchCarRentals"
    headers = {
        "x-rapidapi-key": rapidapi_key,
        "x-rapidapi-host": rapidapi_host,
    }
    base_params = {
        "pick_up_latitude": pick_up_lat,
        "pick_up_longitude": pick_up_lon,
        "drop_off_latitude": drop_off_lat,
        "drop_off_longitude": drop_off_lon,
        "pick_up_date": _booking_date_part(pick_up_time),
        "pick_up_time": _booking_time_part(pick_up_time, include_seconds=False),
        "drop_off_date": _booking_date_part(drop_off_time),
        "drop_off_time": _booking_time_part(drop_off_time, include_seconds=False),
        "driver_age": driver_age,
        "currency_code": currency_code,
        "location": _safe_country_location(location),
    }

    attempts = []
    attempts.append(dict(base_params))  # HH:MM + location
    if base_params.get("location"):
        alt = dict(base_params)
        alt.pop("location", None)
        attempts.append(alt)  # HH:MM, no location

    sec_with_location = dict(base_params)
    sec_with_location["pick_up_time"] = _booking_time_part(pick_up_time, include_seconds=True)
    sec_with_location["drop_off_time"] = _booking_time_part(drop_off_time, include_seconds=True)
    attempts.append(sec_with_location)  # HH:MM:SS + location
    if base_params.get("location"):
        sec_no_location = dict(sec_with_location)
        sec_no_location.pop("location", None)
        attempts.append(sec_no_location)  # HH:MM:SS, no location

    last_data = None
    last_status = 0
    for attempt_index, params in enumerate(attempts):
        waits = [0, 1, 2] if attempt_index == 0 else [0, 1]
        for wait_sec in waits:
            if wait_sec:
                _time.sleep(wait_sec)
            try:
                response = requests.get(url, headers=headers, params=params, timeout=20)
                last_status = response.status_code
                data = _safe_json(response)
            except Exception as e:
                last_data = {"error": f"렌터카 API 요청 실패: {e}"}
                continue

            if not isinstance(data, dict):
                data = {"message": str(data)}

            # return immediately when provider response is not a transient failure/HTTP error
            if response.status_code < 400 and not _is_generic_provider_failure(data):
                return data

            last_data = data

            # transient failures: retry same variant
            if response.status_code == 429 or _is_generic_provider_failure(data):
                continue

            # non-transient errors: move to next variant (e.g. remove location)
            break

    return _finalize_error(last_data or {}, last_status)
