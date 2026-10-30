"""U.S. Energy Information Administration daily spot prices (official history files, no key).

The files cannot be range-limited, so raw files may contain dates after the design end; the
build drops them. Close-only. WTI printed a negative price on 2020-04-20; the schema marks
non-positive prices invalid.
"""

from __future__ import annotations

import io
from datetime import date

import pandas as pd

from lpstgp.data.sources.base import RawDownload, SourceError, http_get, requests_version

URLS = {
    "RWTC": "https://www.eia.gov/dnav/pet/hist_xls/RWTCd.xls",  # WTI Cushing, $/bbl
    "RBRTE": "https://www.eia.gov/dnav/pet/hist_xls/RBRTEd.xls",  # Brent Europe, $/bbl
    "RNGWHHD": "https://www.eia.gov/dnav/ng/hist_xls/RNGWHHDd.xls",  # Henry Hub, $/MMBtu
}
CLOSE_ONLY = True
VENDOR_SPLIT_ADJUSTED = False


def fetch(series: str, start: date, end: date) -> RawDownload:
    if series not in URLS:
        raise SourceError(f"unknown EIA series {series}")
    response = http_get(URLS[series])
    return RawDownload(response.content, ".xls", URLS[series], "requests", requests_version())


def parse_sheet(sheet: pd.DataFrame) -> pd.DataFrame:
    """Parse the 'Data 1' sheet read with ``skiprows=2`` (columns: Date, <series title>)."""
    if sheet.shape[1] < 2 or str(sheet.columns[0]).strip().lower() != "date":
        raise SourceError("unexpected EIA sheet layout")
    frame = pd.DataFrame(
        {
            "date": pd.to_datetime(sheet.iloc[:, 0], errors="coerce"),
            "close": pd.to_numeric(sheet.iloc[:, 1], errors="coerce"),
        }
    )
    frame = frame[frame["date"].notna() & frame["close"].notna()]
    frame["date"] = frame["date"].to_numpy().astype("datetime64[D]")
    if frame["date"].duplicated().any():
        raise SourceError("EIA series has duplicate dates")
    return frame.sort_values("date", kind="stable").reset_index(drop=True)


def parse(content: bytes) -> pd.DataFrame:
    sheet = pd.read_excel(io.BytesIO(content), sheet_name="Data 1", skiprows=2, engine="xlrd")
    return parse_sheet(sheet)


def describe(symbol: str) -> dict[str, object]:
    return {"close_only": CLOSE_ONLY, "vendor_split_adjusted": VENDOR_SPLIT_ADJUSTED}
