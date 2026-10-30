"""Interpret STGP trees on one instrument's sandbox arrays, memoising subtree outputs.

Subtrees are keyed by their node-name sequence (parameters included), so a subtree shared by many
individuals is computed once per run. The cache is per evaluator, i.e. per (run, stage,
instrument): outputs are never shared across periods, stages or horizons, and never sliced from a
longer horizon. Cached arrays are read-only. Per-operator compute time is recorded for the
projection cost model.
"""

from __future__ import annotations

import time
from collections import OrderedDict, defaultdict
from collections.abc import Sequence

import numpy as np

from lpstgp.gp.pset import PrimitiveLibrary


class SubtreeCache:
    """Least-recently-used cache of arrays with a cap on total bytes."""

    def __init__(self, max_bytes: int) -> None:
        self.max_bytes = max_bytes
        self.bytes = 0
        self.hits = 0
        self.misses = 0
        self._items: OrderedDict[tuple, np.ndarray] = OrderedDict()

    def get(self, key: tuple) -> np.ndarray | None:
        value = self._items.get(key)
        if value is None:
            self.misses += 1
            return None
        self._items.move_to_end(key)
        self.hits += 1
        return value

    def put(self, key: tuple, value: np.ndarray) -> None:
        if key in self._items:
            return
        self._items[key] = value
        self.bytes += value.nbytes
        while self.bytes > self.max_bytes and self._items:
            _, old = self._items.popitem(last=False)
            self.bytes -= old.nbytes

    def __len__(self) -> int:
        return len(self._items)


class TreeEvaluator:
    def __init__(
        self,
        lib: PrimitiveLibrary,
        log_price: np.ndarray,
        log_return: np.ndarray,
        cache_bytes: int = 256 * 2**20,
    ) -> None:
        self.lib = lib
        self.log_price = np.asarray(log_price, dtype=np.float64)
        self.log_return = np.asarray(log_return, dtype=np.float64)
        self.cache = SubtreeCache(cache_bytes)
        self.op_calls: dict[str, int] = defaultdict(int)
        self.op_seconds: dict[str, float] = defaultdict(float)

    def __call__(self, tree: Sequence) -> np.ndarray:
        return self._value(tree, 0)

    def _value(self, tree: Sequence, i: int):
        node = tree[i]
        if node.arity == 0:
            if node.name in self.lib.params:
                return self.lib.params[node.name][1]
            key = (node.name,)
            hit = self.cache.get(key)
            if hit is not None:
                return hit
            start = time.perf_counter()
            out = np.asarray(
                self.lib.terminals[node.name](self.log_price, self.log_return), dtype=np.float64
            )
            self._account(node.name, start)
            out.setflags(write=False)
            self.cache.put(key, out)
            return out
        span = tree.searchSubtree(i)
        key = tuple(n.name for n in tree[span])
        hit = self.cache.get(key)
        if hit is not None:
            return hit
        spec = self.lib.operators[node.name]
        args = []
        j = i + 1
        for _ in range(node.arity):
            stop = tree.searchSubtree(j).stop
            args.append(self._value(tree, j))
            j = stop
        n_in = len(spec.inputs)
        params = {p.name: value for p, value in zip(spec.params, args[n_in:], strict=True)}
        start = time.perf_counter()
        out = np.asarray(spec.impl(*args[:n_in], **params), dtype=np.float64)
        self._account(node.name, start)
        out.setflags(write=False)
        self.cache.put(key, out)
        return out

    def _account(self, name: str, start: float) -> None:
        self.op_calls[name] += 1
        self.op_seconds[name] += time.perf_counter() - start
