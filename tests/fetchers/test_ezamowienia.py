from unittest.mock import Mock, patch
from fetchers import ezamowienia

_SAMPLE_NOTICE = {
    "orderObject": "Zakup 22 osobowego autobusu do przewozu osób niepełnosprawnych",
    "cpvCode": "34121000-1 (Autobusy i autokary)",
    "publicationDate": "2026-09-01T03:08:03.1326153Z",
    "tenderId": "ocds-148610-5410c99c-ce3c-4e8e-80b1-189da9952afe",
}


def test_fetch_returns_normalized_leads():
    fake_response = Mock()
    fake_response.json.return_value = [_SAMPLE_NOTICE]
    fake_response.raise_for_status = Mock()
    with patch.object(ezamowienia.requests, "get", return_value=fake_response) as mock_get:
        leads = ezamowienia.fetch(lookback_days=30)

    assert len(leads) == 1
    assert leads[0]["source"] == "e-Zamówienia"
    assert leads[0]["cpv"] == ["34121000"]
    mock_get.assert_called_once()
    called_url = mock_get.call_args.args[0]
    assert called_url == ezamowienia.API_URL
    called_params = mock_get.call_args.kwargs["params"]
    assert called_params["NoticeType"] == "ContractNotice"


def test_fetch_returns_empty_list_when_no_notices():
    fake_response = Mock()
    fake_response.json.return_value = []
    fake_response.raise_for_status = Mock()
    with patch.object(ezamowienia.requests, "get", return_value=fake_response):
        assert ezamowienia.fetch() == []
