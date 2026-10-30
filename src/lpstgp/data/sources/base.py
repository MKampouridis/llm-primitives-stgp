"""Shared helpers for the pilot data sources."""

from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import UTC, date, datetime

import requests

USER_AGENT = "lpstgp-research/0.1 (academic research; pilot market data)"


class SourceError(RuntimeError):
    """A source returned no usable data."""


@dataclass(frozen=True)
class RawDownload:
    content: bytes
    suffix: str  # ".csv", ".json" or ".xls"
    query: str  # URL or call that produced the content
    tool: str
    tool_version: str


def http_get(
    url: str,
    params: dict | None = None,
    timeout: float = 60.0,
    retries: int = 4,
    backoff: float = 5.0,
) -> requests.Response:
    """GET with a descriptive User-Agent and exponential backoff on errors and 429/5xx."""
    last: Exception | None = None
    for attempt in range(retries):
        try:
            response = requests.get(
                url, params=params, timeout=timeout, headers={"User-Agent": USER_AGENT}
            )
            if response.status_code == 200:
                return response
            if response.status_code not in (429, 500, 502, 503, 504):
                raise SourceError(f"{url}: HTTP {response.status_code}: {response.text[:200]}")
            last = SourceError(f"{url}: HTTP {response.status_code}")
        except requests.RequestException as exc:
            last = exc
        time.sleep(backoff * 2**attempt)
    raise SourceError(f"{url}: giving up after {retries} attempts") from last


def unix_seconds(day: date) -> int:
    return int(datetime(day.year, day.month, day.day, tzinfo=UTC).timestamp())


def utc_date(seconds: int | float | str) -> date:
    return datetime.fromtimestamp(int(float(seconds)), tz=UTC).date()


def requests_version() -> str:
    return requests.__version__
