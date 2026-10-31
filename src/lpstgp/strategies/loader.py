"""Load a strategy module after the source policy has passed.

Strategy files import the contract as ``strategy_api`` (the name they see in their session
folder); here that name is bound to :mod:`lpstgp.strategies.api`, so a frozen file is executed
exactly as it was written.
"""

from __future__ import annotations

import hashlib
import importlib.util
import sys
from pathlib import Path

from lpstgp.strategies import api
from lpstgp.strategies.api import Strategy
from lpstgp.strategies.policy import check_strategy_source


class StrategyLoadError(ValueError):
    """The module is inadmissible or does not define a valid ``STRATEGY``."""


def source_hash(source: str) -> str:
    return hashlib.sha256(source.encode()).hexdigest()


def load_file(path: Path, module_name: str | None = None) -> Strategy:
    path = Path(path)
    source = path.read_text(encoding="utf-8")
    problems = check_strategy_source(source)
    if problems:
        raise StrategyLoadError("; ".join(problems))
    sys.modules.setdefault("strategy_api", api)
    name = module_name or f"lpstgp_strategy_{source_hash(source)[:16]}"
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)
    except Exception as exc:  # report any failure of the LLM's module as a load error
        raise StrategyLoadError(f"{type(exc).__name__}: {exc}") from exc
    strategy = getattr(module, "STRATEGY", None)
    if not isinstance(strategy, Strategy):
        raise StrategyLoadError("STRATEGY is not a strategy_api.Strategy")
    return strategy
