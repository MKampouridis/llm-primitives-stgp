"""Equal-weight portfolios of evolved rules (D-033, protocol §primary outcome).

Per instrument, the daily net returns of *all* runs of a configuration are averaged (no run is
picked after the fact); instruments are then weighted equally on the union of their calendars,
where an instrument without a session that day contributes a flat (zero) return.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

import numpy as np

from lpstgp.backtest.metrics import sharpe

Series = tuple[np.ndarray, np.ndarray]  # (dates as datetime64[D], net returns)


def average_runs(runs: Sequence[Series]) -> Series:
    """Average daily net returns of several runs on the same instrument (identical dates)."""
    dates = runs[0][0]
    for d, _ in runs[1:]:
        if not np.array_equal(d, dates):
            raise ValueError("runs of one instrument must share their dates")
    return dates, np.mean(np.vstack([r for _, r in runs]), axis=0)


def equal_weight(instruments: Mapping[str, Series]) -> Series:
    """Equal-weight portfolio on the union calendar; missing sessions count as flat days."""
    dates = np.unique(
        np.concatenate([np.asarray(d, dtype="datetime64[D]") for d, _ in instruments.values()])
    )
    total = np.zeros(len(dates))
    for d, r in instruments.values():
        idx = np.searchsorted(dates, np.asarray(d, dtype="datetime64[D]"))
        r = np.asarray(r, dtype=np.float64)
        if not np.isfinite(r).all():  # an upstream bug, not a flat day: never hide it
            raise ValueError("non-finite daily return in a portfolio input")
        total[idx] += r
    return dates, total / len(instruments)


def periods_per_year(dates: np.ndarray) -> float:
    """Rows per year of a portfolio's own (union) calendar, to annualise its Sharpe (D-047).

    Equal-weight portfolios live on the union of their instruments' calendars: about 260 rows a
    year for weekday markets, about 365 once a 7-day market is included, so a fixed 252 would
    misstate every Sharpe ratio by a calendar-dependent factor.
    """
    dates = np.asarray(dates, dtype="datetime64[D]")
    span_days = int((dates[-1] - dates[0]).astype(int)) + 1
    return len(dates) / (span_days / 365.25)


def portfolio_sharpe(portfolio: Series, periods: float | None = None) -> float:
    return float(sharpe(portfolio[1], periods or periods_per_year(portfolio[0])))
