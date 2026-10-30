"""Static source policy for operator code (gate 1, with compilation).

Operator modules may import only numerical libraries and the operator contract; they may not do
I/O, reach the data layer, evaluate code, use global randomness, or ask numba for ``fastmath``
(which may drop NaN checks) or ``parallel`` (order-dependent reductions). Modelling packages
(GP, backtest) may not import the data layer either.
"""

from __future__ import annotations

import ast

ALLOWED_OPERATOR_IMPORTS = (
    "__future__",
    "math",
    "numpy",
    "numba",
    "scipy.special",
    "scipy.stats",
    "scipy.signal",
    "scipy.fft",
    "scipy.linalg",
    "lpstgp.types",
    "lpstgp.operators",
)
FORBIDDEN_CALLS = {
    "open",
    "eval",
    "exec",
    "compile",
    "__import__",
    "globals",
    "input",
    "breakpoint",
}
FORBIDDEN_NUMPY_ATTRS = {
    "random",
    "load",
    "save",
    "savez",
    "fromfile",
    "tofile",
    "loadtxt",
    "genfromtxt",
}
DATA_LAYER = ("lpstgp.data", "lpstgp.sandbox", "lpstgp.config")
IO_MODULES = (
    "os",
    "sys",
    "io",
    "pathlib",
    "shutil",
    "subprocess",
    "socket",
    "pickle",
    "requests",
    "urllib",
)


def _module_allowed(module: str, allowed: tuple[str, ...]) -> bool:
    return any(module == a or module.startswith(a + ".") for a in allowed)


def _imports(tree: ast.AST) -> list[tuple[int, str]]:
    found = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found.extend((node.lineno, alias.name) for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            found.append((node.lineno, node.module or ""))
    return found


def check_operator_source(source: str) -> list[str]:
    """Problems with an operator module's source (empty list = admissible)."""
    try:
        tree = ast.parse(source)
        compile(source, "<operator>", "exec")
    except SyntaxError as exc:
        return [f"does not compile: {exc}"]
    problems = []
    for line, module in _imports(tree):
        if not _module_allowed(module, ALLOWED_OPERATOR_IMPORTS):
            problems.append(f"line {line}: import of {module!r} is not allowed in operator code")
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id in FORBIDDEN_CALLS
        ):
            problems.append(f"line {node.lineno}: call to {node.func.id}() is not allowed")
        if (
            isinstance(node, ast.Attribute)
            and isinstance(node.value, ast.Name)
            and node.value.id in ("np", "numpy")
            and node.attr in FORBIDDEN_NUMPY_ATTRS
        ):
            problems.append(
                f"line {node.lineno}: numpy.{node.attr} is not allowed in operator code"
            )
        if (
            isinstance(node, ast.keyword)
            and node.arg in ("fastmath", "parallel")
            and not (isinstance(node.value, ast.Constant) and node.value.value is False)
        ):
            problems.append(f"line {node.value.lineno}: numba {node.arg}= is not allowed")
    return problems


def check_modelling_source(source: str) -> list[str]:
    """GP/backtest modules: no data-layer imports and no I/O modules."""
    tree = ast.parse(source)
    problems = []
    for line, module in _imports(tree):
        if _module_allowed(module, DATA_LAYER) or _module_allowed(module, IO_MODULES):
            problems.append(f"line {line}: modelling code may not import {module!r}")
    return problems
