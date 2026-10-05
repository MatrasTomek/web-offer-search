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
