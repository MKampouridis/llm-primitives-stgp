"""Static source policy for LLM-written modules (checked before any code runs).

Used for whole strategies (WP2, ``strategy_api``) and for LLM-authored operators (WP3,
``operator_api``): the same rules, with the module's own contract as the only extra import.

Stricter than the WP1 operator policy (``lpstgp.gates.policy``), whose gaps it closes: numpy may
be imported only whole (``import numpy`` / ``import numpy as np``); no ``numpy.random`` or file
I/O under any alias or ``from`` import; no randomness via ``rvs``/``random_state``; no
reflection (``getattr``, ``vars``, private or dunder attributes) and no ``global``/``nonlocal``
state.
"""

from __future__ import annotations

import ast

COMMON_IMPORTS = (
    "__future__",
    "typing",
    "collections.abc",
    "math",
    "numpy",
    "scipy.special",
    "scipy.stats",
    "scipy.signal",
    "scipy.fft",
    "scipy.linalg",
    "scipy.optimize",
    "scipy.interpolate",
    "scipy.integrate",
    "scipy.spatial",
    "scipy.ndimage",
)
ALLOWED_IMPORTS = (*COMMON_IMPORTS, "strategy_api")
FORBIDDEN_NAMES = {
    "open",
    "eval",
    "exec",
    "compile",
    "__import__",
    "globals",
    "locals",
    "vars",
    "getattr",
    "setattr",
    "delattr",
    "input",
    "breakpoint",
    "exit",
    "quit",
    "help",
    "memoryview",
    "__builtins__",
}
FORBIDDEN_ATTRS = {
    "random",
    "load",
    "save",
    "savez",
    "savez_compressed",
    "fromfile",
    "tofile",
    "loadtxt",
    "savetxt",
    "genfromtxt",
    "memmap",
    "ctypeslib",
    "DataSource",
    "npyio",
    "open_memmap",
    "rvs",
    # file reading reachable through numpy without a forbidden import (D-074)
    "open",
    "fromregex",
    "fromtextfile",
    "recfromtxt",
    "recfromcsv",
}
FORBIDDEN_KEYWORDS = {"random_state", "seed", "rng"}


def _allowed(module: str, allowed: tuple[str, ...] = ALLOWED_IMPORTS) -> bool:
    return any(module == a or module.startswith(a + ".") for a in allowed)


def check_strategy_source(source: str) -> list[str]:
    """Problems with a strategy module's source; an empty list means admissible."""
    return check_llm_source(source, "strategy_api", "STRATEGY", "Strategy")


def check_llm_source(source: str, api: str, required: str, cls: str) -> list[str]:
    """Problems with an LLM-written module that imports contract ``api`` and defines ``required``."""
    allowed = (*COMMON_IMPORTS, api)
    try:
        tree = ast.parse(source)
        compile(source, "<llm module>", "exec")
    except SyntaxError as exc:
        return [f"does not compile: {exc}"]
    problems: list[str] = []
    for node in ast.walk(tree):
        line = getattr(node, "lineno", 0)
        if isinstance(node, ast.Import):
            for alias in node.names:
                if not _allowed(alias.name, allowed) or alias.name.startswith("numpy."):
                    problems.append(f"line {line}: import {alias.name} is not allowed")
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            if node.level or not _allowed(module, allowed):
                problems.append(f"line {line}: from {module or '.'} import is not allowed")
            elif module.split(".")[0] == "numpy":
                bad = [a.name for a in node.names if a.name in FORBIDDEN_ATTRS or a.name == "*"]
                if module != "numpy" or bad:
                    problems.append(
                        f"line {line}: from {module} import {bad or '...'} is not allowed"
                    )
        elif isinstance(node, ast.Name) and (
            node.id in FORBIDDEN_NAMES or (node.id.startswith("__") and node.id != "__name__")
        ):
            problems.append(f"line {line}: use of {node.id} is not allowed")
        elif isinstance(node, ast.Attribute) and (
            node.attr in FORBIDDEN_ATTRS or node.attr.startswith("_")
        ):  # private attributes (e.g. ``np.lib._datasource``) as well as dunders (D-074)
            problems.append(f"line {line}: attribute .{node.attr} is not allowed")
        elif isinstance(node, ast.keyword) and node.arg in FORBIDDEN_KEYWORDS:
            problems.append(f"line {line}: keyword {node.arg}= is not allowed (no randomness)")
        elif isinstance(node, ast.Global | ast.Nonlocal):
            problems.append(f"line {line}: global/nonlocal state is not allowed")
    defines = any(
        isinstance(node, ast.Assign)
        and any(getattr(t, "id", None) == required for t in node.targets)
        for node in tree.body
    )
    if not defines:
        problems.append(f"the module must define {required} = {cls}(...) at top level")
    return problems
