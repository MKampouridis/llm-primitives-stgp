"""Arm 5's proposals: entry/exit rule pairs over the fixed library, parsed and type-checked (§4.2).

The session writes ``rules.json``: a list of objects ``{"entry": "<tree>", "exit": "<tree>"}`` in
the printed form of the elite trees it was shown. Each pair is parsed against the typed primitive
set and checked against the tree limits (depth, nodes, lookback); a pair that fails is discarded.
At most ``MAX_RULES`` pairs are kept, in the session's order; duplicates count once.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from lpstgp.gp.pset import PrimitiveLibrary
from lpstgp.gp.variation import Limits, valid
from lpstgp.runner import parse_tree

MAX_RULES = 25  # of the 250 initial individuals (D-067; fixed at protocol 1.0, D-073)
RULES_FILE = "rules.json"
ALLOWED_KEYS = {"entry", "exit", "note"}


def check_rules(
    path: Path, lib: PrimitiveLibrary, limits: Limits
) -> tuple[list[tuple[str, str]], list[str]]:
    """The admitted pairs (canonical printed form) and one problem line per discarded pair."""
    if not path.exists():
        return [], [f"{path.name} does not exist"]
    try:
        items = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return [], [f"{path.name} is not valid JSON: {exc}"]
    if not isinstance(items, list):
        return [], [f"{path.name} must hold a JSON list of {{entry, exit}} objects"]
    admitted: list[tuple[str, str]] = []
    problems: list[str] = []
    for k, item in enumerate(items, 1):
        if len(admitted) >= MAX_RULES:
            problems.append(f"pair {k}: beyond the first {MAX_RULES} admitted pairs; ignored")
            continue
        if not isinstance(item, dict) or not {"entry", "exit"} <= set(item) <= ALLOWED_KEYS:
            problems.append(f"pair {k}: needs exactly the keys entry and exit (and optional note)")
            continue
        trees = []
        for side in ("entry", "exit"):
            try:
                tree = parse_tree(str(item[side]), lib)
            except Exception as exc:  # any parse or type error discards the pair
                problems.append(f"pair {k} {side}: {type(exc).__name__}: {str(exc)[:200]}")
                break
            if not valid(tree, lib, limits):
                problems.append(
                    f"pair {k} {side}: exceeds the limits (depth {limits.max_depth}, nodes "
                    f"{limits.max_nodes}, lookback {limits.lookback_max})"
                )
                break
            trees.append(str(tree))
        else:
            pair = (trees[0], trees[1])
            if pair in admitted:
                problems.append(f"pair {k}: duplicate of an earlier pair")
            else:
                admitted.append(pair)
    return admitted, problems


def report(admitted: Sequence[tuple[str, str]], problems: Sequence[str]) -> dict[str, Any]:
    return {"admitted": len(admitted), "max": MAX_RULES, "problems": list(problems)[:40]}
