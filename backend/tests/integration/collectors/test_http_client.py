"""``HttpClient``: retries, backoff with jitter, Retry-After, rate limits and the request count."""

from __future__ import annotations

import ssl
from pathlib import Path

import httpx
import pytest
import respx

from gwylio.infrastructure.http.client import (
    BRAVE_HOST,
    HttpClient,
    HttpError,
    RateLimit,
    default_verify,
    user_agent,
)
from tests.integration.collectors.cassettes import CONTACT, FakeTime, client

pytestmark = pytest.mark.integration

URL = "https://api.example.org/items"
BRAVE = f"https://{BRAVE_HOST}/res/v1/web/search"


def test_429_then_200_succeeds_with_two_requests_counted(
    http: HttpClient, mocked: respx.MockRouter, fake_time: FakeTime
) -> None:
    route = mocked.get(URL).mock(
        side_effect=[httpx.Response(429), httpx.Response(200, json={"ok": True})]
    )
    assert http.get_json(URL) == {"ok": True}
    assert route.call_count == 2
    assert http.requests_made == 2
    # Full jitter: the injected fraction (0.5) of the first backoff (1 second).
    assert 0.5 in fake_time.sleeps


def test_three_5xx_then_200_succeeds(
    http: HttpClient, mocked: respx.MockRouter, fake_time: FakeTime
) -> None:
    mocked.get(URL).mock(
        side_effect=[
            httpx.Response(500),
            httpx.Response(502),
            httpx.Response(503),
            httpx.Response(200, text="fine"),
        ]
    )
    assert http.get_text(URL) == "fine"
    assert http.requests_made == 4
    # Exponential backoff with jitter 0.5: half of 1, 2 and 4 seconds (no rate wait at 5/s
    # because each backoff is longer than the 0.2 second interval).
    assert fake_time.sleeps == [0.5, 1.0, 2.0]


def test_four_5xx_raise_http_error(http: HttpClient, mocked: respx.MockRouter) -> None:
    route = mocked.get(URL).mock(return_value=httpx.Response(503))
    with pytest.raises(HttpError) as raised:
        http.get_json(URL)
    assert raised.value.status == 503
    assert raised.value.url == URL
    assert route.call_count == 4
    assert http.requests_made == 4


def test_a_client_error_is_not_retried(http: HttpClient, mocked: respx.MockRouter) -> None:
    route = mocked.get(URL).mock(return_value=httpx.Response(404))
    with pytest.raises(HttpError, match="HTTP 404"):
        http.get_text(URL)
    assert route.call_count == 1


def test_retry_after_is_honoured(
    http: HttpClient, mocked: respx.MockRouter, fake_time: FakeTime
) -> None:
    mocked.get(URL).mock(
        side_effect=[httpx.Response(429, headers={"Retry-After": "2"}), httpx.Response(200)]
    )
    http.get_text(URL)
    assert fake_time.sleeps == [2.0]


def test_a_long_retry_after_is_capped(
    http: HttpClient, mocked: respx.MockRouter, fake_time: FakeTime
) -> None:
    mocked.get(URL).mock(
        side_effect=[httpx.Response(503, headers={"Retry-After": "86400"}), httpx.Response(200)]
    )
    http.get_text(URL)
    assert fake_time.sleeps == [120.0]


def test_timeouts_and_connection_errors_are_retried_then_raised(
    http: HttpClient, mocked: respx.MockRouter
) -> None:
    mocked.get(URL).mock(
        side_effect=[
            httpx.ConnectTimeout("slow"),
            httpx.ConnectError("refused"),
            httpx.Response(200),
        ]
    )
    assert http.get_text(URL) == ""
    assert http.requests_made == 3
    mocked.get("https://down.example.org/").mock(side_effect=httpx.ReadTimeout("slow"))
    with pytest.raises(HttpError, match="no response") as raised:
        http.get_text("https://down.example.org/")
    assert raised.value.status is None
    assert http.requests_made == 7


