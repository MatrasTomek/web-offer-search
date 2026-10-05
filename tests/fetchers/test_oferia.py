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


def test_fetch_skips_card_without_title_link_and_keeps_others():
    broken = '<div class="listing-card"><h3 class="listing-title">no link</h3></div>'
    fake_response = Mock(text=broken + _SAMPLE_HTML)
    with patch.object(oferia, "robots_allows", return_value=True), patch.object(
        oferia, "rate_limited_get", return_value=fake_response
    ):
        leads = oferia.fetch()
    assert [lead["link"] for lead in leads] == ["https://oferia.com.pl/pl/zlecenie/1024"]
