"""Child process that runs LLM-authored operator code (started by ``strategies.execute.run``).

Usage: python -I -m lpstgp.authoring.worker {meta,gates,describe,hash} OPERATOR INPUTS OUT [OTHER...]

INPUTS is the anonymised development ``.npz`` (``lp::<id>``, ``lr::<id>``, ``start::<id>``) or
``-``. OTHER are further operator files of the same session (``describe`` correlates with them).
Results go to OUT as JSON; errors are reported in the JSON, never raised. No returns-based
quantity is computed here: ``describe`` reports the operator's own output only.
"""

from __future__ import annotations

import hashlib
import json
import sys
import traceback
from pathlib import Path

import numpy as np
from scipy.stats import rankdata

from lpstgp.authoring import gates
from lpstgp.authoring.loader import OperatorLoadError, load_spec
from lpstgp.gates import checks
from lpstgp.operators.contract import OperatorSpec, Provenance
from lpstgp.strategies import channel

PROVENANCE = Provenance(implemented_by="authoring session", specified_by="LLM", date="")
DOMAIN = "core"  # placeholder for loading; the host assigns the session's domain


def meta(spec: OperatorSpec) -> dict:
    return {
        "name": spec.name,
        "summary": spec.summary,
        "signature": signature(spec),
        "inputs": [t.__name__ for t in spec.inputs],
        "params": {p.name: {"kind": p.kind.__name__, "grid": list(p.grid)} for p in spec.params},
        "output": spec.output.__name__,
        "missing": spec.missing.value,
        "min_valid": spec.min_valid,
        "invariances": list(spec.invariances),
        "lookback_range": [spec.lookback_for(p) for p in _extremes(spec)],
        "definition": spec.definition,
        "references": list(spec.references),
    }


def signature(spec: OperatorSpec) -> str:
    args = [t.__name__ for t in spec.inputs]
    args += [f"{p.name}: {p.kind.__name__.removeprefix('Llm')}" for p in spec.params]
    return f"{spec.name}({', '.join(args)}) -> {spec.output.__name__}"


def _extremes(spec: OperatorSpec) -> list[dict]:
    if not spec.params:
        return [{}]
    return [{p.name: min(p.grid) for p in spec.params}, {p.name: max(p.grid) for p in spec.params}]


