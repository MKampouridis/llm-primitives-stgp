# Decisions and assumptions

Every assumption and design choice made while building the code base, in the order made. The research plan (`docs/research_plan.md`) is authoritative; where an entry departs from it or fills a gap, it says so.

Status: **Decided** = agreed with the PI. **Provisional** = engineer's default, open for review. **Open** = needs a decision before the work package named.

---

## WP1 (from 30 Oct 2026)

### D-001 Repository location — Decided; layout superseded by D-032
The git repository is a local clone at `~/code/llm-primitives-stgp`, outside Box; the private GitHub repository is the code backup. The Box project folder keeps the plan, survey and notes, and receives generated reports (`reports/wp1/`) and results (`results/`) through paths in `config/paths.toml`.
*Why:* Box Drive syncs files while git rewrites `.git` (index, refs, packs), which can corrupt the repository or leave conflict copies; Box would also sync `.venv` and caches.

### D-002 Arm 6 (expert-written control) provenance — Decided
The WP1 seed library is written by Claude Code (`claude-opus-5-5`) in an interactive session, without API calls, and serves as arm 6. It is described as **expert-specified, AI-assisted, expert-verified**. Each operator contract records its provenance; the PI's review time per operator is logged in `docs/arm6_review.md` and is arm 6's "human effort" for H2a. The arm-3 authoring prompts in WP3 must contain only the domain list and the contract specification, never this code.
*Departure from the plan:* Method §1 says the seed library is LLM-written, and arm 6 is "expert-written versions of arm 3's operators". Both wordings need updating in the plan.

### D-003 Python and tooling — Decided (plan approval)
CPython 3.12 managed by uv; `requires-python >= 3.12`. The brief asks for 3.11+; 3.12 is the minimum because the test-only reference libraries nolds 0.6.3 and PyWavelets 1.10 need it. Only uv-managed interpreters are used (`python-preference = "only-managed"`; currently 3.12.16), so the local build matches CI and never picks up the Anaconda or Homebrew Python. pytest (+ xdist, Hypothesis) and ruff (lint and format). uv installed with Homebrew. All versions are pinned in the committed `uv.lock`.

### D-004 Continuous integration — Decided (plan approval)
GitHub Actions on every push and pull request: Ubuntu, Python 3.12, `uv sync --locked`, ruff lint and format checks, the hygiene check, and `pytest -m "not realdata"`. Tests never call the network. Tests that need the local Tier A data carry the `realdata` marker and are skipped in CI, where synthetic data stand in. One BLAS/numba thread per process.

### D-005 Data and secrets never enter git — Decided
`.gitignore` excludes data, results, reports, caches, `.env*`, keys and credentials, and `config/paths.toml`. `scripts/check_hygiene.py` (run by the `.githooks/pre-commit` hook and in CI) rejects data file types, files over 512 KB (except `uv.lock`) and secret-like strings. Secrets are read from the environment only; WP1 needs none.

### D-006 Commit identity — Provisional
Commits use the machine's global git identity. Change with a repo-local `git config user.email` if an institutional identity is preferred.

### D-007 Licence — Open (before the repository is made public)
No licence file yet; the plan defers the choice to submission or preprint time. DEAP is LGPL-3.0, which allows use as an imported dependency.

### D-008 Walk-forward periods — Decided (plan approval); dates provisional until the LLMs are chosen
Rolling periods with a 1-year step: train 3 years = fit 2 years + validation 1 year (the last year of train); test 1 year. Anchored in July so that the provisional post-cutoff test year (2025-07 to 2026-06) is the last regular period: 18 periods, P01 fit 2005-07-01, validation 2007-07-01, test 2008-07-01 to 2009-06-30, …, P18 test 2025-07-01 to 2026-06-30 (`config/settings.toml`, `src/lpstgp/splits.py`). One period's test year is the next period's validation year.

### D-009 Lookback cap and eligibility — Provisional
L_max = 504 bars is the largest lookback any rule may have (enforced in generation and variation). An (instrument, period) pair is eligible when there are at least 504 valid bars before the fit start and at least 95% of the expected sessions in [fit start, test end) are present. Eligibility uses availability only, never values.

### D-010 Schema v1 and causal adjustment — Decided (plan approval)
One zstd Parquet file per instrument with `date`, raw `open/high/low/close`, `volume` and event columns `dividend` (cash per share, ex-date) and `split` (ratio), plus JSON metadata (source, symbol, calendar, raw-file checksums, code version). Prices are stored raw; "adjusted" series are computed at read time, causally: the total log return of a bar uses that bar's events and the previous valid close, and the log-price path adds the cumulative event adjustment since the read start. Events on an invalid bar are carried to the next valid bar. Back-adjusted vendor series are avoided because back-adjustment rewrites past prices when later events occur. Exception: Yahoo split-adjusts its raw prices; that adjustment is multiplicative, i.e. a constant shift of the log price, so the invariance gate (D-020) makes it harmless. One row group per calendar month: with month-aligned horizons, row groups after a horizon are pruned by their statistics and never read.

### D-011 Structural validation only — Decided
Write-time checks are row-local: sorted unique dates; a missing or non-positive close invalidates the bar (prices set to NaN, flagged); inconsistent open/high/low are dropped while the close is kept (flagged); negative volume or dividends are removed (flagged). No cleaning uses statistics of other rows, so building from raw data cut at any date reproduces the earlier rows bit for bit (tested).

### D-012 Pilot data sources — Decided (pilot only; not for the final results)
Free sources are used for the Tier A pilot only.
- **Stooq** is excluded: CSV downloads have needed an API key behind a captcha since about March 2026 and a browser check since about June 2026.
- **FRED** is not used: its key-less CSV endpoint now fails for scripted clients (HTTP/2 stream errors or hangs), and its API needs a key.
- **FX** comes from the ECB euro reference rates (official, from 1999-01-04, no key). USD pairs are ratios of two EUR rates on the same date.
- **Energy spot** comes from the EIA daily history files (official; the same data FRED mirrors).
- **Indices, metal futures and bond ETFs** come from Yahoo Finance (yfinance 1.7, `auto_adjust=False`, actions on).
- **Crypto** comes from the Bitstamp and Coinbase public APIs.

Raw files are immutable and checksummed; every download is in an append-only `manifest.csv` (source, symbol, query, UTC time, file, bytes, sha256, rows, date range, tool version). Downloads stop at the design end (2026-06-30). EIA files cannot be range-limited, so later rows are dropped at build. Yahoo's terms describe its data as for personal use: raw data are never redistributed.

