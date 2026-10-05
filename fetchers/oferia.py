from bs4 import BeautifulSoup

from normalize import normalize_oferia
from scrape_utils import rate_limited_get, robots_allows

BASE_URL = "https://oferia.com.pl"
LISTING_PATH = "/pl/zlecenia/programowanie-it"
LISTING_URL = BASE_URL + LISTING_PATH


def fetch() -> list[dict]:
    if not robots_allows(BASE_URL, LISTING_PATH):
        raise RuntimeError(f"robots.txt disallows {LISTING_PATH} on {BASE_URL}")
    response = rate_limited_get(LISTING_URL)
    soup = BeautifulSoup(response.text, "html.parser")
    raw_items = [_parse_card(card) for card in soup.select("div.listing-card") if card.select_one("h3.listing-title a")]
    return [normalize_oferia(item) for item in raw_items]


def _parse_card(card) -> dict:
    title_el = card.select_one("h3.listing-title a")
    excerpt_el = card.select_one("p.listing-excerpt")
    budget_el = card.select_one("div.listing-budget span")
    date_el = card.select_one("div.listing-date")
    link = title_el["href"]
    if link.startswith("/"):
        link = BASE_URL + link
    return {
        "title": title_el.get_text(strip=True),
        "description": excerpt_el.get_text(strip=True) if excerpt_el else "",
        "budget": budget_el.get_text(strip=True) if budget_el else None,
        "date": date_el.get_text(strip=True) if date_el else "",
        "link": link,
    }
