"""WP4's pre-registered primary analysis (protocol_wp4 §7; D-078).

Per arm, the equal-weight portfolio of each test year (all runs averaged per instrument, the
period's eligible instruments weighted equally on the union calendar) is concatenated over
P01..P18. The eight confirmatory comparisons are one-sided paired stationary-bootstrap tests on
those daily returns, Holm-adjusted as one family.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass
from typing import Any

import numpy as np

from lpstgp.analysis.inference import holm, one_sided_bootstrap
from lpstgp.analysis.portfolio import Series, periods_per_year, portfolio_sharpe

ALPHA = 0.05
NON_INFERIORITY_MARGIN = 0.1  # H2a, annualised Sharpe (D-078)


@dataclass(frozen=True)
class Comparison:
    hypothesis: str
    a: str  # configuration names as in the WP4 plans
    b: str
    margin: float = 0.0  # H0: Sharpe(a) - Sharpe(b) <= margin

    @property
    def name(self) -> str:
        return f"{self.hypothesis}: {self.a} - {self.b}"


COMPARISONS = (
    Comparison("H1", "arm2c", "arm1"),
    Comparison("H1", "arm2c", "arm2a"),
    Comparison("H2a", "arm3", "arm6", -NON_INFERIORITY_MARGIN),
    Comparison("H2b", "arm3", "armGPconv"),
    Comparison("H2b", "arm6", "armGPconv"),
    Comparison("H3", "arm4full", "arm3"),
    Comparison("H3", "arm4full", "arm4grow"),
    Comparison("H4", "arm4full", "arm5"),
)


def concatenate(by_period: Mapping[str, Series], periods: Sequence[str]) -> Series:
    """One arm's test-year portfolios, in period order; test years never overlap."""
    parts = [by_period[p] for p in periods]
    dates = np.concatenate([d for d, _ in parts])
    if np.any(np.diff(dates.astype("datetime64[D]").astype(np.int64)) <= 0):
        raise ValueError("test years overlap or are out of order")
    return dates, np.concatenate([r for _, r in parts])


def _aligned(a: Series, b: Series) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    dates = np.intersect1d(a[0], b[0])
    return a[1][np.isin(a[0], dates)], b[1][np.isin(b[0], dates)], dates


def primary(
    portfolios: Mapping[str, Series], resamples: int = 10_000, seed: int = 0
) -> dict[str, Any]:
    """The confirmatory family on concatenated portfolios ``portfolios[config]``."""
    rows = []
    for c in COMPARISONS:
        a, b, dates = _aligned(portfolios[c.a], portfolios[c.b])
        result = one_sided_bootstrap(
            a, b, c.margin, periods_per_year(dates), resamples=resamples, seed=seed
        )
        rows.append({"comparison": c.name, **asdict(c), **vars(result)})
    adjusted = holm([r["p_value"] for r in rows])
    for row, p in zip(rows, adjusted, strict=True):
        row["p_holm"] = float(p)
        row["rejected"] = bool(p < ALPHA)
    return {
        "alpha": ALPHA,
        "family": "Holm over the 8 confirmatory comparisons (D-078)",
        "sharpe": {arm: portfolio_sharpe(s) for arm, s in sorted(portfolios.items())},
        "comparisons": rows,
    }
