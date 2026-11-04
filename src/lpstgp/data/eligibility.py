"""Which tier-A instruments are eligible in each WP4 period (availability counts only, D-009).

The same rule as the WP1 data report (``quality.assess``): ``lookback_max`` valid bars before the
fit start and at least ``min_session_coverage`` of the expected sessions present in
[fit start, test end). It counts sessions only and never looks at a price, a return or a result
(D-017). The post-cutoff period PC is assessed on [fit start, test start), because its test year
is not in the data yet; its test-year coverage is reported at its own freeze (D-083).
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import replace
from datetime import timedelta
from typing import Any

import numpy as np
import pandas as pd

from lpstgp.config import Paths
from lpstgp.data import schema
from lpstgp.data.quality import expected_sessions
from lpstgp.data.tier_a import load_universe
from lpstgp.splits import Period, all_periods, is_eligible

WP4_PERIODS = (*(f"P{k:02d}" for k in range(1, 19)), "PC")


def assessed(period: Period) -> Period:
    """The window an eligibility check may count over (PC: without its test year)."""
    return replace(period, test_end=period.test_start) if period.id == "PC" else period


def table(
    paths: Paths, settings: Mapping[str, Any], period_ids=WP4_PERIODS
) -> dict[str, list[str]]:
    """period id -> sorted eligible primary instruments, for P01..P18 and PC by default."""
    periods = [assessed(all_periods(settings)[p]) for p in period_ids]
    lmax = settings["splits"]["lookback_max_bars"]
    coverage = settings["splits"]["min_session_coverage"]
    out: dict[str, list[str]] = {p.id: [] for p in periods}
    processed = paths.tier_dir("A") / "processed"
    for inst in load_universe():
        path = processed / f"{inst.id}.parquet"
        if not path.is_file():
            continue
        meta = schema.read_meta(path)
        frame: pd.DataFrame = schema.read_frame(path)
        dates = frame["date"].to_numpy().astype("datetime64[D]")
        valid = dates[np.isfinite(frame["close"].to_numpy(dtype="float64"))]
        if not len(valid):
            continue
        first = valid[0].astype(object)
        last_day = max(p.test_end for p in periods) - timedelta(days=1)
        expected = expected_sessions(
            meta["calendar"],
            meta.get("qa_calendar", ""),
            min(first, periods[0].fit_start),
            last_day,
        )
        for p in periods:
            if is_eligible(valid, expected, p, lmax, coverage):
                out[p.id].append(inst.id)
    return {k: sorted(v) for k, v in out.items()}
