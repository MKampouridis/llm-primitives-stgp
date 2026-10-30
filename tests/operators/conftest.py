import numpy as np
import pytest

from lpstgp.gates.synthetic import garch_returns
from lpstgp.operators.registry import discover


@pytest.fixture(scope="session")
def ops():
    return {spec.name: spec for spec in discover().operators.values()}


@pytest.fixture(scope="session")
def terminals():
    return {spec.name: spec for spec in discover().terminals.values()}


@pytest.fixture(scope="session")
def returns():
    return garch_returns(1500, 11)


@pytest.fixture(scope="session")
def path(returns):
    return np.cumsum(returns)


def sample_bars(n: int, window: int, k: int = 6, seed: int = 0) -> list[int]:
    rng = np.random.default_rng(seed)
    return sorted(int(t) for t in rng.integers(window + 5, n, k))
