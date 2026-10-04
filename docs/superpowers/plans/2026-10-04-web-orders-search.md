# web-orders-search Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a manually-run Python script that fetches current web-dev/web-app leads from five verified free sources (e-Zamówienia, TED, Oferia.com.pl, Freelancer.com, PeoplePerHour), filters them for relevance, tracks which are new since the last run, and renders them into a single offline HTML report table.

**Architecture:** A small pipeline of pure, independently-testable modules (`normalize.py`, `filter.py`, `store.py`, `report.py`, `scrape_utils.py`) plus one `fetch()` function per source under `fetchers/`, orchestrated by `run.py`. Each fetcher turns its source's native data (JSON API or scraped HTML) into the shared Lead schema by calling the matching `normalize_*` function; `run.py` isolates failures per source so one broken fetcher never blocks the others.

**Tech Stack:** Python 3.14, `requests`, `beautifulsoup4`, `playwright` (Chromium, only for the PeoplePerHour fetcher), `pytest`.

**Spec:** `docs/superpowers/specs/2026-10-04-web-orders-search-design.md` (including the 2026-10-04 technical-verification addendum — read both; the addendum overrides the original 6-source scope with the verified 5-source v1 scope).

## Global Constraints

- Darmowe/publiczne źródła tylko — no paid APIs, no paid proxies, no paid scraping services.
- No automatic account creation or login anywhere. Useme is excluded from v1 entirely (Cloudflare blocks scraping even via Playwright); it becomes a fast-follow fetcher only once the official API access (requested by email) is granted.
- `report.html` must render correctly when opened directly from disk, offline, with zero external CDN dependencies (no CDN `<script>`/`<link>` tags).
- Run mode is manual/on-demand only — no cron/scheduler in v1.
- Scraping fetchers (Oferia, Freelancer.com, PeoplePerHour) must check `robots.txt` once per run before fetching, and must rate-limit to one request per 2 seconds per domain (`RATE_LIMIT_DELAY_SECONDS = 2.0`).
- CPV relevance filter for tender sources (e-Zamówienia, TED) uses prefix `"72"` (covers the 72000000–72999999 range).
- A failing fetcher (network error, robots disallow, parse error) must not stop the other fetchers from running, and must be listed by name in the generated report.

## Review Focus

- CPV codes from e-Zamówienia arrive as a free-text string with a human-readable suffix (e.g. `"34121000-1 (Autobusy i autokary)"`), sometimes with multiple codes — extraction must pull out only the bare 8-digit codes, not crash on the suffix or silently treat the whole string as one code. → Task 2.
- Neither e-Zamówienia nor TED's search API returns a budget/value field — leads from those two sources must always have `value: None` and the report must render a clear placeholder (`—`), never the literal text `"None"`. → Task 2 and Task 6.
- The same lead reappearing across separate runs (same `link`) must be marked as already-seen (`is_new: False`), never re-flagged as `"NOWE"` on every run. → Task 4.
- A scraping source whose `robots.txt` disallows the listing path, or whose HTTP request fails/times out, must disable only that source and appear by name in the report's "nie odpowiedziały" list — not crash the whole run. → Task 5 and Task 12.
- A run where zero leads pass the relevance filter must still produce a valid, readable `report.html` (with an explicit "no leads" message) instead of an empty or malformed table. → Task 6.

---

### Task 1: Project scaffolding and config

**Files:**
- Create: `requirements.txt`
- Create: `config.py`
- Create: `tests/__init__.py` (empty — see note below)
- Create: `.gitignore` (already exists from brainstorming — append `report.html` and confirm `data/` is present)
- Test: `tests/test_config.py`

**Interfaces:**
- Produces: `config.BASE_DIR: Path`, `config.DATA_DIR: Path`, `config.SEEN_STORE_PATH: Path`, `config.REPORT_PATH: Path`, `config.CPV_PREFIX: str`, `config.KEYWORDS_PL: list[tuple[str, ...]]`, `config.KEYWORDS_EN: list[tuple[str, ...]]`, `config.RATE_LIMIT_DELAY_SECONDS: float`, `config.ROBOTS_USER_AGENT: str` — every later task imports from this module. Each keyword entry is a tuple of stems that must **all** co-occur in a lead's text (see Task 3) — not a whole phrase — because Polish declines nouns/adjectives by case and a literal phrase match misses most real postings (e.g. "strona internetowa" never appears verbatim in "potrzebuję **strony internetowej**").

