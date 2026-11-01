"""Higuchi smooth-path regime filter: hold a market while its price path is locally smooth
(low fractal dimension relative to its own recent history) and step aside when it turns rough."""

from __future__ import annotations

import numpy as np

from strategy_api import Kmax, LongWindow, Signal, Strategy, Window, trailing_windows


def _higuchi_fd(log_price: np.ndarray, window: int, kmax: int) -> np.ndarray:
    """Rolling Higuchi (1988) fractal dimension of the last ``window`` log prices."""
    p = np.asarray(log_price, dtype=np.float64)
    n = len(p)
    out = np.full(n, np.nan)
    rows = trailing_windows(p, window)
    ok = np.all(np.isfinite(rows), axis=1)
    if not ok.any():
        return out
    X = rows[ok]
    N = window
    ks = np.arange(1, kmax + 1)
    logL = np.zeros((len(X), kmax))
    for j, k in enumerate(ks):
        Lk = np.zeros(len(X))
        for m in range(k):
            sub = X[:, m::k]
            cnt = sub.shape[1] - 1
            length = np.abs(np.diff(sub, axis=1)).sum(axis=1)
            Lk += length * (N - 1) / (cnt * k) / k
        Lk /= k
        with np.errstate(divide="ignore"):
            logL[:, j] = np.log(Lk)
    lk = np.log(ks.astype(float))
    xs = lk - lk.mean()
    slope = (logL - logL.mean(axis=1, keepdims=True)) @ xs / (xs @ xs)
    out[ok] = -slope
    out[~np.isfinite(out)] = np.nan
    return out


def _trailing_rank(x: np.ndarray, ref: int) -> np.ndarray:
    """Fraction of the last ``ref`` finite values that are <= the current value."""
    n = len(x)
    out = np.full(n, np.nan)
    for t in range(ref - 1, n):
        if not np.isfinite(x[t]):
            continue
        seg = x[t - ref + 1 : t + 1]
        seg = seg[np.isfinite(seg)]
        if len(seg) < ref // 2:
            continue
        out[t] = np.mean(seg <= x[t])
    return out


def fd_rank_sig(log_price, *, window, kmax, ref):
    """Trailing percentile rank of the rolling Higuchi fractal dimension."""
    return _trailing_rank(_higuchi_fd(log_price, window, kmax), ref)


ENTRY_RANK = 0.7  # enter while D is not in the roughest 30% of its recent history
EXIT_RANK = 0.8  # leave when D enters the roughest 20%


def rule(s):
    r = s["fd_rank"]
    ok = np.isfinite(r)
    entry = np.where(ok, (r < ENTRY_RANK).astype(float), np.nan)
    exit_ = np.where(ok, (r > EXIT_RANK).astype(float), np.nan)
    return entry, exit_


STRATEGY = Strategy(
    name="higuchi_smooth_path_filter",
    domain="fractal",
    hypothesis=(
        "The local fractal dimension D of a price path measures its roughness (for a self-affine "
        "path D = 2 - H). Calm, orderly markets trace comparatively smooth paths (D low relative to "
        "the market's own recent norm), while stressed, disorderly markets - liquidation cascades, "
        "violent two-way trading, regime transitions - trace rough paths with excess short-scale "
        "length. Risk-adjusted returns of long exposure are better in the smooth regime, so a "
        "long-only holder should stay invested while the path is smooth and step aside when its "
        "roughness rises into the top of its recent distribution."
    ),
    definition=(
        "Let x_1..x_N be the last N=window log prices. For each scale k=1..kmax and offset "
        "m=1..k, the Higuchi curve length is L_m(k) = [sum_{i=1}^{M} |x_{m+ik} - x_{m+(i-1)k}|] * "
        "(N-1)/(M k) / k with M = floor((N-m)/k); L(k) = mean_m L_m(k). For a fractal curve "
        "L(k) ~ k^{-D}, so D_t = -slope of the least-squares fit of log L(k) on log k. "
        "The signal is the trailing percentile rank r_t = #{s in (t-ref, t] : D_s <= D_t} / ref, "
        "which makes the roughness comparison scale-free and instrument-adaptive (it removes the "
        "finite-sample bias of the estimator and differences between markets). Rule (stateless): "
        "entry when r_t < 0.7, exit when r_t > 0.8 (hysteresis band). Defaults: window=90, "
        "kmax=4 (so D measures roughness at the 1-4 day scales, where daily-price "
        "self-affinity breaks down first under stress), ref=180; total lookback 270 bars."
    ),
    references=(
        "Higuchi, T. (1988). Approach to an irregular time series on the basis of the fractal "
        "theory. Physica D 31(2), 277-283.",
        "Mandelbrot, B. B. (1982). The Fractal Geometry of Nature. W. H. Freeman.",
        "Gneiting, T., Sevcikova, H. & Percival, D. B. (2012). Estimators of fractal dimension: "
        "assessing the roughness of time series and spatial data. Statistical Science 27(2), "
        "247-277.",
        "Peters, E. E. (1994). Fractal Market Analysis: Applying Chaos Theory to Investment and "
        "Economics. Wiley.",
    ),
    signals=(
        Signal(
            "fd_rank",
            fd_rank_sig,
            ("log_price",),
            {"window": Window(90), "kmax": Kmax(4), "ref": LongWindow(180)},
            lambda window, kmax, ref: window + ref,
            "Trailing percentile rank of the rolling Higuchi fractal dimension of log price.",
        ),
    ),
    rule=rule,
    rule_lookback=0,
    novelty=(
        "Uses the fractal dimension itself - not price direction, volatility level or a moving "
        "average - as the sole state variable of a long-only exposure switch. Roughness is judged "
        "relative to each market's own recent fractal-dimension distribution, so the same rule "
        "transfers unchanged across asset classes with different typical roughness."
    ),
    limitations=(
        "Long-only and direction-agnostic: a smooth, persistent decline is held, so the filter "
        "helps mainly in markets with positive drift (equity indices, some commodities) and is "
        "roughly neutral to negative in driftless currency pairs. Higuchi D on 90 bars is a noisy "
        "estimate; results on development data were sensitive to the window length (60 and 120 "
        "bars were clearly weaker than 90) though stable across kmax 4-8 and ref 120-252. The "
        "strategy trades about 3-6 round trips per year, so turnover is low but a very "
        "persistent market could approach the minimum trade count. The percentile rank is "
        "relative, so the strategy always spends roughly 30-40% of the time flat even in "
        "markets that are uniformly smooth or rough, and it cannot avoid a slow, smooth bear "
        "market."
    ),
)
