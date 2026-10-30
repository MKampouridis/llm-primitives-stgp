"""ECB euro foreign exchange reference rates (daily, 14:15 CET fixing, from 1999-01-04).

Each series is "units of currency per 1 EUR". USD-based pairs are built as ratios of two
EUR-based series on the same date (row-local, hence causal). Close-only.
"""

from __future__ import annotations

import io
from datetime import date

import pandas as pd

from lpstgp.data.sources.base import RawDownload, SourceError, http_get, requests_version

URL = "https://data-api.ecb.europa.eu/service/data/EXR/D.{currency}.EUR.SP00.A"
CLOSE_ONLY = True
VENDOR_SPLIT_ADJUSTED = False


def fetch(currency: str, start: date, end: date) -> RawDownload:
    url = URL.format(currency=currency)
    params = {
        "format": "csvdata",
        "detail": "dataonly",  # drop per-row attribute columns: the full-history CSV is ~1.5 MB otherwise
        "startPeriod": start.isoformat(),
        "endPeriod": end.isoformat(),
    }
    # The API can take well over a minute to assemble a full history.
    response = http_get(url, params=params, timeout=300.0)
    query = response.url
    return RawDownload(response.content, ".csv", query, "requests", requests_version())


def parse(content: bytes) -> pd.DataFrame:
    raw = pd.read_csv(io.BytesIO(content))
    if "TIME_PERIOD" not in raw or "OBS_VALUE" not in raw:
        raise SourceError("unexpected ECB CSV layout")
    frame = pd.DataFrame(
        {
            "date": pd.to_datetime(raw["TIME_PERIOD"]).to_numpy().astype("datetime64[D]"),
            "close": pd.to_numeric(raw["OBS_VALUE"], errors="coerce"),
        }
    )
    frame = frame[frame["close"].notna()]
    if frame["date"].duplicated().any():
        raise SourceError("ECB series has duplicate dates")
    return frame.sort_values("date", kind="stable").reset_index(drop=True)


def describe(symbol: str) -> dict[str, object]:
    return {"close_only": CLOSE_ONLY, "vendor_split_adjusted": VENDOR_SPLIT_ADJUSTED}
