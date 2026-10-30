"""Yahoo Finance via yfinance (indices, futures, ETFs, FX alternates).

Raw prices with ``auto_adjust=False``. Yahoo's raw OHLC are already split-adjusted by the vendor
(multiplicative, so harmless for shift-invariant operators); dividends and capital-gains
distributions are kept as events. Yahoo's terms describe the data as for personal use: raw files
are never redistributed.
"""

from __future__ import annotations

import io
from datetime import date, timedelta

import pandas as pd

from lpstgp.data.sources.base import RawDownload, SourceError

VENDOR_SPLIT_ADJUSTED = True
CLOSE_ONLY = False


def fetch(symbol: str, start: date, end: date) -> RawDownload:
    try:
        import yfinance as yf
    except ImportError as exc:  # optional "download" extra
        raise SourceError("yfinance is not installed; uv sync --extra download") from exc
    end_exclusive = end + timedelta(days=1)
    history = yf.Ticker(symbol).history(
        start=start.isoformat(),
        end=end_exclusive.isoformat(),
        interval="1d",
        auto_adjust=False,
        actions=True,
    )
    if history.empty:
        raise SourceError(f"yahoo {symbol}: no data")
    query = (
        f"yfinance.Ticker({symbol!r}).history(start={start.isoformat()!r}, "
        f"end={end_exclusive.isoformat()!r}, interval='1d', auto_adjust=False, actions=True)"
    )
    return RawDownload(history.to_csv().encode("utf-8"), ".csv", query, "yfinance", yf.__version__)


def parse(content: bytes) -> pd.DataFrame:
    raw = pd.read_csv(io.BytesIO(content))
    if "Date" not in raw or "Close" not in raw:
        raise SourceError("unexpected yahoo CSV layout")
    # Timestamps are exchange-local midnight with an offset; the local calendar date is the session.
    dates = (
        pd.to_datetime(raw["Date"].astype(str).str.slice(0, 10)).to_numpy().astype("datetime64[D]")
    )
    frame = pd.DataFrame(
        {
            "date": dates,
            "open": raw.get("Open"),
            "high": raw.get("High"),
            "low": raw.get("Low"),
            "close": raw["Close"],
            "volume": raw.get("Volume"),
            "dividend": raw.get("Dividends", 0.0),
        }
    )
    if "Capital Gains" in raw:  # fund cash distributions also belong in the total return
        frame["dividend"] = frame["dividend"].fillna(0.0) + raw["Capital Gains"].fillna(0.0)
    frame["split"] = 1.0  # prices are already split-adjusted by the vendor
    prices = frame[["open", "high", "low", "close"]]
    frame = frame[
        prices.notna().any(axis=1).to_numpy()
    ]  # rows with no price at all are not sessions
    # Yahoo occasionally repeats a date (e.g. a provisional and a final row): keep the last one.
    frame = frame.drop_duplicates("date", keep="last")
    frame["volume"] = frame["volume"].astype("float64")
    return frame.reset_index(drop=True)


def describe(symbol: str) -> dict[str, object]:
    return {"close_only": CLOSE_ONLY, "vendor_split_adjusted": VENDOR_SPLIT_ADJUSTED}
