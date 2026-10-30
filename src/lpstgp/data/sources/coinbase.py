"""Coinbase Exchange public candles (no key; at most 300 candles per request; UTC days).

Each candle is ``[time, low, high, open, close, volume]``, newest first.
"""

from __future__ import annotations

import json
import time
from datetime import UTC, date, datetime, timedelta

import pandas as pd

from lpstgp.data.sources.base import RawDownload, SourceError, http_get, requests_version, utc_date

URL = "https://api.exchange.coinbase.com/products/{product}/candles"
WINDOW_DAYS = 300
EARLIEST = date(2015, 1, 1)
CLOSE_ONLY = False
VENDOR_SPLIT_ADJUSTED = False


def _iso(day: date) -> str:
    return datetime(day.year, day.month, day.day, tzinfo=UTC).isoformat().replace("+00:00", "Z")


def fetch(product: str, start: date, end: date, pause: float = 0.25) -> RawDownload:
    url = URL.format(product=product)
    lo = max(start, EARLIEST)
    windows = []
    while lo <= end:
        hi = min(lo + timedelta(days=WINDOW_DAYS - 1), end)
        params = {"granularity": 86_400, "start": _iso(lo), "end": _iso(hi)}
        windows.append({"params": params, "response": http_get(url, params=params).json()})
        lo = hi + timedelta(days=1)
        time.sleep(pause)
    if not any(w["response"] for w in windows):
        raise SourceError(f"coinbase {product}: no data")
    query = f"{url}?granularity=86400&start=..&end=.. (windows of {WINDOW_DAYS} days from {max(start, EARLIEST)})"
    content = json.dumps(windows, sort_keys=True).encode("utf-8")
    return RawDownload(content, ".json", query, "requests", requests_version())


def parse(content: bytes) -> pd.DataFrame:
    windows = json.loads(content)
    rows = [c for w in windows for c in (w["response"] or [])]
    if not rows:
        raise SourceError("coinbase: empty raw file")
    frame = pd.DataFrame(rows, columns=["time", "low", "high", "open", "close", "volume"])
    frame["date"] = pd.to_datetime([utc_date(t) for t in frame["time"]]).to_numpy().astype("datetime64[D]")
    frame = frame.drop(columns="time").astype({c: "float64" for c in ("low", "high", "open", "close", "volume")})
    frame = frame.drop_duplicates("date", keep="first")
    return frame.sort_values("date", kind="stable").reset_index(drop=True)[
        ["date", "open", "high", "low", "close", "volume"]
    ]


def describe(symbol: str) -> dict[str, object]:
    return {"close_only": CLOSE_ONLY, "vendor_split_adjusted": VENDOR_SPLIT_ADJUSTED}
