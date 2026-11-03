"""Run strategy code in a separate, locked-down process (host side).

The worker (``lpstgp.strategies.worker``) runs with a scrubbed environment, a timeout and, on
macOS, a ``sandbox-exec`` profile that denies all network access, every file write outside the
job folder, and reading the contents of any file under the user, volume and temporary areas
except the Python runtime, the ``lpstgp`` package (without the other libraries' sources) and the
job folder (D-074, D-081). Inputs arrive through stdin, and results are signed (``channel``).
So code that slips past the source policy cannot read data, results or validation records. The
source policy has already rejected file, network and reflection APIs; the sandbox is defence in
depth for code that has not been reviewed yet.
"""

from __future__ import annotations

import io
import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

import numpy as np

from lpstgp.strategies import channel

SANDBOX_EXEC = "/usr/bin/sandbox-exec"
PROFILE = """(version 1)
(allow default)
(deny network*)
(deny file-write*)
(allow file-write* (subpath "{job}") (literal "/dev/null") (literal "/dev/stdout")
       (literal "/dev/stderr") (regex #"^/dev/tty"))
(deny file-read-data {denied})
(allow file-read-data {readable})
(deny file-read-data {private})
"""
# Areas whose file contents the worker may not read (data, results, caches, home, mounts) ...
DENIED_READS = ("/Users", "/Volumes", "/private/tmp", "/private/var/folders", "/tmp", "/opt")


# Inside the package, the sources of the other libraries and of the experiment machinery: an
# untrusted module could otherwise read them and pass them back in an error message (D-081).
PRIVATE_PACKAGE_PARTS = (
    "operators/fractal", "operators/information_geometry", "operators/information_theory",
    "operators/optimal_transport", "operators/rough_paths", "operators/spectral",
    "operators/statistical_physics", "operators/conventional", "strategies/generated",
    "authoring/generated", "authoring/prompts", "maintenance", "campaign", "analysis",
)  # fmt: skip


def _package() -> Path:
    import lpstgp

    return Path(lpstgp.__file__).resolve().parent


def _readable(job: Path) -> list[str]:
    """... except these: the Python runtime and environment, the package, the job folder."""
    package = _package()
    runtime = {Path(sys.prefix), Path(sys.base_prefix), Path(sys.executable).resolve().parents[1]}
    rules = [f'(subpath "{p.resolve()}")' for p in sorted(runtime)]
    rules += [f'(literal "{package.parent}")', f'(subpath "{package}")', f'(subpath "{job}")']
    return rules


def profile(job: Path) -> str:
    denied = " ".join(f'(subpath "{d}")' for d in DENIED_READS)
    home = Path.home().resolve()
    if not any(home.is_relative_to(d) for d in DENIED_READS):
        denied += f' (subpath "{home}")'
    private = " ".join(f'(subpath "{_package() / part}")' for part in PRIVATE_PACKAGE_PARTS)
    return PROFILE.format(
        job=job, denied=denied, readable=" ".join(_readable(job)), private=private
    )


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
    cmd = [sys.executable, "-I", "-m", worker, command, str(local), "-", str(out), *copies]
    if sandboxed():
        cmd = [SANDBOX_EXEC, "-p", profile(job_dir), *cmd]
    secret = channel.new_secret()  # inputs and secret go through stdin, never a file (D-081)
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
            cmd, env=env, cwd=job_dir, timeout=timeout, capture_output=True,
            input=channel.message(secret, inputs_path),
        )  # fmt: skip
    except subprocess.TimeoutExpired:
        return {"ok": False, "stage": "timeout", "error": f"{command} exceeded {timeout:.0f} s"}
    if error.exists() or out.exists():
        answer = error if error.exists() else out
        data = channel.read_verified(answer, secret)
        if data is None:  # written by the untrusted code, not by the worker (D-081)
            return {"ok": False, "stage": "integrity", "error": "the result was not the worker's"}
        if answer is error or command != "evaluate":
            return json.loads(data)
        with np.load(io.BytesIO(data), allow_pickle=False) as npz:
            return {"ok": True, "arrays": {k: npz[k] for k in npz.files}}
    tail = (proc.stderr or proc.stdout).decode(errors="replace")[-1500:]
    return {"ok": False, "stage": "crash", "error": f"worker exit {proc.returncode}: {tail}"}