Known issues:
- Yahoo indices are price, not total-return, indices.
- Yahoo continuous futures are unadjusted front-month splices, so roll days carry a spurious return.
- Yahoo FX highs and lows are unreliable.
- ECB rates are a 14:15 CET fixing, not a close.
- EIA spot is close-only; WTI printed a negative price on 2020-04-20, which is marked invalid.
- Crypto prices are exchange-specific (UTC days, outages appear as gaps); Coinbase XRP has a 2021–2023 suspension.
- Close times differ across markets.

### D-013 Tier A universe and proxies — Provisional (pilot)
31 instruments:
- 10 equity indices (US 2, Europe 3 — SMI, DAX, CAC 40 —, UK 1, Japan 1, Asia 3);
- 8 FX pairs;
- 6 commodities;
- 2 government bonds;
- 5 crypto.

Roll-free proxies replace continuous futures where a free one exists:
- WTI, Brent and Henry Hub gas use EIA spot. This removes the largest roll gaps.
- US 10Y and 30Y futures are proxied by the IEF and TLT ETFs (total return via distribution events).
- No free daily Bund price history was found: Yahoo has no Bund futures and returned no data for the S&P Euro-Bund total-return index (`^SPEUBDTR`), Stooq is blocked, and the Bundesbank publishes yields, not prices. Tier A therefore has 2 bond instruments (the plan allows 2–3); a Bund future should come from the vendor data.

Gold, silver and copper stay on COMEX continuous futures, because FRED dropped LBMA spot and no other free roll-free daily history was found; their roll jumps are counted in the data report. Continuous futures and ETFs are downloaded as alternates for comparison. The Swiss SMI replaced the Euro Stoxx 50 as primary because Yahoo's Euro Stoxx 50 history starts only in 2007-03 (eligible P05–P18 instead of P01–P18); it is kept as an alternate. EIA's WTI spot history has real gaps (113 missing sessions in 2003, 67 in 2004, 48 in 2005, 25 in 2006, 40 in 2011), so WTI is eligible from P02 only; the roll-free spot series is still preferred to the continuous future. With these sources, 496 (instrument, period) pairs are eligible (25 instruments in P01 rising to 31 from P15). SOL was replaced by BCH because SOL's exchange history cannot cover warm-up plus one period. Per-instrument base costs are in `config/universe_tierA.toml` (broker-spread model v1, provisional; see the backtester entry).

### D-014 Close-only terminals in Tier A; native crypto calendar — Decided (plan approval)
Every Tier A primitive set uses close-derived streams only (log price, log return, |log return|), because ECB and EIA series have no OHLC and Yahoo FX highs and lows are unreliable. OHLC and volume are stored where available. Crypto keeps its 7-day UTC calendar; windows count bars, so a 252-bar window spans about 8 months for crypto.

### D-015 Tier B — Decided (interface only in WP1)
WP1 provides the selection rule and the loader interface only; no data are downloaded.
- **Source:** the final source must be survivorship-free, with point-in-time constituents and market caps, delisted names and delisting returns (e.g. WRDS/CRSP + Compustat Global, Refinitiv, Bloomberg), to be provided by the PI. Credentials come from the environment only.
- **Selection rule:** per market, the 25 largest primary-listed common equities by USD market cap as of the last session before the selection date; one share class per issuer (the largest); ties broken by security id; names delisted later stay selected.
- **Modes:** `once` (selection at the sample start) and `per_period` (point-in-time re-selection at every fit start) are both implemented. Which one to use is open for WP2.
- **Markets (provisional):** US; Europe ex-UK (14 countries); UK; Japan/Asia = JP, HK, KR, SG, TW. The Japan/Asia composition is open for WP2.

### D-016 Tier C — Open (awaiting data)
A manifest-driven loader (`tierC/manifest.toml`) maps each Essex DC-GP or ActTrade dataset to schema v1, keeps extra columns (e.g. sentiment) and the published splits, and checksums the files. `tierC/` was empty when WP1 was built.

### D-017 What "never look at test-period data" means in WP1 — Decided (plan approval)
Test years are period-relative (P01's test year is P02's validation year). The data layer necessarily touches all dates: download, storage, the causal-build test and the data reports. These compute availability and integrity counts only. No prices, returns, plots or performance from any date are inspected. Every modelling computation (gates on real data, smoke test, calibration, fitness, timing) uses FIT or VALIDATE sandboxes, never TEST.

### D-018 Leakage enforcement — Decided
- `DataStore.read(instrument, start, horizon)` is the only route from disk to modelling code. It returns owned, read-only copies of rows in [start, horizon) only.
- A `Sandbox(period, stage)` holds exactly 504 warm-up bars before the fit start plus the bars before its horizon:
  - FIT: horizon = validation start;
  - VALIDATE: horizon = test start;
  - TEST: sealed, raises `SealedPeriodError` (WP4 will add a sealed evaluator that requires a frozen, hashed rule).
- Sandboxes hold no reference to the store and log every read for the run record.
- Tests enforce it:
  - poisoned-future canaries (garbage after the horizon leaves every value bit-identical);
  - FIT is a prefix of VALIDATE;
  - the causal-build test;
  - a static import policy (operators, GP and backtest code cannot import the data layer or any I/O module).
- Caches are keyed by period, stage and horizon, and are never sliced from a longer horizon.

### D-019 Semantic types and Kleene logic — Decided (plan approval)
- **Types.** Series (increments), Path (levels), Hist (rolling distribution on 16 fixed bins), Real (scale-free feature), Bool and Regime. All are float arrays aligned with the bars.
- **Kleene logic.** Bool is three-valued: unknown (NaN) propagates through Kleene's strong logic; an unknown entry or exit means no action. AND/OR are written as explicit truth tables, since `np.minimum` and `np.fmin` are not Kleene.
- **Parameters** are typed terminals on fixed grids rather than ephemeral constants, so every rule is enumerable and reproducible.
- **No free real-valued constants.** Thresholds are adaptive operators (rolling percentile, mean + k·sd), plus fused self-threshold primitives (`ExceedsQuantile`, `ExceedsKSd`). The fused ones avoid duplicating a feature subtree, which would otherwise bias the size penalty against multi-node cross-domain features.

### D-020 Operator contract, versions and admission gates — Decided (plan approval); thresholds provisional
**Contract.** Each primitive is a contract (`OperatorSpec` or `TerminalSpec`) with:
- name, integer version and domain;
- semantic input/output types;
- parameters with legal grids;
- lookback L (output at t depends only on t−L+1..t) and earliest availability;
- missing-data policy (propagate, min-valid fraction, elementwise);
- declared invariances, size weight and memory class;
- LaTeX definition, references and the reference implementation used in tests;
- provenance and the implementation.

**Versions.** There is one file per operator version (`{name}__v{n}.py`). Once `registry.lock.toml` is created at the library freeze (end of M4), a contract's code (its module plus every lpstgp module it imports) may not change; a modification must be a new version.

