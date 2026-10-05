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
