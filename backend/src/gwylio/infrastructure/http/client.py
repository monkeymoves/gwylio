"""The one HTTP client every collector uses: retries, backoff, rate limits and a request count.

``HttpClient`` wraps ``httpx.Client`` with:

- a 20 second timeout and a User-Agent naming Gwylio and a contact address;
- up to three retries on HTTP 429, any 5xx, timeouts and connection errors,
  with exponential backoff starting at one second and full jitter (a random
  wait between zero and the backoff), or the server's ``Retry-After`` when it
  sends one;
- a per-host token bucket (``RateLimit``): one request per second for the
  Brave Search API, five per second elsewhere;
- a count of every request made, retries included, so a scan's request
  budget is honest.

When the retries are spent, or the answer is a client error other than 429,
it raises ``HttpError(status, url)``. Sleeping, the monotonic clock and the
jitter are injectable, so tests run instantly and deterministically. Outbound
HTTPS honours ``HTTPS_PROXY`` (httpx does by default); ``default_verify``
picks the certificate bundle from ``SSL_CERT_FILE`` when it names a readable
file, and never turns verification off.
"""

from __future__ import annotations

import json
import os
import random
import ssl
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Final, Self
from urllib.parse import urlsplit

import httpx

__all__ = [
    "BRAVE_HOST",
    "DEFAULT_TIMEOUT_SECONDS",
    "MAX_RETRIES",
    "HttpClient",
    "HttpError",
    "RateLimit",
    "default_verify",
    "user_agent",
]

DEFAULT_TIMEOUT_SECONDS: Final[float] = 20.0
MAX_RETRIES: Final[int] = 3
"""Retries after the first attempt, so at most four requests per call."""
BACKOFF_BASE_SECONDS: Final[float] = 1.0
MAX_RETRY_AFTER_SECONDS: Final[float] = 120.0
"""A ``Retry-After`` longer than this is capped: a scan never waits minutes for one host."""
BRAVE_HOST: Final[str] = "api.search.brave.com"
_RETRY_STATUSES: Final[frozenset[int]] = frozenset({429})
_RETRYABLE_ERRORS: Final[tuple[type[httpx.TransportError], ...]] = (
    httpx.TimeoutException,
    httpx.ConnectError,
    httpx.ReadError,
    httpx.WriteError,
    httpx.RemoteProtocolError,
)


class HttpError(Exception):
    """A request that failed for good: ``status`` is ``None`` when no response came back."""

    def __init__(self, status: int | None, url: str, reason: str = "") -> None:
        self.status = status
        self.url = url
        self.reason = reason
        what = f"HTTP {status}" if status is not None else "no response"
        super().__init__(f"{what} from {url}" + (f": {reason}" if reason else ""))


@dataclass(frozen=True, slots=True)
class RateLimit:
    """At most ``requests_per_second`` requests to one host, with bursts of ``burst``."""

    requests_per_second: float
    burst: int = 1

    def __post_init__(self) -> None:
        if self.requests_per_second <= 0:
            raise ValueError("requests_per_second must be positive")
        if self.burst < 1:
            raise ValueError("burst must be at least 1")

    @property
    def interval(self) -> float:
        """Seconds between requests at the steady rate."""
        return 1.0 / self.requests_per_second


@dataclass(slots=True)
class _Bucket:
    """A token bucket kept as its theoretical arrival time (the generic cell rate algorithm)."""

    limit: RateLimit
    next_free: float | None = field(default=None)

    def wait_time(self, now: float) -> float:
        """Take a token, returning how long to sleep first (zero when one is ready)."""
        interval = self.limit.interval
        arrival = now if self.next_free is None else max(self.next_free, now)
        allowance = (self.limit.burst - 1) * interval
        wait = max(0.0, arrival - now - allowance)
        self.next_free = arrival + interval
        return wait


def user_agent(contact_email: str, version: str = "0.1.0") -> str:
    """``gwylio/<version> (Welsh environmental OSINT; mailto:<contact>)``."""
    return f"gwylio/{version} (Welsh environmental OSINT; mailto:{contact_email})"


def default_verify(environ: Mapping[str, str] | None = None) -> ssl.SSLContext | bool:
    """The certificate bundle to verify against: never ``False``.

    ``SSL_CERT_FILE`` when it names a file this process can read, else ``True``
    (httpx's own bundle). A path that cannot be checked, such as one under a
    directory the process may not enter, falls back to the default rather than
    failing.
    """
    env = os.environ if environ is None else environ
    named = env.get("SSL_CERT_FILE", "").strip()
    if not named:
        return True
    candidate = Path(named)
    try:
        readable = candidate.is_file()
    except OSError:
        readable = False
    if readable:
        return ssl.create_default_context(cafile=str(candidate))
    return True


