"""WP4's frozen-rule evaluation (protocol_wp4 §6; D-079, D-086).

``evaluate_period`` runs every frozen rule of one period's plan on a sandbox of that period:
the VALIDATE year for the rehearsal (and the validation–test gap of H3), the TEST year at the
single read. It returns every run's daily net returns per instrument, which are saved whole
(``save``), so per-instrument and per-run analyses never need a second read (D-060).
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import replace
from pathlib import Path
from types import MappingProxyType
from typing import Any

import numpy as np

from lpstgp import pilot
from lpstgp.analysis.portfolio import Series, average_runs, equal_weight
from lpstgp.gp.fitness import FitnessConfig
from lpstgp.sandbox import Sandbox
from lpstgp.splits import Stage

BUY_AND_HOLD = "BH"


def as_test(box: Sandbox) -> Sandbox:
    """A VALIDATE sandbox seen as a test window (its validation year), for the rehearsal."""
    if box.stage is not Stage.VALIDATE:
        raise ValueError("only a VALIDATE sandbox can stand in for the test window")
    return replace(box, period=replace(box.period, test_start=box.period.val_start))


def _subset(box: Sandbox, instruments: Sequence[str]) -> Sandbox:
    return replace(box, bars=MappingProxyType({k: box[k] for k in instruments}))


def evaluate_period(
    box: Sandbox, records: Sequence[Mapping[str, Any]], cfg: FitnessConfig, frozen=()
) -> dict[tuple[str, str, int], Series]:
    """(config, instrument, run) -> daily net returns of the frozen rule; buy-and-hold under
    config ``BH`` with run 0."""
    out: dict[tuple[str, str, int], Series] = {}
    for record in records:
        meta = record["campaign"]
        config, run = meta["config"], int(meta["run"])
        sub = _subset(box, record["instruments"])
        for name, series in pilot.evaluate_on_test(record, sub, cfg, frozen).items():
            out[(config, name, run)] = series
    for name, series in pilot.buy_and_hold(box, cfg).items():
        out[(BUY_AND_HOLD, name, 0)] = series
    return out


def portfolios(series: Mapping[tuple[str, str, int], Series]) -> dict[str, Series]:
    """Per config: average all runs per instrument, then weight instruments equally."""
    by_config: dict[str, dict[str, list[Series]]] = defaultdict(lambda: defaultdict(list))
    for (config, name, _run), s in series.items():
        by_config[config][name].append(s)
    return {
        c: equal_weight({n: average_runs(runs) for n, runs in by_inst.items()})
        for c, by_inst in by_config.items()
    }


def save(path: Path, series: Mapping[tuple[str, str, int], Series]) -> None:
    """Every series, float32 returns per (config, instrument, run) and dates per instrument."""
    arrays: dict[str, np.ndarray] = {}
    for (config, name, run), (dates, values) in series.items():
        key = f"dates|{name}"
        d = np.asarray(dates, dtype="datetime64[D]").astype(np.int64)
        if key in arrays and not np.array_equal(arrays[key], d):
            raise ValueError(f"{name}: series of one instrument must share their dates")
        arrays[key] = d
        arrays[f"r|{config}|{name}|{run}"] = np.asarray(values, dtype=np.float32)
    path.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(path, **arrays)


def load(path: Path) -> dict[tuple[str, str, int], Series]:
    out = {}
    with np.load(path, allow_pickle=False) as npz:
        dates = {k.split("|", 1)[1]: npz[k].astype("datetime64[D]") for k in npz.files
                 if k.startswith("dates|")}  # fmt: skip
        for k in npz.files:
            if k.startswith("r|"):
                _, config, name, run = k.split("|")
                out[(config, name, int(run))] = (dates[name], npz[k].astype(np.float64))
    return out
