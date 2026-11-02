"""The authoring contract (operator_api), the source policy and conversion to OperatorSpec."""

from pathlib import Path

import numpy as np
import pytest

from lpstgp import types as T
from lpstgp.authoring import loader
from lpstgp.authoring import operator_api as api
from lpstgp.operators.contract import Provenance

FIX = Path(__file__).parent / "fixtures"
PROV = Provenance(implemented_by="test", specified_by="test", date="2026-11-02")


def _impl(x, window):
    return np.asarray(x, dtype=float)


def _op(**overrides):
    fields = dict(
        name="t_op",
        summary="s",
        inputs=(api.Series,),
        params=(("window", api.Window),),
        output=api.Real,
        lookback=lambda window: window,
        missing="propagate",
        definition="d",
        references=("r",),
        impl=_impl,
        invariances=("scale",),
    )
    return api.Operator(**(fields | overrides))


def test_valid_operator_builds():
    assert _op().name == "t_op"


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"output": api.Bool}, "must be Real"),
        ({"invariances": ()}, "scale-invariant"),
        ({"inputs": (api.Path,), "invariances": ("scale",)}, "shift-invariant"),
        ({"params": (("length", api.Window),)}, "inputs first"),
        ({"lookback": lambda window: 600}, "lookback"),
        ({"missing": "ignore"}, "missing"),
        ({"references": ()}, "references"),
        ({"name": "BadName"}, "snake_case"),
    ],
)
def test_contract_rejects(overrides, message):
    with pytest.raises(ValueError, match=message):
        _op(**overrides)


def test_param_kinds_are_validated():
    with pytest.raises(ValueError, match="increasing"):
        api.param_kind("Order2", (5, 3), "x")
    with pytest.raises(ValueError, match="all int or all float"):
        api.param_kind("Mixed", (1, 2.0), "x")
    with pytest.raises(ValueError, match="standard kind"):
        api.param_kind("Window", (1, 2), "x")


def test_standard_kinds_match_the_gp_grids():
    for kind in api.STANDARD_KINDS:
        assert tuple(loader.STANDARD[kind.name].grid) == kind.grid


def test_session_contract_file_reveals_no_project_code_or_arm6_kinds():
    text = Path(api.__file__).read_text()
    assert "lpstgp" not in text
    for name in ("Order", "Levels", "Kmax", "Moment", "QEnt", "Alpha", "Epsilon", "PVar", "WLevel"):
        assert f'"{name}"' not in text
        assert f"{name} =" not in text


def test_policy_rejects_project_imports_and_io():
    assert loader.check_source("from lpstgp.types import Real\nOPERATOR = 1\n")
    assert loader.check_source("import os\nOPERATOR = 1\n")
    assert loader.check_source("import numpy as np\n") == [
        "the module must define OPERATOR = Operator(...) at top level"
    ]
    assert loader.check_source("from operator_api import Operator\nOPERATOR = 1\n") == []


def test_loaded_spec_uses_project_types_and_host_provenance():
    spec = loader.load_spec(FIX / "toy_operator.py", "spectral", PROV)
    assert spec.inputs == (T.Series,)
    assert spec.output is T.Real
    assert spec.params[0].kind is T.Window
    assert spec.domain == "spectral"
    assert spec.provenance == PROV
    assert spec.version == 1
    x = np.random.default_rng(0).standard_normal(200)
    np.testing.assert_array_equal(spec(x, window=20)[19:], spec.impl(x, 20)[19:])


def test_declared_kind_is_shared_and_its_grid_is_fixed():
    spec = loader.load_spec(FIX / "new_kind.py", "information_theory", PROV)
    kind = spec.params[0].kind
    assert kind.__name__ == "LlmPower"
    assert kind.grid == (0.5, 2.0)
    assert issubclass(kind, T.Param)
    again = loader.load_spec(FIX / "new_kind.py", "information_theory", PROV)
    assert again.params[0].kind is kind
    with pytest.raises(loader.OperatorLoadError, match="another name"):
        loader.param_class(api.ParamKind("Power", (1.0, 3.0), "other"))


def test_bad_import_is_a_load_error():
    with pytest.raises(loader.OperatorLoadError, match="import os"):
        loader.load_operator(FIX / "bad_import.py")