**Admission gates.** These are tests parametrised over every operator, using the grid extremes plus one random parameter combination:
1. compiles and passes the source policy (allowed imports only, no I/O, no `eval`/`exec`, no global RNG, no numba `fastmath`/`parallel`);
2. type-correct output;
3. finite (≥ 99% of bars whose inputs are defined, after warm-up) and non-constant, on seeded synthetic GARCH data in CI and on real P01 data locally;
4. deterministic, including across a fresh process with different BLAS threads and hash seed;
5. prefix-invariant, bit for bit, under adversarial appended bars (spikes, NaN blocks, constants, sharp reversals, regime shifts, a NaN at the cut);

plus an exact declared-lookback check (garbage before the window changes nothing) and the declared invariances. Every Path consumer must be shift-invariant, because the log-price level depends on adjustments since the read start.

### D-021 Numerical kernels — Decided
Rolling statistics are computed from each window's own values (never running sums), so prefix invariance and window locality hold bit for bit. numba is used without `fastmath` (which may drop NaN checks) or `parallel` (order-dependent reductions); parallelism is across runs, one thread each. The numba cache lives in `__pycache__` inside the local, git-ignored clone. Rolling operators default to a minimum valid fraction of 0.9. Histograms use 16 bins on robust z-scores in [−4, 4] (trailing 252-bar median/MAD at t; outer bins absorb tails) with Jeffreys (+½) smoothing. All of these are provisional.

