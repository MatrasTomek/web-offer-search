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