**Note on `tests/__init__.py`:** Task 7 onward adds test files under `tests/fetchers/`, mirroring the `fetchers/` package. Without a `tests/__init__.py` present, pytest's default import mode registers that subdirectory's own `__init__.py` as the top-level module name `fetchers` (shadowing the real `fetchers/` package at the project root), and `from fetchers import ezamowienia` then fails with a confusing `ImportError: cannot import name 'ezamowienia' from 'fetchers'` pointing at the *test* directory. Creating `tests/__init__.py` now (even though it's empty) makes pytest import test modules by their full dotted path (`tests.fetchers.test_ezamowienia`) instead, avoiding the collision. This was caught by actually running the full suite while verifying this plan — it is not a hypothetical.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_config.py
from pathlib import Path
import config

def test_paths_are_under_base_dir():
    assert isinstance(config.DATA_DIR, Path)
    assert config.DATA_DIR == config.BASE_DIR / "data"
    assert config.SEEN_STORE_PATH == config.DATA_DIR / "seen.json"
    assert config.REPORT_PATH == config.BASE_DIR / "report.html"

def test_cpv_prefix_covers_it_services_range():
    assert config.CPV_PREFIX == "72"

def test_keyword_lists_are_non_empty_tuples_of_lowercase_stems():
    assert len(config.KEYWORDS_PL) >= 5
    assert len(config.KEYWORDS_EN) >= 5
    all_groups = config.KEYWORDS_PL + config.KEYWORDS_EN
    assert all(isinstance(group, tuple) and len(group) >= 1 for group in all_groups)
    assert all(
        isinstance(stem, str) and stem == stem.lower()
        for group in all_groups
        for stem in group
    )

def test_rate_limit_and_robots_defaults():
    assert config.RATE_LIMIT_DELAY_SECONDS == 2.0
    assert config.ROBOTS_USER_AGENT == "*"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_config.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'config'`

- [ ] **Step 3: Write minimal implementation**

```python
# config.py
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
SEEN_STORE_PATH = DATA_DIR / "seen.json"
REPORT_PATH = BASE_DIR / "report.html"

CPV_PREFIX = "72"

# Each entry is a tuple of stems that must ALL co-occur in the lead's text.
# Polish declines nouns/adjectives by case (e.g. "strona internetowa" ->
# "strony internetowej", "stronę internetową", ...), so a literal phrase
# match on the nominative form misses most real postings. Using the common
# stem of each word ("stron", "internetow") instead of the full word is what
# makes the match survive case inflection; single-stem tuples are for
# borrowed/technical terms that don't decline in Polish business usage.
KEYWORDS_PL = [
    ("stron", "internetow"),
    ("stron", "www"),
    ("aplikacj", "webow"),
    ("aplikacj", "mobiln"),
    ("serwis", "www"),
    ("portal", "internetow"),
    ("sklep", "internetow"),
    ("e-commerce",),
    ("frontend",),
    ("backend",),
    ("wordpress",),
    ("landing page",),
]

KEYWORDS_EN = [
    ("website",),
    ("web app",),
    ("web application",),
    ("frontend",),
    ("backend",),
    ("e-commerce",),
    ("landing page",),
    ("wordpress",),
]

RATE_LIMIT_DELAY_SECONDS = 2.0
ROBOTS_USER_AGENT = "*"
```

```text
# requirements.txt
requests
beautifulsoup4
playwright
pytest
```

`tests/__init__.py` is an empty file — no content to show.

- [ ] **Step 4: Run test to verify it passes**

Run: `pip install -r requirements.txt && pytest tests/test_config.py -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
git add requirements.txt config.py tests/__init__.py tests/test_config.py
git commit -m "feat: add project config module"
```

---

### Task 2: normalize.py — map raw source data to the common Lead schema

**Files:**
- Create: `normalize.py`
- Test: `tests/test_normalize.py`

**Interfaces:**
- Consumes: nothing from earlier tasks (pure functions over plain dicts).
- Produces: `normalize.normalize_ezamowienia(raw: dict) -> dict`, `normalize.normalize_ted(raw: dict) -> dict`, `normalize.normalize_oferia(raw: dict) -> dict`, `normalize.normalize_freelancer(raw: dict) -> dict`, `normalize.normalize_peopleperhour(raw: dict) -> dict`. Every one returns a **Lead** dict with keys `source: str`, `title: str`, `description: str`, `value: str | None`, `published_at: str`, `link: str`, `category: "przetarg" | "freelance" | "b2b"`, plus `cpv: list[str]` **only** on `przetarg`-category leads (bare 8-digit CPV codes, no description suffix). Later tasks (`filter.py`, `store.py`, `report.py`, all fetchers) rely on exactly these keys and the `cpv` convention.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_normalize.py
import normalize

def test_normalize_ezamowienia_extracts_bare_cpv_codes_and_builds_link():
    raw = {
        "orderObject": "Zakup 22 osobowego autobusu do przewozu osób niepełnosprawnych",
        "cpvCode": "34121000-1 (Autobusy i autokary)",
        "publicationDate": "2026-09-01T03:08:03.1326153Z",
        "tenderId": "ocds-148610-5410c99c-ce3c-4e8e-80b1-189da9952afe",
    }
    lead = normalize.normalize_ezamowienia(raw)
    assert lead["source"] == "e-Zamówienia"
    assert lead["title"] == raw["orderObject"]
    assert lead["value"] is None
    assert lead["published_at"] == raw["publicationDate"]
    assert lead["link"] == (
        "https://ezamowienia.gov.pl/mp-client/search/list/"
        "ocds-148610-5410c99c-ce3c-4e8e-80b1-189da9952afe"
    )
    assert lead["category"] == "przetarg"
    assert lead["cpv"] == ["34121000"]

def test_normalize_ezamowienia_handles_multiple_comma_joined_cpv_codes():
    raw = {
        "orderObject": "Usługi informatyczne i dostawa sprzętu",
        "cpvCode": "72212000-4 (Usługi programowania), 30213000-5 (Komputery osobiste)",
        "publicationDate": "2026-09-02T00:00:00Z",
        "tenderId": "ocds-148610-aaaa",
    }
    lead = normalize.normalize_ezamowienia(raw)
    assert lead["cpv"] == ["72212000", "30213000"]

def test_normalize_ted_picks_english_title_and_direct_link():
    raw = {
        "ND": "599742-2026",
        "TI": {"pol": "Tytuł po polsku", "eng": "Title in English"},
        "PD": "2026-09-01+02:00",
        "CY": ["POL"],
        "classification-cpv": ["72224000", "79421100"],
        "links": {
            "htmlDirect": {
                "ENG": "https://ted.europa.eu/en/notice/599742-2026/html",
                "POL": "https://ted.europa.eu/pl/notice/599742-2026/html",
            }
        },
    }
    lead = normalize.normalize_ted(raw)
    assert lead["source"] == "TED"
    assert lead["title"] == "Title in English"
    assert lead["value"] is None
    assert lead["published_at"] == "2026-09-01+02:00"
    assert lead["link"] == "https://ted.europa.eu/en/notice/599742-2026/html"
    assert lead["category"] == "przetarg"
    assert lead["cpv"] == ["72224000", "79421100"]

def test_normalize_ted_falls_back_to_any_language_when_english_missing():
    raw = {
        "ND": "1-2026",
        "TI": {"pol": "Tylko polski tytuł"},
        "PD": "2026-09-01+02:00",
        "CY": ["POL"],
        "classification-cpv": ["72000000"],
        "links": {"htmlDirect": {"POL": "https://ted.europa.eu/pl/notice/1-2026/html"}},
    }
    lead = normalize.normalize_ted(raw)
    assert lead["title"] == "Tylko polski tytuł"
    assert lead["link"] == "https://ted.europa.eu/pl/notice/1-2026/html"

def test_normalize_oferia_maps_scraped_fields():
    raw = {
        "title": "Pilnie potrzebuję osoby do konfiguracji konwersji",
        "description": "Potrzebuję osoby, która pomoże mi skonfigurować konwersje.",
        "budget": "Do negocjacji",
        "date": "21.09.2026",
        "link": "https://oferia.com.pl/pl/zlecenie/1024",
    }
    lead = normalize.normalize_oferia(raw)
    assert lead["source"] == "Oferia.com.pl"
    assert lead["value"] == "Do negocjacji"
    assert lead["category"] == "b2b"
    assert "cpv" not in lead

def test_normalize_freelancer_maps_scraped_fields():
    raw = {
        "title": "Vibrant Business Website Showcase",
        "description": "I need a bright, colorful website...",
        "budget": "$18 / hr",
        "date": "6 days left",
        "link": "https://www.freelancer.com/projects/web-design/vibrant-business-website-showcase",
    }
    lead = normalize.normalize_freelancer(raw)
    assert lead["source"] == "Freelancer.com"
    assert lead["category"] == "freelance"
    assert lead["value"] == "$18 / hr"

def test_normalize_peopleperhour_maps_scraped_fields():
    raw = {
        "title": "Copy & Paste Images",
        "description": "Hello I have a simple project...",
        "budget": "$8",
        "date": "6 hours ago",
        "link": "https://www.peopleperhour.com/freelance-jobs/business/administration-assistance/copy-paste-images-4524971",
    }
    lead = normalize.normalize_peopleperhour(raw)
    assert lead["source"] == "PeoplePerHour"
    assert lead["category"] == "freelance"
    assert lead["value"] == "$8"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_normalize.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'normalize'`

- [ ] **Step 3: Write minimal implementation**

```python
# normalize.py
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
    """e-Zamówienia's cpvCode is free text like '34121000-1 (Autobusy i autokary)',
    sometimes several comma-joined codes. Pull out only the bare 8-digit codes."""
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_normalize.py -v`
Expected: PASS (9 tests)

- [ ] **Step 5: Commit**

```bash
git add normalize.py tests/test_normalize.py
git commit -m "feat: add normalize.py mapping raw source data to the Lead schema"
```

---

### Task 3: filter.py — relevance filtering and within-batch dedup

**Files:**
- Create: `filter.py`
- Test: `tests/test_filter.py`

**Interfaces:**
- Consumes: `config.KEYWORDS_PL`, `config.KEYWORDS_EN`, `config.CPV_PREFIX` (Task 1); Lead dicts shaped by `normalize.py` (Task 2).
- Produces: `filter.is_relevant(lead: dict) -> bool`, `filter.dedup_within_batch(leads: list[dict]) -> list[dict]` — both used by `run.py` (Task 12).

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_filter.py
import filter as lead_filter


def _lead(**overrides):
    base = {
        "source": "Test",
        "title": "",
        "description": "",
        "value": None,
        "published_at": "2026-01-01",
        "link": "https://example.com/1",
        "category": "freelance",
    }
    base.update(overrides)
    return base


def test_is_relevant_matches_polish_keyword_in_title():
    lead = _lead(title="Potrzebuję strony internetowej dla firmy")
    assert lead_filter.is_relevant(lead) is True


def test_is_relevant_matches_polish_keyword_across_other_case_inflections():
    # Polish declines nouns/adjectives by case; these are all real forms of
    # "strona internetowa" that a naive whole-phrase match would miss.
    for phrase in [
        "zamawiam stronę internetową",
        "mam stronie internetowej problem z formularzem",
        "ile kosztuje kilka stron internetowych",
    ]:
        assert lead_filter.is_relevant(_lead(title=phrase)) is True


def test_is_relevant_matches_english_keyword_in_description():
    lead = _lead(description="Looking for a developer to build a website")
    assert lead_filter.is_relevant(lead) is True


def test_is_relevant_rejects_unrelated_lead():
    lead = _lead(title="Zakup 22 osobowego autobusu", description="dostawa pojazdu")
    assert lead_filter.is_relevant(lead) is False


def test_is_relevant_matches_tender_by_cpv_even_without_keyword():
    lead = _lead(
        category="przetarg",
        title="Usługa informatyczna bez słów kluczowych",
        description="opis bez dopasowania",
        cpv=["72212000"],
    )
    assert lead_filter.is_relevant(lead) is True


def test_is_relevant_rejects_tender_outside_cpv_range_without_keyword_match():
    lead = _lead(
        category="przetarg",
        title="Zakup autobusu",
        description="dostawa pojazdu",
        cpv=["34121000"],
    )
    assert lead_filter.is_relevant(lead) is False


def test_dedup_within_batch_removes_duplicate_links():
    leads = [_lead(link="https://example.com/1"), _lead(link="https://example.com/1")]
    deduped = lead_filter.dedup_within_batch(leads)
    assert len(deduped) == 1


def test_dedup_within_batch_keeps_distinct_links():
    leads = [_lead(link="https://example.com/1"), _lead(link="https://example.com/2")]
    deduped = lead_filter.dedup_within_batch(leads)
    assert len(deduped) == 2
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_filter.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'filter'`

- [ ] **Step 3: Write minimal implementation**

```python
# filter.py
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_filter.py -v`
Expected: PASS (8 tests)

- [ ] **Step 5: Commit**

```bash
git add filter.py tests/test_filter.py
git commit -m "feat: add filter.py for relevance and within-batch dedup"
```

---

### Task 4: store.py — cross-run history (new vs. already-seen)

**Files:**
- Create: `store.py`
- Test: `tests/test_store.py`

**Interfaces:**
- Consumes: nothing from earlier tasks directly (works on plain Lead dicts and a `Path`).
- Produces: `store.load_seen(path: Path) -> dict[str, dict]`, `store.save_seen(seen: dict[str, dict], path: Path) -> None`, `store.mark_new_or_seen(leads: list[dict], seen: dict[str, dict], now: str) -> tuple[list[dict], dict[str, dict]]` — `run.py` (Task 12) calls these in sequence; `report.py` (Task 6) reads the `is_new` key this step adds to each lead.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_store.py
from pathlib import Path
import store


def _lead(link="https://example.com/1", title="T", description="D"):
    return {
        "source": "Test",
        "title": title,
        "description": description,
        "value": None,
        "published_at": "2026-01-01",
        "link": link,
        "category": "freelance",
    }


def test_load_seen_returns_empty_dict_when_file_missing(tmp_path):
    assert store.load_seen(tmp_path / "missing.json") == {}


def test_save_then_load_round_trips(tmp_path):
    path = tmp_path / "seen.json"
    store.save_seen({"https://example.com/1": {"link": "https://example.com/1"}}, path)
    assert store.load_seen(path) == {"https://example.com/1": {"link": "https://example.com/1"}}


def test_mark_new_or_seen_flags_first_occurrence_as_new():
    leads = [_lead()]
    annotated, updated = store.mark_new_or_seen(leads, {}, now="2026-10-04T12:00:00Z")
    assert annotated[0]["is_new"] is True
    assert updated["https://example.com/1"]["first_seen"] == "2026-10-04T12:00:00Z"
    assert updated["https://example.com/1"]["last_seen"] == "2026-10-04T12:00:00Z"


def test_mark_new_or_seen_flags_repeat_link_as_not_new_and_keeps_first_seen():
    existing_seen = {
        "https://example.com/1": {
            "link": "https://example.com/1",
            "content_hash": "irrelevant-old-hash",
            "first_seen": "2026-09-01T00:00:00Z",
            "last_seen": "2026-09-01T00:00:00Z",
        }
    }
    leads = [_lead()]
    annotated, updated = store.mark_new_or_seen(leads, existing_seen, now="2026-10-04T12:00:00Z")
    assert annotated[0]["is_new"] is False
    assert updated["https://example.com/1"]["first_seen"] == "2026-09-01T00:00:00Z"
    assert updated["https://example.com/1"]["last_seen"] == "2026-10-04T12:00:00Z"


def test_mark_new_or_seen_treats_different_links_independently():
    leads = [_lead(link="https://example.com/1"), _lead(link="https://example.com/2")]
    annotated, updated = store.mark_new_or_seen(leads, {}, now="2026-10-04T12:00:00Z")
    assert all(lead["is_new"] for lead in annotated)
    assert set(updated.keys()) == {"https://example.com/1", "https://example.com/2"}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_store.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'store'`

- [ ] **Step 3: Write minimal implementation**

```python
# store.py
import hashlib
import json
from pathlib import Path


def _content_hash(lead: dict) -> str:
    text = f"{lead['title']}|{lead['description']}"
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def load_seen(path: Path) -> dict[str, dict]:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def save_seen(seen: dict[str, dict], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(seen, f, ensure_ascii=False, indent=2)


def mark_new_or_seen(
    leads: list[dict], seen: dict[str, dict], now: str
) -> tuple[list[dict], dict[str, dict]]:
    updated = {link: dict(entry) for link, entry in seen.items()}
    annotated = []
    for lead in leads:
        link = lead["link"]
        existing = updated.get(link)
        if existing is None:
            updated[link] = {
                "link": link,
                "content_hash": _content_hash(lead),
                "first_seen": now,
                "last_seen": now,
            }
            annotated.append({**lead, "is_new": True})
        else:
            existing["content_hash"] = _content_hash(lead)
            existing["last_seen"] = now
            annotated.append({**lead, "is_new": False})
    return annotated, updated
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_store.py -v`
Expected: PASS (5 tests)

- [ ] **Step 5: Commit**

```bash
git add store.py tests/test_store.py
git commit -m "feat: add store.py for cross-run new/seen lead tracking"
```

---

### Task 5: scrape_utils.py — robots.txt check and per-domain rate limiting

**Files:**
- Create: `scrape_utils.py`
- Test: `tests/test_scrape_utils.py`

**Interfaces:**
- Consumes: `requests` (third-party, installed in Task 1).
- Produces: `scrape_utils.robots_allows(base_url: str, path: str, user_agent: str = "*") -> bool`, `scrape_utils.rate_limited_get(url: str, delay: float = 2.0, **kwargs) -> requests.Response` — used by the Oferia, Freelancer.com and PeoplePerHour fetchers (Tasks 9, 10, 11).

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_scrape_utils.py
from urllib.robotparser import RobotFileParser
from unittest.mock import Mock, patch
import scrape_utils


def test_robots_allows_true_when_path_not_disallowed(monkeypatch):
    def fake_read(self):
        self.parse(["User-agent: *", "Disallow: /private/"])

    monkeypatch.setattr(RobotFileParser, "read", fake_read)
    assert scrape_utils.robots_allows("https://example.com", "/public/page") is True


def test_robots_allows_false_when_path_disallowed(monkeypatch):
    def fake_read(self):
        self.parse(["User-agent: *", "Disallow: /private/"])

    monkeypatch.setattr(RobotFileParser, "read", fake_read)
    assert scrape_utils.robots_allows("https://example.com", "/private/page") is False


def test_robots_allows_fails_open_when_robots_txt_unreachable(monkeypatch):
    def fake_read(self):
        raise OSError("connection refused")

    monkeypatch.setattr(RobotFileParser, "read", fake_read)
    assert scrape_utils.robots_allows("https://example.com", "/anything") is True


def test_rate_limited_get_sleeps_remaining_delay_for_same_domain(monkeypatch):
    times = iter([100.0, 100.3])
    monkeypatch.setattr(scrape_utils.time, "monotonic", lambda: next(times))
    sleep_calls = []
    monkeypatch.setattr(scrape_utils.time, "sleep", lambda s: sleep_calls.append(s))
    scrape_utils._last_request_at["example.com"] = 99.0

    fake_response = Mock(status_code=200)
    fake_response.raise_for_status = Mock()
    with patch.object(scrape_utils.requests, "get", return_value=fake_response) as mock_get:
        result = scrape_utils.rate_limited_get("https://example.com/page", delay=2.0)

    assert sleep_calls == [1.0]
    mock_get.assert_called_once()
    assert result is fake_response


def test_rate_limited_get_raises_on_http_error(monkeypatch):
    monkeypatch.setattr(scrape_utils.time, "monotonic", lambda: 200.0)
    monkeypatch.setattr(scrape_utils.time, "sleep", lambda s: None)

    fake_response = Mock(status_code=500)
    fake_response.raise_for_status = Mock(side_effect=scrape_utils.requests.HTTPError("boom"))
    with patch.object(scrape_utils.requests, "get", return_value=fake_response):
        try:
            scrape_utils.rate_limited_get("https://example.com/page")
            assert False, "expected HTTPError"
        except scrape_utils.requests.HTTPError:
            pass
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_scrape_utils.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'scrape_utils'`

- [ ] **Step 3: Write minimal implementation**

```python
# scrape_utils.py
import time
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

import requests

_last_request_at: dict[str, float] = {}


def robots_allows(base_url: str, path: str, user_agent: str = "*") -> bool:
    parser = RobotFileParser()
    parser.set_url(base_url.rstrip("/") + "/robots.txt")
    try:
        parser.read()
    except OSError:
        return True
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_scrape_utils.py -v`
Expected: PASS (5 tests)

- [ ] **Step 5: Commit**

```bash
git add scrape_utils.py tests/test_scrape_utils.py
git commit -m "feat: add scrape_utils.py for robots.txt checks and rate limiting"
```

---

### Task 6: report.py — render the offline HTML report

**Files:**
- Create: `report.py`
- Test: `tests/test_report.py`

**Interfaces:**
- Consumes: Lead dicts annotated with `is_new` (Task 4's output); a list of failed source names (strings).
- Produces: `report.render_html(leads: list[dict], failed_sources: list[str], generated_at: str) -> str`, `report.write_report(leads: list[dict], failed_sources: list[str], generated_at: str, path: Path) -> None` — called by `run.py` (Task 12).

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_report.py
from pathlib import Path
import report


def _lead(**overrides):
    base = {
        "source": "Test Source",
        "title": "Przykładowy tytuł",
        "description": "Przykładowy opis zlecenia",
        "value": "1000 PLN",
        "published_at": "2026-10-01",
        "link": "https://example.com/lead/1",
        "category": "freelance",
        "is_new": True,
    }
    base.update(overrides)
    return base


def test_render_html_includes_lead_fields_and_marks_new_rows():
    html = report.render_html([_lead()], failed_sources=[], generated_at="2026-10-04 20:00")
    assert "Przykładowy tytuł" in html
    assert "https://example.com/lead/1" in html
    assert "1000 PLN" in html
    assert "new-lead" in html


def test_render_html_marks_old_rows_without_new_class_on_row():
    html = report.render_html([_lead(is_new=False)], failed_sources=[], generated_at="2026-10-04 20:00")
    assert '<tr class="">' in html


def test_render_html_shows_dash_for_missing_value_not_the_word_none():
    html = report.render_html([_lead(value=None)], failed_sources=[], generated_at="2026-10-04 20:00")
    assert ">None<" not in html
    assert "—" in html


def test_render_html_lists_failed_sources():
    html = report.render_html([], failed_sources=["TED", "Oferia.com.pl"], generated_at="2026-10-04 20:00")
    assert "TED" in html
    assert "Oferia.com.pl" in html


def test_render_html_shows_empty_message_when_no_leads():
    html = report.render_html([], failed_sources=[], generated_at="2026-10-04 20:00")
    assert "Brak zleceń" in html


def test_render_html_escapes_html_in_lead_fields():
    html = report.render_html(
        [_lead(title="<script>alert(1)</script>")], failed_sources=[], generated_at="2026-10-04 20:00"
    )
    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;" in html


def test_write_report_creates_file_with_rendered_content(tmp_path):
    path = tmp_path / "out" / "report.html"
    report.write_report([_lead()], failed_sources=[], generated_at="2026-10-04 20:00", path=path)
    assert path.exists()
    assert "Przykładowy tytuł" in path.read_text(encoding="utf-8")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_report.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'report'`

- [ ] **Step 3: Write minimal implementation**

```python
# report.py
from html import escape
from pathlib import Path

_PAGE_TEMPLATE = """<!DOCTYPE html>
<html lang="pl">
<head>
<meta charset="utf-8">
<title>Zlecenia web-dev — raport</title>
<style>
  body {{ font-family: system-ui, sans-serif; margin: 2rem; color: #1a1a1a; }}
  h1 {{ font-size: 1.4rem; }}
  .meta {{ color: #555; margin-bottom: 1rem; }}
  table {{ width: 100%; border-collapse: collapse; }}
  th, td {{ border: 1px solid #ddd; padding: 0.5rem; text-align: left; vertical-align: top; }}
  th {{ background: #f4f4f4; cursor: pointer; user-select: none; }}
  tr.new-lead {{ background: #fff8d8; }}
  .empty {{ color: #555; font-style: italic; }}
</style>
</head>
<body>
<h1>Zlecenia web-dev — raport</h1>
<p class="meta">Wygenerowano: {generated_at}<br>Źródła, które nie odpowiedziały: {failed}</p>
{empty_message}
<table id="leads">
<thead>
<tr>
  <th data-col="0">Źródło</th>
  <th data-col="1">Tytuł / Opis</th>
  <th data-col="2">Budżet / Wartość</th>
  <th data-col="3">Data publikacji</th>
  <th data-col="4">Link bezpośredni</th>
</tr>
</thead>
<tbody>
{rows}
</tbody>
</table>
<script>
document.querySelectorAll('th[data-col]').forEach(function (th) {{
  th.addEventListener('click', function () {{
    var col = parseInt(th.dataset.col, 10);
    var tbody = document.querySelector('#leads tbody');
    var rows = Array.from(tbody.querySelectorAll('tr'));
    var asc = th.dataset.asc !== 'true';
    rows.sort(function (a, b) {{
      var av = a.children[col].textContent.trim().toLowerCase();
      var bv = b.children[col].textContent.trim().toLowerCase();
      return asc ? av.localeCompare(bv) : bv.localeCompare(av);
    }});
    th.dataset.asc = asc;
    rows.forEach(function (row) {{ tbody.appendChild(row); }});
  }});
}});
</script>
</body>
</html>
"""

_ROW_TEMPLATE = """<tr class="{row_class}">
  <td>{source}</td>
  <td><strong>{title}</strong><br>{description}</td>
  <td>{value}</td>
  <td>{published_at}</td>
  <td><a href="{link}" target="_blank" rel="noopener">otwórz</a></td>
</tr>"""


def _render_row(lead: dict) -> str:
    row_class = "new-lead" if lead.get("is_new") else ""
    value = lead.get("value") or "—"
    return _ROW_TEMPLATE.format(
        row_class=row_class,
        source=escape(lead["source"]),
        title=escape(lead["title"]),
        description=escape(lead["description"][:300]),
        value=escape(str(value)),
        published_at=escape(str(lead["published_at"])),
        link=escape(lead["link"]),
    )


def render_html(leads: list[dict], failed_sources: list[str], generated_at: str) -> str:
    rows = "\n".join(_render_row(lead) for lead in leads)
    failed = ", ".join(escape(s) for s in failed_sources) if failed_sources else "brak"
    empty_message = "" if leads else '<p class="empty">Brak zleceń spełniających kryteria w tym przebiegu.</p>'
    return _PAGE_TEMPLATE.format(
        generated_at=escape(generated_at),
        failed=failed,
        rows=rows,
        empty_message=empty_message,
    )


def write_report(leads: list[dict], failed_sources: list[str], generated_at: str, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_html(leads, failed_sources, generated_at), encoding="utf-8")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_report.py -v`
Expected: PASS (7 tests)

- [ ] **Step 5: Commit**

```bash
git add report.py tests/test_report.py
git commit -m "feat: add report.py for offline sortable HTML report generation"
```

---

### Task 7: fetchers/ezamowienia.py

**Files:**
- Create: `fetchers/__init__.py` (empty)
- Create: `fetchers/ezamowienia.py`
- Test: `tests/fetchers/test_ezamowienia.py`

**Interfaces:**
- Consumes: `normalize.normalize_ezamowienia` (Task 2).
- Produces: `fetchers.ezamowienia.fetch(lookback_days: int = 30) -> list[dict]` — called by `run.py` (Task 12).

- [ ] **Step 1: Write the failing test**

```python
# tests/fetchers/test_ezamowienia.py
from unittest.mock import Mock, patch
from fetchers import ezamowienia

_SAMPLE_NOTICE = {
    "orderObject": "Zakup 22 osobowego autobusu do przewozu osób niepełnosprawnych",
    "cpvCode": "34121000-1 (Autobusy i autokary)",
    "publicationDate": "2026-09-01T03:08:03.1326153Z",
    "tenderId": "ocds-148610-5410c99c-ce3c-4e8e-80b1-189da9952afe",
}


def test_fetch_returns_normalized_leads():
    fake_response = Mock()
    fake_response.json.return_value = [_SAMPLE_NOTICE]
    fake_response.raise_for_status = Mock()
    with patch.object(ezamowienia.requests, "get", return_value=fake_response) as mock_get:
        leads = ezamowienia.fetch(lookback_days=30)

    assert len(leads) == 1
    assert leads[0]["source"] == "e-Zamówienia"
    assert leads[0]["cpv"] == ["34121000"]
    mock_get.assert_called_once()
    called_url = mock_get.call_args.args[0]
    assert called_url == ezamowienia.API_URL
    called_params = mock_get.call_args.kwargs["params"]
    assert called_params["NoticeType"] == "ContractNotice"


def test_fetch_returns_empty_list_when_no_notices():
    fake_response = Mock()
    fake_response.json.return_value = []
    fake_response.raise_for_status = Mock()
    with patch.object(ezamowienia.requests, "get", return_value=fake_response):
        assert ezamowienia.fetch() == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/fetchers/test_ezamowienia.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'fetchers'`

- [ ] **Step 3: Write minimal implementation**

```python
# fetchers/ezamowienia.py
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/fetchers/test_ezamowienia.py -v`
Expected: PASS (2 tests)

- [ ] **Step 5: Commit**

```bash
git add fetchers/__init__.py fetchers/ezamowienia.py tests/fetchers/test_ezamowienia.py
git commit -m "feat: add e-Zamówienia fetcher"
```

---

### Task 8: fetchers/ted.py

**Files:**
- Create: `fetchers/ted.py`
- Test: `tests/fetchers/test_ted.py`

**Interfaces:**
- Consumes: `normalize.normalize_ted` (Task 2).
- Produces: `fetchers.ted.fetch(lookback_days: int = 30) -> list[dict]` — called by `run.py` (Task 12).

- [ ] **Step 1: Write the failing test**

```python
# tests/fetchers/test_ted.py
from unittest.mock import Mock, patch
from fetchers import ted

_SAMPLE_NOTICE = {
    "ND": "599742-2026",
    "TI": {"pol": "Tytuł po polsku", "eng": "Title in English"},
    "PD": "2026-09-01+02:00",
    "CY": ["POL"],
    "classification-cpv": ["72224000"],
    "links": {"htmlDirect": {"ENG": "https://ted.europa.eu/en/notice/599742-2026/html"}},
}


def test_fetch_returns_normalized_leads():
    fake_response = Mock()
    fake_response.json.return_value = {"notices": [_SAMPLE_NOTICE]}
    fake_response.raise_for_status = Mock()
    with patch.object(ted.requests, "post", return_value=fake_response) as mock_post:
        leads = ted.fetch(lookback_days=30)

    assert len(leads) == 1
    assert leads[0]["source"] == "TED"
    assert leads[0]["link"] == "https://ted.europa.eu/en/notice/599742-2026/html"
    mock_post.assert_called_once()
    assert mock_post.call_args.args[0] == ted.API_URL
    payload = mock_post.call_args.kwargs["json"]
    assert "classification-cpv" in payload["query"]


def test_fetch_returns_empty_list_when_no_notices():
    fake_response = Mock()
    fake_response.json.return_value = {"notices": []}
    fake_response.raise_for_status = Mock()
    with patch.object(ted.requests, "post", return_value=fake_response):
        assert ted.fetch() == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/fetchers/test_ted.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'fetchers.ted'`

- [ ] **Step 3: Write minimal implementation**

```python
# fetchers/ted.py
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/fetchers/test_ted.py -v`
Expected: PASS (2 tests)

- [ ] **Step 5: Commit**

```bash
git add fetchers/ted.py tests/fetchers/test_ted.py
git commit -m "feat: add TED fetcher"
```

---

### Task 9: fetchers/oferia.py

**Files:**
- Create: `fetchers/oferia.py`
- Test: `tests/fetchers/test_oferia.py`

**Interfaces:**
- Consumes: `normalize.normalize_oferia` (Task 2), `scrape_utils.robots_allows` / `scrape_utils.rate_limited_get` (Task 5).
- Produces: `fetchers.oferia.fetch() -> list[dict]` — called by `run.py` (Task 12).

- [ ] **Step 1: Write the failing test**

```python
# tests/fetchers/test_oferia.py
from unittest.mock import Mock, patch
from fetchers import oferia

_SAMPLE_HTML = """
<div class="listing-card">
  <div class="listing-card-header">
    <span class="listing-category">Programowanie, IT</span>
  </div>
  <div class="listing-card-body">
    <h3 class="listing-title">
      <a href="/pl/zlecenie/1024">Pilnie potrzebuję osoby do konfiguracji konwersji</a>
    </h3>
    <p class="listing-excerpt">Potrzebuję osoby, która pomoże mi skonfigurować konwersje.</p>
  </div>
  <div class="listing-card-footer">
    <div class="listing-budget"><span>Do negocjacji</span></div>
    <div class="listing-date">21.09.2026</div>
  </div>
</div>
"""


def test_fetch_parses_real_card_markup_into_normalized_leads():
    fake_response = Mock(text=_SAMPLE_HTML)
    with patch.object(oferia, "robots_allows", return_value=True), patch.object(
        oferia, "rate_limited_get", return_value=fake_response
    ):
        leads = oferia.fetch()

    assert len(leads) == 1
    lead = leads[0]
    assert lead["source"] == "Oferia.com.pl"
    assert lead["title"] == "Pilnie potrzebuję osoby do konfiguracji konwersji"
    assert lead["value"] == "Do negocjacji"
    assert lead["published_at"] == "21.09.2026"
    assert lead["link"] == "https://oferia.com.pl/pl/zlecenie/1024"
    assert lead["category"] == "b2b"


def test_fetch_raises_when_robots_disallows():
    with patch.object(oferia, "robots_allows", return_value=False):
        try:
            oferia.fetch()
            assert False, "expected RuntimeError"
        except RuntimeError:
            pass
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/fetchers/test_oferia.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'fetchers.oferia'`

- [ ] **Step 3: Write minimal implementation**

```python
# fetchers/oferia.py
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
    raw_items = [_parse_card(card) for card in soup.select("div.listing-card")]
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/fetchers/test_oferia.py -v`
Expected: PASS (2 tests)

- [ ] **Step 5: Commit**

```bash
git add fetchers/oferia.py tests/fetchers/test_oferia.py
git commit -m "feat: add Oferia.com.pl fetcher"
```

---

### Task 10: fetchers/freelancer.py

**Files:**
- Create: `fetchers/freelancer.py`
- Test: `tests/fetchers/test_freelancer.py`

**Interfaces:**
- Consumes: `normalize.normalize_freelancer` (Task 2), `scrape_utils.robots_allows` / `scrape_utils.rate_limited_get` (Task 5).
- Produces: `fetchers.freelancer.fetch() -> list[dict]` — called by `run.py` (Task 12).

- [ ] **Step 1: Write the failing test**

```python
# tests/fetchers/test_freelancer.py
from unittest.mock import Mock, patch
from fetchers import freelancer

_SAMPLE_HTML = """
<div class="JobSearchCard-item-inner" data-project-card="true">
  <div class="JobSearchCard-primary">
    <div class="JobSearchCard-primary-heading">
      <a href="/projects/web-design/vibrant-business-website-showcase"
         class="JobSearchCard-primary-heading-link">Vibrant Business Website Showcase</a>
      <div class="JobSearchCard-primary-heading-daystatus">
        <span class="JobSearchCard-primary-heading-days">6 days left</span>
      </div>
    </div>
    <p class="JobSearchCard-primary-description">I need a bright, colorful website.</p>
    <div class="JobSearchCard-primary-hidden">
      <div class="JobSearchCard-primary-price">$18 / hr</div>
    </div>
  </div>
</div>
"""


def test_fetch_parses_real_card_markup_into_normalized_leads():
    fake_response = Mock(text=_SAMPLE_HTML)
    with patch.object(freelancer, "robots_allows", return_value=True), patch.object(
        freelancer, "rate_limited_get", return_value=fake_response
    ):
        leads = freelancer.fetch()

    assert len(leads) == 1
    lead = leads[0]
    assert lead["source"] == "Freelancer.com"
    assert lead["title"] == "Vibrant Business Website Showcase"
    assert lead["value"] == "$18 / hr"
    assert lead["published_at"] == "6 days left"
    assert lead["link"] == "https://www.freelancer.com/projects/web-design/vibrant-business-website-showcase"
    assert lead["category"] == "freelance"


def test_fetch_raises_when_robots_disallows():
    with patch.object(freelancer, "robots_allows", return_value=False):
        try:
            freelancer.fetch()
            assert False, "expected RuntimeError"
        except RuntimeError:
            pass
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/fetchers/test_freelancer.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'fetchers.freelancer'`

- [ ] **Step 3: Write minimal implementation**

```python
# fetchers/freelancer.py
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
    raw_items = [_parse_card(card) for card in soup.select("div.JobSearchCard-item-inner")]
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/fetchers/test_freelancer.py -v`
Expected: PASS (2 tests)

- [ ] **Step 5: Commit**

```bash
git add fetchers/freelancer.py tests/fetchers/test_freelancer.py
git commit -m "feat: add Freelancer.com fetcher"
```

---

### Task 11: fetchers/peopleperhour.py (Playwright)

**Files:**
- Create: `fetchers/peopleperhour.py`
- Test: `tests/fetchers/test_peopleperhour.py`

**Interfaces:**
- Consumes: `normalize.normalize_peopleperhour` (Task 2), `scrape_utils.robots_allows` (Task 5).
- Produces: `fetchers.peopleperhour.fetch() -> list[dict]` (drives a real headless browser — not unit tested, see Step 1 note) and `fetchers.peopleperhour._parse_cards(html: str) -> list[dict]` (pure, unit tested). `run.py` (Task 12) calls `fetch()`.

This fetcher needs one extra one-time setup step beyond `pip install`, because Playwright ships its driver separately from the browser binary:

- [ ] **Step 0: Install the Playwright browser binary (one-time, not part of the test cycle)**

Run: `playwright install chromium`
Expected: downloads and installs a Chromium build for Playwright to drive. This is a machine-level setup step (like `pip install`), run once per environment — it does not need to be re-run per test cycle.

- [ ] **Step 1: Write the failing test**

Only `_parse_cards` is unit tested, with real markup captured from a live PeoplePerHour listing page — PeoplePerHour's CSS-module class names get a build-specific hash suffix after `⤚` (e.g. `item__title⤍ListItem⤚2FRMT`), so the parser must match on the stable prefix before `⤍`, not the full class string. The browser-driving half (`fetch`'s call to `_render_listing_html`) is exercised only by the end-to-end smoke test in Task 12, same as the other scrapers.

