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
