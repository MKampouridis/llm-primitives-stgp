"""Bitstamp public OHLC API v2 (no key; at most 1000 candles per call; UTC daily candles).

A call returns the candles inside the window ``[start, start + limit days)``; windows before a
pair's listing are empty. Paged forwards with ``start`` (``end`` would override ``start``); the
last window is shortened so nothing after the requested end is fetched.
"""

from __future__ import annotations

import json
import time
from datetime import date

import pandas as pd

from lpstgp.data.sources.base import (
    RawDownload,
    SourceError,
    http_get,
    requests_version,
    unix_seconds,
    utc_date,
)

URL = "https://www.bitstamp.net/api/v2/ohlc/{pair}/"
DAY = 86_400
PAGE = 1000
EARLIEST = date(2011, 8, 1)
CLOSE_ONLY = False
VENDOR_SPLIT_ADJUSTED = False


def fetch(pair: str, start: date, end: date, pause: float = 0.5) -> RawDownload:
    url = URL.format(pair=pair)
    cursor = unix_seconds(max(start, EARLIEST))
    stop = unix_seconds(end)
    pages = []
    while cursor <= stop:
        limit = min(PAGE, (stop - cursor) // DAY + 1)
        params = {"step": DAY, "limit": limit, "start": cursor, "exclude_current_candle": "true"}
        payload = http_get(url, params=params).json()
        candles = payload.get("data", {}).get("ohlc", [])
        pages.append({"params": params, "response": payload})
        window_end = cursor + limit * DAY
        if candles:
            last = max(int(c["timestamp"]) for c in candles)
            if last < cursor:
                raise SourceError(f"bitstamp {pair}: cursor did not advance")
            cursor = max(last + DAY, window_end)  # correct for window and next-N semantics
        else:
            cursor = window_end  # empty window: before listing, or an outage
        time.sleep(pause)
    if not any(p["response"].get("data", {}).get("ohlc") for p in pages):
        raise SourceError(f"bitstamp {pair}: no data")
    query = f"{url}?step={DAY}&limit={PAGE}&exclude_current_candle=true&start=<paged from {max(start, EARLIEST)}>"
    content = json.dumps(pages, sort_keys=True).encode("utf-8")
    return RawDownload(content, ".json", query, "requests", requests_version())


def parse(content: bytes) -> pd.DataFrame:
    pages = json.loads(content)
    rows = [c for page in pages for c in page["response"].get("data", {}).get("ohlc", [])]
    if not rows:
        raise SourceError("bitstamp: empty raw file")
    frame = pd.DataFrame(
        {
            "date": [utc_date(c["timestamp"]) for c in rows],
            "open": [float(c["open"]) for c in rows],
            "high": [float(c["high"]) for c in rows],
            "low": [float(c["low"]) for c in rows],
            "close": [float(c["close"]) for c in rows],
            "volume": [float(c["volume"]) for c in rows],
        }
    )
    frame["date"] = pd.to_datetime(frame["date"]).to_numpy().astype("datetime64[D]")
    # Overlapping pages repeat a candle with identical content: keep the first occurrence.
    frame = frame.drop_duplicates("date", keep="first")
    return frame.sort_values("date", kind="stable").reset_index(drop=True)


def describe(symbol: str) -> dict[str, object]:
    return {"close_only": CLOSE_ONLY, "vendor_split_adjusted": VENDOR_SPLIT_ADJUSTED}
