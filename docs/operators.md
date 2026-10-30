# Operator catalogue (seed library, arm 6)

Generated from the operator contracts by `scripts/generate_operator_docs.py`; do not edit by hand.
The seed library is expert-specified, AI-assisted and expert-verified (see docs/decisions.md, D-002).

| Domain | Contracts |
|---|---:|
| Data terminals | 3 |
| Core: constructors, adaptive thresholds, comparators, logic, regimes | 17 |
| Information theory | 4 |
| Information geometry | 4 |
| Optimal transport | 4 |
| Rough paths | 4 |
| Fractal analysis | 4 |
| Statistical physics | 4 |
| Spectral methods | 4 |
| Conventional technical-analysis terminals | 23 |
| Conventional directional-change terminals | 20 |

## Data terminals

| Terminal | Type | Lookback | Missing | Definition | Summary |
|---|---|---:|---|---|---|
| `abs_ret@1` | Series | 2 | elementwise | $|r_t|$ | Absolute log return (a volatility proxy). |
| `log_price@1` | Path | 1 | elementwise | $p_t = \log C_t + \sum_{s \le t} a_s, with a_s the dividend/split adjustment at bar s$ | Log price path (raw log close plus causal event adjustment since the sandbox start). |
| `ret@1` | Series | 2 | elementwise | $r_t = p_t - p_{t^-}, t^- the previous valid bar$ | Point-in-time total log return between consecutive valid bars. |

References: Campbell, Lo & MacKinlay (1997), The Econometrics of Financial Markets, ch. 1; Ding, Granger & Engle (1993), J. Empirical Finance 1(1):83-106

## Core: constructors, adaptive thresholds, comparators, logic, regimes

### and@1 — Kleene AND: false if either is false, true if both true, else unknown.

- **Signature:** `And_v1(Bool, Bool) -> Bool`
- **Parameters:** none
- **Lookback (bars):** 1; earliest output at index lookback − 1
- **Missing data:** elementwise
- **Invariances:** none declared; size weight 1; memory finite
- **Definition:** $a \wedge b in Kleene's strong three-valued logic$
- **References:** Kleene (1952), Introduction to Metamathematics, North-Holland, §64
- **Reference test:** truth table
- **Provenance:** Claude Code (claude-opus-5-5), WP1 session; specified by Research plan domain list (PI); 2026-10-30; reviewed by — (pending)

### cross_above@1 — a_t > b_t and a_{t-1} <= b_{t-1}.

- **Signature:** `CrossAbove_v1(Real, Real) -> Bool`
- **Parameters:** none
- **Lookback (bars):** 2; earliest output at index lookback − 1
- **Missing data:** elementwise
- **Invariances:** none declared; size weight 1; memory finite
- **Definition:** $\mathbb 1\{a_t > b_t\} \wedge \neg\mathbb 1\{a_{t-1} > b_{t-1}\} (Kleene)$
- **References:** Murphy (1999), Technical Analysis of the Financial Markets, NYIF, ch. 9
- **Reference test:** explicit loop
- **Provenance:** Claude Code (claude-opus-5-5), WP1 session; specified by Research plan domain list (PI); 2026-10-30; reviewed by — (pending)

### cross_below@1 — a_t < b_t and a_{t-1} >= b_{t-1}.

- **Signature:** `CrossBelow_v1(Real, Real) -> Bool`
- **Parameters:** none
- **Lookback (bars):** 2; earliest output at index lookback − 1
- **Missing data:** elementwise
- **Invariances:** none declared; size weight 1; memory finite
- **Definition:** $\mathbb 1\{a_t < b_t\} \wedge \neg\mathbb 1\{a_{t-1} < b_{t-1}\} (Kleene)$
- **References:** Murphy (1999), Technical Analysis of the Financial Markets, NYIF, ch. 9
- **Reference test:** explicit loop
- **Provenance:** Claude Code (claude-opus-5-5), WP1 session; specified by Research plan domain list (PI); 2026-10-30; reviewed by — (pending)

### exceeds_ksd@1 — x_t above its rolling mean + k sd; equals Gt(x, MeanKSd(x, w, k)).

- **Signature:** `ExceedsKsd_v1(Real, window: LongWindow, k: KSigma) -> Bool`
- **Parameters:** window ∈ {60, 90, 120, 180, 252}; k ∈ {-2, -1, -0.5, 0.5, 1, 2}
- **Lookback (bars):** 60–252; earliest output at index lookback − 1
- **Missing data:** min_valid (min valid share 0.9)
- **Invariances:** none declared; size weight 1; memory finite
- **Definition:** $\mathbb 1\{x_t > \bar x_{t,w} + k s_{t,w}\}$
- **References:** Bollinger (2001), Bollinger on Bollinger Bands, McGraw-Hill
- **Reference test:** composition Gt(x, MeanKSd(x, w, k))
- **Provenance:** Claude Code (claude-opus-5-5), WP1 session; specified by Research plan domain list (PI); 2026-10-30; reviewed by — (pending)

### exceeds_quantile@1 — x_t above the q-quantile of its last `window` values; equals Gt(x, RollingPercentile(x)).

- **Signature:** `ExceedsQuantile_v1(Real, window: LongWindow, q: Quantile) -> Bool`
- **Parameters:** window ∈ {60, 90, 120, 180, 252}; q ∈ {0.05, 0.1, 0.2, 0.3, 0.5, 0.7, 0.8, 0.9, 0.95}
- **Lookback (bars):** 60–252; earliest output at index lookback − 1
- **Missing data:** min_valid (min valid share 0.9)
- **Invariances:** none declared; size weight 1; memory finite
- **Definition:** $\mathbb 1\{x_t > Q_q\{x_s : s \in (t-w,t]\}\} (unknown if either side is missing)$
- **References:** Hyndman & Fan (1996), The American Statistician 50(4):361-365
- **Reference test:** composition Gt(x, RollingPercentile(x, w, q))
- **Provenance:** Claude Code (claude-opus-5-5), WP1 session; specified by Research plan domain list (PI); 2026-10-30; reviewed by — (pending)

### gt@1 — Comparator a_t > b_t (unknown if either is missing).

- **Signature:** `Gt_v1(Real, Real) -> Bool`
- **Parameters:** none
- **Lookback (bars):** 1; earliest output at index lookback − 1
- **Missing data:** elementwise
- **Invariances:** none declared; size weight 1; memory finite
- **Definition:** $\mathbb 1\{a_t > b_t\}$
- **References:** Montana (1995), Evolutionary Computation 3(2):199-230 (strongly typed GP)
- **Reference test:** numpy comparison
- **Provenance:** Claude Code (claude-opus-5-5), WP1 session; specified by Research plan domain list (PI); 2026-10-30; reviewed by — (pending)

### increments@1 — First difference of a path (NaN if either end is missing).

- **Signature:** `Increments_v1(Path) -> Series`
- **Parameters:** none
- **Lookback (bars):** 2; earliest output at index lookback − 1
- **Missing data:** propagate
- **Invariances:** shift; size weight 0; memory finite
- **Definition:** $\Delta P_t = P_t - P_{t-1}$
- **References:** Lyons, Caruana & Lévy (2007), Differential Equations Driven by Rough Paths, LNM 1908
- **Reference test:** numpy.diff
- **Provenance:** Claude Code (claude-opus-5-5), WP1 session; specified by Research plan domain list (PI); 2026-10-30; reviewed by — (pending)

