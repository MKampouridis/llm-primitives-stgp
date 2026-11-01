"""Time the WP2 pilot's compute before calibration (PL1 FIT/VALIDATE data only).

1. Signals: each frozen strategy's entry/exit computation on the six calibration instruments
   (PL1 FIT sandbox), median of 3 repeats after a warm-up.
2. GP alone: one calibration-size run (population 500, tournament 3, 50,000 requested
   evaluations) of arm 2c and of arm 6 on SPX, one at a time.
3. GP under load: six concurrent arm-2c runs, one per calibration instrument.

These runs are timing only: they are not campaign tasks and are not entered in the trial register.
Writes results_dir/wp2/timing/timing.json and prints a summary.
Usage: uv run python scripts/time_wp2.py [--workers 6] [--skip-gp]
"""

from __future__ import annotations

import argparse
import json
import statistics
import time

from lpstgp.campaign.plan import run_seed
from lpstgp.config import load_paths, load_settings
from lpstgp.data.store import modelling_store
from lpstgp.runner import RunTask, configs_from_settings, execute, run_many
from lpstgp.sandbox import Sandbox
from lpstgp.splits import Stage, all_periods
from lpstgp.strategies.registry import load_frozen

INSTRUMENTS = ("SPX", "NKY", "EURUSD", "USDJPY", "GOLD", "NATGAS")  # protocol §6.1
PERIOD = "PL1"
GP = {"population": 500, "generations": 50_000 // 500 - 1, "tournament": 3}


def time_signals(paths, settings) -> dict:
    period = all_periods(settings)[PERIOD]
    store = modelling_store(paths.tier_dir("A"), settings)
    box = Sandbox.open(
        store, period, Stage.FIT, INSTRUMENTS, settings["splits"]["lookback_max_bars"]
    )
    del store
    out = {}
    for f in load_frozen():
        per_instrument = {}
        for name in INSTRUMENTS:
            bars = box[name]
            f.strategy.run(bars.log_price, bars.log_return)  # warm-up (numba compilation)
            reps = []
            for _ in range(3):
                t0 = time.perf_counter()
                f.strategy.run(bars.log_price, bars.log_return)
                reps.append(time.perf_counter() - t0)
            per_instrument[name] = statistics.median(reps)
        out[f.sid] = {"bars": len(box[INSTRUMENTS[0]].log_price), "seconds": per_instrument}
    return out


def gp_task(settings, library: str, instrument: str) -> RunTask:
    gp, fitness = configs_from_settings(settings, **GP)
    return RunTask(
        experiment="wp2_timing",
        library=library,
        instruments=(instrument,),
        period=PERIOD,
        seed=run_seed((instrument,), PERIOD, 1),
        gp=gp,
        fitness=fitness,
    )


def brief(record: dict) -> dict:
    keys = ("wall_clock_s", "setup_s", "peak_rss_mb")
    out = {k: record.get(k) for k in keys}
    out.update({k: v for k, v in record.items() if "eval" in k and not isinstance(v, (list, dict))})
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workers", type=int, default=6)
    parser.add_argument("--skip-gp", action="store_true")
    args = parser.parse_args()
    paths, settings = load_paths(), load_settings()
    out_dir = paths.results_dir / "wp2" / "timing"
    out_dir.mkdir(parents=True, exist_ok=True)
    result: dict = {"signals": time_signals(paths, settings)}
    totals = {sid: sum(v["seconds"].values()) for sid, v in result["signals"].items()}
    print("signals: seconds summed over the 6 instruments (PL1 FIT), slowest first")
    for sid, s in sorted(totals.items(), key=lambda kv: -kv[1]):
        print(f"  {sid}: {s:.3f}")
    (out_dir / "timing.json").write_text(json.dumps(result, indent=1))
    if not args.skip_gp:
        result["gp_alone"] = {}
        for library in ("s2c", "seed"):
            record = execute(gp_task(settings, library, "SPX"), out_dir / "alone")
            result["gp_alone"][library] = brief(record)
            print(library, "alone:", result["gp_alone"][library])
            (out_dir / "timing.json").write_text(json.dumps(result, indent=1, default=str))
        t0 = time.perf_counter()
        tasks = [gp_task(settings, "s2c", name) for name in INSTRUMENTS]
        records = run_many(tasks, args.workers, out_dir / "load")
        result["gp_load"] = {
            "workers": args.workers,
            "elapsed_s": time.perf_counter() - t0,
            "runs": [brief(r) for r in records],
        }
        print("s2c under load:", json.dumps(result["gp_load"], default=str))
    (out_dir / "timing.json").write_text(json.dumps(result, indent=1, default=str))


if __name__ == "__main__":
    main()
