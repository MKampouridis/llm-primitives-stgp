"""Soft-spin order-parameter fluctuation relaxation (statistical physics).

Daily returns are mapped to bounded "soft" Ising spins by dividing them by the local
temperature (superstatistics) and passing them through tanh. The 10-bar block magnetization
is the order parameter. Its equilibrium value and its equilibrium fluctuation scale (the
empirical block susceptibility) come from a trailing 120-bar ensemble. The strategy goes long
after a large spontaneous fluctuation of the order parameter against equilibrium and leaves
once the fluctuation has partly relaxed.
"""

import numpy as np

from strategy_api import LongWindow, Signal, Strategy, Window, trailing_windows


def _soft_spins(log_return: np.ndarray, temp_window: int) -> np.ndarray:
    """s_t = tanh(r_t / T_t), T_t = RMS return over the trailing ``temp_window`` bars."""
    r = np.nan_to_num(np.asarray(log_return, dtype=np.float64), nan=0.0)
    rows = trailing_windows(r, temp_window)
    temp = np.sqrt(np.mean(rows * rows, axis=1))
    with np.errstate(invalid="ignore", divide="ignore"):
        s = np.tanh(r / temp)
    s[~np.isfinite(s)] = np.nan
    return s


def _magnetization_fluctuation(log_return, *, window, temp_window, long_window):
    """zeta_t = (m_t - <m>_L) / std_L(m): the block magnetization m_t (mean soft spin over
    ``window`` bars) in units of its own equilibrium fluctuation scale over ``long_window``."""
    s = _soft_spins(log_return, temp_window)
    m = np.mean(trailing_windows(s, window), axis=1)
    ens = trailing_windows(m, long_window)
    mu = np.mean(ens, axis=1)
    sd = np.std(ens, axis=1, ddof=1)
    with np.errstate(invalid="ignore", divide="ignore"):
        z = (m - mu) / sd
    z[~np.isfinite(z)] = np.nan
    return z


magnetization_fluctuation = Signal(
    name="magnetization_fluctuation",
    fn=_magnetization_fluctuation,
    inputs=("log_return",),
    params={
        "window": Window(10),
        "temp_window": Window(20),
        "long_window": LongWindow(120),
    },
    lookback=lambda window, temp_window, long_window: window + temp_window + long_window,
    description=(
        "Block magnetization of temperature-scaled soft spins tanh(r/T), standardised by "
        "its equilibrium mean and fluctuation (susceptibility) over a trailing ensemble."
    ),
)

ENTRY_SIGMA = -1.0  # spontaneous fluctuation of at least one equilibrium std against <m>
EXIT_SIGMA = -0.5  # fluctuation has relaxed back to within half a std


def rule(signals):
    z = signals["magnetization_fluctuation"]
    ok = np.isfinite(z)
    entry = np.where(ok, (z < ENTRY_SIGMA).astype(float), np.nan)
    exit_ = np.where(ok, (z > EXIT_SIGMA).astype(float), np.nan)
    return entry, exit_


