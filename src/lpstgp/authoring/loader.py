"""Load an LLM-authored operator module and convert it to an :class:`OperatorSpec`.

Operator files import their contract as ``operator_api`` (the self-contained file the session
sees); here that name is bound to :mod:`lpstgp.authoring.operator_api`, so a frozen file runs
exactly as written. The source policy (the one for LLM-written strategies, with ``operator_api``
as the only extra import) is checked before the module is executed.

Conversion maps the contract's types to :mod:`lpstgp.types` and its parameter kinds to
:class:`lpstgp.types.Param` subclasses: the five standard kinds are the existing ones; a kind
declared by the LLM becomes a class named ``Llm<Name>``, shared by every operator that declares
the same name and grid (a different grid under the same name is an error).
"""

from __future__ import annotations

import hashlib
import importlib.util
import sys
from pathlib import Path as FilePath

from lpstgp import types as T
from lpstgp.authoring import operator_api as api
from lpstgp.operators.contract import Memory, Missing, OperatorSpec, ParamSpec, Provenance
from lpstgp.strategies.policy import check_llm_source

STANDARD = {
    "Window": T.Window,
    "LongWindow": T.LongWindow,
    "Lag": T.Lag,
    "Quantile": T.Quantile,
    "KSigma": T.KSigma,
}
SEM = {cls: getattr(T, cls.__name__) for cls in api.SEM_TYPES}
MISSING = {"propagate": Missing.PROPAGATE, "min_valid": Missing.MIN_VALID}
MISSING["elementwise"] = Missing.ELEMENTWISE
_DECLARED: dict[str, type[T.Param]] = {}


class OperatorLoadError(ValueError):
    """The module is inadmissible or does not define a valid ``OPERATOR``."""


def source_hash(source: str) -> str:
    return hashlib.sha256(source.encode()).hexdigest()


def check_source(source: str) -> list[str]:
    return check_llm_source(source, "operator_api", "OPERATOR", "Operator")


def load_operator(path: FilePath) -> api.Operator:
    """Execute an operator file (after the source policy) and return its ``OPERATOR``."""
    path = FilePath(path)
    source = path.read_text(encoding="utf-8")
    problems = check_source(source)
    if problems:
        raise OperatorLoadError("; ".join(problems))
    sys.modules.setdefault("operator_api", api)
    name = f"lpstgp_authored_{source_hash(source)[:16]}"
    module_spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(module_spec)
    try:
        module_spec.loader.exec_module(module)
    except Exception as exc:  # any failure of the LLM's module is a load error
        raise OperatorLoadError(f"{type(exc).__name__}: {exc}") from exc
    operator = getattr(module, "OPERATOR", None)
    if not isinstance(operator, api.Operator):
        raise OperatorLoadError("OPERATOR is not an operator_api.Operator")
    return operator


def param_class(kind: api.ParamKind) -> type[T.Param]:
    """The :class:`lpstgp.types.Param` subclass of a contract parameter kind."""
    if kind.name in STANDARD:
        standard = STANDARD[kind.name]
        if tuple(standard.grid) != tuple(kind.grid):
            raise OperatorLoadError(f"{kind.name}: a standard kind's grid cannot be changed")
        return standard
    cls_name = f"Llm{kind.name}"
    existing = _DECLARED.get(cls_name)
    if existing is not None:
        if tuple(existing.grid) != tuple(kind.grid):
            raise OperatorLoadError(
                f"parameter kind {kind.name} is declared with grid {existing.grid} elsewhere; "
                f"use the same grid or another name"
            )
        return existing
    cls = type(cls_name, (T.Param,), {"grid": tuple(kind.grid), "description": kind.description})
    _DECLARED[cls_name] = cls
    return cls


def to_spec(
    op: api.Operator, domain: str, provenance: Provenance, version: int = 1
) -> OperatorSpec:
    """The registry contract of an authored operator (domain and provenance are the host's)."""
    try:
        return OperatorSpec(
            name=op.name,
            version=version,
            domain=domain,
            summary=op.summary,
            inputs=tuple(SEM[t] for t in op.inputs),
            params=tuple(ParamSpec(p, param_class(k)) for p, k in op.params),
            output=SEM[op.output],
            lookback=op.lookback,
            missing=MISSING[op.missing],
            definition=op.definition,
            references=tuple(op.references),
            reference_test="none: LLM-authored, admitted by the gates only (D-062)",
            impl=op.impl,
            min_valid=op.min_valid,
            invariances=tuple(op.invariances),
            memory=Memory.FINITE,
            provenance=provenance,
        )
    except ValueError as exc:
        raise OperatorLoadError(str(exc)) from exc


def load_spec(path: FilePath, domain: str, provenance: Provenance) -> OperatorSpec:
    return to_spec(load_operator(path), domain, provenance)
