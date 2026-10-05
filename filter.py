import re
from config import KEYWORDS_PL, KEYWORDS_EN, CPV_PREFIX

_ALL_KEYWORD_GROUPS = [
    tuple(stem.lower() for stem in group) for group in (KEYWORDS_PL + KEYWORDS_EN)
]
_CPV_8DIGIT_RE = re.compile(r"^\d{8}$")


def is_relevant(lead: dict) -> bool:
    if lead.get("category") == "przetarg":
        for code in lead.get("cpv", []):
            if _CPV_8DIGIT_RE.match(code) and code.startswith(CPV_PREFIX):
                return True
    text = f"{lead['title']} {lead['description']}".lower()
    return any(all(stem in text for stem in group) for group in _ALL_KEYWORD_GROUPS)


def dedup_within_batch(leads: list[dict]) -> list[dict]:
    seen_links = set()
    deduped = []
    for lead in leads:
        if lead["link"] in seen_links:
            continue
        seen_links.add(lead["link"])
        deduped.append(lead)
    return deduped