STRATEGY = Strategy(
    name="soft_spin_fluctuation_relaxation",
    domain="statistical_physics",
    hypothesis=(
        "Treat the sequence of daily returns as a chain of soft Ising spins at a slowly "
        "varying temperature. Superstatistics: returns are locally Gaussian with a "
        "fluctuating temperature, so each return is scaled by the local temperature before "
        "being squashed into a bounded spin. The block magnetization over two weeks is the "
        "order parameter of the 'market mood'. Its statistics over the previous six months "
        "define the current equilibrium state: the mean is the field-polarised equilibrium "
        "magnetization, and the dispersion is the equilibrium fluctuation scale, i.e. the "
        "empirical susceptibility. Onsager's regression hypothesis and the "
        "fluctuation-dissipation theorem say that spontaneous fluctuations away from "
        "equilibrium decay on the same time scale and the same way as an externally imposed "
        "perturbation. If markets have a restoring response at the 1-2 week scale "
        "(effective anti-ferromagnetic coupling between successive blocks of spins), a large "
        "collective down-fluctuation of the order parameter is partly undone by subsequent up "
        "spins, not merely diluted. Being long only during the fast initial part of this "
        "relaxation, after a fluctuation larger than one equilibrium standard deviation and "
        "until it has relaxed to within half a standard deviation, harvests the restoring "
        "response with low exposure. Because the scale comes from each instrument's own "
        "equilibrium, the rule transfers unchanged across asset classes and volatility regimes."
    ),
    definition=(
        "Inputs: daily log returns r_t.\n"
        "1. Local temperature (superstatistics): T_t = sqrt( (1/20) * sum_{k=0..19} r_{t-k}^2 ).\n"
        "2. Soft spins (bounded, tail-robust): s_t = tanh(r_t / T_t), in (-1, 1).\n"
        "3. Order parameter (block magnetization, W = 10): m_t = (1/W) * sum_{k=0..W-1} s_{t-k}.\n"
        "4. Equilibrium ensemble over the trailing L = 120 values of m:\n"
        "   <m>_t = mean(m_{t-L+1..t}),   chi_t = std(m_{t-L+1..t}) (block susceptibility,\n"
        "   W * Var(m) = chi * T in the fluctuation-dissipation sense).\n"
        "5. Fluctuation in equilibrium units: zeta_t = (m_t - <m>_t) / chi_t.\n"
        "Rule: entry when zeta_t < -1 (spontaneous fluctuation against equilibrium of at least "
        "one equilibrium std); exit when zeta_t > -0.5 (fluctuation relaxed to within half a "
        "std). The position is long from entry to exit. Because the down-spins that caused "
        "the fluctuation leave the W-bar block after at most 10 bars, the exit is reached "
        "either by restoring up-spins (a profitable relaxation) or by natural decay of the "
        "block. So holding periods are short (typically under two weeks) without any "
        "explicit stop. "
        "Total lookback: 20 + 10 + 120 = 150 bars."
    ),
    references=(
        "Glauber, R. J. (1963). Time-dependent statistics of the Ising model. Journal of "
        "Mathematical Physics 4(2), 294-307.",
        "Onsager, L. (1931). Reciprocal relations in irreversible processes. I. Physical "
        "Review 37, 405-426; II. Physical Review 38, 2265-2279.",
        "Kubo, R. (1966). The fluctuation-dissipation theorem. Reports on Progress in "
        "Physics 29(1), 255-284.",
        "Beck, C. & Cohen, E. G. D. (2003). Superstatistics. Physica A 322, 267-275.",
        "Chaikin, P. M. & Lubensky, T. C. (1995). Principles of Condensed Matter Physics. "
        "Cambridge University Press (soft-spin / Landau-Ginzburg order parameters, "
        "susceptibility and fluctuations).",
        "Bornholdt, S. (2001). Expectation bubbles in a spin model of markets: intermittency "
        "from frustration across scales. International Journal of Modern Physics C 12(5), "
        "667-674.",
        "Sornette, D. (2014). Physics and financial economics (1776-2014): puzzles, Ising and "
        "agent-based models. Reports on Progress in Physics 77(6), 062001.",
        "Bouchaud, J.-P. & Potters, M. (2003). Theory of Financial Risk and Derivative "
        "Pricing: From Statistical Physics to Risk Management, 2nd ed. Cambridge University "
        "Press.",
    ),
    rule=rule,
    rule_lookback=0,
    signals=(magnetization_fluctuation,),
    novelty=(
        "Unlike the Kramers-Moyal strategy, no drift or diffusion field is estimated as a "
        "function of a price-displacement state. Unlike the fluctuation-theorem strategy, no "
        "entropy production, time-reversal asymmetry or steady-state current is measured. "
        "The state variable lives in spin space: the magnetization of temperature-scaled, "
        "bounded soft spins, which is insensitive to single outlier returns. Its fluctuation "
        "is measured in units of the instrument's own equilibrium susceptibility estimated "
        "from an ensemble of block magnetizations. Entry and exit follow the relaxation of an "
        "order-parameter fluctuation (Onsager regression), not price levels, moving averages "
        "or bands. In development, a hard gate on a critical-slowing-down resilience estimate "
        "(lag-averaged return autocorrelation) and a long-window field gate did not add "
        "value. The final rule is the bare order-parameter fluctuation-relaxation mechanism."
    ),
    limitations=(
        "The edge relies on a restoring (anti-persistent) response at the 1-2 week block "
        "scale. In strongly ferromagnetic, trending regimes (e.g. crashes with herding, or "
        "persistent commodity or crypto trends) down-fluctuations are not reversed, and the "
        "rule buys into them, although the 10-bar block bounds the holding time. The "
        "equilibrium is estimated over only 120 bars, so in a prolonged bear market "
        "'equilibrium' itself drifts down and fluctuations are judged relative to it. tanh "
        "soft spins deliberately discard tail magnitude, so extreme single-day crashes count "
        "as at most one spin. In development, per-instrument scores were positive for 7 of 10 "
        "equity indices and 5 of 8 currency pairs, but weak for commodities (1 of 3). They were noisy "
        "and moderately sensitive to the block size (10 better than 15 or 20) and temperature "
        "window. Turnover is moderate (about 15-20 per year, roughly 8-10 round trips). The "
        "first ~150 bars produce no signal."
    ),
)
