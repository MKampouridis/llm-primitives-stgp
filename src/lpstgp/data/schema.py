"""Canonical daily-bar schema (v1), shared by all tiers.

Prices are stored *raw*; corporate-action events are stored alongside, and adjustment is
applied causally at read time (see ``store.py``). Every check here is row-local, so building
from a raw file cut at any date reproduces the earlier rows exactly (causal build).
"""

from __future__ import annotations

import itertools
import json
import os
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

SCHEMA_VERSION = 1
PRICE_COLUMNS = ("open", "high", "low", "close")
COLUMNS = ("date", *PRICE_COLUMNS, "volume", "dividend", "split")
ARROW_SCHEMA = pa.schema([("date", pa.date32())] + [(name, pa.float64()) for name in COLUMNS[1:]])
META_KEY = b"lpstgp"
REQUIRED_META = (
    "schema_version",
    "instrument_id",
    "tier",
    "asset_class",
    "calendar",
    "source",
    "source_symbol",
    "close_only",
    "vendor_split_adjusted",
    "raw_files",
)


class SchemaError(ValueError):
    """A frame cannot be represented in the canonical schema."""


def normalise(frame: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Coerce a parsed source frame to schema v1 with structural, row-local checks.

    Returns ``(bars, flags)``; ``flags`` has columns ``date`` and ``flag``. Rows are never
    dropped or repaired using information from other rows.
    """
    if "date" not in frame or "close" not in frame:
        raise SchemaError("frame needs at least 'date' and 'close' columns")
    out = pd.DataFrame({"date": pd.to_datetime(frame["date"]).values.astype("datetime64[D]")})
    for name in ("open", "high", "low", "close", "volume"):
        out[name] = pd.to_numeric(frame[name], errors="coerce") if name in frame else np.nan
    out["dividend"] = (
        pd.to_numeric(frame["dividend"], errors="coerce") if "dividend" in frame else 0.0
    )
    out["split"] = pd.to_numeric(frame["split"], errors="coerce") if "split" in frame else 1.0
    out = out.astype({name: "float64" for name in COLUMNS[1:]})

    if out["date"].duplicated().any():
        raise SchemaError("duplicate dates; the source parser must resolve them explicitly")
    out = out.sort_values("date", kind="stable").reset_index(drop=True)

    flags: list[tuple[np.datetime64, str]] = []

    def flag(mask: pd.Series, name: str) -> None:
        flags.extend((d, name) for d in out.loc[mask, "date"].to_numpy())

    bad_close = ~np.isfinite(out["close"]) | (out["close"] <= 0)
    flag(bad_close & out["close"].notna(), "invalid_close")
    out.loc[bad_close, list(PRICE_COLUMNS)] = np.nan

    for name in ("open", "high", "low"):
        bad = out[name].notna() & (~np.isfinite(out[name]) | (out[name] <= 0))
        flag(bad, f"invalid_{name}")
        out.loc[bad, name] = np.nan

    complete = out[list(PRICE_COLUMNS)].notna().all(axis=1)
    hi = out[["open", "close", "low"]].max(axis=1)
    lo = out[["open", "close", "high"]].min(axis=1)
    violation = complete & ((out["high"] < hi) | (out["low"] > lo))
    flag(violation, "ohlc_violation")
    out.loc[violation, ["open", "high", "low"]] = (
        np.nan
    )  # keep the close, drop inconsistent extremes

    bad_volume = out["volume"].notna() & (~np.isfinite(out["volume"]) | (out["volume"] < 0))
    flag(bad_volume, "invalid_volume")
    out.loc[bad_volume, "volume"] = np.nan

    bad_div = out["dividend"].notna() & (~np.isfinite(out["dividend"]) | (out["dividend"] < 0))
    flag(bad_div, "invalid_dividend")
    out["dividend"] = out["dividend"].where(~bad_div & out["dividend"].notna(), 0.0)

    bad_split = ~np.isfinite(out["split"]) | (out["split"] <= 0)
    out["split"] = out["split"].where(~bad_split, 1.0)

    flag_frame = pd.DataFrame(flags, columns=["date", "flag"])
    if not flag_frame.empty:
        flag_frame = flag_frame.sort_values(["date", "flag"], kind="stable").reset_index(drop=True)
    return out[list(COLUMNS)], flag_frame


def to_table(bars: pd.DataFrame) -> pa.Table:
    arrays = [pa.array(bars["date"].to_numpy().astype("datetime64[D]"), type=pa.date32())]
    arrays += [
        pa.array(bars[name].to_numpy(dtype="float64"), type=pa.float64()) for name in COLUMNS[1:]
    ]
    return pa.Table.from_arrays(arrays, schema=ARROW_SCHEMA)


def write_parquet(bars: pd.DataFrame, meta: Mapping[str, Any], path: Path) -> None:
    """Write bars with one row group per calendar month, so horizon reads prune by statistics."""
    missing = [key for key in REQUIRED_META if key not in meta]
    if missing:
        raise SchemaError(f"metadata missing {missing}")
    table = to_table(bars)
    schema = ARROW_SCHEMA.with_metadata(
        {META_KEY: json.dumps(dict(meta), sort_keys=True, default=str)}
    )
    months = bars["date"].to_numpy().astype("datetime64[M]")
    starts = [0, *list(np.flatnonzero(months[1:] != months[:-1]) + 1), len(bars)]
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".parquet.tmp")
    with pq.ParquetWriter(tmp, schema, compression="zstd") as writer:
        for lo, hi in itertools.pairwise(starts):
            if hi > lo:
                writer.write_table(table.slice(lo, hi - lo))
    os.replace(tmp, path)


def read_meta(path: Path) -> dict[str, Any]:
    metadata = pq.read_schema(path).metadata or {}
    if META_KEY not in metadata:
        raise SchemaError(f"{path} has no lpstgp metadata")
    return json.loads(metadata[META_KEY])


def read_frame(path: Path) -> pd.DataFrame:
    """Read a whole processed file (data-layer use only: building and quality reports)."""
    table = pq.read_table(path)
    frame = table.to_pandas()
    frame["date"] = pd.to_datetime(frame["date"]).to_numpy().astype("datetime64[D]")
    return frame
