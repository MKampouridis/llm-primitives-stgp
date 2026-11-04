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
# Introspection that reaches builtins, frames, the process or the interpreter without a
# forbidden name (D-081: ``inspect.currentframe().f_builtins`` got past the first policy).
INTROSPECTION_ATTRS = {
    "f_builtins", "f_globals", "f_locals", "f_back", "f_code", "f_trace", "f_lineno",
    "gi_frame", "gi_code", "cr_frame", "cr_code", "ag_frame", "ag_code", "tb_frame", "tb_next",
    "currentframe", "getmembers", "getsource", "getfile", "getmodule",
    "modules", "argv", "environ", "stdin", "stdout", "stderr", "system", "popen", "spawn",
    "builtins", "inspect", "importlib", "import_module", "loader", "spec", "func_globals",
    "co_consts", "co_code", "mro", "subclasses",
    # modules re-exported by an allowed library that reach files, processes or the interpreter
    "os", "sys", "subprocess", "shutil", "pathlib", "ctypes", "pickle", "socket", "f2py",
    "distutils", "testing", "compat", "io",
    # string evaluation: ``get_type_hints`` evaluates annotations such as
    # ``"__import__('builtins').open"`` (D-089, ChatGPT's re-check of D-088)
    "get_type_hints", "ForwardRef", "evaluate_forward_ref", "get_annotations", "TypeAliasType",
}  # fmt: skip
# The only names an LLM module may take from ``typing`` and ``collections.abc``, by ``from``
# import or by attribute: annotation constructs and abstract base classes, none of which evaluates
# a string or reaches the interpreter (D-089). Everything else of these two modules is refused.
EXPLICIT_EXPORTS = {
    "typing": frozenset({
        "Any", "Callable", "ClassVar", "Dict", "Final", "FrozenSet", "Iterable", "Iterator",
        "List", "Literal", "Mapping", "MutableMapping", "MutableSequence", "Optional",
        "Sequence", "Set", "Tuple", "TypeAlias", "Union",
    }),
    "collections.abc": frozenset({
        "Callable", "Collection", "Container", "Hashable", "ItemsView", "Iterable", "Iterator",
        "KeysView", "Mapping", "MappingView", "MutableMapping", "MutableSequence", "MutableSet",
        "Reversible", "Sequence", "Set", "Sized", "ValuesView",
    }),
}  # fmt: skip
CONTRACT_MODULES = {
    "strategy_api": "lpstgp.strategies.api",
    "operator_api": "lpstgp.authoring.operator_api",
}


def contract_names(api: str) -> frozenset[str]:
    """The names a module may import from its contract: the contract's own public classes,
    functions and constants, never a module or a name it imported itself (``inspect``, ``np``,
    ``dataclass``; D-081)."""
    import importlib
    import inspect as _inspect

    module = importlib.import_module(CONTRACT_MODULES[api])
    out = set()
    for name, value in vars(module).items():
        if name.startswith("_") or _inspect.ismodule(value):
            continue
        owner = getattr(value, "__module__", None)
        if owner is None or owner == module.__name__ or not callable(value):
            out.add(name)
    return frozenset(out)


def _allowed(module: str, allowed: tuple[str, ...] = ALLOWED_IMPORTS) -> bool:
    return any(module == a or module.startswith(a + ".") for a in allowed)


def _bad_name(name: str) -> bool:
    """A name an LLM module may never bind or import: private or dunder (``__builtins__``),
    or one of the forbidden names, attributes or introspection hooks."""
    return (
        name == "*"
        or name.startswith("_")
        or name in FORBIDDEN_NAMES
        or name in FORBIDDEN_ATTRS
        or name in INTROSPECTION_ATTRS
    )


def _importable(module: str, name: str, allowed: tuple[str, ...]) -> bool:
    """``from module import name`` is allowed only for a public name the trusted library really
    has, and a module only if it is itself an allowed import (D-088: an allowlist, not a
    blocklist; ``from numpy import __builtins__`` reached ``open``)."""
    import importlib
    import types

    if module == "__future__":
        return name == "annotations"
    if module in EXPLICIT_EXPORTS:
        return name in EXPLICIT_EXPORTS[module]
    if _bad_name(name):
        return False
    try:
        value = getattr(importlib.import_module(module), name)
    except (ImportError, AttributeError):
        try:  # a submodule not yet imported as an attribute
            value = importlib.import_module(f"{module}.{name}")
        except ImportError:
            return False
    if isinstance(value, types.ModuleType):
        return _allowed(value.__name__, allowed) and not any(
            _bad_name(part) for part in value.__name__.split(".")
        )
    return True


def _dotted(node: ast.AST) -> str | None:
    """``a.b.c`` for an attribute chain on a plain name (the outermost node only)."""
    parts = []
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
    if not parts or not isinstance(node, ast.Name):
        return None
    return ".".join([node.id, *reversed(parts)])


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
    explicit = {  # local name -> module: ``import typing``, ``import collections.abc as c``
        alias.asname or alias.name: alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
        if alias.name in EXPLICIT_EXPORTS
    }
    packages = {  # ``import scipy.stats`` binds ``scipy``: only its allowed submodules follow
        alias.name.split(".")[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
        if alias.asname is None and "." in alias.name
    } - set(allowed)
    for node in ast.walk(tree):
        line = getattr(node, "lineno", 0)
        dotted = _dotted(node)
        for local, module in explicit.items():
            if dotted and dotted.startswith(local + "."):
                name = dotted[len(local) + 1 :].split(".")[0]
                if name not in EXPLICIT_EXPORTS[module]:
                    problems.append(f"line {line}: {module}.{name} is not allowed")
        if dotted and dotted.split(".")[0] in packages:
            parts = dotted.split(".")
            heads = (".".join(parts[:k]) for k in range(2, len(parts) + 1))
            if not any(_allowed(h, allowed) for h in heads) and not any(
                a.startswith(dotted + ".") for a in allowed
            ):
                problems.append(f"line {line}: {dotted} is not an allowed module")
        if isinstance(node, ast.Import):
            for alias in node.names:
                if (
                    not _allowed(alias.name, allowed)
                    or alias.name.startswith("numpy.")
                    or alias.name == api  # the contract only through ``from api import name``
                    or (alias.asname is not None and _bad_name(alias.asname))
                ):
                    problems.append(f"line {line}: import {alias.name} is not allowed")
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            if node.level or not _allowed(module, allowed):
                problems.append(f"line {line}: from {module or '.'} import is not allowed")
            elif module == api:
                extra = [a.name for a in node.names if a.name not in contract_names(api)]
                if extra:
                    problems.append(
                        f"line {line}: {', '.join(extra)} is not part of {api}'s contract"
                    )
            elif module.split(".")[0] == "numpy" and module != "numpy":
                problems.append(f"line {line}: from {module} import ... is not allowed")
            else:  # every other allowed library: public names it really has (D-088)
                bad = [
                    a.name
                    for a in node.names
                    if not _importable(module, a.name, allowed)
                    or (a.asname is not None and _bad_name(a.asname))
                ]
                if bad:
                    problems.append(
                        f"line {line}: from {module} import {', '.join(bad)} is not allowed"
                    )
        elif isinstance(node, ast.Name) and (
            node.id in FORBIDDEN_NAMES or (node.id.startswith("__") and node.id != "__name__")
        ):
            problems.append(f"line {line}: use of {node.id} is not allowed")
        elif isinstance(node, ast.Attribute) and (
            node.attr in FORBIDDEN_ATTRS
            or node.attr in INTROSPECTION_ATTRS
            or node.attr.startswith("_")
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