### lt@1 — Comparator a_t < b_t (unknown if either is missing).

- **Signature:** `Lt_v1(Real, Real) -> Bool`
- **Parameters:** none
- **Lookback (bars):** 1; earliest output at index lookback − 1
- **Missing data:** elementwise
- **Invariances:** none declared; size weight 1; memory finite
- **Definition:** $\mathbb 1\{a_t < b_t\}$
- **References:** Montana (1995), Evolutionary Computation 3(2):199-230 (strongly typed GP)
- **Reference test:** numpy comparison
- **Provenance:** Claude Code (claude-opus-5-5), WP1 session; specified by Research plan domain list (PI); 2026-10-30; reviewed by — (pending)

### mean_ksd@1 — Rolling mean plus k rolling (sample) standard deviations; an adaptive threshold.

- **Signature:** `MeanKsd_v1(Real, window: LongWindow, k: KSigma) -> Real`
- **Parameters:** window ∈ {60, 90, 120, 180, 252}; k ∈ {-2, -1, -0.5, 0.5, 1, 2}
- **Lookback (bars):** 60–252; earliest output at index lookback − 1
- **Missing data:** min_valid (min valid share 0.9)
- **Invariances:** none declared; size weight 1; memory finite
- **Definition:** $\bar x_{t,w} + k\, s_{t,w}, mean and sample sd over (t-w, t]$
- **References:** Bollinger (2001), Bollinger on Bollinger Bands, McGraw-Hill
- **Reference test:** pandas Series.rolling().mean()/std()
- **Provenance:** Claude Code (claude-opus-5-5), WP1 session; specified by Research plan domain list (PI); 2026-10-30; reviewed by — (pending)

### not@1 — Kleene NOT: unknown stays unknown.

- **Signature:** `Not_v1(Bool) -> Bool`
- **Parameters:** none
- **Lookback (bars):** 1; earliest output at index lookback − 1
- **Missing data:** elementwise
- **Invariances:** none declared; size weight 1; memory finite
- **Definition:** $\neg a = 1 - a (unknown stays unknown)$
- **References:** Kleene (1952), Introduction to Metamathematics, North-Holland, §64
- **Reference test:** truth table
- **Provenance:** Claude Code (claude-opus-5-5), WP1 session; specified by Research plan domain list (PI); 2026-10-30; reviewed by — (pending)

### or@1 — Kleene OR: true if either is true, false if both false, else unknown.

- **Signature:** `Or_v1(Bool, Bool) -> Bool`
- **Parameters:** none
- **Lookback (bars):** 1; earliest output at index lookback − 1
- **Missing data:** elementwise
- **Invariances:** none declared; size weight 1; memory finite
- **Definition:** $a \vee b in Kleene's strong three-valued logic$
- **References:** Kleene (1952), Introduction to Metamathematics, North-Holland, §64
- **Reference test:** truth table
- **Provenance:** Claude Code (claude-opus-5-5), WP1 session; specified by Research plan domain list (PI); 2026-10-30; reviewed by — (pending)

### past_hist@1 — Distribution of x over (t-2w, t-w] on the same bins and scale as RollingHist at t.

- **Signature:** `PastHist_v1(Series, window: Window) -> Hist`
- **Parameters:** window ∈ {10, 15, 20, 30, 40, 60, 90, 120}
- **Lookback (bars):** 252; earliest output at index lookback − 1
- **Missing data:** min_valid (min valid share 0.9)
- **Invariances:** scale; size weight 0; memory finite
- **Definition:** $as RollingHist but over s \in (t-2w, t-w], standardised with the median/MAD at t$
- **References:** Hampel (1974), J. Am. Stat. Assoc. 69(346):383-393
- **Reference test:** numpy.histogram on explicit windows
- **Provenance:** Claude Code (claude-opus-5-5), WP1 session; specified by Research plan domain list (PI); 2026-10-30; reviewed by — (pending)

### quantile_regime@1 — +1 in the top tercile of the last `window` values, -1 in the bottom tercile, else 0.

- **Signature:** `QuantileRegime_v1(Real, window: LongWindow) -> Regime`
- **Parameters:** window ∈ {60, 90, 120, 180, 252}
- **Lookback (bars):** 60–252; earliest output at index lookback − 1
- **Missing data:** min_valid (min valid share 0.9)
- **Invariances:** none declared; size weight 1; memory finite
- **Definition:** $\mathrm{sign\text{-}tercile}(x_t \mid \{x_s\}_{s \in (t-w,t]}), terciles by Hyndman-Fan type 7$
- **References:** Hamilton (1989), Econometrica 57(2):357-384 (regimes; here a model-free tercile variant)
- **Reference test:** pandas rolling quantiles
- **Provenance:** Claude Code (claude-opus-5-5), WP1 session; specified by Research plan domain list (PI); 2026-10-30; reviewed by — (pending)

### regime_is@1 — True when the regime equals `state` (unknown when the regime is unknown).

- **Signature:** `RegimeIs_v1(Regime, state: RegimeState) -> Bool`
- **Parameters:** state ∈ {-1, 0, 1}
- **Lookback (bars):** 1; earliest output at index lookback − 1
- **Missing data:** elementwise
- **Invariances:** none declared; size weight 1; memory finite
- **Definition:** $\mathbb 1\{R_t = s\}$
- **References:** Montana (1995), Evolutionary Computation 3(2):199-230 (strongly typed GP)
- **Reference test:** numpy comparison
- **Provenance:** Claude Code (claude-opus-5-5), WP1 session; specified by Research plan domain list (PI); 2026-10-30; reviewed by — (pending)

### rolling_hist@1 — Distribution of the last `window` values on 16 fixed bins of robust z-scores.

- **Signature:** `RollingHist_v1(Series, window: Window) -> Hist`
- **Parameters:** window ∈ {10, 15, 20, 30, 40, 60, 90, 120}
- **Lookback (bars):** 252; earliest output at index lookback − 1
- **Missing data:** min_valid (min valid share 0.9)
- **Invariances:** scale; size weight 0; memory finite
- **Definition:** $z_s = (x_s - \mathrm{med}_t)/(1.4826\,\mathrm{MAD}_t), s \in (t-w, t], with median and MAD over the last 252 bars; p_t(b) \propto \tfrac12 + \#\{s: z_s \in B_b\}, 16 equal bins on [-4,4], outer bins absorbing the tails (Jeffreys smoothing)$
- **References:** Hampel (1974), J. Am. Stat. Assoc. 69(346):383-393 (MAD scale); Krichevsky & Trofimov (1981), IEEE Trans. Inf. Theory 27(2):199-207 (add-1/2 estimator)
- **Reference test:** numpy.histogram on explicit windows
- **Provenance:** Claude Code (claude-opus-5-5), WP1 session; specified by Research plan domain list (PI); 2026-10-30; reviewed by — (pending)

### rolling_percentile@1 — q-quantile of the last `window` values (linear interpolation); an adaptive threshold.

- **Signature:** `RollingPercentile_v1(Real, window: LongWindow, q: Quantile) -> Real`
- **Parameters:** window ∈ {60, 90, 120, 180, 252}; q ∈ {0.05, 0.1, 0.2, 0.3, 0.5, 0.7, 0.8, 0.9, 0.95}
- **Lookback (bars):** 60–252; earliest output at index lookback − 1
- **Missing data:** min_valid (min valid share 0.9)
- **Invariances:** none declared; size weight 1; memory finite
- **Definition:** $Q_q\{x_s : s \in (t-w, t]\}, Hyndman-Fan type 7 interpolation$
- **References:** Hyndman & Fan (1996), The American Statistician 50(4):361-365
- **Reference test:** pandas Series.rolling().quantile()
- **Provenance:** Claude Code (claude-opus-5-5), WP1 session; specified by Research plan domain list (PI); 2026-10-30; reviewed by — (pending)

