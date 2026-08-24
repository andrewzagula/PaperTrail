import asyncio
import unittest
from unittest.mock import patch

import httpx

from app.services.arxiv_fetcher import (
    ARXIV_MAX_ATTEMPTS,
    ARXIV_RETRY_MAX_DELAY,
    _retry_delay,
    arxiv_get,
)
from app.services.errors import UserSafeServiceError

URL = "http://export.arxiv.org/api/query"


def _response(status: int, *, body: str = "ok", headers: dict | None = None):
    return httpx.Response(
        status_code=status,
        text=body,
        headers=headers or {},
        request=httpx.Request("GET", URL),
    )


class _ScriptedClient:
    """Async client stub that returns a scripted sequence of outcomes."""

    calls = 0
    script: list = []

    def __init__(self, *args, **kwargs):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def get(self, url, **kwargs):
        outcome = type(self).script[min(type(self).calls, len(type(self).script) - 1)]
        type(self).calls += 1
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


def _run(script, **kwargs):
    _ScriptedClient.calls = 0
    _ScriptedClient.script = script
    with patch("app.services.arxiv_fetcher.httpx.AsyncClient", _ScriptedClient), patch(
        "app.services.arxiv_fetcher.asyncio.sleep", new=_no_sleep
    ):
        result = asyncio.run(arxiv_get(URL, **kwargs))
    return result, _ScriptedClient.calls


async def _no_sleep(_seconds):
    return None


def _run_expecting_error(script, **kwargs):
    _ScriptedClient.calls = 0
    _ScriptedClient.script = script
    with patch("app.services.arxiv_fetcher.httpx.AsyncClient", _ScriptedClient), patch(
        "app.services.arxiv_fetcher.asyncio.sleep", new=_no_sleep
    ):
        try:
            asyncio.run(arxiv_get(URL, **kwargs))
        except UserSafeServiceError as error:
            return error, _ScriptedClient.calls
    raise AssertionError("expected UserSafeServiceError")


class RetryDelayTests(unittest.TestCase):
    def test_backs_off_exponentially(self):
        self.assertLess(_retry_delay(1, None), _retry_delay(2, None))
        self.assertLess(_retry_delay(2, None), _retry_delay(3, None))

    def test_honours_retry_after_header(self):
        self.assertEqual(_retry_delay(1, "7"), 7.0)

    def test_caps_the_delay(self):
        self.assertLessEqual(_retry_delay(1, "9999"), ARXIV_RETRY_MAX_DELAY)
        self.assertLessEqual(_retry_delay(99, None), ARXIV_RETRY_MAX_DELAY)

    def test_ignores_a_malformed_retry_after(self):
        """arXiv may send an HTTP-date; fall back rather than crash."""
        self.assertGreater(_retry_delay(1, "Wed, 21 Oct 2026 07:28:00 GMT"), 0)


class ArxivGetRetryTests(unittest.TestCase):
    def test_recovers_from_a_rate_limit(self):
        """The exact failure that killed discovery runs."""
        resp, calls = _run([_response(429), _response(200, body="recovered")])
        self.assertEqual(resp.text, "recovered")
        self.assertEqual(calls, 2)

    def test_recovers_from_a_connection_error(self):
        resp, calls = _run(
            [httpx.ConnectError("reset"), _response(200, body="recovered")]
        )
        self.assertEqual(resp.text, "recovered")
        self.assertEqual(calls, 2)

    def test_recovers_from_a_timeout(self):
        resp, calls = _run(
            [httpx.ReadTimeout("slow"), _response(200, body="recovered")]
        )
        self.assertEqual(resp.text, "recovered")
        self.assertEqual(calls, 2)

    def test_recovers_from_a_server_error(self):
        resp, calls = _run([_response(503), _response(200, body="recovered")])
        self.assertEqual(resp.text, "recovered")
        self.assertEqual(calls, 2)

    def test_no_retry_when_the_first_attempt_succeeds(self):
        _, calls = _run([_response(200)])
        self.assertEqual(calls, 1)

    def test_gives_up_after_the_attempt_cap(self):
        error, calls = _run_expecting_error([_response(429)])
        self.assertEqual(calls, ARXIV_MAX_ATTEMPTS)
        self.assertEqual(error.status_code, 502)

    def test_does_not_retry_a_permanent_client_error(self):
        """A malformed query will fail identically every time."""
        error, calls = _run_expecting_error([_response(400)])
        self.assertEqual(calls, 1)
        self.assertEqual(error.status_code, 502)

    def test_does_not_retry_a_missing_paper(self):
        error, calls = _run_expecting_error([_response(404)], not_found_on_404=True)
        self.assertEqual(calls, 1)
        self.assertEqual(error.status_code, 404)

    def test_connection_failure_reports_unavailable(self):
        error, calls = _run_expecting_error([httpx.ConnectError("down")])
        self.assertEqual(calls, ARXIV_MAX_ATTEMPTS)
        self.assertEqual(error.status_code, 503)

    def test_uses_retry_after_when_arxiv_sends_it(self):
        delays = []

        async def record(seconds):
            delays.append(seconds)

        _ScriptedClient.calls = 0
        _ScriptedClient.script = [
            _response(429, headers={"retry-after": "5"}),
            _response(200),
        ]
        with patch(
            "app.services.arxiv_fetcher.httpx.AsyncClient", _ScriptedClient
        ), patch("app.services.arxiv_fetcher.asyncio.sleep", new=record):
            asyncio.run(arxiv_get(URL))

        self.assertEqual(delays, [5.0])


class SearchArxivRetryTests(unittest.TestCase):
    def test_search_recovers_from_a_rate_limit(self):
        from app.services.arxiv_searcher import search_arxiv

        feed = (
            "<feed><entry><id>http://arxiv.org/abs/1706.03762v5</id>"
            "<title>Attention Is All You Need</title>"
            "<summary>abstract</summary><published>2017-06-12</published>"
            "<name>Vaswani</name></entry></feed>"
        )
        _ScriptedClient.calls = 0
        _ScriptedClient.script = [_response(429), _response(200, body=feed)]
        with patch(
            "app.services.arxiv_fetcher.httpx.AsyncClient", _ScriptedClient
        ), patch("app.services.arxiv_fetcher.asyncio.sleep", new=_no_sleep):
            results = asyncio.run(search_arxiv("attention", max_results=1))

        self.assertEqual(_ScriptedClient.calls, 2)
        self.assertEqual(results[0].arxiv_id, "1706.03762")


if __name__ == "__main__":
    unittest.main()
