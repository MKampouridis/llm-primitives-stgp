"""spectral_entropy_coherence_gate

Long-only daily strategy built on the Shannon entropy of the (Hann-tapered) periodogram of
daily log returns. Stay long while the recent return spectrum is noise-like (high spectral
entropy relative to its own recent history); step aside when the spectrum becomes concentrated
(low spectral entropy) while the window's drift is negative, i.e. during spectrally coherent
declines.
"""

import numpy as np

from strategy_api import LongWindow, Signal, Strategy, Window


def _win(x, n):
    x = np.asarray(x, dtype=np.float64)
    if len(x) < n:
        return np.empty((0, n))
    return np.lib.stride_tricks.sliding_window_view(x, n)


def _spectral_entropy(log_return, window):
    """Normalised Shannon entropy of the Hann-tapered periodogram of the demeaned returns in
    each trailing window (DC bin excluded). 1 = flat (white) spectrum, 0 = a single line."""
    r = np.nan_to_num(np.asarray(log_return, dtype=np.float64))
    out = np.full(len(r), np.nan)
    W = _win(r, window)
    if len(W) == 0:
        return out
    W = W - W.mean(axis=1, keepdims=True)
    taper = np.hanning(window)
    P = np.abs(np.fft.rfft(W * taper, axis=1)[:, 1:]) ** 2
    p = P / np.maximum(P.sum(axis=1, keepdims=True), 1e-30)
    H = -(p * np.log(np.maximum(p, 1e-30))).sum(axis=1) / np.log(P.shape[1])
    out[window - 1:] = H
    return out


def entropy_rank(log_return, *, window, long_window):
    """Fraction of the last `long_window` spectral-entropy values strictly below today's value
    (causal percentile rank in [0, 1))."""
    H = _spectral_entropy(log_return, window)
    out = np.full(len(H), np.nan)
    Wd = _win(H, long_window)
    if len(Wd) == 0:
        return out
    ok = np.all(np.isfinite(Wd), axis=1)
    rk = (Wd < Wd[:, -1:]).mean(axis=1)
    out[long_window - 1:] = np.where(ok, rk, np.nan)
    return out


def window_drift(log_return, *, window):
    """Zero-frequency (DC) Fourier coefficient of the return window = sum of the last `window`
    log returns; its sign gives the direction of the window's motion."""
    r = np.nan_to_num(np.asarray(log_return, dtype=np.float64))
    out = np.full(len(r), np.nan)
    W = _win(r, window)
    if len(W) == 0:
        return out
    out[window - 1:] = W.sum(axis=1)
    return out


ENTRY_RANK = 0.5   # re-enter once the spectrum is back in the upper half of its entropy range
EXIT_RANK = 0.3    # "coherent" = entropy in the lowest 30% of its trailing range


def rule(s):
    q = s["entropy_rank"]
    d = s["window_drift"]
    ok = np.isfinite(q) & np.isfinite(d)
    entry = np.where(ok, (q > ENTRY_RANK).astype(float), np.nan)
    exit_ = np.where(ok, ((q < EXIT_RANK) & (d < 0.0)).astype(float), np.nan)
    return entry, exit_