### to_path@1 — Running sum of a series; a path whose level is arbitrary (consumers are shift-invariant).

- **Signature:** `ToPath_v1(Series) -> Path`
- **Parameters:** none
- **Lookback (bars):** 1; earliest output at index lookback − 1
- **Missing data:** elementwise
- **Invariances:** none declared; size weight 0; memory cumulative
- **Definition:** $P_t = \sum_{s \le t,\ x_s \text{ valid}} x_s (NaN where x_t is missing)$
- **References:** Lyons, Caruana & Lévy (2007), Differential Equations Driven by Rough Paths, LNM 1908
- **Reference test:** numpy.nancumsum
- **Provenance:** Claude Code (claude-opus-5-5), WP1 session; specified by Research plan domain list (PI); 2026-10-30; reviewed by — (pending)

## Information theory

### lagged_mutual_info@1 — Mutual information of (x_s, x_{s-lag}) pairs in the window, on 4 equal-frequency bins, / log 4.

- **Signature:** `LaggedMutualInfo_v1(Series, window: LongWindow, lag: Lag) -> Real`
- **Parameters:** window ∈ {60, 90, 120, 180, 252}; lag ∈ {1, 2, 3, 5, 10}
- **Lookback (bars):** 60–252; earliest output at index lookback − 1
- **Missing data:** min_valid (min valid share 0.9)
- **Invariances:** scale; size weight 1; memory finite
- **Definition:** $I = \sum_{a,b} p(a,b)\log\frac{p(a,b)}{p(a)p(b)} / \log 4, over symbol pairs (q(x_s), q(x_{s-\ell})), s, s-\ell in the window, q = within-window quartile bin$
- **References:** Fraser & Swinney (1986), Physical Review A 33(2):1134-1140; Cover & Thomas (2006), Elements of Information Theory, 2nd ed., Wiley, ch. 2
- **Reference test:** sklearn.metrics.mutual_info_score on the window's symbol pairs
- **Provenance:** Claude Code (claude-opus-5-5), WP1 session; specified by Research plan domain list (PI); 2026-10-30; reviewed by — (pending)

### lz_compressibility@1 — Normalised LZ76 complexity of the window quantised into `levels` equal-frequency symbols.

- **Signature:** `LzCompressibility_v1(Series, window: Window, levels: Levels) -> Real`
- **Parameters:** window ∈ {10, 15, 20, 30, 40, 60, 90, 120}; levels ∈ {2, 3, 4}
- **Lookback (bars):** 10–120; earliest output at index lookback − 1
- **Missing data:** min_valid (min valid share 0.9)
- **Invariances:** scale; size weight 1; memory finite
- **Definition:** $C = c(n)\,\log_k n / n: c(n) the number of LZ76 phrases of the symbol sequence of length n, symbols = within-window quantile bins (L levels), k the number of distinct symbols$
- **References:** Lempel & Ziv (1976), IEEE Trans. Information Theory 22(1):75-81; Kaspar & Schuster (1987), Physical Review A 36(2):842-848; Cover & Thomas (2006), Elements of Information Theory, ch. 10 (rate-distortion)
- **Reference test:** antropy.lziv_complexity(normalize=True) per window
- **Provenance:** Claude Code (claude-opus-5-5), WP1 session; specified by Research plan domain list (PI); 2026-10-30; reviewed by — (pending)

### permutation_entropy@1 — Normalised entropy of the ordinal patterns (embedding dimension m, delay 1) in the window.

- **Signature:** `PermutationEntropy_v1(Series, window: LongWindow, order: Order) -> Real`
- **Parameters:** window ∈ {60, 90, 120, 180, 252}; order ∈ {3, 4, 5}
- **Lookback (bars):** 60–252; earliest output at index lookback − 1
- **Missing data:** min_valid (min valid share 0.9)
- **Invariances:** scale; size weight 1; memory finite
- **Definition:** $H_m = -\sum_\pi p(\pi)\log p(\pi) / \log m!, p(\pi) the relative frequency of ordinal pattern \pi among the w-m+1 patterns (x_i, ..., x_{i+m-1}) in the window; ties ordered by time$
- **References:** Bandt & Pompe (2002), Physical Review Letters 88(17):174102
- **Reference test:** ordpy.permutation_entropy and antropy.perm_entropy per window
- **Provenance:** Claude Code (claude-opus-5-5), WP1 session; specified by Research plan domain list (PI); 2026-10-30; reviewed by — (pending)

### shannon_entropy@1 — Entropy of the rolling histogram, normalised to [0, 1] by log(number of bins).

- **Signature:** `ShannonEntropy_v1(Hist) -> Real`
- **Parameters:** none
- **Lookback (bars):** 1; earliest output at index lookback − 1
- **Missing data:** elementwise
- **Invariances:** none declared; size weight 1; memory finite
- **Definition:** $H(p_t) = -\sum_b p_t(b)\log p_t(b) / \log B$
- **References:** Shannon (1948), Bell System Technical Journal 27(3):379-423; Cover & Thomas (2006), Elements of Information Theory, 2nd ed., Wiley, ch. 2
- **Reference test:** scipy.stats.entropy
- **Provenance:** Claude Code (claude-opus-5-5), WP1 session; specified by Research plan domain list (PI); 2026-10-30; reviewed by — (pending)

## Information geometry

### alpha_divergence@1 — Amari alpha-divergence D_alpha(p||q); alpha=0 is 4(1 - Bhattacharyya), alpha -> -1 is KL(p||q).

- **Signature:** `AlphaDivergence_v1(Hist, Hist, alpha: Alpha) -> Real`
- **Parameters:** alpha ∈ {-0.5, 0, 0.5}
- **Lookback (bars):** 1; earliest output at index lookback − 1
- **Missing data:** elementwise
- **Invariances:** none declared; size weight 1; memory finite
- **Definition:** $D_\alpha(p\|q) = \frac{4}{1-\alpha^2}\left(1 - \sum_b p(b)^{\frac{1-\alpha}2} q(b)^{\frac{1+\alpha}2}\right)$
- **References:** Amari (2009), IEEE Trans. Information Theory 55(11):4925-4931; Amari (2016), Information Geometry and Its Applications, Springer, ch. 3
- **Reference test:** KL limits (scipy.special.rel_entr) and the Hellinger closed form
- **Provenance:** Claude Code (claude-opus-5-5), WP1 session; specified by Research plan domain list (PI); 2026-10-30; reviewed by — (pending)

### fisher_information@1 — Fisher information of the binned density (location family), in [0, 1]: high when irregular.

