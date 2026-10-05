from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
SEEN_STORE_PATH = DATA_DIR / "seen.json"
REPORT_PATH = BASE_DIR / "report.html"

CPV_PREFIX = "72"

# Each entry: stems that must ALL co-occur in the lead text (Polish declines by case, so whole phrases miss).
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
