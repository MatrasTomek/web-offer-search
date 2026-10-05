from datetime import date, timedelta

import requests

from normalize import normalize_ted

API_URL = "https://api.ted.europa.eu/v3/notices/search"


def fetch(lookback_days: int = 30) -> list[dict]:
    date_from = (date.today() - timedelta(days=lookback_days)).strftime("%Y%m%d")
    payload = {
        "query": f"classification-cpv IN (72000000) AND publication-date >= {date_from}",
        "fields": ["ND", "TI", "PD", "CY", "classification-cpv", "links"],
        "limit": 100,
    }
    response = requests.post(API_URL, json=payload, timeout=15)
    response.raise_for_status()
    notices = response.json().get("notices", [])
    return [normalize_ted(notice) for notice in notices]
