# Decisions and assumptions

Every assumption and design choice made while building the code base, in the order made. The research plan (`docs/research_plan.md` in the Box project folder) is authoritative; where an entry departs from it or fills a gap, it says so.

Status: **Decided** = agreed with the PI. **Provisional** = engineer's default, open for review. **Open** = needs a decision before the work package named.

---

## WP1 (from 30 Oct 2026)

### D-001 Repository location — Decided
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
