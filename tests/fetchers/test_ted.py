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
