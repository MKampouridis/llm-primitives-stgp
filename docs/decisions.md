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

### D-032 One project location — Decided (PI, 31 Oct 2026); "one" means one active Mac at a time since D-055
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

### D-047 Fixes and conventions from the pre-calibration code review — Decided (engineer, under D-042; 1 Nov 2026)
Four independent Claude reviewers (leakage, backtest and fitness, GP engine, campaigns and statistics) read the code at `aabe6fa`. None found a critical defect or look-ahead in the modelling computation. Their findings were checked against the code, and the following changes were made before any calibration run.

**Pilot test read (protocol §7–§8):**
- `Sandbox.open_pilot_test` accepts only a manifest loaded by `FreezeManifest.load_committed` that freezes at least one rule. Before, a hand-built manifest opened the test stage.
- The manifest's context now holds the settings digest, both lock digests, the data digest of the 22 pilot instruments, each go/no-go plan's configuration digests, and the code revision. `pilot-test` refuses to run if any of these, or any file under `src/`, `scripts/` or `config/`, has changed since the freeze.
- `pilot-test` evaluates exactly the manifest's tasks, checks each record's period, lag and cost multiplier, and runs once: it refuses if `reports/wp2/pilot_go_no_go.json` exists. The test sandbox's access log is saved with the result.

**Periods in WP2.** P01 and P02 windows overlap the pilot test years, so `[leakage] allowed_periods = ["DEV", "PL1", "PL2"]` makes the modelling store refuse every other period until WP4.

**PL1's test year is PL2's validation year.** This follows from the rolling design (D-034) and is not a leak into PL1's frozen rules, which never see it. But the go/no-go campaign's PL2 records contain validation scores on 2006-07..2007-06. Rule: nothing from the go/no-go records is inspected between `gonogo` and `freeze`, and `freeze` runs straight after `gonogo` completes. The PL1 test-year result is reported with this caveat. D-034's statement that the pilot test years are readable only through `open_pilot_test` holds for PL2's test year only.

**Records and plans:**
- A record is complete only for its plan's data digest, as well as its settings and configuration digests.
- The configuration digest of arms 2a–2c includes the operator lock, since they use core operators.
- Every step reads records from the plan's own task list and refuses missing tasks, never a folder listing.
- Records from more than one code revision raise a warning.
- An identical plan is reused untouched. A different plan cannot replace one that has records.
- Record writes use a temporary file per writer.
- `run_many` finishes the other runs when one fails, then reports the failures.

**Calibration rules (§6):**
- A candidate's rounded-up generations are capped at the generations it actually ran: population 1000 never gets 51,000 evaluations.
- §6.3's "never trade" counts rules with no entry at all; a rule below the minimum activity does trade. It is measured on the runs of steps 1 and 2, as the protocol says.
- Raising λ_turnover can only lower turnover, so only the turnover condition (median above 50) raises it. A never-trade share above 25% is reported and needs a recorded decision before the go/no-go.

**Fitness and evaluation:**
- **Hall of fame:** members are deduplicated by their held-position vector on the fit window, as D-029 intended. Raw signals differ where they have no effect: exit values while flat, entry values while long.
- **Defaults:** `FitnessConfig` defaults now equal the protocol (execution lag 2, minimum 2 entries a year), so an ad-hoc script can no longer silently use WP1's values. Campaigns always took them from `config/settings.toml`.
- **Missing values:** a missing `cost_bps` raises instead of meaning zero cost. A non-finite daily return in a portfolio raises instead of becoming a flat day. A score with no usable segment counts as no trade.
- **Annualisation:** portfolio Sharpe ratios and the paired bootstrap use the portfolio's own rows per year, not 252. An equal-weight portfolio lives on the union calendar: about 260 rows a year for weekday markets, about 365 once a 7-day market is in. The go/no-go margin (−0.2 in Sharpe) is unchanged.
- **Unique budget:** if the budget check picks a unique-evaluation budget, the go/no-go runs stop at the cap or at 10× the calibrated generations, whichever comes first. Each record says whether the cap was reached and by how much it was overshot.

**Accepted conventions (no change):**
- **No exit cost at the end of a window.** No forced exit is charged when a window ends, for every arm and buy-and-hold alike. A held position therefore pays one one-way cost (a few basis points) less than a round trip.
- **Lag 2 across an invalid bar.** It can earn from the signal bar's own close. Tier A has one invalid bar (WTI, 20 Apr 2020), outside the pilot.
- **Unique-budget overshoot.** It is at most population − 1 evaluations (≤ 1% at 500 × 50k), and is now recorded per run.
- **Non-finite strategy outputs.** Some LLM strategies return ±inf or all-NaN for some 2c parameter values (s11, s16, s17, s19). The glue treats them as "unknown", so the fitness stays finite; this only costs those arms wasted evaluations.
- **Trial counting for the Deflated Sharpe Ratio (WP4).** It counts distinct configuration digests: `bud-2c` and `arm2c` are one trial when their digests match. Arm 1 counts as one trial; its selection among 28 strategies is disclosed.
- **Digests.** They cover the whole settings file and the cache size, so settings must not change during a campaign.
- **Extra leakage tests.** Prefix invariance FIT→VALIDATE→TEST for all five GP libraries, and a poisoned-future canary through a whole GP run and arm-1 selection (`tests/leakage/test_library_prefix.py`).

