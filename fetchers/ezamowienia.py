from datetime import date, timedelta

import requests

from normalize import normalize_ezamowienia

API_URL = "https://ezamowienia.gov.pl/mo-board/api/v1/notice"


def fetch(lookback_days: int = 30) -> list[dict]:
    date_to = date.today()
    date_from = date_to - timedelta(days=lookback_days)
    params = {
        "PageSize": 100,
        "NoticeType": "ContractNotice",
        "PublicationDateFrom": date_from.isoformat(),
        "PublicationDateTo": date_to.isoformat(),
    }
    response = requests.get(API_URL, params=params, timeout=15)
    response.raise_for_status()
    notices = response.json()
    return [normalize_ezamowienia(notice) for notice in notices]