```python
# tests/fetchers/test_peopleperhour.py
from fetchers import peopleperhour

_SAMPLE_CARD_HTML = """
<li class="list__item⤍List⤚2ytmm">
  <div class="item⤍ListItem⤚1iGUH item--container⤍ListItem⤚2wpiz">
    <div class="pph-row item__top_container⤍ListItem⤚3pRrO">
      <div class="item__container⤍ListItem⤚Fk4RX">
        <div class="pph-col-md-12 pph-col-xs-12">
          <div class="card__meta⤍ListItem⤚3wkEV">
            <div class="u-txt--right card__price⤍ListItem⤚3VxJ9">
              <span class="title-nano"><div><span>$8</span></div></span>
            </div>
          </div>
        </div>
        <div class="pph-col-md-12 pph-col-xs-12">
          <h6 class="item__title⤍ListItem⤚2FRMT">
            <a class="item__url⤍ListItem⤚20ULx"
               href="https://www.peopleperhour.com/freelance-jobs/business/administration-assistance/copy-paste-images-4524971">Copy &amp; Paste Images</a>
          </h6>
          <p class="item__desc⤍ListItem⤚3f4JV">Hello I have a simple project.</p>
        </div>
      </div>
      <div class="card__footer⤍ListItem⤚1KHhv">
        <div class="nano card__footer-left⤍ListItem⤚16Odv">
          <span>6 hours ago</span><span class="u-mgl--1">27 proposals</span>
        </div>
      </div>
    </div>
  </div>
</li>
"""


def test_parse_cards_extracts_fields_despite_hashed_css_module_classes():
    items = peopleperhour._parse_cards(_SAMPLE_CARD_HTML)

    assert len(items) == 1
    item = items[0]
    assert item["title"] == "Copy & Paste Images"
    assert item["description"] == "Hello I have a simple project."
    assert item["budget"] == "$8"
    assert item["date"] == "6 hours ago"
    assert item["link"] == (
        "https://www.peopleperhour.com/freelance-jobs/business/"
        "administration-assistance/copy-paste-images-4524971"
    )


def test_parse_cards_returns_empty_list_for_page_with_no_cards():
    assert peopleperhour._parse_cards("<html><body>no jobs here</body></html>") == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/fetchers/test_peopleperhour.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'fetchers.peopleperhour'`