### D-022 Seed library composition — Decided (plan approval); deviations from the plan listed
- **Cross-domain operators.** 28, exactly 4 per domain (the plan's fixed quota):
  - information theory: ShannonEntropy, PermutationEntropy, LZCompressibility, LaggedMutualInfo;
  - information geometry: FisherRaoHist, FisherRaoGauss, FisherInformation, AlphaDivergence;
  - optimal transport: W1Hist, SinkhornDivergence, W2ToGaussian, TransportAsymmetry;
  - rough paths: LevyArea, ChordArea, PVariation, SignatureSimilarity;
  - fractal: HurstRS, DFA, HiguchiFD, GeneralizedHurst;
  - statistical physics: CriticalSlowing, KramersMoyalDrift, TsallisEntropy, HillTailIndex;
  - spectral: SpectralEntropy, SpectralSlope (GPH), WaveletEnergyShare, SSATrendShare.
- **Core.** 17 operators: RollingHist, PastHist, ToPath, Increments, RollingPercentile, MeanKSd, ExceedsQuantile, ExceedsKSd, Gt, Lt, CrossAbove, CrossBelow, And, Or, Not, QuantileRegime, RegimeIs.
- **Data terminals.** 3: log price, log return, |log return|.
- **Window changes against the plan's signatures.** HiguchiFD, CriticalSlowing and KramersMoyalDrift take `LongWindow` (60–252) instead of `Window`: Higuchi with kmax up to 10 needs well over 20 points, and lag-1 autocorrelation and kernel drift are unusable on 10 bars.
- **Rough-path operators.** All four standardise increments within their window, so they are scale- and shift-invariant.
- **Every cross-domain output is scale-free.** Path consumers are shift-invariant (D-020).

### D-023 Estimator conventions — Decided (documented in each contract and docs/operators.md)
- **R/S:**
  - population sd;
  - non-overlapping blocks of 6–64 bars with at least 2 per scale;
  - blocks aligned to the latest bar (the oldest remainder is dropped);
  - no Anis–Lloyd correction;
  - equals `nolds.hurst_rs` on the reversed window.
- **DFA-1:**
  - standard F(n) = RMS of the residuals over all boxes (Peng et al. 1994), as in nolds 0.6.3;
  - boxes of 6–64 bars, at least 4 per scale, aligned to the latest bar.
- **Higuchi:** the textbook formula. antropy's loop omits the last increment of each subsequence, so the two agree only to about 0.05.
- **Generalised Hurst:** τ = 1–10.
- **Hill:** k = max(5, 10% of the window).
- **Kramers–Moyal drift:** Nadaraya–Watson with a Gaussian kernel and Silverman bandwidth on window z-scores; "unknown" when every kernel weight underflows.
- **W2 to Gaussian:** exact closed form (per-atom integrals of Φ⁻¹ and (Φ⁻¹)²).
- **TransportAsymmetry:** sign(mean gain − mean loss) × W1(gains, losses) / mean |x|.
- **LZ76:** on within-window equal-frequency symbols, normalised by n / log_k n with k the distinct symbols (as antropy).
- **Lagged mutual information:** on within-window quartile symbols, divided by log 4.
- **Spectral entropy:** one-sided periodogram with scipy "density" weights (as antropy).
- **GPH:** m = ⌊√w⌋ frequencies.
- **Wavelet energy share:** Haar DWT, 4 levels, over the most recent 16⌊w/16⌋ bars.
- **SSA:** embedding dimension 10; only eigenvalues of the lag-covariance matrix are used, so results are deterministic.

### D-024 Sinkhorn divergence — Decided; departs from the plan's ε grid
- **Algorithm:** debiased Sinkhorn divergence (Feydy et al. 2019 objective), using kernel-domain scaling iterations. Each row has its own stopping rule (L1 marginal error < 1e-9, at most 10,000 iterations), so prefix invariance is exact.
- **ε grid:** changed from the plan's {0.05, 0.1, 0.5} to **{0.25, 0.5, 1.0}** squared z-units (bins are 0.5 wide).
- **Why:** log-domain iterations at ε ≤ 0.1 needed 1,000–6,000 iterations per row (35–93 s per 1,200-bar call).
- **Cost:** it is still the most expensive operator, at 0.16–0.87 s per call. Per-run memoisation computes it once per distinct subtree.

### D-025 Conventional terminals — Decided; departs from the plan in three places
**Technical analysis (23 terminals, close-only):**
- MAGap 20/50/200, MACross 5/20 10/50 50/200, ROC 5/20/60, RSI 7/14/28, StochK 14/28, BollingerZ 20/50;
- Donchian-style breakout high/low 20/55 (Bool), Volatility 20/60, MACD histogram (log EMA12/EMA26 minus EMA9).
- Williams %R and Donchian position are omitted: on closes alone they are affine maps of StochK.
- EMA/Wilder smoothers are truncated after 6×span / 8×n bars (at most 252) and renormalised. Memory is therefore finite and checkable; agreement with `ta`/pandas after warm-up is within 0.1 RSI points.

**Directional change (20 terminals):**
- Outputs: trend (Regime), event (Bool), overshoot, total move, age (Real).
- θ ∈ {0.5, 1, 2, 4}%. 0.25% was dropped from the plan's grid: it is below the daily noise of most instruments, and dropping it keeps the set at 20.
- The online state machine is restarted on each trailing 252-bar window, giving finite memory equal to the lookback. With θ ≤ 4% it re-synchronises well within a year.

### D-026 Version lock semantics — Decided
The lock hashes each contract's module, the lpstgp helper modules it imports, and a canonical fingerprint of the contract: types, parameter grids, lookbacks at the grid extremes, missing-data policy, invariances, memory, size weight and bin edges. The metadata modules (`types.py`, `contract.py`) are not hashed as text, so editing their documentation does not re-version every operator. The seed library was frozen at the end of M4 (30 Oct 2026). Review notes go to `docs/arm6_review.md`, not into code, for the same reason.

### D-027 Gate data and thresholds — Provisional
- **Synthetic gates:** seeded GARCH(1,1) with Student-t(5) shocks and alternating volatility regimes; the regime is applied outside the variance recursion, which keeps it stationary. Bars: 1,200. Cuts at 600 and 1,000. Appended tails of 1, 7 and 63 bars in five adversarial modes.
- **Real-data gate:** P01 VALIDATE sandboxes, scoring the fit and validation years (2005-07 to 2008-06), all before the first test year. All instruments with full warm-up then (crypto excluded). Pass if the output is finite on ≥ 99% of bars with defined inputs and non-constant on ≥ 90% of instruments.
- **Scoring change:** a single validation year was too short for rare-event booleans at extreme thresholds (e.g. `ExceedsKSd(252, k = 2)`).
- **Kleene crossovers:** AND(false, unknown) = false, so "a is not above b now" rules out a cross even when the previous bar is unknown.

### D-028 Backtest conventions and cost model — Decided (plan approval); cost levels provisional
- **Rule semantics** (long-only):
  - flat → long when entry = 1 and exit ≠ 1 (an unknown exit does not block an entry);
  - long → flat when exit = 1;
  - an unknown entry or exit means no action;
  - flat and inactive before its first scored bar.
- **Execution:** the position held over bar t is the decision of bar t − 1 (`execution_lag = 1`: trade at the signal bar's close, earn the next close-to-close return). `execution_lag = 2` (next close) is available for robustness. The primary lag is an open question for WP2.
- **Returns and costs:**
  - simple returns from point-in-time total log returns;
  - a bar with an unknown return contributes 0, and the next valid return spans the gap;
  - costs are charged on every change of the held position (buy and sell rates may differ, e.g. UK stamp duty for Tier B), times a global multiplier (sensitivity sweep 0.5/1/2/3×).
- **Base one-way costs (broker-spread model v1, pilot):**

  | Asset class | One-way cost (bps) |
  |---|---|
  | Equity indices | 2 (HSI, KOSPI 3) |
  | FX majors | 1 (EURUSD, GBPUSD, USDJPY) |
  | Other FX | 1.5 |
  | WTI, Brent | 3 |
  | Natural gas | 8 |
  | Gold | 2 |
  | Silver, copper | 4 |
  | Bond ETFs | 1 |
  | Crypto | 10 |

  These are engineering assumptions in line with typical institutional spreads plus commissions. They should be replaced by contemporaneous spreads where available (the engine accepts per-bar cost arrays).
- **Metrics:**
  - Sharpe and Sortino annualised with 252 (business calendar) or 365 (crypto) periods; a series with no variation has Sharpe 0;
  - maximum drawdown of compounded equity;
  - Calmar;
  - total and annualised return;
  - annualised one-way turnover (position changes per year), number of entries, exposure.

### D-029 STGP implementation — Decided (plan approval); parameters provisional
- **What DEAP 1.4.4 is used for:** only the typed primitive registry (`PrimitiveSetTyped`) and prefix-list trees.
- **Own components**, all driven by one seeded `random.Random` and iterating ordered lists only, so a seed reproduces a run bit for bit across processes (tested in a fresh process):
  - the generator: aware of minimum depth and the lookback budget, never fails;
  - homologous crossover: entry×entry or exit×exit; 90% internal points; never at parameter leaves; the second point is drawn among same-type nodes in tree order;
  - mutation: subtree 0.5, point 0.2, parameter 0.2, shrink 0.1;
  - tournament selection, elitism and the hall of fame.
- **Why own components:** DEAP's typed generator fails when a type has no terminal at the depth limit, and `cxOnePoint` draws from an unordered set (DEAP issue #765).
- **Evaluation and storage:** trees are interpreted, never compiled with `eval`, and rules are stored as JSON lists of node names.
- **Constraints:** depth ≤ 12, ≤ 60 nodes per tree, lookback ≤ 504. Any offspring that violates one is replaced by its parent.
- **Defaults (`config/settings.toml`, placeholders for WP2):** population 500; 50 generations; tournament 5; elitism 5; crossover 0.8; mutation 0.2; ramped half-and-half with depth 2–5.
- **Hall of fame:** 10 members, deduplicated by identical fit-period signals. The final rule is the member with the best validation fitness (one rule per run).
- **Fitness (D-020, D-028):** calendar half-year segments (4 in the fit years, 2 in validation). Placeholder weights: λ_dd = 0.5 per unit of MDD/σ, λ_turnover = 0.005 per annual position change, λ_size = 0.01 per weighted node. Minimum exposure 10 bars per segment; no-trade value −1; lag 1; cost multiplier 1. The weights are to be set on named pilot periods in WP2 and then frozen.
- **Budget:** both requested evaluations (population × (generations + 1)) and unique evaluations (fitness-cache misses) are recorded; which one defines the matched budget is open for WP2.
- **Memoisation:** a subtree cache per run, stage and instrument, keyed by node sequence, LRU-capped at 512 MB per run. Cached outputs are read-only. Per-operator compute time is recorded.
- **Run records:** one compact JSON per run, containing:
  - configuration, and code and contract hashes;
  - the sandbox access log;
  - per-generation aggregates, including operator usage in the elite;
  - the hall of fame with fit and validation components;
  - timings, peak memory and environment.

  No populations are stored. Records go under `results_dir/tier<T>/<experiment>/`.
- **Orchestration:** `runner.py` is the only module that opens sandboxes and writes files. Parallel runs use spawned processes with one BLAS/numba thread each.

### D-030 Smoke test, calibration and projection method — Decided (WP1 deliverable); projection assumptions provisional
- **Smoke test (as specified):**
  - S&P 500 and EUR/USD on P01 (fit 2005-07 to 2007-06, validation 2007-07 to 2008-06; test year sealed);
  - seed library; population 200 × 10 generations; 2 seeds per asset; 4 parallel workers.
- **Calibration** (training and validation data only):
  - per-operator micro-benchmarks on P01 sandbox arrays;
  - the conventional library at smoke size;
  - a single-worker baseline;
  - 6 concurrent workers;
  - one full-budget run (population 500 × 50 generations).
- **Projection model:** core-seconds = Σ over GP configurations × eligible (instrument, period) pairs × 30 seeds × requested evaluations × cost per evaluation.
- **Cost per evaluation:**
  - central value from the full-budget run (warm caches); high value from the small-budget single-worker run (cold caches);
  - terminal-only configurations (arms 2a/2b/7b, GP-TA, DC-GP, ActTrade) scaled by the measured conventional/cross-domain ratio;
  - crypto scaled by its longer fit windows;
  - arms 4 and 7 get +5% evaluations for maintenance evidence and gates.
- **Hardware:** laptop throughput as measured with 6 workers; cluster nodes assumed at one M1 core's speed and 90% parallel efficiency.
- **Disk:** measured record sizes as a function of the number of generations.
- **Tier B:**
  - option 1: 100 stocks × 18 periods, one rule each;
  - option 2: 4 markets × 18 periods, each evaluation scoring 25 stocks.
- **Not projected:** LLM tokens and API time.
- **Cost sweep:** evaluating fixed rules at 0.5/1/2/3× costs is negligible; re-evolving at each level would multiply the affected arms by 4.
- **Where the results are:** `reports/wp1/smoke_and_projections.md` in the project folder; run records in `results/tierA/wp1_*`.

### D-031 Open questions for WP2 — Open
1. **Pilot periods.** Which periods are used for calibration (fitness weights, GP parameters) and for the February go/no-go? Proposal: P01–P02, excluded from the primary outcome.
2. **Execution lag.** Primary lag 1 (trade at the signal bar's close, current default) or 2 (next close)?
3. **Final-rule selection.** On validation (default; best of a 10-member hall of fame) or on fit? H3 uses the validation–test gap, which validation selection inflates.
4. **Budget unit.** Requested or unique evaluations? The STGP converges: in the full-budget run 17% of requested evaluations were new rules, so the two definitions differ in cost by about 5×. Consider diversity control or deduplication.
5. **Fitness.** Weights (λ_dd, λ_turnover, λ_size), minimum exposure, no-trade value and segment length; or NSGA-II instead.
6. **Cost sweep.** Re-evaluate fixed rules at 0.5/1/2/3× (default; negligible compute), or re-evolve at each level (×4 compute for the affected arms)?
7. **Portfolio aggregation for the primary outcome.** How to combine 5-day and 7-day calendars, instruments entering at different periods, and flat periods.
8. **Arm 3 protocol.** Free authoring from the domain list, or implementing arm 6's specification list (same mathematics, different author)? Which LLM(s), and therefore the post-cutoff test year.
9. **Arm 2c source.** This seed library (arm 6), or operators decomposed from the ~30 whole LLM strategies (a cleaner granularity comparison for RQ1)?
10. **Tier B.**
    - Vendor: WRDS/CRSP, Refinitiv or Bloomberg.
    - Selection mode: once vs per period.
    - Composition of "Japan/Asia".
    - One rule per stock vs one per market: same compute; pooling gives 25× fewer runs, run records and LLM maintenance cycles.
11. **Final cross-asset data (WP4).**
    - Vendor back-adjusted continuous futures instead of the pilot proxies (COMEX metals have roll gaps; no Bund; WTI spot has gaps that make it ineligible for P01).
    - Euro Stoxx 50 history before 2007, if it is wanted instead of the SMI.
12. **Compute.** The full Tier A design needs about 4,100 core-hours at 25k evaluations per run (central), and up to about 5× more under a unique-evaluation budget. Tier B needs about 3.6× Tier A. This is 1.5–7.5 days of a 128-core node for Tier A, versus 46+ days on this laptop, so a cluster allocation is needed from WP4.
13. **Sinkhorn divergence.** At 0.1–0.4 s per call it is the costliest operator. Keep it, restrict ε to {0.5, 1}, or replace it in a v2.
14. **Arm 6 review.** The PI should review the 45 seed-library contracts and log minutes in `docs/arm6_review.md`; the plan's Method §1 and arm-6 wording need updating (D-002).
15. **Tier C.** The Essex DC-GP and ActTrade datasets still need copying into `tierC/` with a `manifest.toml`.
16. **Licence.** Choose one before the repository is made public.

---

## Between WP1 and WP2 (31 Oct 2026)

### D-032 One project location — Decided (PI, 31 Oct 2026)
Everything lives in the repository folder `~/code/llm-primitives-stgp`, which supersedes the three locations of D-001.
- **Tracked in git:** code; the research plan and survey (`docs/research_plan.md`, `docs/survey.md`); the survey working notes (`docs/survey/`, renamed from the Box `research_notes/` and survey reports, contents checksum-verified); and generated reports (`reports/<wp>/`, small markdown). WP1 kept reports out of git; they are now versioned with the code that produced them.
- **Git-ignored subfolders:** `data/` (moved from `~/llm-primitives-stgp-data`; all 58 raw files re-verified against the manifest), `results/` (copied from Box) and `cache/`.
- **Paths:** `config/paths.toml` uses paths relative to the repository root. Working paths may not be inside a cloud-synced folder (enforced in `load_paths`).
- **Box** becomes a one-way backup mirror written only by `scripts/backup.py`, at milestones: docs, reports, results, raw data and manifests (processed Parquet is rebuilt from raw). Files that later change or disappear are moved to `_superseded/<timestamp>/` in the mirror, never deleted. The old Box `research_notes/` folder went to `_superseded/` once its copy was verified.
- **Claude Code:** sessions start in the repository folder. `CLAUDE.md` carries the standing rules of the WP1 brief, and the project memory moved to that folder's key.
- **Release:** the survey working notes are internal. Decide at release whether they go public (D-007).

*Why:* the PI asked for a single location. The repository folder is the only one that can hold code safely (D-001), and GitHub backs up everything tracked. The Box mirror protects what git cannot hold: free-source raw downloads, which providers revise, and run records.

### D-033 Review of related code bases — Decided (what is adopted); protocol items go to WP2
Reviewed on 31 Oct 2026, at the PI's suggestion:
- LLQ_CIFEr (andrewclayman, `dc4b9c7`): prompt, strategies, provenance, portfolio GA, harness;
- Evolutionary-Algorithms (MKampouridis, `0d7a480`);
- the Markdown documents of regime-fusion-gp (MKampouridis, `5786b99`; its code and results were not read).

**No code is ported.** Our harness already covers what these repositories implement, and each has conventions we must not copy (below).

**Adopted as engineering practice** (all Provisional; built in WP2):
1. `CLAUDE.md` with the standing rules (done).
2. **Seeds** derive from (instruments, period, run index) only, never from the arm or library, so arms are paired. Today the seed is the run index, which already pairs arms.
3. **Campaign machinery** (from regime-fusion-gp):
   - a planned task list that freezes digests of settings and data;
   - result files written atomically, with completed tasks skipped;
   - a `collect` step that refuses mixed settings;
   - a "pilot periods only" guard on top of the sealed test stage.
4. **Validation checkpoints** every 10 generations in validation-stage run records: the best individual's fit score, validation Sharpe and trades. Never used for selection. They inform the budget decision and H3's validation–test gap.
5. **Configuration register** from the first WP2 run. Every distinct configuration tried counts as a trial for the Deflated Sharpe Ratio.
6. **Long local runs:**
   - a free-disk guard (stop below 5 GB) and clean-up of worker processes;
   - runs under `caffeinate`;
   - laptop thermal throttling noted in the projections.
7. **Uniform execution** for whole LLM strategies: they must not shift their own signals; the harness applies `execution_lag`. In LLQ, 2 of 13 strategy files do not shift and 11 do.
8. **One Sharpe definition** everywhere: mean/sd × √periods. LLQ uses three.
9. **Content-keyed caches** only, which we already have. LLQ keys by `id(df)`.

**For the WP2 protocol (PI decision):**
1. **Protocol document first.** Write `docs/protocol.md` before any pilot run. For each D-031 item the pilot settles, it states the options, the data and the deciding rule, plus a pre-stated go/no-go rule.
2. **Confirmatory test.** The paired difference in equal-weight portfolio Sharpe, using a stationary block bootstrap of days with both arms resampled on the same days, Holm-adjusted. Per-unit Mann–Whitney tests become descriptive only, because units sharing a market year are not independent. regime-fusion-gp made this change after review, and LLQ's aggregate tests were borderline (mixed model p = 0.061) although its per-seed tests were significant.
3. **Aggregation.** Average the daily returns of all runs per (instrument, period), so no run is picked after the fact; then weight instruments equally (D-031 Q7).
4. **Execution lag 2** (next close), at least as a pre-registered robustness setting. ECB fixings and EIA spot prices are not tradable closes (D-031 Q2).
5. **GP parameter pilot** at equal budget, with a convergence rule:
   - candidates: populations × tournament sizes;
   - convergence: the first generation reaching 99% of the run's total rise;
   - choice: the cheapest candidate within 0.05 of the best;
   - data: training data only.

   regime-fusion-gp's pilot chose 2,000 × 40, i.e. 80,000 evaluations. 30 versus 50 runs per configuration is settled by a stability rule.
6. **Secondary analyses:** the Deflated Sharpe Ratio, the probability of backtest overfitting (CSCV), Hansen's SPA test against the best benchmark, and a random-entry null at the method's trade count.
7. **Fitness:** require a minimum number of round trips. The Essex GP requires 6 trades; our 10-bar minimum exposure admits one-trade rules (D-031 Q5).
8. **CERES:**
   - Sun Grid Engine arrays, at most 60 concurrent per array and about 250 per user;
   - about half the M1's per-core speed;
   - CentOS 7 with glibc 2.17: check that our lock installs (numba, pyarrow, roughpy wheels).

   At that speed, Tier A at 25k evaluations is about 7,800 core-hours (D-031 Q12).
9. **Tier B, if free data are ever used:**
   - check fractional "split" days, because Yahoo books spin-offs as splits and some ratios are wrong;
   - handle reused and renamed tickers;
   - freeze the draw once made.
10. **DC reference:** ask to reuse regime-fusion-gp's Java-derived DC fixtures as an extra reference test.

**Hazards in the related code bases** (relevant to the WP4 baselines):
- **LLQ's strategy design data overlap our test years.**
  - Its development and test years (2013–2024) overlap most of our test years, so its strategies are contaminated as a baseline everywhere except a post-cutoff year. Disclose this.
  - Its strategy pool was pruned on out-of-sample trade counts.
  - A legacy tuning path averages validation years that are other periods' test years.
- **LLQ portfolio GA:** three inconsistent descriptions.

  | Source | Crossover | Population | Tournament | Objective |
  |---|---|---|---|---|
  | code | two-point | 300 | 4 | portfolio Sharpe |
  | `GA_DESCRIPTION.md` | uniform | — | — | — |
  | pseudocode | — | 100 | 2 | Σ w·R |

  Ask the authors which is canonical. Re-implement it on our sandboxes and costs, starting from our warm-up: LLQ starts every slice cold, which is why one of its strategies never traded. Fit the allocator on FIT only if rules are selected on VALIDATE.
- **Evolutionary-Algorithms trading fitness:**
  - losses are never realised and open positions are excluded, so the per-trade Sharpe is always positive;
  - one task opens overlapping trades;
  - the "test" file is the validation file.

  Its settings are kept only as a reference for a Tier C replication: population 500 × 25 generations, depth 2–4, crossover 0.95, tournament 4, elitism 1, at least 6 trades.

**Where regime-fusion-gp differs from us:**
- **Execution:** it trades at the next open; we trade at the signal close.
- **Final rule:** it re-evolves on all four training years and keeps the final generation's best; we select on validation, which H3 needs.
- **Stock data:** it accepts free Yahoo stock data with the survivorship bias stated.
- **Tier C:** ActTrade's original datasets no longer exist.

---

## WP2 (from 31 Oct 2026)

Plan approved by the PI on 31 Oct 2026. The protocol (`docs/protocol.md`, draft 0.1) restates these entries operationally. D-031 items 1 (pilot periods), 8 (the model and the post-cutoff year; the arm-3 protocol stays open) and 9 (arm 2c's source) are resolved below.

### D-034 Pre-sample pilot periods and the WP2 data cap — Decided (PI, 31 Oct 2026)
**Pilot periods.**
- PL1: fit 2003-07→2005-06, validation →2006-06, test 2006-07→2007-06.
- PL2: one year later, test 2007-07→2008-06.
- Both have the primary structure, shifted before P01 (`[pilot]` in settings, `splits.pilot_periods`).
- 22 instruments are eligible in both. WTI and Brent fail coverage; bonds and crypto have too little history.

**Data cap.** Nothing on or after 2008-07-01 is read by modelling code in WP2:
- every modelling entry point gets its store from `data.store.modelling_store`, which caps reads at `[leakage] max_horizon`;
- `Sandbox.open` refuses horizons past the cap;
- a test checks that no other code constructs a `DataStore`.

**Pilot test years.** These are readable only through `Sandbox.open_pilot_test`, which requires:
- a pilot period, identified by all its dates, not just its id;
- a test year within the cap;
- a freeze manifest committed to git (`lpstgp.freeze`).

*Why:* all 18 primary test years stay untouched until WP4; the alternative (opening P01–P02 and dropping them from the primary analysis) would lose the 2008–09 test year. The real-data sandbox test now covers P01, PL1, PL2 and DEV only.

### D-035 Strategy generation by isolated headless Claude Code sessions — Decided (PI); details Provisional
LLQ-style generation:
- one `claude -p` session per strategy, on the PI's subscription;
- 28 strategies, 4 per domain;
- sessions within a domain run in order and must differ from the earlier accepted strategies.

**Isolation, refined during M0.** The approved plan gave the agent a sandboxed shell with wrapper commands. Instead, the agent has no shell at all. Its only tools are:
- the file tools, confined to its session folder by `--restricted`;
- two MCP tools served by our own stdio server (`strategies/mcp_devtool.py`): `check` and `backtest`.

The session also runs with `--strict-mcp-config`, `--disable-slash-commands`, `--permission-mode dontAsk`, a scrubbed environment with no API key and auto-update disabled, and a neutrally named folder under `~/Library/Caches/strategy-sessions/`, outside the repository so that no CLAUDE.md is above it. This removes any shell path to the network or the file system, and does not depend on how Claude Code's Bash sandbox treats reads.

**Pre-flight (31 Oct 2026).** Archived in `results/wp2/preflight/`, at an estimated cost of $0.12:
- the session's tools were exactly Read, Write, Edit, Glob, Grep and the two MCP tools;
- reads of `~/code/…`, `~`, and the parent folder were refused;
- there was no shell or web tool;
- no CLAUDE.md, memory or skills were loaded;
- every message came from `claude-opus-5-5`.
- **Disclosure:** Claude Code attaches the account e-mail address to the context.

**Agent's code.** It is never imported on the host. It runs only in a subprocess with a timeout under `sandbox-exec`, with no network and writes only to its job folder; tests show both blocks hold.

**Defaults, provisional until the M0 review:**
- effort `high`;
- 40 backtests and 100 checks per session;
- 1 repair turn plus 1 fresh re-run per failed slot.

### D-036 Model, post-cutoff window and development window — Decided (PI, 31 Oct 2026)
**Model.** `claude-opus-5-5` for all LLM arms (strategies now, operators in WP3).
- Anthropic documents its training-data and reliable-knowledge cutoffs as June 2026.
- Retirement is not before 22 Sep 2027.
- Every current model has the same cutoff. Opus 4.6 has reliable knowledge to May 2025 and training data to Aug 2025, but may retire from 5 Feb 2027.

**Post-cutoff window.** Consequently, P18 (2025-07→2026-06) is an ordinary period. The post-cutoff test is a separate window from 2026-07-01 to the latest data at the WP4 freeze, reported separately; the data download will be extended in WP4.

**Development window.** The generation agent's backtests see dev-fit only: 1995-07-01→2003-06-30, 21 instruments with ≥ 750 bars (10 indices, 8 FX, WTI, Brent, natural gas). Dev-holdout (2003-07-01→2005-06-30, 24 instruments) is scored once per final strategy and never shown to the agent. Both windows end before every pilot validation year.
- Instruments are anonymised (I01…, with asset class) and dates are not shown.
- *Limitation:* no metals, bonds or crypto in dev-fit.

### D-037 Arms run in WP2 — Decided (PI, 31 Oct 2026)
**Arm 1.** Per instrument, the strategy with the best validation F (`strategies.selection`), the score STGP's final selection uses.

**Arms 2a, 2b and 2c** are built by `strategies.adapters` from the frozen strategies:
- **2a:** entry and exit as Bool terminals, plus Kleene And/Or/Not.
- **2b:** signals at the strategy's own parameters as Real terminals, plus core glue (adaptive thresholds, comparators, logic, regimes; no histogram or path constructors, no data terminals).
- **2c:** the same signal functions as typed operators whose grid parameters the GP chooses, on the data terminals (log price, return, |return|), plus the same glue.

So 2c at the strategy's own parameters equals 2b (tested), and arms 1–2c share their mathematics (D-031 Q9).

**References.** Arm 6 (`seed`) and GP-TA (new library `technical`: data, core and the 23 TA terminals) run as references, plus buy-and-hold.

**Lookbacks.** Terminals and operators count lookback in price bars, adding 1 for return inputs.

### D-038 Whole-strategy contract and admission gates — Decided (plan approval)
**Contract.** `strategies/api.py` is copied into each session as `strategy_api.py`:
- 1–4 signals, `fn(inputs…, *, params…)`, with parameters on the GP's grids (a test asserts the grids are identical);
- a stateless rule giving entry/exit in {0, 1, NaN}, with no execution shift;
- metadata (hypothesis, definition, references, novelty, limitations);
- total lookback ≤ 504.

**Source policy** (`strategies/policy.py`). Stricter than WP1's operator policy, whose gaps it closes:
- numpy is importable only whole;
- no `numpy.random` or file functions under any name;
- no `rvs`, `random_state`, reflection, dunder access or global state.

**Behavioural gates** (`strategies/gates.py`):
- type and domain checks;
- runtime cap;
- determinism, also across processes with 1 and 4 threads;
- prefix invariance with joint price/return adversarial appends and a NaN at the cut;
- the declared lookback is an upper bound;
- shift invariance for price inputs.

**On development data:** the finite share is ≥ 0.99, and entries and exits fire on ≥ 50% of instruments.

**Freezing.** Frozen files are kept verbatim (excluded from ruff) and locked by sha256 with provenance (`strategies/registry.py`).

### D-039 Campaign machinery and analysis — Decided (plan approval); parameters Provisional
**Campaigns.** `lpstgp.campaign`:
- Plans freeze settings, data and library digests.
- Seeds come from sha256(instruments, period, run): equal across arms, hence paired.
- Runs whose record is complete and current are skipped.
- Records are written atomically; `run_many` stops below 5 GB free disk and terminates its workers on exit.
- `collect` builds `runs.parquet` and refuses mixed digests.
- Every configuration planned is appended once to `reports/configuration_register.csv`, which counts trials for the Deflated Sharpe Ratio.

**`run_gp` additions:**
- a unique-evaluation budget mode (`budget_unit`, `max_unique_evaluations`);
- validation checkpoints every 10 generations, recorded only and never used for selection.

**Analysis** (`lpstgp.analysis`):
- equal-weight portfolios that average all runs per instrument, on the union calendar with flat days;
- a paired stationary block bootstrap (Politis & Romano 1994);
- the Holm adjustment.

### D-040 Proposals awaiting the PI's M0 review — Resolved by D-041 (31 Oct 2026)
These are proposed in `docs/protocol.md`, marked [PI]:
1. **Execution lag:** 1 as primary with lag 2 as robustness, or the reverse.
2. **Effort:** `high`.
3. **Budget:** 40 backtests per session.
4. **Pilot runs:** 10 per configuration.
5. **Go/no-go rule:** GO unless 2c trails arm 1 by more than 0.2 Sharpe in both pilot years.
6. **Minimum activity:** 4 round trips per fit period.
7. **Calibration:** the rules in protocol §6.
8. **Confirmatory test:** the paired portfolio bootstrap instead of Mann–Whitney U.

### D-041 Resolution of the D-040 items — Decided (engineer, under the PI's delegation, D-042)
1. **Execution lag 2 as primary** (a condition true at bar t's close trades at bar t+1's close); lag 1 is the pre-registered robustness check. `settings.toml` now has `execution_lag = 2`.
   *Why:*
   - The data are close-only, and several are reference prices nobody can trade at: ECB fixings, EIA spot assessments, cash index levels.
   - Lag 2 equals LLQ's convention (compute at the close, execute on the next bar).
   - It handicaps every arm alike, so the arm comparisons stay fair.
   - regime-fusion-gp's next-open convention lies between lag 1 and lag 2 and needs open prices, which are missing.
2. **Minimum activity: at least 2 entries per year of data in the scored window**, rounded to the nearest whole entry (4 in a 2-year fit, 2 in a validation year). Fewer entries score the no-trade value (`min_entries_per_year = 2.0`).
   *Why:* a fit or a selection must not rest on one or two lucky trades. Long-only trend rules typically trade more often than this. The value is fixed a priori, not tuned. It also applies to arm 1's selection and to the generation agent's objective (stated in the brief).
3. **Generation settings:** effort `high` and 40 backtests per session, as proposed.
   *Why:* this makes arm 1 a serious competitor without an unlimited search. LLQ used 60 backtests on one instrument; ours are richer (21 instruments).
4. **10 runs per configuration in the pilot**, averaged per instrument.
5. **Go/no-go.** GO if the paired difference in pooled two-year pilot portfolio Sharpe (2c − arm 1) is at least −0.2. This is a non-inferiority rule on the point estimate, reported with bootstrap confidence intervals.
   *Why:* the gate asks whether primitives are competitive before WP3 is built; it is not the confirmatory test. A one-year Sharpe has a standard error of about 1, so the draft's "both years" rule would mostly track noise.
6. **Calibration rules as in protocol §6.** The 30-versus-50-runs study moves to the start of WP4, which is the only place it matters, and saves about 35 core-hours now.
7. **Confirmatory test: the paired stationary block bootstrap of portfolio returns**, Holm-adjusted within each research question. Per-unit Mann–Whitney U with Holm becomes descriptive.
   *Departure from the research plan.* Units that share a market year are not independent, so per-unit tests overstate the evidence (D-033).

### D-042 Delegation and consultation — Decided (PI, 31 Oct 2026)
**Delegation.** The PI delegates scientific decisions to the engineer, who acts "as an experienced professor": decides, records the reasoning here, and reports.

**Consultation.** The PI is consulted on non-scientific decisions, in particular:
- connecting to CERES or other infrastructure;
- any use of the paid Anthropic API.

**API budget.** API credit is **$60 per month**, so the API is used only with the PI's agreement and within that budget.

**Subscription work.** Strategy generation runs on the PI's Claude subscription through headless Claude Code (D-035) and uses no API credit.

### D-043 CERES access to the code: deploy key, repository stays private — Decided (PI, 31 Oct 2026)
**Code.** CERES gets the code by `git clone`/`git pull` with a read-only deploy key for this repository only:
- the key pair is generated on CERES and never stored in the repository;
- registering the public half on GitHub needs the PI's approval.

**Data and results.** These never go through git (D-005); they move by rsync from and to the laptop.

**Visibility.** The repository stays private until the preprint, as the research plan agreed. It will then be released with a licence and a curated history (D-007, D-032).

*Why:* a public repository now would irreversibly expose:
- the design before publication;
- the internal survey notes and decision log;
- the personal e-mail in commit metadata;

and it has no licence yet. A deploy key gives CERES the same convenience. Fallback if CERES cannot reach GitHub: rsync the repository with its history.

### D-044 Generation pacing and usage limits — Decided (PI, 31 Oct 2026)
**Pacing.** Strategy generation runs one session at a time on the PI's subscription, leaving headroom for interactive work.

**Usage limits.**
- At 10:40 the sessions hit the subscription's 5-hour limit; the notice also mentioned the organisation's monthly spend limit, which the PI is checking.
- Sessions s03 and s07 were interrupted and later resumed in the same conversations.
- Usage-limit notices (model `<synthetic>`) are not counted as a model change.
- A limit stop waits until the reset time stated in the notice, and is not a failure.
- Session state is saved after every run, so the driver can be restarted.
- Costs are reported as each session's cumulative estimate.

### D-045 Repository made public — Decided (PI, 1 Nov 2026)
The PI made the GitHub repository public for convenience. This supersedes D-043's visibility and deploy-key parts: CERES clones over HTTPS without a key (`docs/CERES.md` §2).

Unchanged:
- data, results and caches still never go through git (D-005), and move by rsync;
- frozen strategies, decisions and reports are now visible, which D-043 had wanted to avoid before the preprint.

*Consequence:* commit metadata and the decision log are public from now on. Secrets were never committed (hard rule 2; `scripts/check_hygiene.py`).

### D-046 Where the pilot runs, and cluster slices — Provisional (engineer, 1 Nov 2026)
**Measured on the Mac (`scripts/time_wp2.py`, PL1 FIT/VALIDATE only, timing runs not entered in the trial register):**
- **Signals:** the 28 frozen strategies take at most 0.63 s each, summed over the six calibration instruments (median of 3, after a warm-up). Arm 2c's cost therefore comes from the GP, not from the strategies.
- **One calibration-size run** (population 500, tournament 3, 50,000 requested evaluations, SPX): 64 s for arm 2c, 36 s for arm 6, alone; peak memory 0.65 GB.
- **Under load:** six concurrent arm-2c runs took 135 s in all (113–122 s each).

**Estimate.** At these speeds the pilot is about 3–4 h of laptop time for calibration (720 runs), under 1 h for the budget check, and about 12 h for the go/no-go under a requested-evaluation budget. A unique-evaluation budget could make the go/no-go several times longer.

**Choice:**
- Calibration and the budget check may run on either machine.
- The go/no-go, and every WP4 campaign, run on CERES once its portability check passes (`docs/CERES.md` §5). Runs must be identical on both machines.
- Plans are written, and reports produced, on the Mac. CERES runs slices of a plan (`scripts/campaign_tasks.py`, `scripts/ceres/tasks.sge`) with the same digest checks and skipping as `execute_plan`.
- A test checks that slices give the same hall of fame as the process pool.

*Why:* CERES gives up to 60 concurrent runs, and the laptop stays free. The checks keep results independent of where a task ran.
