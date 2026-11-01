"""Do CERES's node types give bit-identical GP runs? (D-054)

Runs one short GP run (arms 2c and 6, PL1 training and validation data only) under several
settings of the numerical code paths, each in a fresh process because the settings must be set
before numpy and numba load. For each it writes an exact fingerprint of the results (floats by
their full repr) and the time taken, to <results_dir>/node_check/<host>.json. Comparing the files
of different nodes shows which setting makes every node give the same results.

  python scripts/ceres/node_probe.py            # on a compute node (scripts/ceres/node_check.sh)
"""

from __future__ import annotations

import hashlib
import json
import os
import platform
import socket
import subprocess
import sys
import time

AVX512 = (
    "AVX512F AVX512CD AVX512_KNL AVX512_KNM AVX512_SKX AVX512_CLX AVX512_CNL AVX512_ICL AVX512_SPR"
)
NUMBA_GENERIC = {"NUMBA_CPU_NAME": "generic", "NUMBA_DISABLE_INTEL_SVML": "1"}
VARIANTS = {
    "default": {},
    "numba_generic": NUMBA_GENERIC,
    "numpy_no_avx512": {"NPY_DISABLE_CPU_FEATURES": AVX512},
    "both": {**NUMBA_GENERIC, "NPY_DISABLE_CPU_FEATURES": AVX512},
    "both_no_avx2": {**NUMBA_GENERIC, "NPY_DISABLE_CPU_FEATURES": "AVX2 FMA3 " + AVX512},
}
PROBE_RUNS = (("s2c", "EURUSD"), ("seed", "EURUSD"), ("s2c", "NATGAS"))


def probe() -> dict:
    """One variant, in this process: fingerprints of short runs, plus what the CPU paths are."""
    import numba
    import numpy as np

    from lpstgp.config import load_settings
    from lpstgp.runner import RunTask, configs_from_settings, execute

    settings = load_settings()
    gp_cfg, fit_cfg = configs_from_settings(settings, population=200, generations=10, tournament=5)
    out = {"runs": {}}
    for library, instrument in PROBE_RUNS:
        task = RunTask("node-check", library, (instrument,), "PL1", 12345, gp_cfg, fit_cfg)
        started = time.perf_counter()
        record = execute(task)  # nothing written
        seconds = time.perf_counter() - started
        result = {k: record[k] for k in ("hall_of_fame", "selected", "generations", "budget")}
        result["generations"] = [
            {k: v for k, v in g.items() if not k.endswith("_s")} for g in result["generations"]
        ]
        text = json.dumps(result, sort_keys=True, default=repr)
        out["runs"][f"{library}/{instrument}"] = {
            "fingerprint": hashlib.sha256(text.encode()).hexdigest()[:16],
            "best_validation": repr(
                record["hall_of_fame"][record["selected"]]["validation"]["fitness"]
            ),
            "seconds": round(seconds, 1),
        }
    try:
        from numpy._core._multiarray_umath import __cpu_features__ as features
    except ImportError:
        features = {}
    out["numpy_features_on"] = sorted(k for k, v in features.items() if v)
    out["numba_svml"] = bool(getattr(numba.config, "USING_SVML", False))
    try:
        import llvmlite.binding as llvm

        out["numba_cpu"] = os.environ.get("NUMBA_CPU_NAME") or llvm.get_host_cpu_name()
    except Exception as exc:
        out["numba_cpu"] = f"? {exc}"
    out["numpy"] = np.__version__
    return out


def cpu_model() -> dict:
    model, flags = "?", set()
    try:
        with open("/proc/cpuinfo", encoding="utf-8") as handle:
            for line in handle:
                if line.startswith("model name") and model == "?":
                    model = line.split(":", 1)[1].strip()
                elif line.startswith("flags"):
                    flags = set(line.split(":", 1)[1].split())
                    break
    except OSError:
        pass
    wanted = ("sse4_2", "avx", "avx2", "fma", "avx512f", "avx512dq", "avx512vl")
    return {"model": model, "flags": [f for f in wanted if f in flags]}


def main() -> None:
    if len(sys.argv) > 1 and sys.argv[1] == "--variant":
        print(json.dumps(probe()))
        return
    from lpstgp.config import load_paths

    host = socket.gethostname().split(".")[0]
    report = {"host": host, "cpu_count": os.cpu_count(), "cpu": cpu_model(),
              "platform": platform.platform(), "variants": {}}  # fmt: skip
    for name, env in VARIANTS.items():
        done = subprocess.run(
            [sys.executable, __file__, "--variant"],
            env={**os.environ, **env}, capture_output=True, text=True,
        )  # fmt: skip
        if done.returncode == 0:
            report["variants"][name] = json.loads(done.stdout.strip().splitlines()[-1])
        else:
            report["variants"][name] = {"error": done.stderr.strip().splitlines()[-3:]}
        print(name, json.dumps(report["variants"][name].get("runs", report["variants"][name])))
    out = load_paths().results_dir / "node_check" / f"{host}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=1) + "\n")
    print("written", out)


if __name__ == "__main__":
    main()
