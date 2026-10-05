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