- [ ] **Step 3: Write minimal implementation**

```python
# fetchers/peopleperhour.py
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/fetchers/test_peopleperhour.py -v`
Expected: PASS (2 tests)

- [ ] **Step 5: Commit**

```bash
git add fetchers/peopleperhour.py tests/fetchers/test_peopleperhour.py
git commit -m "feat: add PeoplePerHour fetcher (Playwright-rendered listing)"
```

---

### Task 12: run.py orchestrator, setup checklist and README

**Files:**
- Create: `run.py`
- Create: `README.md`
- Test: `tests/test_run.py`

**Interfaces:**
- Consumes: every fetcher's `fetch()` (Tasks 7–11), `filter.is_relevant` / `filter.dedup_within_batch` (Task 3), `store.load_seen` / `store.mark_new_or_seen` / `store.save_seen` (Task 4), `report.write_report` (Task 6), `config` paths (Task 1).
- Produces: `run.run(sources: list[tuple[str, callable]], now: str) -> dict` (the testable core — takes injected fetchers so tests never hit the network) and a `main()` that calls it with the five real fetchers and `datetime.now(timezone.utc).isoformat()`, writing to `config.SEEN_STORE_PATH` / `config.REPORT_PATH`. This is the last task — nothing depends on it.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_run.py
from pathlib import Path
import run


