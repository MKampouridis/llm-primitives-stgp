"""Run orchestration: sandboxes -> STGP run -> one JSON record per run.

This is the only module that both opens sandboxes and writes results; the GP and backtest packages
never touch the data layer. Records hold per-run summaries and best individuals only (no
populations). Parallel runs use separate spawned processes with one BLAS/numba thread each.
"""

from __future__ import annotations

import json
import os
import platform
import resource
import sys
import time
from collections.abc import Callable, Iterable
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from multiprocessing import get_context
from pathlib import Path

from lpstgp.backtest.costs import from_meta
from lpstgp.config import load_paths, load_settings
from lpstgp.data.store import DataStore
from lpstgp.data.tier_a import git_revision
from lpstgp.gp.fitness import FitnessConfig
from lpstgp.gp.pset import build
from lpstgp.gp.run import GPConfig, Problem, run_gp
from lpstgp.gp.variation import Limits
from lpstgp.operators.registry import discover, read_lock
from lpstgp.sandbox import Sandbox
from lpstgp.splits import Stage, periods_from_settings

THREAD_VARS = (
    "OMP_NUM_THREADS",
    "OPENBLAS_NUM_THREADS",
    "MKL_NUM_THREADS",
    "VECLIB_MAXIMUM_THREADS",
    "NUMBA_NUM_THREADS",
)


@dataclass(frozen=True)
class RunTask:
    experiment: str
    library: str  # "seed", "conventional" or "seed+conventional"
    instruments: tuple[str, ...]  # one instrument: per-asset rule; several: pooled fitness
    period: str
    seed: int
    gp: GPConfig = field(default_factory=GPConfig)
    fitness: FitnessConfig = field(default_factory=FitnessConfig)
    tier: str = "A"

    @property
    def name(self) -> str:
        return f"{self.period}_{'+'.join(self.instruments)}_{self.library}_s{self.seed}"


def configs_from_settings(settings, **gp_overrides) -> tuple[GPConfig, FitnessConfig]:
    """GP and fitness configuration from config/settings.toml, with optional GP overrides."""
    g, f = dict(settings["gp"]), dict(settings["fitness"])
    limits = Limits(g.pop("max_depth"), g.pop("max_nodes"), settings["splits"]["lookback_max_bars"])
    g["init_depth"] = tuple(g["init_depth"])
    g["cache_bytes"] = int(g.pop("cache_mb")) * 2**20
    g.update(gp_overrides)
    return GPConfig(limits=limits, **g), FitnessConfig(**f)


def peak_rss_mb() -> float:
    rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return rss / 2**20 if sys.platform == "darwin" else rss / 2**10  # bytes on macOS, KB on Linux


def environment() -> dict[str, str]:
    import deap
    import numba
    import numpy

    return {
        "python": platform.python_version(),
        "numpy": numpy.__version__,
        "numba": numba.__version__,
        "deap": deap.__version__,
        "platform": platform.platform(),
        "machine": platform.machine(),
        "cpu_count": str(os.cpu_count()),
        "threads": ",".join(f"{v}={os.environ.get(v, '')}" for v in THREAD_VARS),
    }


def execute(
    task: RunTask, results_dir: Path | None = None, progress: Callable | None = None
) -> dict:
    """Run one STGP run; write its record under results_dir/tier<T>/<experiment>/ if a dir is given."""
    started = time.perf_counter()
    paths, settings = load_paths(), load_settings()
    period = {p.id: p for p in periods_from_settings(settings)}[task.period]
    lmax = settings["splits"]["lookback_max_bars"]
    store = DataStore(paths.tier_dir(task.tier))
    fit_box = Sandbox.open(store, period, Stage.FIT, task.instruments, lmax)
    val_box = Sandbox.open(store, period, Stage.VALIDATE, task.instruments, lmax)
    del store  # modelling code below only ever sees the sandboxes
    registry = discover()
    specs = registry.library(task.library)
    lib = build(specs)
    costs = {name: from_meta(fit_box[name].meta) for name in task.instruments}
    fit_problem = Problem(
        lib, fit_box.bars, period.scored_window(Stage.FIT), costs, task.fitness, task.gp.cache_bytes
    )
    val_problem = Problem(
        lib,
        val_box.bars,
        period.scored_window(Stage.VALIDATE),
        costs,
        task.fitness,
        task.gp.cache_bytes // 4,
    )
    setup_s = time.perf_counter() - started
    summary = run_gp(lib, fit_problem, val_problem, task.gp, task.seed, progress)
    lock = read_lock()
    record = {
        "schema": 1,
        "run_id": task.name,
        "created_utc": datetime.now(UTC).isoformat(timespec="seconds"),
        "code_version": git_revision(),
        "experiment": task.experiment,
        "tier": task.tier,
        "library": {"name": task.library, "contracts": {s.key: lock.get(s.key, "") for s in specs}},
        "instruments": list(task.instruments),
        "period": {k: str(v) for k, v in asdict(period).items()},
        "sandbox_access": [
            {k: str(v) for k, v in asdict(r).items()}
            for r in fit_box.access_log + val_box.access_log
        ],
        **summary,
        "setup_s": setup_s,
        "wall_clock_s": time.perf_counter() - started,
        "peak_rss_mb": peak_rss_mb(),
        "environment": environment(),
    }
    if results_dir is not None:
        out = Path(results_dir) / f"tier{task.tier}" / task.experiment / f"{task.name}.json"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(record, separators=(",", ":"), default=str), encoding="utf-8")
        record["record_path"] = str(out)
        record["record_bytes"] = out.stat().st_size
    return record


def _worker(task: RunTask, results_dir: str | None) -> dict:
    return execute(task, Path(results_dir) if results_dir else None)


def run_many(tasks: Iterable[RunTask], workers: int, results_dir: Path | None) -> list[dict]:
    """Run tasks in parallel spawned processes (one BLAS/numba thread each); returns the records."""
    for var in THREAD_VARS:
        os.environ[var] = "1"  # inherited by the spawned workers before they import numpy/numba
    records = []
    with ProcessPoolExecutor(max_workers=workers, mp_context=get_context("spawn")) as pool:
        futures = [
            pool.submit(_worker, t, str(results_dir) if results_dir else None) for t in tasks
        ]
        for future in as_completed(futures):
            records.append(future.result())
    return records
