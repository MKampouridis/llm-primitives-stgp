"""Synthetic sandboxes for the GP tests (no real data needed)."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from lpstgp.data import schema
from lpstgp.data.store import DataStore
from lpstgp.gates.synthetic import garch_returns
from lpstgp.gp.pset import build
from lpstgp.operators.registry import discover
from lpstgp.sandbox import Sandbox
from lpstgp.splits import Stage, walk_forward

PERIOD = walk_forward(date(2005, 7, 1), 1)[0]
LMAX = 504
INSTRUMENTS = ("AAA", "BBB")


def write_synthetic_tier(root: Path) -> Path:
    dates = pd.bdate_range("2001-01-01", "2010-12-31")
    for k, name in enumerate(INSTRUMENTS):
        r = garch_returns(len(dates), 100 + k)
        frame = pd.DataFrame({"date": dates, "close": 100 * np.exp(np.cumsum(r))})
        bars, _ = schema.normalise(frame)
        meta = {
            "schema_version": 1,
            "instrument_id": name,
            "tier": "A",
            "asset_class": "equity_index",
            "calendar": "business",
            "source": "synthetic",
            "source_symbol": name,
            "close_only": True,
            "vendor_split_adjusted": False,
            "raw_files": [],
            "cost_bps": 2.0,
        }
        schema.write_parquet(bars, meta, root / "processed" / f"{name}.parquet")
    return root


@pytest.fixture(scope="session")
def tier_dir(tmp_path_factory) -> Path:
    return write_synthetic_tier(tmp_path_factory.mktemp("tier"))


@pytest.fixture(scope="session")
def fit_box(tier_dir):
    return Sandbox.open(DataStore(tier_dir), PERIOD, Stage.FIT, INSTRUMENTS, LMAX)


@pytest.fixture(scope="session")
def val_box(tier_dir):
    return Sandbox.open(DataStore(tier_dir), PERIOD, Stage.VALIDATE, INSTRUMENTS, LMAX)


@pytest.fixture(scope="session")
def seed_lib():
    return build(discover().library("seed"))


@pytest.fixture(scope="session")
def conventional_lib():
    return build(discover().library("conventional"))
