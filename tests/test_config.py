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