- **Signature:** `FisherInformation_v1(Hist) -> Real`
- **Parameters:** none
- **Lookback (bars):** 1; earliest output at index lookback − 1
- **Missing data:** elementwise
- **Invariances:** none declared; size weight 1; memory finite
- **Definition:** $F[p] = \tfrac12\sum_{b=1}^{B-1}\left(\sqrt{p(b+1)} - \sqrt{p(b)}\right)^2$
- **References:** Frieden (2004), Science from Fisher Information, Cambridge University Press; Vignat & Bercher (2003), Physics Letters A 312(1-2):27-33; Olivares, Plastino & Rosso (2012), Physica A 391(8):2518-2526
- **Reference test:** ordpy.fisher_shannon on ordinal distributions (same discrete functional)
- **Provenance:** Claude Code (claude-opus-5-5), WP1 session; specified by Research plan domain list (PI); 2026-10-30; reviewed by — (pending)

### fisher_rao_gauss@1 — Geodesic distance (Fisher metric) between N(mu, sigma) fits on the last `short` and `long` bars.

- **Signature:** `FisherRaoGauss_v1(Series, short: Window, long: LongWindow) -> Real`
- **Parameters:** short ∈ {10, 15, 20, 30, 40, 60, 90, 120}; long ∈ {60, 90, 120, 180, 252}
- **Lookback (bars):** 60–252; earliest output at index lookback − 1
- **Missing data:** min_valid (min valid share 0.9)
- **Invariances:** scale; size weight 1; memory finite
- **Definition:** $d = \sqrt2\,\mathrm{arccosh}\!\left(1 + \frac{(\mu_1-\mu_2)^2/2 + (\sigma_1-\sigma_2)^2}{2\sigma_1\sigma_2}\right) (hyperbolic half-plane form of the univariate normal family)$
- **References:** Atkinson & Mitchell (1981), Sankhya A 43(3):345-365; Costa, Santos & Strapasson (2015), Discrete Applied Mathematics 197:59-69
- **Reference test:** independent log-form closed formula (Costa et al. 2015)
- **Provenance:** Claude Code (claude-opus-5-5), WP1 session; specified by Research plan domain list (PI); 2026-10-30; reviewed by — (pending)

### fisher_rao_hist@1 — Fisher-Rao distance on the simplex: twice the angle between sqrt(p) and sqrt(q), in [0, pi].

- **Signature:** `FisherRaoHist_v1(Hist, Hist) -> Real`
- **Parameters:** none
- **Lookback (bars):** 1; earliest output at index lookback − 1
- **Missing data:** elementwise
- **Invariances:** none declared; size weight 1; memory finite
- **Definition:** $d_{FR}(p,q) = 2\arccos\sum_b \sqrt{p(b)q(b)}$
- **References:** Rao (1945), Bulletin of the Calcutta Mathematical Society 37:81-91; Amari & Nagaoka (2000), Methods of Information Geometry, AMS/Oxford, ch. 2
- **Reference test:** great-circle distance between sqrt-embeddings on the sphere
- **Provenance:** Claude Code (claude-opus-5-5), WP1 session; specified by Research plan domain list (PI); 2026-10-30; reviewed by — (pending)

## Optimal transport

### sinkhorn_divergence@1 — Debiased Sinkhorn divergence (squared-distance cost on bin centres, regularisation epsilon).

- **Signature:** `SinkhornDivergence_v1(Hist, Hist, epsilon: Epsilon) -> Real`
- **Parameters:** epsilon ∈ {0.25, 0.5, 1}
- **Lookback (bars):** 1; earliest output at index lookback − 1
- **Missing data:** elementwise
- **Invariances:** none declared; size weight 1; memory finite
- **Definition:** $S_\varepsilon(p,q) = OT_\varepsilon(p,q) - \tfrac12 OT_\varepsilon(p,p) - \tfrac12 OT_\varepsilon(q,q), OT_\varepsilon = \min_{P\in U(p,q)} \langle P, C\rangle + \varepsilon\,KL(P\|p\otimes q), C_{ij} = (c_i - c_j)^2$
- **References:** Cuturi (2013), Advances in Neural Information Processing Systems 26:2292-2300; Genevay, Peyre & Cuturi (2018), AISTATS, PMLR 84:1608-1617; Feydy, Sejourne, Vialard, Amari, Trouve & Peyre (2019), AISTATS, PMLR 89:2681-2690
- **Reference test:** POT ot.sinkhorn plan (converged), objective recomputed
- **Provenance:** Claude Code (claude-opus-5-5), WP1 session; specified by Research plan domain list (PI); 2026-10-30; reviewed by — (pending)

### transport_asymmetry@1 — sign(mean gain - mean loss) * W1(gains, losses) / mean |x|: gain/loss distribution asymmetry.

- **Signature:** `TransportAsymmetry_v1(Series, window: LongWindow) -> Real`
- **Parameters:** window ∈ {60, 90, 120, 180, 252}
- **Lookback (bars):** 60–252; earliest output at index lookback − 1
- **Missing data:** propagate
- **Invariances:** scale; size weight 1; memory finite
- **Definition:** $A = \mathrm{sign}(\bar G - \bar L)\, W_1(\mu_G, \mu_L) / \overline{|x|}, \mu_G = law of x_s>0, \mu_L = law of -x_s for x_s<0, s in the window$
- **References:** Villani (2009), Optimal Transport: Old and New, Springer, ch. 6; Cont (2001), Quantitative Finance 1(2):223-236 (gain/loss asymmetry)
- **Reference test:** scipy.stats.wasserstein_distance
- **Provenance:** Claude Code (claude-opus-5-5), WP1 session; specified by Research plan domain list (PI); 2026-10-30; reviewed by — (pending)

### w1_hist@1 — Earth mover's distance between two histograms on the shared robust-z bin centres.

- **Signature:** `W1Hist_v1(Hist, Hist) -> Real`
- **Parameters:** none
- **Lookback (bars):** 1; earliest output at index lookback − 1
- **Missing data:** elementwise
- **Invariances:** none declared; size weight 1; memory finite
- **Definition:** $W_1(p,q) = \int |F_p - F_q| = \Delta\sum_{b<B} |\sum_{c\le b} (p(c) - q(c))|, \Delta = bin width$
- **References:** Villani (2009), Optimal Transport: Old and New, Springer, ch. 6; Peyre & Cuturi (2019), Foundations and Trends in Machine Learning 11(5-6):355-607, §2.6
- **Reference test:** POT ot.emd2 with |c_i - c_j| cost and ot.wasserstein_1d
- **Provenance:** Claude Code (claude-opus-5-5), WP1 session; specified by Research plan domain list (PI); 2026-10-30; reviewed by — (pending)

### w2_to_gaussian@1 — W2 distance between the z-scored window and the standard normal: a transport non-Gaussianity.

- **Signature:** `W2ToGaussian_v1(Series, window: LongWindow) -> Real`
- **Parameters:** window ∈ {60, 90, 120, 180, 252}
- **Lookback (bars):** 60–252; earliest output at index lookback − 1
- **Missing data:** propagate
- **Invariances:** scale; size weight 1; memory finite
- **Definition:** $W_2(\hat\mu_t, N(0,1)) = \left(\int_0^1 (F_n^{-1}(u) - \Phi^{-1}(u))^2 du\right)^{1/2}, \hat\mu_t of z-scores$
- **References:** del Barrio, Cuesta-Albertos, Matran & Rodriguez-Rodriguez (1999), Annals of Statistics 27(4):1230-1239; Villani (2009), Optimal Transport: Old and New, Springer, ch. 6
- **Reference test:** numerical quadrature of the quantile-function integral (scipy.integrate.quad)
- **Provenance:** Claude Code (claude-opus-5-5), WP1 session; specified by Research plan domain list (PI); 2026-10-30; reviewed by — (pending)

