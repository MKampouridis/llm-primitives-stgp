"""Run orchestration: sandboxes -> STGP run -> one JSON record per run.

This is the only module that both opens sandboxes and writes results; the GP and backtest packages
never touch the data layer. Records hold per-run summaries and best individuals only (no
populations). Parallel runs use separate spawned processes with one BLAS/numba thread each.
"""

from __future__ import annotations

import gzip
import json
import os
import platform
import re
import resource
import shutil
import sys
import time
from collections.abc import Callable, Iterable, Mapping
from concurrent.futures import ProcessPoolExecutor, as_completed
from concurrent.futures.process import BrokenProcessPool
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from multiprocessing import get_context
from pathlib import Path
from typing import Any

from deap import gp

from lpstgp.backtest.costs import from_meta
from lpstgp.config import load_paths, load_settings
from lpstgp.data.store import modelling_store
from lpstgp.data.tier_a import git_revision
from lpstgp.gp.fitness import FitnessConfig
from lpstgp.gp.pset import build
from lpstgp.gp.run import GPConfig, Problem, run_gp
from lpstgp.gp.variation import Limits, Rule
from lpstgp.libraries import STRATEGY_LIBRARIES, resolve
from lpstgp.operators.contract import OperatorSpec
from lpstgp.operators.registry import read_lock
from lpstgp.sandbox import Sandbox
from lpstgp.splits import Stage, all_periods
from lpstgp.strategies.registry import lock_digest as strategy_lock_digest
from lpstgp.types import Bool

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
    library: str  # a name in lpstgp.libraries.NAMES, e.g. "seed", "technical", "s2c"
    instruments: tuple[str, ...]  # one instrument: per-asset rule; several: pooled fitness
    period: str
    seed: int
    gp: GPConfig = field(default_factory=GPConfig)
    fitness: FitnessConfig = field(default_factory=FitnessConfig)
    tier: str = "A"
    campaign: tuple[tuple[str, str], ...] = ()  # task id, run index and digests (campaign plans)
    # WP3 maintenance cycles: knock-out evidence for the hall of fame (FIT only, §4.1), and
    # arm 5's proposed rules as (entry, exit) tree strings seeded into the initial population.
    knockouts: bool = False
    seed_rules: tuple[tuple[str, str], ...] = ()
    # WP4 (D-085): records are gzip-compressed JSON (``.json.gz``), about 6 times smaller.
    compressed: bool = False

    @property
    def name(self) -> str:
        task_id = dict(self.campaign).get("task_id")
        if task_id:  # campaign tasks are named by their (unique) task id
            return task_id.replace("/", "__")
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
    period = all_periods(settings)[task.period]
    lmax = settings["splits"]["lookback_max_bars"]
    store = modelling_store(paths.tier_dir(task.tier), settings)
    fit_box = Sandbox.open(store, period, Stage.FIT, task.instruments, lmax)
    val_box = Sandbox.open(store, period, Stage.VALIDATE, task.instruments, lmax)
    del store  # modelling code below only ever sees the sandboxes
    specs = resolve(task.library)
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
    seeded = [Rule(parse_tree(e, lib), parse_tree(x, lib)) for e, x in task.seed_rules]
    summary = run_gp(lib, fit_problem, val_problem, task.gp, task.seed, progress, seeded)
    if task.knockouts:
        from lpstgp.maintenance.knockout import contributions

        hall = [
            Rule(lib.from_names(h["entry"]), lib.from_names(h["exit"]))
            for h in summary["hall_of_fame"]
        ]
        t0 = time.perf_counter()
        targets = [s.gp_name for s in specs if isinstance(s, OperatorSpec) and s.domain != "core"]
        summary["knockouts"] = contributions(fit_problem, hall, targets)
        summary["timings"]["knockout_s"] = time.perf_counter() - t0
    lock = read_lock()
    record = {
        "schema": 1,
        "run_id": task.name,
        "created_utc": datetime.now(UTC).isoformat(timespec="seconds"),
        "code_version": git_revision(),
        "experiment": task.experiment,
        "campaign": dict(task.campaign),
        "tier": task.tier,
        "library": {
            "name": task.library,
            "contracts": {s.key: lock.get(s.key, "") for s in specs},
            "strategies_lock": strategy_lock_digest() if task.library in STRATEGY_LIBRARIES else "",
            # A maintained state's id pins each operator file's hash (lpstgp.maintenance.state).
            "state": task.library.removeprefix("state:")
            if task.library.startswith("state:")
            else "",
        },
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
        out = record_path(results_dir, task)
        write_record(out, record)
        record["record_path"] = str(out)
        record["record_bytes"] = out.stat().st_size
    return record


def parse_tree(text: str, lib) -> gp.PrimitiveTree:
    """A tree from its printed form (as in hall-of-fame ``entry_str``), typed by ``lib``.

    Every token must name a node of the primitive set before deap parses the text: deap would
    otherwise ``eval`` unknown tokens, and arm 5's text is LLM output.
    """
    tokens = [t for t in re.split(r"[\s,()]+", text) if t]
    unknown = sorted({t for t in tokens if t not in lib.pset.mapping})
    if not tokens or unknown or not re.fullmatch(r"[\w\s,()]+", text):
        raise ValueError(f"unknown nodes {unknown[:5]} or characters in: {text[:200]}")
    tree = gp.PrimitiveTree.from_string(text, lib.pset)
    if getattr(tree[0], "ret", None) is not Bool:
        raise ValueError(f"not a Bool tree: {text}")
    try:
        complete = tree.searchSubtree(0).stop == len(tree)
    except IndexError:
        complete = False
    if not complete or any(n.arity == 0 and n.name.startswith("ARG") for n in tree):
        raise ValueError(f"malformed tree (wrong number of arguments): {text}")
    return tree


def record_path(results_dir: Path | str, task: RunTask) -> Path:
    suffix = ".json.gz" if task.compressed else ".json"
    return Path(results_dir) / f"tier{task.tier}" / task.experiment / f"{task.name}{suffix}"


def write_record(path: Path, record: Mapping[str, Any]) -> None:
    """A run record, whole or not at all; gzip-compressed if ``path`` ends in ``.gz``."""
    text = json.dumps(record, separators=(",", ":"), default=str)
    if path.suffix == ".gz":  # mtime 0: the same record gives the same bytes on every machine
        write_atomic_bytes(path, gzip.compress(text.encode(), compresslevel=6, mtime=0))
    else:
        write_atomic(path, text)


def read_record(path: Path) -> dict[str, Any]:
    data = Path(path).read_bytes()
    return json.loads(gzip.decompress(data) if Path(path).suffix == ".gz" else data)


def write_atomic_bytes(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f"{path.name}.{os.getpid()}.{os.urandom(4).hex()}.tmp")
    tmp.write_bytes(data)
    os.replace(tmp, path)


def write_atomic(path: Path, text: str) -> None:
    """Write whole or not at all: a crash never leaves a truncated record behind."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f"{path.name}.{os.getpid()}.{os.urandom(4).hex()}.tmp")  # one per writer
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)


class RunFailuresError(RuntimeError):
    """Some runs raised; every other run finished and was written."""


class DiskSpaceError(RuntimeError):
    """Free disk space fell below the guard; remaining runs were cancelled."""


MIN_FREE_BYTES = 5 * 2**30


def _worker(task: RunTask, results_dir: str | None) -> dict:
    return execute(task, Path(results_dir) if results_dir else None)


def run_many(
    tasks: Iterable[RunTask],
    workers: int,
    results_dir: Path | None,
    min_free_bytes: int = MIN_FREE_BYTES,
) -> list[dict]:
    """Run tasks in parallel spawned processes (one BLAS/numba thread each); returns the records.

    Stops (``DiskSpaceError``) when free space under ``results_dir`` falls below
    ``min_free_bytes``; on any exit, pending runs are cancelled and worker processes terminated.
    """
    for var in THREAD_VARS:
        os.environ[var] = "1"  # inherited by the spawned workers before they import numpy/numba
    records, failures = [], []
    pool = ProcessPoolExecutor(max_workers=workers, mp_context=get_context("spawn"))
    try:
        futures = {
            pool.submit(_worker, t, str(results_dir) if results_dir else None): t for t in tasks
        }
        for future in as_completed(futures):
            try:
                records.append(future.result())
            except BrokenProcessPool:
                raise
            except Exception as exc:  # one failing run must not stop the others
                failures.append(f"{futures[future].name}: {type(exc).__name__}: {exc}")
                continue
            if results_dir is not None and shutil.disk_usage(results_dir).free < min_free_bytes:
                raise DiskSpaceError(f"less than {min_free_bytes / 2**30:.0f} GB free; stopping")
    finally:
        pool.shutdown(wait=False, cancel_futures=True)
        processes = getattr(pool, "_processes", None) or {}
        for process in list(processes.values()):
            if process.is_alive():
                process.terminate()
    if failures:
        raise RunFailuresError(f"{len(failures)} run(s) failed:\n" + "\n".join(failures))
    return records
