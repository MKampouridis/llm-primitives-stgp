"""Run strategy code in a separate, locked-down process (host side).

The worker (``lpstgp.strategies.worker``) runs with a scrubbed environment, a timeout and, on
macOS, a ``sandbox-exec`` profile that denies all network access and every file write outside
the job folder. The source policy has already rejected file, network and reflection APIs; the
sandbox is defence in depth for code that has not been reviewed yet.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

import numpy as np

SANDBOX_EXEC = "/usr/bin/sandbox-exec"
PROFILE = """(version 1)
(allow default)
(deny network*)
(deny file-write*)
(allow file-write* (subpath "{job}") (literal "/dev/null") (literal "/dev/stdout")
       (literal "/dev/stderr") (regex #"^/dev/tty"))
"""


def sandboxed() -> bool:
    return sys.platform == "darwin" and Path(SANDBOX_EXEC).exists()


def run(
    command: str,
    strategy_path: Path,
    job_dir: Path,
    inputs_path: Path | None = None,
    timeout: float = 600.0,
    threads: int = 1,
    worker: str = "lpstgp.strategies.worker",
    extra: tuple[str, ...] = (),
) -> dict[str, Any]:
    """Run one worker command; returns its JSON result, or the arrays for ``evaluate``.

    ``worker`` is the child module (strategies here; ``lpstgp.authoring.worker`` for operators);
    ``extra`` are further file arguments, copied into the job folder first.
    """
    job_dir = Path(job_dir).resolve()
    job_dir.mkdir(parents=True, exist_ok=True)
    local = job_dir / Path(strategy_path).name
    if Path(strategy_path).resolve() != local:
        shutil.copyfile(strategy_path, local)
    out = job_dir / (f"{command}.npz" if command == "evaluate" else f"{command}.json")
    error = out.with_name(out.name + ".error.json")
    out.unlink(missing_ok=True)
    error.unlink(missing_ok=True)
    copies = []
    for path in extra:
        target = job_dir / "others" / Path(path).name
        target.parent.mkdir(exist_ok=True)
        shutil.copyfile(path, target)
        copies.append(str(target))
    cmd = [sys.executable, "-I", "-m", worker, command, str(local)]
    cmd += [str(inputs_path) if inputs_path else "-", str(out), *copies]
    if sandboxed():
        cmd = [SANDBOX_EXEC, "-p", PROFILE.format(job=job_dir), *cmd]
    threads_env = {
        k: str(threads)
        for k in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMBA_NUM_THREADS")
    }
    env = {
        "PATH": "/usr/bin:/bin",
        "HOME": str(job_dir),
        "LANG": "C.UTF-8",
        "PYTHONHASHSEED": "0",
        "PYTHONDONTWRITEBYTECODE": "1",
        "NUMBA_CACHE_DIR": str(job_dir / "numba"),
        **threads_env,
    }
    try:
        proc = subprocess.run(
            cmd, env=env, cwd=job_dir, timeout=timeout, capture_output=True, text=True
        )
    except subprocess.TimeoutExpired:
        return {"ok": False, "stage": "timeout", "error": f"{command} exceeded {timeout:.0f} s"}
    if error.exists():
        return json.loads(error.read_text())
    if not out.exists():
        tail = (proc.stderr or proc.stdout)[-1500:]
        return {"ok": False, "stage": "crash", "error": f"worker exit {proc.returncode}: {tail}"}
    if command == "evaluate":
        with np.load(out, allow_pickle=False) as npz:
            return {"ok": True, "arrays": {k: npz[k] for k in npz.files}}
    return json.loads(out.read_text())
