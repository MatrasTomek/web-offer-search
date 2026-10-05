from datetime import date, timedelta

import requests

from normalize import normalize_ezamowienia

API_URL = "https://ezamowienia.gov.pl/mo-board/api/v1/notice"

# The API caps each query at 100 notices and ignores paging, but filters
# server-side on OrderObject (title), so one query per term widens coverage.
TITLE_TERMS = ["strona", "aplikacj", "www", "sklep", "portal", "oprogramowan"]


def fetch(lookback_days: int = 30) -> list[dict]:
    date_to = date.today()
    date_from = date_to - timedelta(days=lookback_days)
    notices_by_id: dict[str, dict] = {}
    for term in TITLE_TERMS:
        params = {
            "PageSize": 100,
            "NoticeType": "ContractNotice",
            "PublicationDateFrom": date_from.isoformat(),
            "PublicationDateTo": date_to.isoformat(),
            "OrderObject": term,
        }
        response = requests.get(API_URL, params=params, timeout=15)
        response.raise_for_status()
        for notice in response.json():
            notices_by_id.setdefault(notice["tenderId"], notice)
    return [normalize_ezamowienia(notice) for notice in notices_by_id.values()]
