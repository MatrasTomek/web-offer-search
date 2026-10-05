from unittest.mock import Mock, patch
import scrape_utils


ROBOTS_TXT = "User-agent: *\nDisallow: /private/\n"


def _robots_response(status=200, text=ROBOTS_TXT):
    response = Mock(status_code=status, text=text)
    return response


def test_robots_allows_true_when_path_not_disallowed():
    with patch.object(scrape_utils.requests, "get", return_value=_robots_response()):
        assert scrape_utils.robots_allows("https://example.com", "/public/page") is True


def test_robots_allows_false_when_path_disallowed():
    with patch.object(scrape_utils.requests, "get", return_value=_robots_response()):
        assert scrape_utils.robots_allows("https://example.com", "/private/page") is False


def test_robots_allows_fails_open_when_robots_txt_unreachable():
    with patch.object(scrape_utils.requests, "get", side_effect=scrape_utils.requests.Timeout("slow")):
        assert scrape_utils.robots_allows("https://example.com", "/anything") is True


def test_robots_allows_fails_open_on_server_error():
    with patch.object(scrape_utils.requests, "get", return_value=_robots_response(status=503, text="")):
        assert scrape_utils.robots_allows("https://example.com", "/private/page") is True


def test_rate_limited_get_sleeps_remaining_delay_for_same_domain(monkeypatch):
    times = iter([100.0, 100.3])
    monkeypatch.setattr(scrape_utils.time, "monotonic", lambda: next(times))
    sleep_calls = []
    monkeypatch.setattr(scrape_utils.time, "sleep", lambda s: sleep_calls.append(s))
    scrape_utils._last_request_at["example.com"] = 99.0

    fake_response = Mock(status_code=200)
    fake_response.raise_for_status = Mock()
    with patch.object(scrape_utils.requests, "get", return_value=fake_response) as mock_get:
        result = scrape_utils.rate_limited_get("https://example.com/page", delay=2.0)

    assert sleep_calls == [1.0]
    mock_get.assert_called_once()
    assert result is fake_response


def test_rate_limited_get_raises_on_http_error(monkeypatch):
    monkeypatch.setattr(scrape_utils.time, "monotonic", lambda: 200.0)
    monkeypatch.setattr(scrape_utils.time, "sleep", lambda s: None)

    fake_response = Mock(status_code=500)
    fake_response.raise_for_status = Mock(side_effect=scrape_utils.requests.HTTPError("boom"))
    with patch.object(scrape_utils.requests, "get", return_value=fake_response):
        try:
            scrape_utils.rate_limited_get("https://example.com/page")
            assert False, "expected HTTPError"
        except scrape_utils.requests.HTTPError:
            pass