STRATEGY = Strategy(
    name="spectral_entropy_coherence_gate",
    domain="spectral",
    hypothesis=(
        "When daily returns over the last ~2 months are spectrally noise-like (power spread "
        "evenly over frequencies, high spectral entropy), the market is in an ordinary, "
        "unstructured regime in which a long position earns the asset's drift premium. When "
        "the spectrum becomes concentrated in a few frequencies (low spectral entropy) the "
        "price path is driven by an organised, persistent component; if that coherent episode "
        "is a decline (negative window drift), it tends to carry on and to concentrate "
        "drawdowns, so being flat during it reduces drawdown relative to volatility more than "
        "it costs in return. Re-entering only once the spectrum has returned to a noise-like "
        "state avoids buying into the middle of the organised move."
    ),
    definition=(
        "Let r_t be daily log returns, N = window (default 40), L = long_window (default 120). "
        "For each t take x_n = r_{t-N+1+n} - mean, n = 0..N-1, apply the Hann taper "
        "w_n = 0.5(1 - cos(2*pi*n/(N-1))), and compute the periodogram "
        "P_k = |sum_n w_n x_n exp(-2*pi*i*k*n/N)|^2 for k = 1..floor(N/2) (DC excluded). "
        "Normalise p_k = P_k / sum_j P_j and define the normalised spectral entropy "
        "H_t = -sum_k p_k ln p_k / ln(K), K = floor(N/2) (H = 1 for a flat/white spectrum). "
        "Signal 1 (entropy_rank): Q_t = (1/L) * #{s in [t-L+1, t] : H_s < H_t}, a causal "
        "percentile rank that makes the threshold self-calibrating for every market. "
        "Signal 2 (window_drift): D_t = sum_{j=0}^{N-1} r_{t-j} (the zero-frequency Fourier "
        "coefficient of the window). Rule: entry when Q_t > 0.5; exit when Q_t < 0.3 and "
        "D_t < 0. The harness holds from entry to exit (exit wins on ties) with its own "
        "one-bar delay and costs. Total lookback 160 bars."
    ),
    references=(
        "Powell, G.E. and Percival, I.C. (1979). A spectral entropy method for distinguishing "
        "regular and irregular motion of Hamiltonian systems. Journal of Physics A: "
        "Mathematical and General, 12(11), 2053-2071.",
        "Inouye, T., Shinosaki, K., Sakamoto, H., Toi, S., Ukai, S., Iyama, A., Katsuda, Y. and "
        "Hirano, M. (1991). Quantification of EEG irregularity by use of the entropy of the "
        "power spectrum. Electroencephalography and Clinical Neurophysiology, 79(3), 204-210.",
        "Harris, F.J. (1978). On the use of windows for harmonic analysis with the discrete "
        "Fourier transform. Proceedings of the IEEE, 66(1), 51-83.",
        "Percival, D.B. and Walden, A.T. (1993). Spectral Analysis for Physical Applications: "
        "Multitaper and Conventional Univariate Techniques. Cambridge University Press.",
    ),
    signals=(
        Signal(
            "entropy_rank",
            entropy_rank,
            ("log_return",),
            {"window": Window(40), "long_window": LongWindow(120)},
            lambda window, long_window: window + long_window,
            "causal percentile rank of the normalised spectral entropy of returns",
        ),
        Signal(
            "window_drift",
            window_drift,
            ("log_return",),
            {"window": Window(40)},
            lambda window: window,
            "sum of the last `window` log returns (DC Fourier coefficient)",
        ),
    ),
    rule=rule,
    rule_lookback=0,
    novelty=(
        "Uses the shape of the whole power distribution (its Shannon entropy) as a regime "
        "detector, not any particular component. Unlike ssa_residual_reversion it does not "
        "decompose the price into a trend plus residual or trade reversion of a residual. "
        "Unlike bridge_fourier_phase it does not use the phase of a fundamental harmonic or "
        "try to time a cycle. Here the frequency domain only says whether the market is "
        "unstructured (stay long) or organised (step aside if the organised move is down). "
        "The strategy is long about 65-80% of the time and exits only during spectrally "
        "coherent declines."
    ),
    limitations=(
        "The edge on the development data was small: the objective was 0.084, and nearby "
        "parameter settings scored between about -0.12 and +0.08, so the result is within "
        "sampling noise of a near-buy-and-hold profile. A 40-bar periodogram is a noisy "
        "spectral estimate; a multitaper estimate did not help. Being mostly long, it earns "
        "little on driftless markets such as currency pairs, where it scores negative because "
        "of drawdowns, and on markets with persistent negative drift. It reacts with a lag of "
        "several weeks, so it does not avoid sudden one-day crashes, which spread power over "
        "all frequencies and therefore have high entropy. On some instruments the number of "
        "entries per year is close to the minimum of 2 required by the evaluation."
    ),
)