def _retry_after(response: httpx.Response, now: datetime) -> float | None:
    value = response.headers.get("Retry-After")
    if value is None:
        return None
    value = value.strip()
    seconds: float
    if value.isdigit():
        seconds = float(value)
    else:
        try:
            when = parsedate_to_datetime(value)
        except (TypeError, ValueError, IndexError):
            return None
        if when.tzinfo is None:
            when = when.replace(tzinfo=UTC)
        seconds = (when - now).total_seconds()
    return min(max(seconds, 0.0), MAX_RETRY_AFTER_SECONDS)


def _host(url: str) -> str:
    return (urlsplit(url).hostname or "").lower()


class HttpClient:
    """GET requests with retries, backoff, per-host rate limits and an honest request count."""

    def __init__(
        self,
        *,
        contact_email: str,
        timeout: float = DEFAULT_TIMEOUT_SECONDS,
        max_retries: int = MAX_RETRIES,
        rate_limits: Mapping[str, RateLimit] | None = None,
        default_rate: RateLimit | None = None,
        sleep: Callable[[float], None] = time.sleep,
        monotonic: Callable[[], float] = time.monotonic,
        jitter: Callable[[], float] = random.random,
        transport: httpx.BaseTransport | None = None,
        verify: ssl.SSLContext | bool | None = None,
    ) -> None:
        if max_retries < 0:
            raise ValueError("max_retries cannot be negative")
        self._max_retries = max_retries
        self._limits: dict[str, RateLimit] = (
            {BRAVE_HOST: RateLimit(1.0)} if rate_limits is None else dict(rate_limits)
        )
        self._default_rate = default_rate or RateLimit(5.0)
        self._buckets: dict[str, _Bucket] = {}
        self._sleep = sleep
        self._monotonic = monotonic
        self._jitter = jitter
        self._requests_made = 0
        self._client = httpx.Client(
            timeout=timeout,
            headers={"User-Agent": user_agent(contact_email)},
            follow_redirects=True,
            transport=transport,
            verify=default_verify() if verify is None else verify,
        )

    @property
    def requests_made(self) -> int:
        """Every request sent so far, retries included."""
        return self._requests_made

    def close(self) -> None:
        """Close the underlying connection pool."""
        self._client.close()

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()

    def get_json(
        self,
        url: str,
        params: Mapping[str, str | int] | None = None,
        headers: Mapping[str, str] | None = None,
    ) -> object:
        """The parsed JSON body of a successful GET, or ``HttpError``."""
        response = self._get(url, params, headers)
        try:
            parsed: object = json.loads(response.content)
        except (ValueError, UnicodeDecodeError) as error:
            raise HttpError(response.status_code, url, f"response is not JSON: {error}") from error
        return parsed

    def get_text(
        self,
        url: str,
        params: Mapping[str, str | int] | None = None,
        headers: Mapping[str, str] | None = None,
    ) -> str:
        """The decoded text body of a successful GET, or ``HttpError``."""
        return self._get(url, params, headers).text

    def get_bytes(
        self,
        url: str,
        params: Mapping[str, str | int] | None = None,
        headers: Mapping[str, str] | None = None,
    ) -> bytes:
        """The raw body of a successful GET, for formats that declare their own encoding (XML)."""
        return self._get(url, params, headers).content

    def _throttle(self, url: str) -> None:
        host = _host(url)
        bucket = self._buckets.get(host)
        if bucket is None:
            bucket = _Bucket(self._limits.get(host, self._default_rate))
            self._buckets[host] = bucket
        wait = bucket.wait_time(self._monotonic())
        if wait > 0:
            self._sleep(wait)

    def _backoff(self, attempt: int) -> float:
        """Full jitter: a random wait between zero and ``base * 2 ** attempt`` seconds."""
        return self._jitter() * BACKOFF_BASE_SECONDS * float(1 << attempt)

    def _get(
        self,
        url: str,
        params: Mapping[str, str | int] | None,
        headers: Mapping[str, str] | None,
    ) -> httpx.Response:
        attempt = 0
        while True:
            self._throttle(url)
            self._requests_made += 1
            try:
                response = self._client.get(url, params=params, headers=headers)
            except _RETRYABLE_ERRORS as error:
                if attempt >= self._max_retries:
                    raise HttpError(None, url, f"{type(error).__name__}: {error}") from error
                self._sleep(self._backoff(attempt))
                attempt += 1
                continue
            except (httpx.HTTPError, httpx.InvalidURL) as error:
                # A proxy refusal or an invalid request: retrying would not help.
                raise HttpError(None, url, f"{type(error).__name__}: {error}") from error
            status = response.status_code
            if status < 400:
                return response
            retryable = status in _RETRY_STATUSES or status >= 500
            if not retryable or attempt >= self._max_retries:
                raise HttpError(status, url)
            wait = _retry_after(response, datetime.now(UTC))
            self._sleep(self._backoff(attempt) if wait is None else wait)
            attempt += 1
