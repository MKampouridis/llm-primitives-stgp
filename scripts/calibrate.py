"""Calibration runs for the compute projections (training and validation data only).

1. Per-operator micro-benchmarks on P01 FIT data (S&P 500): every operator at its grid extremes and
   every terminal, on the sandbox arrays a run actually uses (504 warm-up + 504 fit bars).
2. Conventional (TA/DC) library with the smoke configuration (SPX, EURUSD x 2 seeds, 4 workers).
3. Single-worker baseline: one smoke-size run alone.
4. Six concurrent smoke-size runs: throughput and memory per worker under load.
5. One full-budget run: SPX, P01, seed library, population 500 x 50 generations.

Writes results_dir/tierA/wp1_calibration/calibration.json.
Usage: uv run python scripts/calibrate.py [--skip-full]
"""

from __future__ import annotations

import argparse
import json
import statistics
import time
from pathlib import Path

import numpy as np

from lpstgp.config import load_paths, load_settings
from lpstgp.data.store import DataStore
from lpstgp.gates.checks import sample_params
from lpstgp.operators.registry import discover
from lpstgp.runner import RunTask, configs_from_settings, execute, run_many
from lpstgp.sandbox import Sandbox
from lpstgp.splits import Stage, periods_from_settings
from lpstgp.types import Bool, Hist, Real, Regime, Series
from lpstgp.types import Path as PathType

EXPERIMENT = "wp1_calibration"


def load_smoke_summarise():
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "smoke_test", Path(__file__).with_name("smoke_test.py")
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.summarise


def micro_benchmarks(paths, settings, repeats: int = 3) -> list[dict]:
    period = periods_from_settings(settings)[0]
    box = Sandbox.open(
        DataStore(paths.tier_dir("A")),
        period,
        Stage.FIT,
        ["SPX"],
        settings["splits"]["lookback_max_bars"],
    )
    bars = box["SPX"]
    reg = discover()
    ops = {s.name: s for s in reg.operators.values()}
    ret, price = np.asarray(bars.log_return), np.asarray(bars.log_price)
    feature = ops["mean_ksd"].impl(ret, 60, 0.0)
    inputs = {
        Series: [ret, np.abs(ret)],
        PathType: [price, ops["to_path"](np.abs(ret))],
        Hist: [ops["rolling_hist"](ret, window=20), ops["rolling_hist"](ret, window=120)],
        Real: [feature, ops["rolling_percentile"](feature, window=120, q=0.5)],
        Bool: [ops["gt"](ret, np.zeros_like(ret)), ops["gt"](feature, np.zeros_like(feature))],
        Regime: [ops["quantile_regime"](feature, window=120)] * 2,
    }
    rows = []
    for spec in sorted(reg.operators.values(), key=lambda s: s.key):
        counts: dict = {}
        args = []
        for t in spec.inputs:
            k = counts.get(t, 0)
            counts[t] = k + 1
            args.append(inputs[t][k % 2])
        for params in sample_params(spec, 0, n_random=0):
            spec.impl(*args, **params)  # compile / warm up
            times = []
            for _ in range(repeats):
                t0 = time.perf_counter()
                spec.impl(*args, **params)
                times.append(1000 * (time.perf_counter() - t0))
            rows.append(
                {
                    "key": spec.key,
                    "domain": spec.domain,
                    "params": params,
                    "ms": statistics.median(times),
                    "bars": len(ret),
                }
            )
    for spec in sorted(reg.terminals.values(), key=lambda s: s.key):
        spec(price, ret)
        times = []
        for _ in range(repeats):
            t0 = time.perf_counter()
            spec(price, ret)
            times.append(1000 * (time.perf_counter() - t0))
        rows.append(
            {
                "key": spec.key,
                "domain": spec.domain,
                "params": {},
                "ms": statistics.median(times),
                "bars": len(ret),
            }
        )
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--skip-full", action="store_true")
    parser.add_argument("--concurrent", type=int, default=6)
    args = parser.parse_args()
    paths, settings = load_paths(), load_settings()
    summarise = load_smoke_summarise()
    smoke_cfg, fit_cfg = configs_from_settings(settings, population=200, generations=10)
    out: dict = {"started": time.strftime("%Y-%m-%d %H:%M:%S")}

    t0 = time.perf_counter()
    out["micro_benchmarks"] = micro_benchmarks(paths, settings)
    print(
        f"micro-benchmarks: {len(out['micro_benchmarks'])} rows in {time.perf_counter() - t0:.0f}s",
        flush=True,
    )

    tasks = [
        RunTask(
            f"{EXPERIMENT}_conventional", "conventional", (inst,), "P01", seed, smoke_cfg, fit_cfg
        )
        for inst in ("SPX", "EURUSD")
        for seed in (1, 2)
    ]
    t0 = time.perf_counter()
    out["conventional"] = [summarise(r) for r in run_many(tasks, 4, paths.results_dir)]
    print(f"conventional smoke: {time.perf_counter() - t0:.0f}s", flush=True)

    t0 = time.perf_counter()
    single = execute(
        RunTask(f"{EXPERIMENT}_single", "seed", ("SPX",), "P01", 11, smoke_cfg, fit_cfg),
        paths.results_dir,
    )
    out["single_worker"] = summarise(single)
    print(f"single-worker baseline: {time.perf_counter() - t0:.0f}s", flush=True)

    tasks = [
        RunTask(f"{EXPERIMENT}_concurrent", "seed", ("SPX",), "P01", seed, smoke_cfg, fit_cfg)
        for seed in range(21, 21 + args.concurrent)
    ]
    t0 = time.perf_counter()
    records = run_many(tasks, args.concurrent, paths.results_dir)
    out["concurrent"] = {
        "workers": args.concurrent,
        "elapsed_s": time.perf_counter() - t0,
        "runs": [summarise(r) for r in records],
    }
    print(f"{args.concurrent} concurrent runs: {out['concurrent']['elapsed_s']:.0f}s", flush=True)

    if not args.skip_full:
        full_cfg, _ = configs_from_settings(settings, population=500, generations=50)
        t0 = time.perf_counter()
        full = execute(
            RunTask(f"{EXPERIMENT}_full", "seed", ("SPX",), "P01", 31, full_cfg, fit_cfg),
            paths.results_dir,
        )
        s = summarise(full)
        s["generation_curve"] = [
            {
                k: g[k]
                for k in (
                    "gen",
                    "eval_s",
                    "new_unique",
                    "mean_nodes",
                    "mean_size_w",
                    "cache_hit_rate",
                    "elapsed_s",
                )
            }
            for g in full["generations"]
        ]
        s["operator_seconds"] = full["operator_seconds"]
        out["full_budget"] = s
        print(f"full-budget run: {time.perf_counter() - t0:.0f}s", flush=True)

    target = paths.results_dir / "tierA" / EXPERIMENT / "calibration.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(out, indent=1, default=str), encoding="utf-8")
    print(f"wrote {target}")


if __name__ == "__main__":
    main()
