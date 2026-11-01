"""Protocol §6 calibration rules on hand-made run records."""

from lpstgp.calibration import budget_unit, choose_candidate, convergence_generation, lambda_check


def _gens(best):
    return [{"gen": g, "best": b} for g, b in enumerate(best)]


def _record(
    pop, tour, val, best, unique=100, requested=1000, library="seed", trades=5, turnover=10.0,
    ran=None,
):  # fmt: skip
    comps = {"trades": trades, "no_trade": trades < 2}
    if trades >= 1:  # as market_part: every rule that trades records its turnover
        comps["median_turnover"] = turnover
    return {
        "config": {"population": pop, "tournament": tour, "generations": ran or len(best) - 1},
        "generations": _gens(best),
        "hall_of_fame": [{"validation": {"fitness": val, "instruments": {"X": comps}}}],
        "selected": 0,
        "budget": {"unique_evaluations": unique, "requested_evaluations": requested},
        "library": {"name": library},
    }


def test_convergence_generation():
    assert convergence_generation(_gens([0.0, 0.5, 0.99, 1.0])) == 2
    assert convergence_generation(_gens([0.3, 0.3, 0.3])) == 0
    assert convergence_generation(_gens([0.0, 1.0, 1.0])) == 1


def test_choose_the_cheapest_candidate_within_tolerance():
    slow = [0.0] * 30 + [1.0] * 70  # converges at generation 30
    fast = [0.0] * 5 + [1.0] * 15  # converges at generation 5
    records = [_record(250, 3, 0.30, slow) for _ in range(3)] + [
        _record(1000, 5, 0.27, fast) for _ in range(3)
    ]
    out = choose_candidate(records, tolerance=0.05)
    assert (out["population"], out["tournament"]) == (250, 3)  # 250 x 31 < 1000 x 11
    assert out["generations"] == 30
    records = [_record(250, 3, 0.30, slow), _record(1000, 5, 0.20, fast)]
    assert choose_candidate(records)["population"] == 250  # 1000/5 is outside the tolerance


def test_budget_unit_and_lambda_rules():
    same = [_record(500, 5, 0, [0, 1], unique=200, library=a) for a in ("s2a", "s2c")]
    assert budget_unit(same)["unit"] == "requested"
    apart = [
        _record(500, 5, 0, [0, 1], unique=100, library="s2a"),
        _record(500, 5, 0, [0, 1], unique=300, library="s2c"),
    ]
    assert budget_unit(apart)["unit"] == "unique"
    quiet = [_record(500, 5, 0, [0, 1], trades=k) for k in range(4)]  # 25% never trade
    out = lambda_check(quiet)
    assert out["no_trade_share"] == 0.25  # the 1-trade rule is below minimum activity, not idle
    assert not out["no_trade_exceeded"]
    assert not out["raise_lambda_turnover"]
    idle = [_record(500, 5, 0, [0, 1], trades=0) for _ in range(2)] + quiet
    assert lambda_check(idle)["no_trade_exceeded"]
    assert not lambda_check(idle)["raise_lambda_turnover"]  # lambda_turnover cannot fix idleness
    busy = [_record(500, 5, 0, [0, 1], turnover=80.0) for _ in range(3)]
    assert lambda_check(busy)["raise_lambda_turnover"]


def test_rounded_generations_never_exceed_the_calibrated_run():
    late = [0.0] * 45 + [1.0] * 5  # converges at generation 45 of 49
    out = choose_candidate([_record(1000, 3, 0.3, late, ran=49) for _ in range(3)])
    assert out["generations"] == 49
    assert out["requested_evaluations"] == 50_000


def test_idle_rules_count_in_the_median_turnover():
    """Rules that never trade count with turnover 0 (D-049), pulling the median below 50."""
    busy = [_record(500, 5, 0, [0, 1], turnover=80.0) for _ in range(2)]
    idle = [_record(500, 5, 0, [0, 1], trades=0) for _ in range(3)]
    out = lambda_check(busy + idle)
    assert out["median_turnover"] == 0.0
    assert not out["raise_lambda_turnover"]
