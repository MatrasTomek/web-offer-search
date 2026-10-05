import re
from typing import Optional

_CPV_8DIGIT_RE = re.compile(r"\d{8}")


def _lead(
    source: str,
    title: str,
    description: str,
    value: Optional[str],
    published_at: str,
    link: str,
    category: str,
) -> dict:
    return {
        "source": source,
        "title": title,
        "description": description,
        "value": value,
        "published_at": published_at,
        "link": link,
        "category": category,
    }


def _extract_cpv_codes(cpv_field: str) -> list[str]:
    return _CPV_8DIGIT_RE.findall(cpv_field)


def normalize_ezamowienia(raw: dict) -> dict:
    lead = _lead(
        source="e-Zamówienia",
        title=raw["orderObject"],
        description=raw["orderObject"],
        value=None,
        published_at=raw["publicationDate"],
        link=f"https://ezamowienia.gov.pl/mp-client/search/list/{raw['tenderId']}",
        category="przetarg",
    )
    lead["cpv"] = _extract_cpv_codes(raw.get("cpvCode") or "")
    return lead


def normalize_ted(raw: dict) -> dict:
    titles = raw.get("TI", {})
    title = titles.get("eng") or next(iter(titles.values()), "")
    html_links = raw.get("links", {}).get("htmlDirect", {})
    link = html_links.get("ENG") or next(iter(html_links.values()), "")
    lead = _lead(
        source="TED",
        title=title,
        description=title,
        value=None,
        published_at=raw["PD"],
        link=link,
        category="przetarg",
    )
    lead["cpv"] = raw.get("classification-cpv", [])
    return lead


def normalize_oferia(raw: dict) -> dict:
    return _lead(
        source="Oferia.com.pl",
        title=raw["title"],
        description=raw["description"],
        value=raw.get("budget"),
        published_at=raw["date"],
        link=raw["link"],
        category="b2b",
    )


def normalize_freelancer(raw: dict) -> dict:
    return _lead(
        source="Freelancer.com",
        title=raw["title"],
        description=raw["description"],
        value=raw.get("budget"),
        published_at=raw["date"],
        link=raw["link"],
        category="freelance",
    )


def normalize_peopleperhour(raw: dict) -> dict:
    return _lead(
        source="PeoplePerHour",
        title=raw["title"],
        description=raw["description"],
        value=raw.get("budget"),
        published_at=raw["date"],
        link=raw["link"],
        category="freelance",
    )