## Rough paths

### chord_area@1 — Levy area of (time in [0,1], z-scored path / sqrt(w)): signed area between path and chord.

- **Signature:** `ChordArea_v1(Path, window: Window) -> Real`
- **Parameters:** window ∈ {10, 15, 20, 30, 40, 60, 90, 120}
- **Lookback (bars):** 11–121; earliest output at index lookback − 1
- **Missing data:** propagate
- **Invariances:** shift, scale; size weight 1; memory finite
- **Definition:** $A_t = \tfrac12\sum_{k=1}^{w}(\tau_{k-1}\Delta\tilde X_k - \tilde X_{k-1}\Delta\tau_k), \tau_k = k/w, \tilde X = cumulative z-scored increments / \sqrt w$
- **References:** Chevyrev & Kormilitzin (2016), A Primer on the Signature Method in Machine Learning, arXiv:1603.03788; Lyons, Caruana & Levy (2007), Differential Equations Driven by Rough Paths, LNM 1908
- **Reference test:** roughpy signature (depth 2) of the time-augmented path
- **Provenance:** Claude Code (claude-opus-5-5), WP1 session; specified by Research plan domain list (PI); 2026-10-30; reviewed by — (pending)

### levy_area@1 — Levy area of (X, Y) over the window, each path's increments z-scored, divided by the window length.

- **Signature:** `LevyArea_v1(Path, Path, window: Window) -> Real`
- **Parameters:** window ∈ {10, 15, 20, 30, 40, 60, 90, 120}
- **Lookback (bars):** 11–121; earliest output at index lookback − 1
- **Missing data:** propagate
- **Invariances:** shift, scale; size weight 1; memory finite
- **Definition:** $A_t = \frac{1}{2w}\sum_{k=1}^{w}(\tilde X_{k-1}\Delta\tilde Y_k - \tilde Y_{k-1}\Delta\tilde X_k) = \frac{1}{2w}(S^{12} - S^{21}), \tilde X the path of z-scored increments started at 0$
- **References:** Levy (1940), American Journal of Mathematics 62(1):487-550; Lyons (1998), Revista Matematica Iberoamericana 14(2):215-310; Lyons, Caruana & Levy (2007), Differential Equations Driven by Rough Paths, LNM 1908
- **Reference test:** roughpy signature (depth 2): (S^{12} - S^{21}) / 2
- **Provenance:** Claude Code (claude-opus-5-5), WP1 session; specified by Research plan domain list (PI); 2026-10-30; reviewed by — (pending)

### p_variation@1 — log(V_p / sum|dX|^p) over the window: >0 when coarser partitions add variation (trend).

- **Signature:** `PVariation_v1(Path, window: Window, pvar: PVar) -> Real`
- **Parameters:** window ∈ {10, 15, 20, 30, 40, 60, 90, 120}; pvar ∈ {2, 2.5, 3}
- **Lookback (bars):** 11–121; earliest output at index lookback − 1
- **Missing data:** propagate
- **Invariances:** shift, scale; size weight 1; memory finite
- **Definition:** $\log\frac{\sup_{\mathcal P}\sum_i |X_{t_i}-X_{t_{i-1}}|^p}{\sum_k |\Delta X_k|^p}, partitions of the w+1 points of the window (exact dynamic programme)$
- **References:** Lyons (1998), Revista Matematica Iberoamericana 14(2):215-310; Friz & Victoir (2010), Multidimensional Stochastic Processes as Rough Paths, Cambridge UP, ch. 5; Butkus & Norvaisa (2018), Lithuanian Mathematical Journal 58(4):360-378
- **Reference test:** brute-force enumeration of all partitions on short paths
- **Provenance:** Claude Code (claude-opus-5-5), WP1 session; specified by Research plan domain list (PI); 2026-10-30; reviewed by — (pending)

### signature_similarity@1 — Cosine between the depth-3 signatures of (t, X) over the last and the previous w bars.

- **Signature:** `SignatureSimilarity_v1(Path, window: Window) -> Real`
- **Parameters:** window ∈ {10, 15, 20, 30, 40, 60, 90, 120}
- **Lookback (bars):** 21–241; earliest output at index lookback − 1
- **Missing data:** propagate
- **Invariances:** shift, scale; size weight 1; memory finite
- **Definition:** $\cos\angle(S^{\le3}(\gamma_t), S^{\le3}(\gamma_{t-w})), \gamma_s = (\tau, \tilde X) on (s-w, s], signature levels 1-3 (14 terms) via Chen's identity$
- **References:** Chen (1958), Annals of Mathematics 65(1):163-178; Kiraly & Oberhauser (2019), Journal of Machine Learning Research 20(31):1-45; Chevyrev & Oberhauser (2022), Journal of Machine Learning Research 23(176):1-42
- **Reference test:** roughpy signature (depth 3) of each window
- **Provenance:** Claude Code (claude-opus-5-5), WP1 session; specified by Research plan domain list (PI); 2026-10-30; reviewed by — (pending)

## Fractal analysis

### dfa@1 — DFA-1 scaling exponent: slope of log F(n) on log n (boxes of 6-64 bars, at least 4 per scale).

- **Signature:** `Dfa_v1(Series, window: LongWindow) -> Real`
- **Parameters:** window ∈ {60, 90, 120, 180, 252}
- **Lookback (bars):** 60–252; earliest output at index lookback − 1
- **Missing data:** propagate
- **Invariances:** scale; size weight 1; memory finite
- **Definition:** $\alpha = \mathrm{slope}(\log n, \log F(n)), F(n) = RMS over all boxes of the residual of the profile Y_k = \sum_{j\le k}(x_j - \bar x) around a per-box linear fit$
- **References:** Peng, Buldyrev, Havlin, Simons, Stanley & Goldberger (1994), Physical Review E 49(2):1685-1689
- **Reference test:** nolds.dfa(overlap=False, order=1, fit_exp='poly') on windows divisible by every scale
- **Provenance:** Claude Code (claude-opus-5-5), WP1 session; specified by Research plan domain list (PI); 2026-10-30; reviewed by — (pending)

### generalized_hurst@1 — H(q): slope of log E|X(s+tau)-X(s)|^q on log tau (tau = 1..10) divided by q.

- **Signature:** `GeneralizedHurst_v1(Path, window: LongWindow, q: Moment) -> Real`
- **Parameters:** window ∈ {60, 90, 120, 180, 252}; q ∈ {1, 2}
- **Lookback (bars):** 60–252; earliest output at index lookback − 1
- **Missing data:** propagate
- **Invariances:** shift, scale; size weight 1; memory finite
- **Definition:** $K_q(\tau) = \langle|X_{s+\tau} - X_s|^q\rangle_s \propto \tau^{qH(q)}, H(q) = \mathrm{slope}(\log\tau, \log K_q(\tau))/q, \tau = 1..10$
- **References:** Barabasi & Vicsek (1991), Physical Review A 44(4):2730-2733; Di Matteo, Aste & Dacorogna (2003), Physica A 324(1-2):183-188
- **Reference test:** independent numpy implementation; fractional Brownian motion recovery
- **Provenance:** Claude Code (claude-opus-5-5), WP1 session; specified by Research plan domain list (PI); 2026-10-30; reviewed by — (pending)

### higuchi_fd@1 — Higuchi fractal dimension of the window's path, scales k = 1..kmax (1 smooth, 2 very rough).