def _lead(link, title="Strona internetowa dla firmy", description="potrzebuję strony internetowej"):
    return {
        "source": "Fake",
        "title": title,
        "description": description,
        "value": None,
        "published_at": "2026-10-04",
        "link": link,
        "category": "freelance",
    }


def test_run_collects_leads_from_all_sources_and_writes_report(tmp_path):
    def source_a():
        return [_lead("https://example.com/a")]

    def source_b():
        return [_lead("https://example.com/b")]

    seen_path = tmp_path / "seen.json"
    report_path = tmp_path / "report.html"

    result = run.run(
        sources=[("Source A", source_a), ("Source B", source_b)],
        now="2026-10-04T12:00:00Z",
        seen_path=seen_path,
        report_path=report_path,
    )

    assert result["failed_sources"] == []
    assert len(result["leads"]) == 2
    assert report_path.exists()
    assert "example.com/a" in report_path.read_text(encoding="utf-8")
    assert seen_path.exists()


def test_run_isolates_a_failing_source_and_still_reports_the_rest(tmp_path):
    def good_source():
        return [_lead("https://example.com/good")]

    def broken_source():
        raise RuntimeError("network exploded")

    result = run.run(
        sources=[("Good", good_source), ("Broken", broken_source)],
        now="2026-10-04T12:00:00Z",
        seen_path=tmp_path / "seen.json",
        report_path=tmp_path / "report.html",
    )

    assert result["failed_sources"] == ["Broken"]
    assert len(result["leads"]) == 1