def middle(spec: OperatorSpec) -> dict:
    return {p.name: p.grid[len(p.grid) // 2] for p in spec.params}


def _stats(out: np.ndarray, scored: np.ndarray) -> dict:
    values = out[scored]
    finite = values[np.isfinite(values)]
    row = {"finite_share": float(np.isfinite(values).mean()) if len(values) else 0.0}
    if len(finite) > 2:
        q = np.quantile(finite, (0.05, 0.25, 0.5, 0.75, 0.95))
        row |= {
            f"q{int(k * 100):02d}": float(v)
            for k, v in zip((0.05, 0.25, 0.5, 0.75, 0.95), q, strict=True)
        }
        a, b = values[:-1], values[1:]
        ok = np.isfinite(a) & np.isfinite(b)
        row["lag1_autocorrelation"] = (
            float(np.corrcoef(a[ok], b[ok])[0, 1]) if ok.sum() > 2 and np.std(a[ok]) > 0 else None
        )
        row["distinct_share"] = float(len(np.unique(finite)) / len(finite))
    return row


def _rank(x: np.ndarray) -> np.ndarray:
    """Average ranks of ties (D-074; ranking by position gave tied values distinct ranks)."""
    return rankdata(x, method="average")


def _spearman(a: np.ndarray, b: np.ndarray) -> float | None:
    ok = np.isfinite(a) & np.isfinite(b)
    if ok.sum() < 30:
        return None
    ra, rb = _rank(a[ok]), _rank(b[ok])
    if np.std(ra) == 0 or np.std(rb) == 0:
        return None
    return float(np.corrcoef(ra, rb)[0, 1])


def _median(rows: list[dict], key: str):
    values = [r[key] for r in rows if r.get(key) is not None]
    return round(float(np.median(values)), 4) if values else None


def describe(spec: OperatorSpec, data: gates.DevInputs, others: list[OperatorSpec]) -> dict:
    """Descriptive statistics of the output on development data (medians across instruments)."""
    points = [*checks.sample_params(spec, gates.SEED, n_random=0), middle(spec)]
    unique = [p for i, p in enumerate(points) if p not in points[:i]]
    by_point = []
    for params in unique:
        rows = []
        for lp, lr, start in data.values():
            inputs = gates.real_inputs(spec, lp, lr)
            out = checks.run(spec, inputs, params)
            scored = np.zeros(len(out), dtype=bool)
            scored[max(start, spec.earliest(params) + 1) :] = True
            rows.append(_stats(out, scored))
        keys = sorted({k for r in rows for k in r})
        by_point.append({"params": params, **{k: _median(rows, k) for k in keys}})
    correlations = {}
    for other in others:
        values = []
        for lp, lr, start in data.values():
            a = checks.run(spec, gates.real_inputs(spec, lp, lr), middle(spec))[start:]
            b = checks.run(other, gates.real_inputs(other, lp, lr), middle(other))[start:]
            values.append(_spearman(a, b))
        finite = [v for v in values if v is not None]
        correlations[other.name] = round(float(np.median(finite)), 3) if finite else None
    return {
        "instruments": len(data),
        "statistics": by_point,
        "rank_correlation_with_other_operators": correlations,
        "note": "medians across instruments; descriptive statistics of the feature only",
    }


def output_hash(spec: OperatorSpec) -> str:
    digest = hashlib.sha256()
    for params in checks.sample_params(spec, gates.SEED, n_random=2):
        out = checks.run(spec, gates.synthetic_inputs(spec), params)
        digest.update(np.ascontiguousarray(out).tobytes())
    return digest.hexdigest()


def main(argv: list[str]) -> int:
    command, path, _inputs, out_path, *other_paths = argv[1:]
    out = Path(out_path)
    # Secret and inputs first, before any LLM code is loaded (D-081).
    secret, inputs = channel.receive()

    def answer(result: dict) -> int:
        channel.write_signed(out, json.dumps(result, default=float).encode(), secret)
        return 0

    try:
        spec = load_spec(Path(path), DOMAIN, PROVENANCE)
    except OperatorLoadError as exc:
        return answer({"ok": False, "stage": "load", "error": str(exc)})
    except Exception as exc:  # the module's own top-level code, with data in memory (D-081)
        return answer({"ok": False, "stage": "load", "error": gates.withheld(exc)})
    try:
        if command == "meta":
            result = {"ok": True, "operator": meta(spec)}
        elif command == "gates":
            results = gates.synthetic_gates(spec)
            if inputs and gates.passed(results):
                results += gates.development_gates(spec, inputs)
            result = {"ok": True, "passed": gates.passed(results), "results": results}
        elif command == "describe":
            others = []
            for other in other_paths:
                try:
                    others.append(load_spec(Path(other), DOMAIN, PROVENANCE))
                except Exception:  # an unfinished sibling file is simply skipped
                    continue
            result = {"ok": True, **describe(spec, inputs, others)}
        elif command == "hash":
            result = {"ok": True, "hash": output_hash(spec)}
        else:
            result = {"ok": False, "stage": "command", "error": f"unknown command {command}"}
    except Exception as exc:  # the operator's own code failed
        if command == "describe":  # it ran on development data: no message (D-074)
            result = {"ok": False, "stage": command, "error": gates.withheld(exc)}
        else:  # synthetic inputs only: the full message helps the session fix its code
            tb = traceback.format_exception(exc)
            result = {
                "ok": False,
                "stage": command,
                "error": f"{type(exc).__name__}: {exc}",
                "traceback": "".join(tb[-6:]),
            }
    return answer(result)


if __name__ == "__main__":
    sys.exit(main(sys.argv))