- **Signature:** `HiguchiFd_v1(Path, window: LongWindow, kmax: Kmax) -> Real`
- **Parameters:** window ∈ {60, 90, 120, 180, 252}; kmax ∈ {4, 6, 8, 10}
- **Lookback (bars):** 60–252; earliest output at index lookback − 1
- **Missing data:** propagate
- **Invariances:** shift, scale; size weight 1; memory finite
- **Definition:** $L_m(k) = \frac{N-1}{\lfloor\frac{N-1-m}{k}\rfloor k^2}\sum_{i=1}^{\lfloor (N-1-m)/k\rfloor}|X_{m+ik} - X_{m+(i-1)k}|, L(k) = \overline{L_m(k)}, D = -\mathrm{slope}(\log k, \log L(k))$
- **References:** Higuchi (1988), Physica D 31(2):277-283
- **Reference test:** textbook implementation; antropy.higuchi_fd within tolerance; Brownian motion ~ 1.5
- **Provenance:** Claude Code (claude-opus-5-5), WP1 session; specified by Research plan domain list (PI); 2026-10-30; reviewed by — (pending)

### hurst_rs@1 — Slope of log mean R/S against log block size (blocks of 6-64 bars, at least 2 per scale).

- **Signature:** `HurstRs_v1(Series, window: LongWindow) -> Real`
- **Parameters:** window ∈ {60, 90, 120, 180, 252}
- **Lookback (bars):** 60–252; earliest output at index lookback − 1
- **Missing data:** propagate
- **Invariances:** scale; size weight 1; memory finite
- **Definition:** $H = \mathrm{slope}(\log n, \log \overline{R/S}(n)), R = range of the cumulative mean-deviations, S = population sd, averaged over non-overlapping blocks of length n$
- **References:** Hurst (1951), Transactions of the ASCE 116:770-799; Mandelbrot & Wallis (1969), Water Resources Research 5(5):967-988
- **Reference test:** nolds.hurst_rs(fit='poly', corrected=False, unbiased=False) on the reversed window
- **Provenance:** Claude Code (claude-opus-5-5), WP1 session; specified by Research plan domain list (PI); 2026-10-30; reviewed by — (pending)

## Statistical physics

### critical_slowing@1 — Lag-1 autocorrelation of |x| after removing a linear trend within the window.

- **Signature:** `CriticalSlowing_v1(Series, window: LongWindow) -> Real`
- **Parameters:** window ∈ {60, 90, 120, 180, 252}
- **Lookback (bars):** 60–252; earliest output at index lookback − 1
- **Missing data:** propagate
- **Invariances:** scale; size weight 1; memory finite
- **Definition:** $\rho_1 = \sum_{s} r_s r_{s-1} / \sum_s r_s^2, r = residuals of |x_s| on a linear time trend (demeaned), s in the window$
- **References:** Scheffer, Bascompte, Brock, Brovkin, Carpenter, Dakos, Held, van Nes, Rietkerk & Sugihara (2009), Nature 461:53-59; Dakos et al. (2012), PLoS ONE 7(7):e41010
- **Reference test:** statsmodels.tsa.stattools.acf on the detrended window
- **Provenance:** Claude Code (claude-opus-5-5), WP1 session; specified by Research plan domain list (PI); 2026-10-30; reviewed by — (pending)

### hill_tail_index@1 — Hill tail exponent of |x| from the top max(5, 10%) order statistics (smaller = heavier tail).

- **Signature:** `HillTailIndex_v1(Series, window: LongWindow) -> Real`
- **Parameters:** window ∈ {60, 90, 120, 180, 252}
- **Lookback (bars):** 60–252; earliest output at index lookback − 1
- **Missing data:** propagate
- **Invariances:** scale; size weight 1; memory finite
- **Definition:** $\hat\alpha = k / \sum_{i=1}^{k}(\log a_{(i)} - \log a_{(k+1)}), a_{(1)}\ge a_{(2)}\ge\dots the ordered |x_s|, k = \max(5, \lfloor 0.1 w\rfloor)$
- **References:** Hill (1975), Annals of Statistics 3(5):1163-1174; Gopikrishnan, Plerou, Amaral, Meyer & Stanley (1999), Physical Review E 60(5):5305-5316
- **Reference test:** independent numpy implementation; Pareto recovery
- **Provenance:** Claude Code (claude-opus-5-5), WP1 session; specified by Research plan domain list (PI); 2026-10-30; reviewed by — (pending)

### kramers_moyal_drift@1 — Kernel estimate of E[dz | z = z_t] for the z-scored path in the window (Gaussian kernel).

- **Signature:** `KramersMoyalDrift_v1(Path, window: LongWindow) -> Real`
- **Parameters:** window ∈ {60, 90, 120, 180, 252}
- **Lookback (bars):** 60–252; earliest output at index lookback − 1
- **Missing data:** propagate
- **Invariances:** shift, scale; size weight 1; memory finite
- **Definition:** $D^{(1)}(z_t) = \frac{\sum_s K_h(z_s - z_t)(z_{s+1} - z_s)}{\sum_s K_h(z_s - z_t)}, z = window z-scores, K_h Gaussian, h = 1.06 (w-1)^{-1/5}$
- **References:** Siegert, Friedrich & Peinke (1998), Physics Letters A 243(5-6):275-280; Friedrich, Peinke, Sahimi & Tabar (2011), Physics Reports 506(5):87-162
- **Reference test:** statsmodels KernelReg (local constant, Gaussian, fixed bandwidth)
- **Provenance:** Claude Code (claude-opus-5-5), WP1 session; specified by Research plan domain list (PI); 2026-10-30; reviewed by — (pending)

### tsallis_entropy@1 — Tsallis entropy S_q of the rolling histogram divided by its maximum (uniform distribution).

- **Signature:** `TsallisEntropy_v1(Hist, q: QEnt) -> Real`
- **Parameters:** q ∈ {0.5, 1.5, 2, 3}
- **Lookback (bars):** 1; earliest output at index lookback − 1
- **Missing data:** elementwise
- **Invariances:** none declared; size weight 1; memory finite
- **Definition:** $S_q/S_q^{\max} = \frac{1 - \sum_b p(b)^q}{1 - B^{1-q}}, \lim_{q\to1} = H/\log B$
- **References:** Tsallis (1988), Journal of Statistical Physics 52(1-2):479-487; Tsallis (2009), Introduction to Nonextensive Statistical Mechanics, Springer
- **Reference test:** closed form; q -> 1 limit equals normalised Shannon entropy (scipy.stats.entropy)
- **Provenance:** Claude Code (claude-opus-5-5), WP1 session; specified by Research plan domain list (PI); 2026-10-30; reviewed by — (pending)

## Spectral methods

### spectral_entropy@1 — Entropy of the normalised one-sided periodogram of the demeaned window, divided by log(#bins).

- **Signature:** `SpectralEntropy_v1(Series, window: Window) -> Real`
- **Parameters:** window ∈ {10, 15, 20, 30, 40, 60, 90, 120}
- **Lookback (bars):** 10–120; earliest output at index lookback − 1
- **Missing data:** propagate
- **Invariances:** scale; size weight 1; memory finite
- **Definition:** $H_s = -\sum_k \hat P(f_k)\log\hat P(f_k) / \log K, \hat P = periodogram / its sum, K frequencies$
- **References:** Powell & Percival (1979), Journal of Physics A 12(11):2053-2071; Inouye et al. (1991), Electroencephalography and Clinical Neurophysiology 79(3):204-210
- **Reference test:** antropy.spectral_entropy(method='fft', normalize=True) per window
- **Provenance:** Claude Code (claude-opus-5-5), WP1 session; specified by Research plan domain list (PI); 2026-10-30; reviewed by — (pending)

