"""Tier C: the datasets of the Essex DC-GP and ActTrade papers, for head-to-head comparison.

The datasets are copied by hand into ``tierC/`` together with a ``manifest.toml`` describing each
one, because their formats differ by paper. Example entry::

    [[dataset]]
    id = "dcgp_fx"
    paper = "Long, Kampouridis & Kanellopoulos (PPSN 2022)"
    files = ["dcgp/EURUSD.csv"]
    date_column = "Date"
    date_format = "%Y-%m-%d"          # optional
    columns = { close = "Close", open = "Open", high = "High", low = "Low", volume = "Volume" }
    extra_columns = ["sentiment"]      # kept as-is (e.g. ActTrade sentiment/fundamental inputs)
    frequency = "daily"
    splits = [{ train = ["2010-01-01", "2014-12-31"], test = ["2015-01-01", "2015-12-31"] }]

Files are checksummed when loaded; the published splits are kept with the data.
"""

from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pandas as pd

from lpstgp.data import manifest as mf
from lpstgp.data import schema


@dataclass(frozen=True)
class TierCDataset:
    id: str
    paper: str
    files: tuple[str, ...]
    date_column: str
    columns: dict[str, str]
    frequency: str = "daily"
    date_format: str | None = None
    extra_columns: tuple[str, ...] = ()
    splits: tuple[dict[str, Any], ...] = field(default=())


def load_manifest(tier_dir: Path) -> list[TierCDataset]:
    """Datasets described in ``tierC/manifest.toml``; empty when nothing has been copied yet."""
    path = Path(tier_dir) / "manifest.toml"
    if not path.is_file():
        return []
    raw = tomllib.loads(path.read_text(encoding="utf-8"))
    datasets = []
    for item in raw.get("dataset", []):
        if "close" not in item["columns"]:
            raise ValueError(f"tier C dataset {item['id']}: a 'close' column mapping is required")
        datasets.append(
            TierCDataset(
                id=item["id"],
                paper=item["paper"],
                files=tuple(item["files"]),
                date_column=item["date_column"],
                columns=dict(item["columns"]),
                frequency=item.get("frequency", "daily"),
                date_format=item.get("date_format"),
                extra_columns=tuple(item.get("extra_columns", [])),
                splits=tuple(item.get("splits", [])),
            )
        )
    return datasets


def load_file(tier_dir: Path, dataset: TierCDataset, file: str) -> tuple[pd.DataFrame, pd.DataFrame, str]:
    """One file mapped to schema v1 (+ extra columns). Returns ``(bars, flags, sha256)``."""
    path = Path(tier_dir) / file
    raw = pd.read_csv(path)
    dates = pd.to_datetime(raw[dataset.date_column], format=dataset.date_format)
    frame = pd.DataFrame({"date": dates.to_numpy().astype("datetime64[D]")})
    for target, column in dataset.columns.items():
        frame[target] = raw[column]
    bars, flags = schema.normalise(frame)
    for extra in dataset.extra_columns:
        bars[extra] = raw.set_index(dates.to_numpy().astype("datetime64[D]"))[extra].reindex(bars["date"]).to_numpy()
    return bars, flags, mf.sha256_file(path)


def inventory(tier_dir: Path) -> dict[str, Any]:
    """What is in tierC/: files present and manifest status (for the data report)."""
    tier_dir = Path(tier_dir)
    files = sorted(
        str(p.relative_to(tier_dir)) for p in tier_dir.rglob("*") if p.is_file() and not p.name.startswith(".")
    )
    return {"files": files, "datasets": load_manifest(tier_dir)}
