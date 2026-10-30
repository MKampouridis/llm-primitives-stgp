"""Static policy: operator code cannot do I/O or reach data; modelling code cannot import the data layer."""

from pathlib import Path

import pytest

from lpstgp.gates import policy
from lpstgp.operators.registry import PACKAGE_ROOT

MODELLING_PACKAGES = ("operators", "gp", "backtest", "gates")
# Discovery and the version lock read source files; they are infrastructure, never called by operators.
INFRASTRUCTURE = {"operators/registry.py"}


def modelling_files():
    files = []
    for package in MODELLING_PACKAGES:
        root = PACKAGE_ROOT / package
        if root.is_dir():
            files.extend(sorted(root.rglob("*.py")))
    return [f for f in files if str(f.relative_to(PACKAGE_ROOT)) not in INFRASTRUCTURE]


@pytest.mark.parametrize("path", modelling_files(), ids=lambda p: str(p.relative_to(PACKAGE_ROOT)))
def test_modelling_code_does_not_import_the_data_layer(path: Path):
    assert policy.check_modelling_source(path.read_text(encoding="utf-8")) == []


@pytest.mark.parametrize(
    "snippet",
    [
        "import os",
        "from pathlib import Path",
        "from lpstgp.data.store import DataStore",
        "import pandas as pd",
        "x = open('prices.csv')",
        "y = eval('1+1')",
        "import numpy as np\nz = np.random.normal()",
        "import numpy as np\nw = np.load('a.npy')",
        "from numba import njit\n@njit(fastmath=True)\ndef f(x):\n    return x",
        "from numba import njit\n@njit(parallel=True)\ndef f(x):\n    return x",
    ],
)
def test_operator_policy_rejects(snippet):
    assert policy.check_operator_source(snippet)


def test_operator_policy_accepts_numerical_code():
    source = (
        "import numpy as np\nfrom numba import njit\nfrom scipy.special import gammaln\n"
        "from lpstgp.types import Real\nfrom lpstgp.operators._kernels import rolling_quantile\n"
        "@njit(cache=True)\ndef f(x):\n    return np.sort(x)\n"
    )
    assert policy.check_operator_source(source) == []


def test_operator_policy_rejects_syntax_errors():
    assert policy.check_operator_source("def broken(:\n")