### spectral_slope@1 — GPH estimate of d: minus the slope of log I(w_j) on log(4 sin^2(w_j/2)), j = 1..floor(sqrt(w)).

- **Signature:** `SpectralSlope_v1(Series, window: LongWindow) -> Real`
- **Parameters:** window ∈ {60, 90, 120, 180, 252}
- **Lookback (bars):** 60–252; earliest output at index lookback − 1
- **Missing data:** propagate
- **Invariances:** scale; size weight 1; memory finite
- **Definition:** $\hat d = -\mathrm{slope}(\log(4\sin^2(\omega_j/2)), \log I(\omega_j)), \omega_j = 2\pi j/w, j = 1..\lfloor\sqrt w\rfloor, I the periodogram of the demeaned window$
- **References:** Geweke & Porter-Hudak (1983), Journal of Time Series Analysis 4(4):221-238
- **Reference test:** scipy.signal.periodogram + numpy.polyfit
- **Provenance:** Claude Code (claude-opus-5-5), WP1 session; specified by Research plan domain list (PI); 2026-10-30; reviewed by — (pending)

### ssa_trend_share@1 — lambda_1 / sum(lambda) of the 10-lag trajectory matrix of the centred path (trend dominance).

- **Signature:** `SsaTrendShare_v1(Path, window: LongWindow) -> Real`
- **Parameters:** window ∈ {60, 90, 120, 180, 252}
- **Lookback (bars):** 60–252; earliest output at index lookback − 1
- **Missing data:** propagate
- **Invariances:** shift, scale; size weight 1; memory finite
- **Definition:** $\sigma_1^2/\sum_i\sigma_i^2, \sigma_i the singular values of the L\times K Hankel matrix of the window's centred path, L = 10$
- **References:** Broomhead & King (1986), Physica D 20(2-3):217-236; Golyandina, Nekrutkin & Zhigljavsky (2001), Analysis of Time Series Structure: SSA, Chapman & Hall
- **Reference test:** numpy.linalg.svd of the explicit Hankel matrix (scipy.linalg.hankel)
- **Provenance:** Claude Code (claude-opus-5-5), WP1 session; specified by Research plan domain list (PI); 2026-10-30; reviewed by — (pending)

### wavelet_energy_share@1 — E_j / (E_1+..+E_4): Haar detail energy at level j over the last 16*floor(w/16) bars.

- **Signature:** `WaveletEnergyShare_v1(Series, window: LongWindow, level: WLevel) -> Real`
- **Parameters:** window ∈ {60, 90, 120, 180, 252}; level ∈ {1, 2, 3, 4}
- **Lookback (bars):** 60–252; earliest output at index lookback − 1
- **Missing data:** propagate
- **Invariances:** scale; size weight 1; memory finite
- **Definition:** $E_j = \sum_k d_{j,k}^2 (Haar DWT detail coefficients at level j), share = E_j / \sum_{i=1}^4 E_i$
- **References:** Mallat (1989), IEEE Trans. Pattern Analysis and Machine Intelligence 11(7):674-693; Percival & Walden (2000), Wavelet Methods for Time Series Analysis, Cambridge UP
- **Reference test:** pywt.wavedec(wavelet='haar', level=4)
- **Provenance:** Claude Code (claude-opus-5-5), WP1 session; specified by Research plan domain list (PI); 2026-10-30; reviewed by — (pending)

## Conventional technical-analysis terminals

| Terminal | Type | Lookback | Missing | Definition | Summary |
|---|---|---:|---|---|---|
| `bollinger_z_20@1` | Real | 20 | propagate | $(C_t - \mathrm{SMA}_{20})/\sigma_{20}$ | (close - SMA20) / SD20 (Bollinger %b in sd units) |
| `bollinger_z_50@1` | Real | 50 | propagate | $(C_t - \mathrm{SMA}_{50})/\sigma_{50}$ | (close - SMA50) / SD50 (Bollinger %b in sd units) |
| `breakout_high_20@1` | Bool | 21 | propagate | $\mathbb 1\{C_t > max(C_{t-20},\dots,C_{t-1})\}$ | close above the highest of the previous 20 closes |
| `breakout_high_55@1` | Bool | 56 | propagate | $\mathbb 1\{C_t > max(C_{t-55},\dots,C_{t-1})\}$ | close above the highest of the previous 55 closes |
| `breakout_low_20@1` | Bool | 21 | propagate | $\mathbb 1\{C_t < min(C_{t-20},\dots,C_{t-1})\}$ | close below the lowest of the previous 20 closes |
| `breakout_low_55@1` | Bool | 56 | propagate | $\mathbb 1\{C_t < min(C_{t-55},\dots,C_{t-1})\}$ | close below the lowest of the previous 55 closes |
| `ma_cross_10_50@1` | Real | 50 | propagate | $\log(\mathrm{SMA}_{10}/\mathrm{SMA}_{50})$ | log(SMA10 / SMA50) |
| `ma_cross_50_200@1` | Real | 200 | propagate | $\log(\mathrm{SMA}_{50}/\mathrm{SMA}_{200})$ | log(SMA50 / SMA200) |
| `ma_cross_5_20@1` | Real | 20 | propagate | $\log(\mathrm{SMA}_{5}/\mathrm{SMA}_{20})$ | log(SMA5 / SMA20) |
| `ma_gap_200@1` | Real | 200 | propagate | $\log(C_t/\mathrm{SMA}_{200}(C)_t)$ | log(close / SMA200) |
| `ma_gap_20@1` | Real | 20 | propagate | $\log(C_t/\mathrm{SMA}_{20}(C)_t)$ | log(close / SMA20) |
| `ma_gap_50@1` | Real | 50 | propagate | $\log(C_t/\mathrm{SMA}_{50}(C)_t)$ | log(close / SMA50) |
| `macd_hist@1` | Real | 209 | propagate | $M_t - \mathrm{EMA}_9(M)_t, M = \log(\mathrm{EMA}_{12}(C)/\mathrm{EMA}_{26}(C))$ | log(EMA12/EMA26) minus its EMA9 signal (truncated EMAs) |
| `roc_20@1` | Real | 21 | propagate | $\log(C_t/C_{t-20})$ | 20-bar log return (momentum) |
| `roc_5@1` | Real | 6 | propagate | $\log(C_t/C_{t-5})$ | 5-bar log return (momentum) |
| `roc_60@1` | Real | 61 | propagate | $\log(C_t/C_{t-60})$ | 60-bar log return (momentum) |
| `rsi_14@1` | Real | 113 | propagate | $100\,\bar U/(\bar U + \bar D), Wilder averages (\alpha = 1/n) of up/down close changes$ | Wilder RSI(14), smoothing truncated after 112 bars |
| `rsi_28@1` | Real | 225 | propagate | $100\,\bar U/(\bar U + \bar D), Wilder averages (\alpha = 1/n) of up/down close changes$ | Wilder RSI(28), smoothing truncated after 224 bars |
| `rsi_7@1` | Real | 57 | propagate | $100\,\bar U/(\bar U + \bar D), Wilder averages (\alpha = 1/n) of up/down close changes$ | Wilder RSI(7), smoothing truncated after 56 bars |
| `stoch_k_14@1` | Real | 14 | propagate | $100(C_t - \min_{14} C)/(\max_{14} C - \min_{14} C)$ | stochastic %K(14) on closes |
| `stoch_k_28@1` | Real | 28 | propagate | $100(C_t - \min_{28} C)/(\max_{28} C - \min_{28} C)$ | stochastic %K(28) on closes |
| `volatility_20@1` | Real | 21 | propagate | $\mathrm{sd}(r_{t-20+1},\dots,r_t)$ | sd of the last 20 log returns |
| `volatility_60@1` | Real | 61 | propagate | $\mathrm{sd}(r_{t-60+1},\dots,r_t)$ | sd of the last 60 log returns |