def test_run_filters_out_irrelevant_leads(tmp_path):
    def source():
        return [
            _lead(
                "https://example.com/x",
                title="Zakup 22 osobowego autobusu",
                description="dostawa pojazdu dla gminy",
            )
        ]

    result = run.run(
        sources=[("Source", source)],
        now="2026-10-04T12:00:00Z",
        seen_path=tmp_path / "seen.json",
        report_path=tmp_path / "report.html",
    )

    assert result["leads"] == []


def test_run_marks_repeat_run_leads_as_not_new(tmp_path):
    def source():
        return [_lead("https://example.com/a")]

    seen_path = tmp_path / "seen.json"
    report_path = tmp_path / "report.html"

    first = run.run(
        sources=[("Source", source)], now="2026-10-04T12:00:00Z", seen_path=seen_path, report_path=report_path
    )
    second = run.run(
        sources=[("Source", source)], now="2026-10-05T12:00:00Z", seen_path=seen_path, report_path=report_path
    )

    assert first["leads"][0]["is_new"] is True
    assert second["leads"][0]["is_new"] is False
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_run.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'run'`

- [ ] **Step 3: Write minimal implementation**

```python
# run.py
from datetime import datetime, timezone
from pathlib import Path

import config
from filter import dedup_within_batch, is_relevant
from report import write_report
from store import load_seen, mark_new_or_seen, save_seen


