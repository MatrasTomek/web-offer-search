import time
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

import requests

_last_request_at: dict[str, float] = {}


def robots_allows(base_url: str, path: str, user_agent: str = "*") -> bool:
    try:
        response = requests.get(base_url.rstrip("/") + "/robots.txt", timeout=10)
    except requests.RequestException:
        return True
    if response.status_code != 200:
        return True
    parser = RobotFileParser()
    parser.parse(response.text.splitlines())
    return parser.can_fetch(user_agent, path)


def rate_limited_get(url: str, delay: float = 2.0, **kwargs) -> requests.Response:
    domain = urlparse(url).netloc
    now = time.monotonic()
    wait = delay - (now - _last_request_at.get(domain, 0.0))
    if wait > 0:
        time.sleep(wait)
    _last_request_at[domain] = time.monotonic()
    response = requests.get(url, timeout=10, **kwargs)
    response.raise_for_status()
    return response