def test_a_proxy_refusal_is_not_retried(http: HttpClient, mocked: respx.MockRouter) -> None:
    route = mocked.get(URL).mock(side_effect=httpx.ProxyError("403 Forbidden"))
    with pytest.raises(HttpError, match="ProxyError"):
        http.get_text(URL)
    assert route.call_count == 1


def test_the_rate_limiter_spaces_two_brave_calls_by_a_second(
    mocked: respx.MockRouter, fake_time: FakeTime
) -> None:
    mocked.get(BRAVE).mock(return_value=httpx.Response(200, json={}))
    with client(fake_time) as http:
        http.get_json(BRAVE)
        http.get_json(BRAVE)
    assert fake_time.sleeps == [1.0]


def test_other_hosts_get_five_a_second_and_their_own_bucket(
    mocked: respx.MockRouter, fake_time: FakeTime
) -> None:
    mocked.get(URL).mock(return_value=httpx.Response(200))
    mocked.get(BRAVE).mock(return_value=httpx.Response(200, json={}))
    with client(fake_time) as http:
        http.get_text(URL)
        http.get_json(BRAVE)
        http.get_text(URL)
    assert fake_time.sleeps == [pytest.approx(0.2)]


def test_a_rate_limit_allows_a_burst() -> None:
    time = FakeTime()
    with (
        respx.mock() as router,
        HttpClient(
            contact_email=CONTACT,
            rate_limits={"api.example.org": RateLimit(1.0, burst=2)},
            sleep=time.sleep,
            monotonic=time.monotonic,
        ) as http,
    ):
        router.get(URL).mock(return_value=httpx.Response(200))
        for _ in range(3):
            http.get_text(URL)
    assert time.sleeps == [1.0]


def test_rate_limit_rejects_nonsense() -> None:
    with pytest.raises(ValueError):
        RateLimit(0)
    with pytest.raises(ValueError):
        RateLimit(1, burst=0)


def test_the_user_agent_names_gwylio_and_the_contact(
    http: HttpClient, mocked: respx.MockRouter
) -> None:
    route = mocked.get(URL).mock(return_value=httpx.Response(200))
    http.get_text(URL, params={"a": 1}, headers={"X-Test": "yes"})
    sent = route.calls.last.request
    assert sent.headers["User-Agent"] == user_agent(CONTACT)
    assert "gwylio/" in sent.headers["User-Agent"]
    assert "mailto:analyst@example.org" in sent.headers["User-Agent"]
    assert sent.headers["X-Test"] == "yes"
    assert sent.url.params["a"] == "1"


def test_a_non_json_body_is_an_http_error(http: HttpClient, mocked: respx.MockRouter) -> None:
    mocked.get(URL).mock(return_value=httpx.Response(200, text="<html>"))
    with pytest.raises(HttpError, match="not JSON"):
        http.get_json(URL)


def test_get_bytes_returns_the_raw_body(http: HttpClient, mocked: respx.MockRouter) -> None:
    mocked.get(URL).mock(return_value=httpx.Response(200, content=b"\xef\xbb\xbf<rss/>"))
    assert http.get_bytes(URL) == b"\xef\xbb\xbf<rss/>"


def test_default_verify_never_turns_verification_off(tmp_path: Path) -> None:
    bundle = tmp_path / "missing.crt"
    chosen = default_verify({"SSL_CERT_FILE": str(bundle)})
    assert chosen is True or isinstance(chosen, ssl.SSLContext)
    assert default_verify({}) is not False


def test_default_verify_falls_back_when_the_bundle_cannot_be_checked(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def refuse(self: Path) -> bool:
        raise PermissionError(13, "Permission denied", str(self))

    monkeypatch.setattr(Path, "is_file", refuse)
    assert default_verify({"SSL_CERT_FILE": "/root/private/ca-bundle.crt"}) is True


def test_default_verify_uses_the_httpx_bundle_without_ssl_cert_file() -> None:
    assert default_verify({}) is True


def test_negative_retries_are_refused() -> None:
    with pytest.raises(ValueError):
        HttpClient(contact_email=CONTACT, max_retries=-1)