**Departures from the plan:** none. The protocol text is unchanged except where noted (§6.3's remedy, the annualisation and the unique-budget ceiling), all of which make it operational.

### D-048 Portability of runs between the Mac and CERES — Decided (engineer, under D-042; 1 Nov 2026)
**Check (`docs/CERES.md` §5).** Two calibration-size runs (arms 2c and 6; SPX; PL1; population 500 × 100 generations), campaign `wp2-portability`, were run on the Mac (Apple M1, macOS, numba 0.68.1) and on CERES (x86-64, CentOS 7, conda-forge, numba 0.68.0), from the same plan and data.

**Result:**
- **Same:** every generation evolved the same rules, with identical unique and requested evaluation counts, identical halls of fame and the same final rule.
- **Different:** floating-point values differ only in the last bits (at most 4.4 × 10⁻¹⁶). This is rounding from the different CPUs and the numba patch release.
- `scripts/compare_records.py` now requires identical rules, counts and selections, and floats equal within a relative 10⁻¹².

**Speed.** CERES took 145 s (arm 2c) and 97 s (arm 6) per run, against 71 s and 39 s on the Mac: about 2–2.5× slower per core. With 60 concurrent tasks, that is still about 8× the Mac's throughput with six workers.

**Rule.**
- A near-tie in fitness within rounding could, in principle, send a run down a different path on the other machine. So every campaign runs entirely on one machine, with every arm and every period together. That way the paired comparison never mixes platforms.
- Each record states its platform (`environment`).
- Reproducing a run exactly means using the same platform; across platforms, results agree up to such rounding.
- This check is repeated whenever the CERES environment is rebuilt.

### D-049 Fixes from the external code reviews (ChatGPT, Antigravity) — Decided (engineer, under D-042; 1 Nov 2026)
The PI had the code reviewed by two other LLMs with `docs/code_review_prompt.md`. ChatGPT reviewed `91c2925` plus the half-applied D-047 fixes; Antigravity reviewed `7b943a4`. Each finding was checked against the code. Findings that D-047 had already fixed are not repeated.

**Fixed:**
1. **Read once, even after a crash** (ChatGPT 1):
   - `pilot-test` now validates every record, rule hash, period, lag and cost before opening any test data.
   - It then claims the read with a file created atomically (`reports/wp2/pilot_test_claim.json`, `freeze.claim_test_read`). The code never removes the claim.
   - After a crash, or with two processes, a second read is refused until a decision is recorded and the file is removed by hand.
2. **Results from obsolete code** (ChatGPT 2):
   - A plan records a digest of the package source (`src/lpstgp/**/*.py`). `verify` refuses to run a plan, and no record counts as complete, if the source has changed since the plan was written.
   - An empty hall of fame, or an out-of-range selected index, is not complete.
   - Any source change, however small, therefore means a new campaign. That is the price of never mixing code versions within one.
3. **§6.3 enforced** (ChatGPT 3, Antigravity 2):
   - If the λ check calls for it, `budget-check` reruns step 2 at λ_turnover ×2, then ×4, and keeps the first multiplier at which both conditions hold.
   - The go/no-go refuses to plan unless a multiplier was chosen, and it applies the multiplier to every arm, including arm 1's selection. A never-trade share above 25%, or ×4 not being enough, leaves it unresolved until a decision is recorded.
4. **Turnover over every final rule** (Antigravity 1, ChatGPT 4):
   - The §6.3 median turnover now includes rules that never trade (turnover 0) and rules below the minimum activity (their real turnover).
   - Below-minimum rules still score −1, but their record keeps their real Sharpe, turnover, drawdown and exposure (Antigravity 4), so `validation_sharpe` and §6.4 no longer see a fictitious 0.
5. **The unique budget is matched exactly** (ChatGPT 5):
   - The cap is enforced at every new evaluation. Once it is reached, unseen rules are not scored and can never be selected (fitness −∞).
   - Every arm scores exactly the cap; a test confirms this for two libraries.
   - `freeze` refuses if any unique-budget run stopped at the generation ceiling before its budget.
6. **`collect` reads the plan's own tasks** through `plan_records` (ChatGPT 6, Antigravity 5). Stray, stale or duplicate files are never read, and the old `MixedDigestsError` path is gone.
7. **Infinite strategy outputs** (Antigravity 3):
   - The core glue operators treat only NaN as missing, so ±inf from a strategy signal compared as a real value. This corrects D-047, which wrongly said the glue already treated ±inf as unknown.
   - Arm 2b and 2c signals now map ±inf to NaN in the adapter. The locked core operators are unchanged; none of them emits ±inf.
8. **Subtree mutation fits the depth and lookback left at its node** (Antigravity 8). Before, it ignored the ancestors' lookback, and a few percent of deep mutations were wasted.
9. **Leakage tests** (Antigravity 9):
   - Prefix invariance FIT→VALIDATE→TEST now covers every operator and data terminal that can appear in a rule, in all five libraries.
   - The poisoned-future canary now runs a GP run for every library, plus arm-1 selection.
   - In the technical (GP-TA) library, 7 data terminals and operators can never appear in a rule, because no technical operator consumes their types. They are inert, and are listed as such for the library-size description.

**Not changed:**
- **Strategy admission gates test five parameter points, not the full grid** (Antigravity 6). Generation is finished, and the 28 strategies are frozen. A full-grid sweep by both the GP reviewer and Antigravity found no look-ahead and no lookback violations, only the ±inf and all-NaN outputs handled in item 7. The gates stay as they were when the strategies were admitted.
- **A twice-failed slot is not re-run in a fresh session** (Antigravity 7, protocol §4). This is moot: all 28 slots were accepted (none needed a repair). It will be fixed before any new generation campaign.

### D-050 Second-round review of the fixes — Decided (engineer, under D-042; 1 Nov 2026)
A fresh Claude reviewer read only the diff `aabe6fa..c77d604` (D-047, D-049). It found no critical defect and no new bug in the engine-level fixes. It confirmed by mutation that the unique-cap and mutation-budget tests fail when the code they guard is broken.

**Fixed** (in `scripts/wp2_pilot.py` and the tests only, so the source digest of the calibration plan is unchanged):
1. **Where the chosen values live.** Protocol §6 said they are written to `config/settings.toml`. That conflicts with campaigns: writing them before the go/no-go would double-apply the λ multiplier, and writing them afterwards changes the settings digest under every finished run.
   - The chosen values now live in `reports/wp2/calibration.json` and `budget_check.json`, and every go/no-go configuration carries them in its digest. Settings keep the base values (protocol §6 amended).
   - The go/no-go refuses if the settings' base λ_turnover is no longer the one the budget check ran from.
2. **The λ trials stop at any never-trade breach.** A breach at ×2 now stops the trials (a higher λ can only make rules quieter) and needs a decision, as at ×1.
   - An unresolved outcome is resolved by a recorded decision in `reports/wp2/lambda_decision.json` (`{"lambda_turnover_multiplier": m, "decision": "D-0xx"}`), not by editing the generated report.
3. **Rehearsal before the claim.** Before claiming the test read, `pilot-test` runs the whole evaluation (rules, buy-and-hold, portfolios, the go/no-go statistics) on each pilot period's validation year and discards it. A code, library or data error then stops the step before any test bar is read.
4. **Untracked files.** The freeze and pilot-test code checks also refuse untracked files under `src/`, `scripts/` and `config/`.
5. **New tests:**
   - hall-of-fame deduplication by held positions;
   - union-calendar annualisation (≈261 rows a year for weekdays, ≈365 for every day) against a hand calculation;
   - an identical replan is left untouched, a changed plan cannot replace records, and a missing record makes `plan_records` and `collect` refuse;
   - ±inf from arm-2b terminals becomes NaN;
   - the driver's go/no-go guards (`tests/test_wp2_driver.py`).

**Not changed.** The pilot-test step has no end-to-end test, since it needs a committed manifest and two finished campaigns. Its order — validate, rehearse, claim, read — is kept short and was traced by the reviewer.

### D-051 Second-round reviews by ChatGPT and Gemini — Decided (engineer, under D-042; 1 Nov 2026)
Both reviewed the diff `aabe6fa..c77d604`. Gemini's findings check out against the code, but its list of "areas checked and found sound" describes code that does not exist here (for example `MarketCache`, `record_complete`, six libraries), so that list was disregarded. Findings already fixed in D-050 (the λ value in `settings.toml`) are not repeated.

**Fixed:**
1. **One sample for every λ multiplier** (Gemini 1). The ×1 check pooled the 720 step-1 runs with the 90 step-2 runs, while ×2 and ×4 could only use step-2 runs. The two samples are not comparable: step 1 holds only arms 2c and 6, at every candidate's parameters.
   - Every multiplier is now judged on the step-2 runs at that multiplier, which is the go/no-go configuration: the chosen parameters and all five GP arms. The step-1 figures are reported for reference.
   - **Departure:** this departs from §6.3's "the runs of steps 1–2" (protocol log amended). Reason: the condition should describe the configuration it adjusts, on one consistent sample.
   - The budget unit (§6.2) is computed from the runs at the chosen multiplier.
2. **Calibration reports carry their provenance** (ChatGPT 2):
   - `calibration.json` and `budget_check.json` record the source digest, the settings digest and their plans' digests. `budget_check.json` also records the digest of the calibration it used.
   - A report from other code, other settings or another calibration is refused.
   - A budget check under way first marks `budget_check.json` as pending, so an older decision can never be combined with newer evidence. A recorded override (`lambda_decision.json`) applies only to an unresolved check, never to a pending one.
3. **Existing go/no-go plans must match the current decision** (ChatGPT 1, Gemini 6):
   - `gonogo` (all modes) and `freeze` compare each plan's configuration digests with the configurations the current calibration decision implies, and refuse a mismatch.
   - `--mode plan` always goes through `write_plan`, which reuses an identical plan and refuses a different one that has records.
   - `--mode report` checks every task's record.
4. **`budget-check --mode plan` plans the next λ stage** once the previous one is complete (Gemini 4).
5. **Nothing after the unique cap counts** (Gemini 3):
   - Once the cap is reached within a generation, every later rule in that generation, cached duplicates included, is dropped from the generation's statistics, the request count and selection.
   - `budget_unit = "unique"` with no cap raises an error.
6. **Tests that now fail when their fix is reverted** (Gemini 5, ChatGPT 3; checked by reverting each fix):
   - the never-trade/turnover median, with idle rules pulling it below 50;
   - ±inf through the arm-2c adapter itself;
   - the source digest on a real temporary source tree.

**Consequence.** Item 5 changes `src/lpstgp`, so the calibration plan written at `c77d604` is stale and has been replanned.

### D-052 End-to-end rehearsal of the pilot, and runs short of a unique budget — Decided (engineer, under D-042; 1 Nov 2026)
**Rehearsal.** `tests/test_wp2_rehearsal.py` runs the real driver through every WP2 step at a tiny scale:
- calibrate, budget-check, go/no-go (run and report), freeze;
- a manifest committed in a throwaway git repository;
- the one-time test read, then a refused second read;
- the steps run on three synthetic instruments with their own data, results, reports and trial register, so nothing in the real repository is touched (checked).

It has two variants:
- **plain:** λ ×1 and the requested-evaluation budget;
- **strict:** it forces the other branches — λ raised to ×2 and ×4, an unresolved check settled by a recorded decision, and the unique-evaluation budget.

The driver's scale (instruments, candidate grid, runs) and its repository paths are now module constants, which the test overrides. Their values are unchanged.

**What it found.** In the strict variant, one run reached its generation ceiling (10× the calibrated generations) before spending its unique budget: its population had converged and kept proposing rules already scored. Under D-049, `freeze` refused and asked for a decision. But a decision at that point would be taken after the go/no-go records exist, which D-047 rules out.

**Rule, fixed in advance:**
- Under a unique budget, a run that reaches the generation ceiling first is kept. It had ten times its calibrated generations to search, and failing to find new rules is a property of its arm; excluding it would bias the arm.
- `freeze` lists such runs per arm in `reports/wp2/unique_budget_shortfall.json` (commit it with the manifest), and the go/no-go result reports the counts.
- This replaces D-049's refusal at the freeze.

### D-053 The trial register is tracked in git — Decided (engineer, under D-042; 1 Nov 2026)
`reports/configuration_register.csv` lists every registered configuration with its digest. It provides the trial count for the Deflated Sharpe Ratio in WP4, so it is a scientific record, versioned with the reports.

It was git-ignored by the general `*.csv` rule, and only mirrored to Box. It is now the one exception: in `.gitignore`, and by exact path in `scripts/check_hygiene.py`, with a test. Every other CSV is still refused, as data or results.

### D-054 CERES nodes are not numerically identical; calibration choice unaffected — Decided (engineer, under D-042; 1–2 Nov 2026)
**Finding.** The calibration was run twice on CERES with the same code (`c77d604`, then `c83314a`, which differs only in unique-budget code that calibration does not use). 639 of the 720 records are identical. 81 differ, and every one of them ran on an 80-core node in exactly one of the two runs; runs on the 40-, 88- and 176-core nodes agree with each other exactly.
- 67 differ only in per-generation population statistics, by rounding in the last digits.
- 14 differ in their hall of fame: a last-digit difference changed a comparison, and evolution then took another path. 12 selected a different rule.

So D-048's assumption that a campaign on CERES runs "on one machine" does not hold: CERES mixes CPU types, and numpy picks CPU-specific code paths whose rounding differs (see the probe below).

**Effect on the calibration.** None on the choice. Both runs choose population 250, tournament 5, 70 generations; the chosen candidate's median validation F is 0.718 in the first run and 0.674 in the second, and the same candidate is the best in both. The second run (`c83314a`, plan digest in `reports/wp2/calibration.json`) is the one used. The difference is noise in which seed-paths evolution follows, not a bias between arms or candidates: which node a task lands on does not depend on its arm.

**Why it still matters.** Re-running a task should give the same record; the paired-seed design and the paper's reproducibility claim assume it, and `scripts/compare_records.py` is the check.

**Probe.** `scripts/ceres/node_check.sh` ran `scripts/ceres/node_probe.py` on two nodes of each type (eight nodes) in two rounds. Each probe made three short GP runs (arms 2c and 6; PL1 FIT and VALIDATE data only), and the exact results were fingerprinted.
- The 80-core nodes are Broadwell (Xeon E5-2698 v4, no AVX-512); the 40-, 88- and 176-core nodes are Skylake or Cascade Lake with AVX-512. With default settings the two groups disagree and every node within a group agrees, as in the calibration.
- The cause is numpy's AVX-512 code paths (`X86_V4`, numpy 2.5). With every CPU-specific path numpy dispatches switched off (`NPY_DISABLE_CPU_FEATURES`), all eight nodes give identical results, equal to the Broadwells' default results.
- Not the cause: numba's code generation (pinning it to generic x86-64 without SVML changed nothing anywhere) and OpenBLAS's kernel choice (forcing Haswell kernels changed nothing).
- Cost: speed is about the same; at most 10–20% slower on some arm-2c runs.
- Round 1's numpy setting used pre-2.5 feature names, which numpy ignored. Round 2 asks numpy for its own names on each node.

**Rule.**
- `scripts/ceres/tasks.sge` switches off every CPU-specific path that numpy dispatches on the node it lands on.
- `scripts/campaign_tasks.py run` refuses to run on x86-64 while any such path is on, so a task cannot run with node-dependent rounding by mistake.
- No `src` change was needed, so the calibration result and the budget-check plan stay current.
- All campaigns from the budget check onwards run this way. The calibration (default settings, mixed nodes) stands, since its choice is the same in both runs.
- D-048's rule that a campaign runs wholly on one machine still holds: CERES, with this setting, counts as one machine.

### D-055 Two Macs, one active at a time — Decided (PI, 2 Nov 2026)
The PI works on a MacBook Pro by day and a MacBook Air in the evenings and at weekends, and does not want to keep the Air running. D-032's single location becomes one *active* location at a time.
- **git** carries code, docs, reports and the trial register, as before.
- **`scripts/handover.py`** carries what git does not: `data/`, `results/` and Claude's project memory, through a hand-over folder in Box (`handover_dir` in `config/paths.toml`). `cache/` is not carried; it is disposable.
  - `push` at the end of a session. It requires git to be clean and pushed, and refuses unless this Mac holds the project, i.e. the hand-over in Box is the one this Mac last pushed or pulled.
  - `pull` at the start. It refuses while this Mac has data, results or memory changed since its own last hand-over. It verifies every copied file against the pushed checksums, since Box may still be syncing, and then makes this Mac the holder.
  - Nothing is deleted outright: removed or overwritten files go to `_removed/<time>/` in the hand-over folder.
- Each Mac works on its own local copy at the same path (`~/code/llm-primitives-stgp`, so that Claude's memory folder matches). Box is only transport, so the rule against working inside cloud-synced folders stands.
- Campaigns run on CERES and can be driven from either Mac. A plan must be uploaded from, and its records brought back to, the Mac that holds the project.
- Tests in `tests/test_handover.py` simulate two Macs, and each safeguard was checked by breaking it and seeing a test fail.

### D-056 Budget unit and λ from the budget check — Decided (engineer, under D-042; 2 Nov 2026)
The budget check (protocol §6.2–6.3) ran on CERES: every GP arm (2a, 2b, 2c, 6, GP-TA) at the calibrated parameters (population 250, tournament 5, 70 generations), 3 runs on each of the six calibration instruments, PL1 FIT/VALIDATE only — 90 runs. All ran at `5154f57` with numpy's CPU-specific paths off (D-054), spread over all four node types (40, 80, 88 and 176 cores). Results in `reports/wp2/budget_check.{json,md}`.

- **Budget unit: requested evaluations.** The median unique share of evaluations is 0.12–0.15 in every arm (GP-TA 0.120, 2a 0.130, 2c 0.143, 2b 0.147, 6 0.152); the spread between arms is 1.26×, well under the 2× threshold. So D-052's unique-budget shortfall rule does not come into play.
- **λ_turnover kept at its base value (×1, 0.005).** No final rule fails to trade (0 of 90) and the median validation turnover is 11.9 position changes a year, against limits of 25% and 50. No λ step at ×2 or ×4 was needed. The step-1 calibration runs agree (0.6% no trade, median 11.1).
- **Noted, no action:** about 85% of requested evaluations in every arm re-score a rule already seen (the evaluation cache serves them), so each run scores roughly 2,300 distinct rules. This is similar across arms, which is what the rule tests. Cost per requested evaluation differs by up to 7× between arms (2a 0.65 ms, 2c 4.6 ms median), which matters for planning the go/no-go on CERES, not for the science.

**Go/no-go planned (2 Nov 2026, at `786a4a3`):** `wp2-gonogo-PL1` and `wp2-gonogo-PL2`, 1,122 tasks each (22 instruments × 5 GP arms × 10 runs, plus one arm-1 selection per instrument), requested-evaluation budget and λ ×1 as above; seeds paired across arms; source digest unchanged from the budget check. Six configurations added to the trial register. Estimated from the budget-check wall clocks: about 13 core-hours per period. Nobody inspects these records before `freeze` (D-047).

### D-057 Go/no-go campaign run and frozen — Decided (engineer, under D-042; 2 Nov 2026)
The go/no-go campaign (D-056) ran on CERES at `9c9fc2b`: 1,122 tasks each in `wp2-gonogo-PL1` and `wp2-gonogo-PL2`, all complete, all with numpy's CPU-specific paths off (D-054), spread over all four node types. Two arm-1 tasks were run first as a test.

Before the freeze, the records were checked only for completeness, current digests and code version; no results were inspected (D-047). `freeze` wrote `reports/wp2/freeze_manifest.json` (2,244 rules: task → rule hash, plus the settings, data, operator-lock and strategy-lock digests) and `reports/wp2/unique_budget_shortfall.json`, which is empty as the budget is in requested evaluations (D-056). Both are committed, so `pilot-test` may now open the PL1 and PL2 test years once.

### D-058 The pilot test years are read once — Decided (PI, 2 Nov 2026)
The PI authorised `pilot-test` ("run it") after the freeze (D-057, manifest committed in `66c26de`). This is the one read of the PL1 and PL2 test years (protocol §8), through `Sandbox.open_pilot_test`, preceded by a rehearsal on the validation years. Only the frozen rules listed in the manifest are evaluated. No other test data are unsealed.

### D-059 Pilot go/no-go: GO — Decided (rule fixed in advance, protocol §8; 2 Nov 2026)
The one test read (D-058) ran at 15:41 UTC on the MacBook Pro after the rehearsal on the validation years. The claim is in `reports/wp2/pilot_test_claim.json`; the results are in `reports/wp2/pilot_go_no_go.{json,md}`, and the daily portfolio returns are in `results/campaigns/wp2-pilot-test-portfolios.npz` (not in git). The sandbox logged 22 instrument reads per period, and no runs fell short of a unique budget.

- **Decision: GO.** The rule was GO if Sharpe(2c) − Sharpe(1), pooled over both test years, is at least −0.2. It is +0.313 (2c 0.687, arm 1 0.374).
- **How to read it.** The pilot is a feasibility check, not the confirmatory test. Every GP arm beats arm 1 on the point estimate (+0.26 to +0.37), but no paired-bootstrap interval excludes zero (p 0.29–0.48). Buy-and-hold has the highest pooled Sharpe (0.934), so none of the evolved rule sets beats the market here. That comparison is not part of the go/no-go rule, but WP4 should report it. The two years differ sharply: in PL1 every arm is positive (Sharpe 1.7–2.3), while PL2 (mid-2007 to mid-2008) is near zero or negative for every arm. So the pooled figures mostly reflect one regime, and two years cannot separate the arms.
- Results to carry forward: the protocol continues to WP3/WP4 unchanged. The runs-per-configuration study (§6.4) runs at the start of WP4, as planned.

### D-060 Validation–test gap reported; per-instrument pilot results need a PI decision — Decided (engineer, under D-042 as reaffirmed by the PI on 2 Nov 2026); 2 Nov 2026
Protocol §8 also asks for per-instrument results and validation–test gaps.
- **Gap.** `scripts/wp2_validation_gap.py` evaluates the frozen rules on each pilot period's VALIDATE year, through the same code as the rehearsal, and sets the results beside the test Sharpes already in `pilot_go_no_go.json` (`reports/wp2/pilot_validation_gap.{json,md}`). It opens no test data. Arm 1, which selects the best of 28 strategies on the validation year, has the largest gap (4.8 → 1.7 in PL1). Validation scores are selection-biased for every arm, so the gap is descriptive.
- **Per-instrument results: not available — a deviation.** `pilot-test` saved only the portfolio returns per arm, so the per-instrument test figures were never kept. Computing them needs the pilot test years again, which the one-read rule (§8, D-049) forbids without a PI decision. No decision, the go/no-go or otherwise, depends on them. Options: (a) report the deviation and leave it; (b) one re-evaluation of the same frozen rules, recorded as a second read. **Chosen: (a).** A second read would weaken the one-read guarantee the pilot was built around, for figures nothing depends on. The paper reports the deviation. For WP4, the test evaluation keeps per-instrument series from the start.

### D-061 Scope of the delegation — Decided (PI, 2 Nov 2026)
The PI reaffirmed D-042: the engineer takes all scientific decisions from now on, recording the reasoning here. Unchanged: the PI is asked before non-scientific, outward-facing or costly actions (CERES jobs, paid API use, GitHub settings, deleting data or results). Opening any sealed test data (the P01–P18 test years, or a pilot test year a second time) stays a recorded PI decision (hard rule 1), because it cannot be undone.

---

## WP3 (from 2 Nov 2026)

The WP3 protocol is `docs/protocol_wp3.md` (draft 0.1). Each decision below is the engineer's under D-042/D-061. "Provisional" means a value is fixed at protocol 1.0 from the dry run's mechanics, never from performance.

### D-062 Arm 3 is free authoring from the domain list, without performance feedback — Decided (engineer, 2 Nov 2026)
D-031 Q8 asked whether arm 3 implements arm 6's specifications or authors freely. **Free authoring:** same 7 domains, same quota (4 each), same contract and gates, one isolated session per domain; the brief gives domain scopes, not the plan's example operators.
- *Why:* re-implementing arm 6's list would test only who types the code, and arm 6 was itself written with AI help (D-002), so that comparison would be nearly empty. Free authoring tests C1's actual claim: the LLM choosing and writing cross-domain primitives. H2a then compares an LLM-chosen library with an expert-specified one, at measured human effort.
- **No backtest tool**, only gates and descriptive statistics on anonymised dev-fit data, because arm 6 was written without performance feedback. With a backtest tool, arm 3 would be tuned and arm 6 not, which would confound authorship with tuning.
- *Departure from the plan:* the plan calls arm 6 "expert-written versions of arm 3's operators". With free authoring the two libraries contain different operators from the same domains. The paper states this.

### D-063 Arms 4 and 5 start from arm 3's library — Decided (engineer, 2 Nov 2026)
Arms 4-grow, 4-full and 5 all start from arm 3's frozen library, and arm 5 keeps it fixed.
- *Why:* RQ3 and RQ4 should compare maintenance regimes and LLM roles from one starting point. In the plan, arm 5's "fixed 2c grammar" meant the LLM-written seed library, i.e. arm 3's library here. WP2 redefined 2c over the strategies' signals (D-037), so taking 2c literally would make H4 compare libraries as well as roles.

### D-064 Maintenance runs per period on training data, carried forward — Decided (engineer, 2 Nov 2026)
Maintenance runs C cycles on each period's FIT data, with gates on its VALIDATE year, and the library carries forward to the next period. This is causal, because each period's maintenance ends before its test year. Each period's reported runs use the library at the end of its maintenance. C = 3 per period is provisional.

### D-065 Maintenance cycles run on the Mac — Provisional (engineer, 2 Nov 2026)
The LLM session needs the Mac (subscription Claude Code), and a CERES round trip per cycle needs the PI's two-factor sign-in each time, which would be 162 times in WP4. The cycles' GP runs (about 15–20 minutes each on 6 workers) therefore run on the Mac. The reported runs run on CERES. This is revisited after the dry run's timings.

### D-066 Budget accounting and the paired-seed gate — Decided (engineer, 2 Nov 2026)
- The reported runs have the same budget in every arm. Maintenance cycles' GP evaluations and LLM tokens are reported per arm as the method's cost. The comparison is between final libraries, not between total compute; arms 4-grow, 4-full and 5 have the same number of sessions and cycles, which matches H4's budget.
- A patch is admitted unless its paired median validation F is more than 0.05 below the previous library's (provisional). The gate uses the validation year, which can only widen the maintained arms' validation–test gap, so it is conservative for H3. Every cycle of a period uses the same seeds, so the gate needs no extra GP runs.

### D-067 Patch bounds and library cap — Provisional (engineer, 2 Nov 2026)
Per cycle, 4-full may make at most 2 prunes, 2 refines and 2 grows, and 4-grow at most 2 grows. The cap is 64 cross-domain operators (about 2.3× arm 3), and core and data are never touched. A prune needs low usage and contribution in 2 consecutive cycles, checked by the gate. When 4-grow reaches the cap it stops growing, which is reported. Arm 5 proposes at most 25 rule pairs per cycle, which replace 25 of the 250 random initial individuals. All of these are checked for mechanics in the dry run.

### D-068 Subscription usage stops at its limit; no bill — Decided (PI's information, 2 Nov 2026)
The PI confirmed that usage beyond the organisation's monthly limit is not billed: sessions simply stop. So WP3 and WP4 LLM work has no money cost. The only constraint is time:
- the 5-hour and monthly limits pause sessions; the driver resumes after the reset (D-044);
- a monthly stop could delay WP4 maintenance by weeks. The dry run (M4) measures usage per session, and if 162 WP4 sessions would not fit comfortably within the monthly allowance, C drops from 3 to 2 (D-064), before any other change. The model is never changed (D-036).

### D-069 The arm-3 contract and brief — Decided (engineer, 2 Nov 2026)
Made concrete while building M1 (`src/lpstgp/authoring/`), before any authoring session.
- **Brief without examples.** D-062 said "same wording as WP2", but WP2's domain scopes end with "(for example …)" lists that name many of arm 6's operators: permutation entropy, Fisher–Rao, Wasserstein, Sinkhorn, Lévy area, Hurst, DFA, spectral entropy, wavelet energy, SSA and others. Arm 3's brief keeps each scope's opening definition and drops the list. A test renders every brief and refuses any arm-6 operator name, any plan example, any instrument name and any year.
- **Real outputs only, scale-free.** Every arm-6 cross-domain operator outputs a `Real`, and every one with a Series or Path input is scale-invariant. Arm 3 is held to the same structure, so the two libraries differ in their mathematics, not in what kind of node they may add. Thresholds and logic come from the shared core in both.
- **Parameter kinds.** Arm 3 sees the five standard kinds and may declare its own (2–9 increasing values, shared across operators by name). Arm 6's specific kinds (Order, Levels, Kmax, Moment, QEnt, Alpha, Epsilon, PVar, WLevel) are hidden, because their names point to arm 6's operators. Declared kinds become `Llm<Name>` classes, so they never clash with arm 6's.
- **No reference tests** for arm 3: the gates are the admission test. Writing independent reference implementations would add human effort, which H2a measures.
- **Shared code.** The WP2 source policy, the sandboxed runner and the MCP loop were generalised for this. Their behaviour for strategies is unchanged, and the WP2 tests pass.

### D-070 Arm 3 authored and frozen; a re-run, and withdrawing a file in later sessions — Decided (engineer, 3 Nov 2026)
M2 ran 3 Nov 2026 at code version 1298b1f; the report is `reports/wp3/arm3_authoring.md`.
- **Information theory.** The first session wrote a first Lempel–Ziv operator, replaced it with a better one, and could not delete the old file, because its tools only read and write. In the repair turn it emptied the file. The final check still counted five `.py` files, so it failed, and the protocol's one fresh re-run took the slot. The re-run was accepted, with a brief identical to the first session's (no earlier operators). The first attempt's operators are not used, though all four passed the gates: the rule is to take the slot's accepted session, and choosing between attempts would be a selection we did not plan. The failed session stays in the archive and is reported.
- **Withdrawing a file (M3 onwards, provisional).** The maintainer sessions will need to remove files too. From M3, a file whose content is empty or whitespace only counts as withdrawn, and the brief says so. Arm 3's frozen library is not affected.
- **Where the files live.** The files are in `src/lpstgp/authoring/generated/arm3/`, with the lock `src/lpstgp/authoring/arm3.lock.toml`, outside `lpstgp.operators`. That way the WP1 registry and arm 6 (`discover()`) never load them. The named library `arm3` is the WP1 data terminals and core glue plus these 28 operators. The protocol's earlier path, under `operators/generated/`, would have put them inside the registry's module walk.
- **Name overlap.** One operator, `permutation_entropy`, has the same name as an arm-6 operator; its pattern order is fixed at 3, where arm 6's has an order parameter. The briefs name no arm-6 operator (D-069), so this is an independent choice, and it is reported in the H2a overlap analysis. The two names never meet in one library (D-063).
- **Checks.** All 28 still pass the synthetic gates in-process (a slow test). A 5-generation GP smoke test on PL1 training data ran on the library (about 25 ms per unique evaluation, cold).

### D-071 The maintenance machinery made concrete (M3) — Decided (engineer, 3 Nov 2026)
Built in `src/lpstgp/maintenance/` before any maintenance session or cycle run. Values marked *provisional* are checked by the dry run (M4) and fixed at protocol 1.0, from the mechanics only.
- **Patch format.** The maintainer's folder holds the current library, one `<name>.py` per operator with its verbatim code. A new file is a grow; it must set `DOMAIN = "<domain>"` to one of the seven domains and use a name never used in the lineage. An edited file that still defines the same operator is a refine, stored as version k+1 with its parent recorded. An emptied (or deleted) file is a prune (D-070). Any problem rejects the whole patch, and the session gets one repair turn first, as in arm 3.
- **Prune rule** *(provisional)*. A prune needs usage ≤ 0.02 and contribution ≤ 0.01 (or no rule using the operator) in the evidence of this cycle and of the previous one. For a period's first cycle, the previous one is the last cycle of the previous period. In the first period, cycle 1 therefore cannot prune.
- **Evidence (§4.1).**
  - *Survival* uses a new record field, the operator set of each generation's best rule (`best_usage`). It is added to the GP record and leaves every run's evolution unchanged.
  - *Knock-outs* are computed in the run's worker on FIT only. They cover the ten hall-of-fame rules of a run and only the cross-domain operators. Each node of the operator is replaced by the median of its own output over the scored FIT window, and warm-up bars stay missing. Subtrees without the operator reuse the run's cache, so knocked-out values never enter it.
  - *Stability* is the interquartile range of the per-instrument mean drop in F, and of the per-(instrument, segment) mean drop in segment Sharpe.
  - The *elite trees* shown are the rank-0 rules of the runs, the top 20 by FIT fitness, labelled by asset class only.
- **Same evidence for every arm (H4).**
  - Arms 4-grow, 4-full and 5 see the same evidence table, elite trees and library contracts.
  - The maintainers also see their library's code; arm 5 sees only the contracts.
  - Tool budgets per session: check 100, describe 50 and check_patch 30 for arms 4; check_rules 30 for arm 5.
  - `describe` uses the anonymised development window, as for arm 3.
- **No validation figure reaches the LLM.** After a cycle the LLM learns only whether the patch was admitted. A rejection by gates 1–2 is explained with its problems; a rejection by gate 3 is only said to be "clearly worse on held-out data". The gate's median difference is recorded but not shown, which keeps validation feedback to the LLM to one bit per cycle.
- **Arm 5 has gate 3 too.** This departs from §4.3, which had arm 5's trees pass gates 1–2 only. With gate 3 for every LLM arm, a harmful change is guarded against in the same way whatever the LLM's role, which H4 needs. Arm 5's admitted pairs, at most 25, replace its previous set. Like a maintained library, the set carries over to the next period. The seeded rules take the first places of the initial population, and the rest are random as before.
- **Shared runs.** A batch of cycle runs is identified by (period, library state, seeded rules), never by the arm. All three arms share their first PL1 batch, and an admitted candidate's runs are the next cycle's runs. After a rejection the previous runs are reused: same seeds and same library give the same runs.
- **Safety.** Arm 5's trees are LLM text, and deap's parser would `eval` unknown tokens. Every token must be a node of the primitive set before parsing; tokens are never evaluated.
- **Pre-flight (3 Nov 2026).** Two sessions, at effort low, are archived in `results/wp3/preflight_maintenance/`. The 4-full session had check, describe and check_patch; the arm-5 session had check_rules. In both, reads outside the folder were refused, there was no shell or web access and no project instructions, memory or skills, and the model was `claude-opus-5-5`. As before, the account e-mail address was attached to the context.
- **Checks.** A scripted stand-in for the LLM (`scripts/maintain.py --stub`) ran every arm through two periods on a tiny GP. It exercised grows, refines, arm-5 proposals, and admissions and rejections by gate 3. The leakage tests (§7) cover a poisoned-future check for the knock-outs, a canary scan of every arm's brief for instrument names, years and validation figures, a static check that the maintenance code never opens the test stage, seeds paired across arms, states and cycles, and a real-data cycle of every arm whose reads stop at the period's test start.


### D-072 Two provisional rules changed after the M4 dry run, for mechanical reasons — Decided (engineer, 3 Nov 2026)
The M4 dry run (18 sessions, report `reports/wp3/m4_dryrun.md`) checked the maintenance machinery. Two provisional rules of D-066/D-071 did not work as mechanisms. Both are changed here, as §8 of `docs/protocol_wp3.md` allows. The reasons are the rules' reachability and noise level, not any arm's results, and no other provisional value is changed.
- **Prune rule (D-071) made relative.** The fixed thresholds (usage ≤ 0.02, contribution ≤ 0.01) were never met in 356 operator-cycles: the smallest usage was 0.021 and the smallest contribution 0.41. The contribution threshold was set before the scale of a knock-out's drop in F was known. A rule that cannot be met would make 4-full the same as 4-grow plus refines, and RQ4's prune question could not be studied. New rule: an operator is *low* in a cycle when it is in the library's bottom quarter (`PRUNE_QUANTILE = 0.25`) by usage and by contribution (no contribution counts as lowest); it may be pruned when low in this cycle and the previous one. The brief's evidence table now has a *prunable* column for 4-full. On the dry-run evidence the rule would have allowed 0–3 candidates in about a third of cycles: reachable, but not every cycle. *Provisional* until protocol 1.0.
- **Gate 3 (D-066) becomes a test calibrated to the noise.** With 66 pairs, the median paired difference between two replicate batches of one library has a standard deviation of about 0.13 (from the dry run's within-batch replicates), so the old rule (reject if the median is below −0.05) rejected about a third of harmless patches. New rule: a one-sided Wilcoxon signed-rank test on the 66 paired validation differences (candidate − current); the candidate is rejected when p < 0.05 (`ALPHA`). This keeps the gate a guard against harm (D-066) with a known false-rejection rate of about 5% for a harmless patch. Applied after the fact to the dry run's pairs, it would have rejected 4 of the 18 proposals, against the 9 actually rejected. The LLM is still told only admitted or rejected (D-071). The median difference stays in the record. *Provisional* until protocol 1.0.
- **Not changed:** C = 3, 3 runs per instrument, the per-cycle bounds, the cap of 64, 25 arm-5 seeds and the tool budgets. None showed a mechanical problem: no tool budget came within 96 calls of its limit, and the cap was not approached (34 operators after 6 cycles).
- **Not re-run.** The dry run's lineage stays as run under the old rules. A 6-session check of 4-full under the new rules (PL1 → PL2) would exercise the prune path with a real LLM before WP4. It is offered to the PI and not started (subscription use).
- **Re-check (3 Nov 2026, PI go-ahead).** Six 4-full sessions under the new rules: the prune rule marked an operator in 3 of 6 cycles, and the LLM pruned it each time. Gate 3 admitted all 6 patches; the old rule would have rejected 4. All sessions completed with no repairs. Net library growth was +9 in 6 cycles, so the cap of 64 may be reached around WP4 period 6–8; it is kept, and its hits are recorded (D-067). Details: `reports/wp3/m4_dryrun.md`.
