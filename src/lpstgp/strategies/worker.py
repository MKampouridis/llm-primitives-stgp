"""Child-process entry point that runs strategy code (started by ``execute.run``, sandboxed).

Usage: python -I -m lpstgp.strategies.worker {describe,gates,evaluate,hash} STRATEGY INPUTS OUT

INPUTS is an ``.npz`` with ``lp::<name>``, ``lr::<name>`` and ``start::<name>`` arrays (or ``-``).
Results go to OUT (JSON, or ``.npz`` for ``evaluate``); errors are reported in the JSON, never
raised, so the parent always gets a structured answer.
"""

from __future__ import annotations

import hashlib
import io
import json
import sys
import traceback
from pathlib import Path

import numpy as np

from lpstgp.authoring.gates import withheld
from lpstgp.strategies import channel, gates
from lpstgp.strategies.api import Strategy
from lpstgp.strategies.loader import StrategyLoadError, load_file


def describe(strategy: Strategy) -> dict:
    return {
        "name": strategy.name,
        "domain": strategy.domain,
        "hypothesis": strategy.hypothesis,
        "definition": strategy.definition,
        "references": list(strategy.references),
        "novelty": strategy.novelty,
        "limitations": strategy.limitations,
        "rule_lookback": strategy.rule_lookback,
        "lookback": strategy.lookback,
        "signals": [
            {
                "name": s.name,
                "inputs": list(s.inputs),
                "params": {k: {"kind": p.kind, "default": p.default} for k, p in s.params.items()},
                "lookback": s.lookback_for(s.defaults),
                "description": s.description,
            }
            for s in strategy.signals
        ],
    }


def _hash(strategy: Strategy) -> str:
    digest = hashlib.sha256()
    for array in gates._strategy_fn(strategy)(*gates.synthetic_inputs()):
        digest.update(np.ascontiguousarray(array).tobytes())
    return digest.hexdigest()


def main(argv: list[str]) -> int:
    command, strategy_path, _inputs, out_path = argv[1:5]
    out = Path(out_path)
    # Secret and inputs first, before any LLM code is loaded (D-081).
    secret, inputs = channel.receive()
    # ``evaluate`` writes arrays to OUT; every JSON answer of it goes to OUT.error.json
    json_out = out.with_name(out.name + ".error.json") if command == "evaluate" else out

    def answer(result: dict) -> int:
        channel.write_signed(json_out, json.dumps(result, default=float).encode(), secret)
        return 0

    try:
        strategy = load_file(Path(strategy_path))
    except StrategyLoadError as exc:
        return answer({"ok": False, "stage": "load", "error": str(exc)})
    except Exception as exc:  # raised by the module's own top-level code, with data in memory
        return answer({"ok": False, "stage": "load", "error": withheld(exc)})
    try:
        if command == "describe":
            result = {"ok": True, "strategy": describe(strategy)}
        elif command == "gates":
            results = gates.behaviour(strategy)
            if inputs:
                results += gates.on_development_data(strategy, inputs)
            result = {"ok": True, "passed": gates.passed(results), "results": results}
        elif command == "hash":
            result = {"ok": True, "hash": _hash(strategy)}
        elif command == "evaluate":
            arrays = {}
            for name, (lp, lr, _start) in inputs.items():
                signals = strategy.compute(lp, lr)
                arrays[f"entry::{name}"], arrays[f"exit::{name}"] = strategy.entry_exit(signals)
                for sname, values in signals.items():
                    arrays[f"signal::{name}::{sname}"] = values
            buffer = io.BytesIO()
            np.savez(buffer, **arrays)
            channel.write_signed(out, buffer.getvalue(), secret)
            return 0
        else:
            result = {"ok": False, "stage": "command", "error": f"unknown command {command}"}
    except Exception as exc:  # the strategy's own code failed
        if inputs and command == "evaluate":  # it ran on data: no message (D-081)
            result = {"ok": False, "stage": command, "error": withheld(exc)}
        else:
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
