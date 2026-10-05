from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

from normalize import normalize_peopleperhour
from scrape_utils import robots_allows

BASE_URL = "https://www.peopleperhour.com"
LISTING_PATH = "/freelance-jobs"
LISTING_URL = BASE_URL + LISTING_PATH


def fetch() -> list[dict]:
    if not robots_allows(BASE_URL, LISTING_PATH):
        raise RuntimeError(f"robots.txt disallows {LISTING_PATH} on {BASE_URL}")
    html = _render_listing_html()
    raw_items = _parse_cards(html)
    return [normalize_peopleperhour(item) for item in raw_items]


def _render_listing_html() -> str:
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page()
        page.goto(LISTING_URL, wait_until="networkidle")
        html = page.content()
        browser.close()
        return html


def _parse_cards(html: str) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    items = []
    for title_el in soup.select('h6[class*="item__title"]'):
        link_el = title_el.select_one("a")
        if not link_el or not link_el.get("href"):
            continue
        card = title_el.find_parent(
            "div", class_=lambda c: c and "item--container" in c
        )
        desc_el = card.select_one('p[class*="item__desc"]') if card else None
        price_el = card.select_one('div[class*="card__price"] span') if card else None
        footer_el = card.select_one('div[class*="card__footer-left"] span') if card else None
        items.append(
            {
                "title": link_el.get_text(strip=True),
                "description": desc_el.get_text(strip=True) if desc_el else "",
                "budget": price_el.get_text(strip=True) if price_el else None,
                "date": footer_el.get_text(strip=True) if footer_el else "",
                "link": link_el["href"],
            }
        )
    return items
