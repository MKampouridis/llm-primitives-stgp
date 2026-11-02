"""Test fixture: a mean that is not scale-free but claims to be."""

from operator_api import Operator, Real, Series, Window, trailing_windows


def level(x, window):
    return trailing_windows(x, window).mean(axis=1) * 1000.0


OPERATOR = Operator(
    name="toy_level",
    summary="Rolling mean (not scale-free).",
    inputs=(Series,),
    params=(("window", Window),),
    output=Real,
    lookback=lambda window: window,
    missing="propagate",
    definition=r"\bar x",
    references=("none",),
    impl=level,
    invariances=("scale",),
)
