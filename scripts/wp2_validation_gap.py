"""Validation-test gap of the WP2 pilot portfolios (protocol §8, "also reported").

Usage: uv run python scripts/wp2_validation_gap.py

Evaluates the frozen go/no-go rules on each pilot period's VALIDATE year, exactly as the pilot
test evaluation does on the test year (the same code path as the rehearsal in `wp2_pilot.py`),
and sets each arm's validation portfolio Sharpe beside its test Sharpe from
reports/wp2/pilot_go_no_go.json. Reads VALIDATE data only; the test years are not opened.
"""

from __future__ import annotations

import json
import sys
from dataclasses import replace
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import wp2_pilot as w
from lpstgp.analysis.portfolio import portfolio_sharpe
from lpstgp.config import load_paths, load_settings
from lpstgp.data.store import modelling_store
from lpstgp.runner import configs_from_settings
from lpstgp.sandbox import Sandbox
from lpstgp.splits import Stage, pilot_periods
from lpstgp.strategies import registry


def main() -> None:
    paths, settings = load_paths(), load_settings()
    test = json.loads((w.REPORTS / "pilot_go_no_go.json").read_text())
    _, cfg = configs_from_settings(settings)
    frozen = registry.load_frozen()
    store = modelling_store(paths.tier_dir("A"), settings)
    lmax = settings["splits"]["lookback_max_bars"]
    val: dict[str, dict[str, float]] = {}
    for period, plan_path in zip(pilot_periods(settings), w.gonogo_plans(paths), strict=True):
        box = Sandbox.open(store, period, Stage.VALIDATE, w.PILOT_INSTRUMENTS, lmax)
        as_test = replace(box, period=replace(period, test_start=period.val_start))
        portfolios = w._evaluate(as_test, w.records(plan_path), frozen, cfg)
        val[period.id] = {arm: portfolio_sharpe(s) for arm, s in portfolios.items()}
    out = {
        p: {
            arm: {"validation": v, "test": test["yearly_sharpe"][p][arm],
                  "gap": test["yearly_sharpe"][p][arm] - v}
            for arm, v in sorted(arms.items())
        }
        for p, arms in val.items()
    }  # fmt: skip
    (w.REPORTS / "pilot_validation_gap.json").write_text(json.dumps(out, indent=1))
    lines = [
        "# WP2 pilot: validation-test gap (protocol §8)",
        "",
        "Portfolio Sharpe of the frozen rules on each period's validation year and test year "
        "(same aggregation as the go/no-go). Gap = test - validation.",
        "",
        "| arm | PL1 val | PL1 test | PL1 gap | PL2 val | PL2 test | PL2 gap |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for arm in sorted(out["PL1"]):
        a, b = out["PL1"][arm], out["PL2"][arm]
        lines.append(
            f"| {arm} | {a['validation']:.3f} | {a['test']:.3f} | {a['gap']:+.3f} | "
            f"{b['validation']:.3f} | {b['test']:.3f} | {b['gap']:+.3f} |"
        )
    (w.REPORTS / "pilot_validation_gap.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