def run(
    sources: list[tuple[str, callable]],
    now: str,
    seen_path: Path,
    report_path: Path,
) -> dict:
    all_leads = []
    failed_sources = []
    for name, fetch in sources:
        try:
            all_leads.extend(fetch())
        except Exception:
            failed_sources.append(name)

    relevant = [lead for lead in all_leads if is_relevant(lead)]
    deduped = dedup_within_batch(relevant)

    seen = load_seen(seen_path)
    annotated, updated_seen = mark_new_or_seen(deduped, seen, now)
    save_seen(updated_seen, seen_path)

    write_report(annotated, failed_sources, generated_at=now, path=report_path)

    return {"leads": annotated, "failed_sources": failed_sources}


def main() -> None:
    from fetchers import ezamowienia, freelancer, oferia, peopleperhour, ted

    sources = [
        ("e-Zamówienia", ezamowienia.fetch),
        ("TED", ted.fetch),
        ("Oferia.com.pl", oferia.fetch),
        ("Freelancer.com", freelancer.fetch),
        ("PeoplePerHour", peopleperhour.fetch),
    ]
    now = datetime.now(timezone.utc).isoformat()
    result = run(sources, now, config.SEEN_STORE_PATH, config.REPORT_PATH)

    print(f"Znaleziono {len(result['leads'])} zleceń.")
    if result["failed_sources"]:
        print(f"Nie odpowiedziały: {', '.join(result['failed_sources'])}")
    print(f"Raport: {config.REPORT_PATH}")


