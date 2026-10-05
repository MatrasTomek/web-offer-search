from bs4 import BeautifulSoup

from normalize import normalize_freelancer
from scrape_utils import rate_limited_get, robots_allows

BASE_URL = "https://www.freelancer.com"
LISTING_PATH = "/jobs/website-design"
LISTING_URL = BASE_URL + LISTING_PATH


def fetch() -> list[dict]:
    if not robots_allows(BASE_URL, LISTING_PATH):
        raise RuntimeError(f"robots.txt disallows {LISTING_PATH} on {BASE_URL}")
    response = rate_limited_get(LISTING_URL)
    soup = BeautifulSoup(response.text, "html.parser")
    raw_items = [
        _parse_card(card)
        for card in soup.select("div.JobSearchCard-item-inner")
        if card.select_one("a.JobSearchCard-primary-heading-link")
    ]
    return [normalize_freelancer(item) for item in raw_items]


def _parse_card(card) -> dict:
    link_el = card.select_one("a.JobSearchCard-primary-heading-link")
    desc_el = card.select_one("p.JobSearchCard-primary-description")
    price_el = card.select_one("div.JobSearchCard-primary-price")
    days_el = card.select_one("span.JobSearchCard-primary-heading-days")
    link = link_el["href"]
    if link.startswith("/"):
        link = BASE_URL + link
    return {
        "title": link_el.get_text(strip=True),
        "description": desc_el.get_text(strip=True) if desc_el else "",
        "budget": price_el.get_text(strip=True) if price_el else None,
        "date": days_el.get_text(strip=True) if days_el else "",
        "link": link,
    }
