import requests

EXCHANGE_API_URL = "https://api.exchangerate.host/latest"

# 환율 정보 조회 (기본: USD→KRW)
def get_exchange_rate(base="USD", target="KRW"):
    params = {"base": base, "symbols": target}
    resp = requests.get(EXCHANGE_API_URL, params=params, timeout=5)
    resp.raise_for_status()
    data = resp.json()
    return data["rates"][target] if "rates" in data and target in data["rates"] else None