if __name__ == "__main__":
    main()
```

```markdown
# README.md

## web-orders-search

Skrypt do ręcznego, cyklicznego sprawdzania aktualnych zleceń web-dev/web-app
z pięciu darmowych źródeł: e-Zamówienia, TED, Oferia.com.pl, Freelancer.com,
PeoplePerHour.

### Setup (jednorazowo)

1. `pip install -r requirements.txt`
2. `playwright install chromium` (potrzebne tylko dla fetchera PeoplePerHour)
3. Opcjonalnie: wyślij mail na `api@useme.com` z prośbą o dostęp do API — Useme
   nie jest jeszcze zaimplementowane (patrz addendum w specu), ale mailowy
   wniosek warto wysłać od razu, bo odpowiedź może długo nie przychodzić.

### Użycie

```bash
python run.py
```

Wynik: `report.html` w katalogu projektu — otwórz go w przeglądarce. Historia
już widzianych zleceń jest trzymana w `data/seen.json` (tworzony automatycznie,
nie commitowany — jest w `.gitignore`).

### Testy

```bash
pytest
```
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_run.py -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Run the full test suite**

Run: `pytest -v`
Expected: PASS (all tests from Tasks 1–12)

- [ ] **Step 6: Run the real end-to-end smoke test**

Run: `python run.py`
Expected: prints a lead count and the report path, creates/updates `data/seen.json`, and `report.html` opens in a browser showing a sortable table. Check the console output for any entries under "Nie odpowiedziały" — if a live source changed its page structure since this plan was verified (2026-10-04), it will show up here rather than crashing the run.

- [ ] **Step 7: Commit**

```bash
git add run.py README.md tests/test_run.py
git commit -m "feat: add run.py orchestrator tying all fetchers together"
```

---

## Explicitly out of scope for this plan (see spec addendum)

- **Useme fetcher** — blocked by Cloudflare even via Playwright; only the official API (pending manual email approval) is viable. Add as Task 13 in a follow-up plan once API credentials exist — do not attempt to build it against guessed endpoints now.
- Scheduling/cron automation, paid APIs/proxies, and any form of automatic account registration or login remain out of scope per the spec's Global Constraints.
