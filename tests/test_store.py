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
