"""Source parsers on inline fixtures (no network), and the Bitstamp paging logic."""

import json
from datetime import date

import numpy as np
import pandas as pd
import pytest

from lpstgp.data import schema
from lpstgp.data.sources import base, bitstamp, coinbase, ecb, eia, yahoo

YAHOO_CSV = b"""Date,Open,High,Low,Close,Adj Close,Volume,Dividends,Stock Splits
2005-01-03 00:00:00-05:00,10.0,11.0,9.5,10.5,10.4,1000,0.0,0.0
2005-01-04 00:00:00-05:00,10.5,11.5,10.0,11.0,10.9,1100,0.2,0.0
2005-01-05 00:00:00-05:00,,,,,,,0.0,0.0
2005-01-06 00:00:00-05:00,11.0,11.2,10.8,11.1,11.0,900,0.0,0.0
2005-01-06 00:00:00-05:00,11.0,11.3,10.8,11.2,11.1,950,0.0,0.0
"""


def test_yahoo_parse_drops_empty_rows_keeps_last_duplicate_and_ignores_vendor_splits():
    frame = yahoo.parse(YAHOO_CSV)
    assert list(frame["date"].astype(str)) == ["2005-01-03", "2005-01-04", "2005-01-06"]
    assert frame["close"].iloc[-1] == 11.2  # the later duplicate wins
    assert frame["dividend"].tolist() == [0.0, 0.2, 0.0]
    assert frame["split"].eq(1.0).all()  # Yahoo prices are already split-adjusted
    schema.normalise(frame)  # must be schema-compatible


def test_yahoo_parse_adds_capital_gains_to_distributions():
    csv = YAHOO_CSV.replace(b"Stock Splits\n", b"Stock Splits,Capital Gains\n").replace(b",0.0\n", b",0.0,0.0\n")
    csv = csv.replace(b"1100,0.2,0.0,0.0", b"1100,0.2,0.0,0.05")
    frame = yahoo.parse(csv)
    assert frame["dividend"].tolist() == pytest.approx([0.0, 0.25, 0.0])


def test_ecb_parse():
    csv = b"""KEY,FREQ,CURRENCY,CURRENCY_DENOM,EXR_TYPE,EXR_SUFFIX,TIME_PERIOD,OBS_VALUE
EXR.D.USD.EUR.SP00.A,D,USD,EUR,SP00,A,1999-01-04,1.1789
EXR.D.USD.EUR.SP00.A,D,USD,EUR,SP00,A,1999-01-05,
EXR.D.USD.EUR.SP00.A,D,USD,EUR,SP00,A,1999-01-06,1.1743
"""
    frame = ecb.parse(csv)
    assert list(frame["date"].astype(str)) == ["1999-01-04", "1999-01-06"]
    assert frame["close"].tolist() == [1.1789, 1.1743]


def test_eia_parse_sheet():
    sheet = pd.DataFrame(
        {
            "Date": pd.to_datetime(["1986-01-02", "1986-01-03", None, "1986-01-06"]),
            "Cushing, OK WTI Spot Price FOB (Dollars per Barrel)": [25.56, 26.0, 1.0, np.nan],
        }
    )
    frame = eia.parse_sheet(sheet)
    assert list(frame["date"].astype(str)) == ["1986-01-02", "1986-01-03"]


def test_eia_parse_sheet_rejects_unknown_layout():
    with pytest.raises(base.SourceError):
        eia.parse_sheet(pd.DataFrame({"Sourcekey": ["RWTC"], "x": [1]}))


def _candle(day: date, close: float):
    ts = base.unix_seconds(day)
    return {"timestamp": str(ts), "open": "1", "high": "2", "low": "0.5", "close": str(close), "volume": "3"}


def test_bitstamp_parse_dedupes_overlapping_pages():
    pages = [
        {"params": {}, "response": {"data": {"ohlc": [_candle(date(2012, 1, 1), 5.0), _candle(date(2012, 1, 2), 6.0)]}}},
        {"params": {}, "response": {"data": {"ohlc": [_candle(date(2012, 1, 2), 6.0), _candle(date(2012, 1, 3), 7.0)]}}},
    ]
    frame = bitstamp.parse(json.dumps(pages).encode())
    assert frame["close"].tolist() == [5.0, 6.0, 7.0]


def test_bitstamp_fetch_pages_windows_skips_empty_and_stops_at_end(monkeypatch):
    listing = date(2017, 8, 16)
    calls = []

    class FakeResponse:
        def __init__(self, payload):
            self._payload = payload

        def json(self):
            return self._payload

    def fake_get(url, params=None, **_):
        calls.append(dict(params))
        start, limit = int(params["start"]), int(params["limit"])
        days = [base.utc_date(start + k * bitstamp.DAY) for k in range(limit)]
        candles = [_candle(d, 1.0) for d in days if d >= listing]
        return FakeResponse({"data": {"ohlc": candles}})

    monkeypatch.setattr(bitstamp, "http_get", fake_get)
    raw = bitstamp.fetch("ethusd", date(2011, 8, 1), date(2020, 6, 30), pause=0)
    frame = bitstamp.parse(raw.content)
    assert frame["date"].min() == np.datetime64("2017-08-16")
    assert frame["date"].max() == np.datetime64("2020-06-30")  # nothing after the requested end
    assert len(frame) == (date(2020, 6, 30) - listing).days + 1  # no gaps from paging
    assert all(int(c["limit"]) <= bitstamp.PAGE for c in calls)


def test_coinbase_parse_reorders_columns_and_sorts():
    t0 = base.unix_seconds(date(2016, 5, 18))
    windows = [{"params": {}, "response": [[t0 + 86400, 9, 12, 10, 11, 100], [t0, 8, 11, 9, 10, 90]]}, {"params": {}, "response": []}]
    frame = coinbase.parse(json.dumps(windows).encode())
    assert list(frame.columns) == ["date", "open", "high", "low", "close", "volume"]
    assert frame["close"].tolist() == [10.0, 11.0]
    assert frame["low"].tolist() == [8.0, 9.0]