References: Allen & Karjalainen (1999), Journal of Financial Economics 51(2):245-271; Appel (2005), Technical Analysis: Power Tools for Active Investors, FT Prentice Hall; Bollinger (2001), Bollinger on Bollinger Bands, McGraw-Hill; Donchian (1960), Commodity Year Book; channel breakout; Lane (1984), Technical Analysis of Stocks & Commodities 2(3); Murphy (1999), Technical Analysis of the Financial Markets, New York Institute of Finance; Wilder (1978), New Concepts in Technical Trading Systems, Trend Research

## Conventional directional-change terminals

| Terminal | Type | Lookback | Missing | Definition | Summary |
|---|---|---:|---|---|---|
| `dc_age_10@1` | Real | 252 | elementwise | $t - t_{EP}, DC threshold \theta = 0.01$ | DC (theta = 1.0%): bars since the extreme point that started the current trend; state machine restarted on the last 252 bars. |
| `dc_age_20@1` | Real | 252 | elementwise | $t - t_{EP}, DC threshold \theta = 0.02$ | DC (theta = 2.0%): bars since the extreme point that started the current trend; state machine restarted on the last 252 bars. |
| `dc_age_40@1` | Real | 252 | elementwise | $t - t_{EP}, DC threshold \theta = 0.04$ | DC (theta = 4.0%): bars since the extreme point that started the current trend; state machine restarted on the last 252 bars. |
| `dc_age_5@1` | Real | 252 | elementwise | $t - t_{EP}, DC threshold \theta = 0.005$ | DC (theta = 0.5%): bars since the extreme point that started the current trend; state machine restarted on the last 252 bars. |
| `dc_event_10@1` | Bool | 252 | elementwise | $\mathbb 1\{t = t_{DCC}\}, DC threshold \theta = 0.01$ | DC (theta = 1.0%): a DC event (either direction) is confirmed at this bar; state machine restarted on the last 252 bars. |
| `dc_event_20@1` | Bool | 252 | elementwise | $\mathbb 1\{t = t_{DCC}\}, DC threshold \theta = 0.02$ | DC (theta = 2.0%): a DC event (either direction) is confirmed at this bar; state machine restarted on the last 252 bars. |
| `dc_event_40@1` | Bool | 252 | elementwise | $\mathbb 1\{t = t_{DCC}\}, DC threshold \theta = 0.04$ | DC (theta = 4.0%): a DC event (either direction) is confirmed at this bar; state machine restarted on the last 252 bars. |
| `dc_event_5@1` | Bool | 252 | elementwise | $\mathbb 1\{t = t_{DCC}\}, DC threshold \theta = 0.005$ | DC (theta = 0.5%): a DC event (either direction) is confirmed at this bar; state machine restarted on the last 252 bars. |
| `dc_overshoot_10@1` | Real | 252 | elementwise | $(\log P_t - \log P_{DCC})/\log(1+\theta), DC threshold \theta = 0.01$ | DC (theta = 1.0%): move since the last DC confirmation, in units of theta; state machine restarted on the last 252 bars. |
| `dc_overshoot_20@1` | Real | 252 | elementwise | $(\log P_t - \log P_{DCC})/\log(1+\theta), DC threshold \theta = 0.02$ | DC (theta = 2.0%): move since the last DC confirmation, in units of theta; state machine restarted on the last 252 bars. |
| `dc_overshoot_40@1` | Real | 252 | elementwise | $(\log P_t - \log P_{DCC})/\log(1+\theta), DC threshold \theta = 0.04$ | DC (theta = 4.0%): move since the last DC confirmation, in units of theta; state machine restarted on the last 252 bars. |
| `dc_overshoot_5@1` | Real | 252 | elementwise | $(\log P_t - \log P_{DCC})/\log(1+\theta), DC threshold \theta = 0.005$ | DC (theta = 0.5%): move since the last DC confirmation, in units of theta; state machine restarted on the last 252 bars. |
| `dc_total_move_10@1` | Real | 252 | elementwise | $(\log P_t - \log P_{EP})/\log(1+\theta), DC threshold \theta = 0.01$ | DC (theta = 1.0%): move since the extreme that started the trend, in units of theta; state machine restarted on the last 252 bars. |
| `dc_total_move_20@1` | Real | 252 | elementwise | $(\log P_t - \log P_{EP})/\log(1+\theta), DC threshold \theta = 0.02$ | DC (theta = 2.0%): move since the extreme that started the trend, in units of theta; state machine restarted on the last 252 bars. |
| `dc_total_move_40@1` | Real | 252 | elementwise | $(\log P_t - \log P_{EP})/\log(1+\theta), DC threshold \theta = 0.04$ | DC (theta = 4.0%): move since the extreme that started the trend, in units of theta; state machine restarted on the last 252 bars. |
| `dc_total_move_5@1` | Real | 252 | elementwise | $(\log P_t - \log P_{EP})/\log(1+\theta), DC threshold \theta = 0.005$ | DC (theta = 0.5%): move since the extreme that started the trend, in units of theta; state machine restarted on the last 252 bars. |
| `dc_trend_10@1` | Regime | 252 | elementwise | $\pm1 = direction of the last confirmed DC event, DC threshold \theta = 0.01$ | DC (theta = 1.0%): +1 after an upturn confirmation, -1 after a downturn (unknown before any); state machine restarted on the last 252 bars. |
| `dc_trend_20@1` | Regime | 252 | elementwise | $\pm1 = direction of the last confirmed DC event, DC threshold \theta = 0.02$ | DC (theta = 2.0%): +1 after an upturn confirmation, -1 after a downturn (unknown before any); state machine restarted on the last 252 bars. |
| `dc_trend_40@1` | Regime | 252 | elementwise | $\pm1 = direction of the last confirmed DC event, DC threshold \theta = 0.04$ | DC (theta = 4.0%): +1 after an upturn confirmation, -1 after a downturn (unknown before any); state machine restarted on the last 252 bars. |
| `dc_trend_5@1` | Regime | 252 | elementwise | $\pm1 = direction of the last confirmed DC event, DC threshold \theta = 0.005$ | DC (theta = 0.5%): +1 after an upturn confirmation, -1 after a downturn (unknown before any); state machine restarted on the last 252 bars. |

References: Glattfelder, Dupuis & Olsen (2011), Quantitative Finance 11(4):599-614; Guillaume, Dacorogna, Dave, Muller, Olsen & Pictet (1997), Finance and Stochastics 1(2):95-129; Kampouridis & Otero (2017), Expert Systems with Applications 73:145-160; Long, Kampouridis & Kanellopoulos (2022), PPSN XVII, LNCS 13399:33-47

