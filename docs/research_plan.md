# Research plan: LLM-authored mathematical operators for typed GP trading

Exported 30 Oct 2026 from the shared plan document (https://claude.ai/artifact/5ep8kwTcssy6Q4kyMDvU4E), which remains the live version. The two diagrams in it are described in text here.

## Summary

This is a standalone paper on a general question: can an LLM author and maintain the primitive set of a strongly typed GP (STGP), using mathematics from outside finance, to induce trading rules? Throughout, *operators* means functions in the GP function set, not genetic operators such as crossover or mutation.

An LLM writes executable, semantically typed operators for a predefined list of mathematical domains: information theory, information geometry, optimal transport, rough paths, fractal analysis, statistical physics and spectral methods. STGP composes them into per-asset entry/exit rules. Between GP cycles, the LLM grows, prunes and refines the library using evidence of GP usage and fitness. The typed operator library is released openly as a reusable artefact.

The paper's value lies in a controlled answer to three questions:

- Does exposing mathematics as recombinable primitives beat evolving or selecting whole LLM-written strategies?
- Does LLM authorship add anything over hand-written operators?
- Does maintaining the library beat growing it?

Novelty at the level of the general mechanism is not available. The survey (30–31 Oct 2026) found that ALPHAS2 and EvoQuantLab already do LLM-driven GP vocabulary evolution for alpha mining. Large Language Quant (LLQ, CIFEr 2026) is cited as motivation, since it showed LLMs can turn such mathematics into working signals, and it appears as one baseline among several.

**Target venues**

| Option | Fit | Notes |
| --- | --- | --- |
| IEEE Transactions on Evolutionary Computation | Methodological GP contribution; strongest venue | Needs the full ablation design and a discussion of the general mechanism |
| Genetic Programming and Evolvable Machines | Core GP audience; primitive-library theme | Natural home if the trading results are mixed |
| Expert Systems with Applications | Finance application and open library | Fallback if the contribution reads as primarily empirical |

## Background and positioning

GP for trading has evolved rules from the same vocabulary for three decades. The vocabulary is technical indicators and, more recently, directional-change and sentiment terminals (Neely et al. 1997; Allen & Karjalainen 1999; the Essex STGP and DC-GP line). Richer mathematics (entropy, path signatures, information geometry, optimal transport) is rare in trading, because each primitive is costly to design and implement correctly.

LLMs change that cost. LLQ (Clayman, Kampouridis & Papastylianou, CIFEr 2026) showed that an agentic LLM can turn such mathematics into working trading signals. In LLQ, though, each signal remained a fixed, hand-selected whole strategy. A parallel line of work (below) lets LLMs grow a GP vocabulary, but only for cross-sectional alpha mining and only from price/volume motifs.

The five-tool literature survey sets the boundary of what is new:

| Work | What it already does | What it does not do |
| --- | --- | --- |
| ALPHAS2 (anonymous ICLR 2027 submission, OpenReview QjycCr3zns) | LLM writes executable typed operators; a typed tree GP composes them; GP output feeds back to the LLM | Operators are distilled bottom-up from price/volume factors; output is cross-sectional alpha; library only grows; shape-based types |
| EvoQuantLab (arXiv:2610.17130) | Typed tree GP; LLM-assisted terminal admission; evidence-based terminal lifecycle between cycles | No LLM-written operator code; cross-sectional factors; 2.5–3.5-month OOS, equities gross of costs |
| Time Value of Evolution / GPTL (arXiv:2608.13297); ProFiT (GECCO 2026) | LLM mutates trading policies compiled into a typed boolean entry/exit tree language; LLM evolves strategy code | Fixed vocabulary; the LLM never writes primitives |
| PACE (arXiv:2608.07395); CAD (arXiv:2608.17947) | LLM-maintained libraries of executable primitives during evolution | No GP, no typed composition, not finance |

**The gap.** Nobody has used operators imported top-down from information geometry, optimal transport, rough paths or spectral entropy as GP primitives in trading, with or without an LLM. Nobody has pruned and refined an executable operator library on GP usage evidence for trading rules. The full evidence is in the consolidated survey (191 papers; see docs/survey.md).

## Research questions and hypotheses

Four questions, each answered by a specific comparison of arms (see Experimental design).

1. **RQ1 — Granularity.** Should LLM-written mathematics be given to evolution as whole strategies, as signal series, or as parameterised primitives? Arms 1–2 use a fresh set of about 30 LLM-written whole strategies, generated for this paper under a fixed protocol.
   - *H1:* Primitive-level STGP (arm 2c) beats selecting among whole LLM strategies (arm 1) and STGP over whole strategies (arm 2a).
2. **RQ2 — Authorship.** Do LLM-authored cross-domain operators add value over the same mathematics written by hand, and over conventional technical/directional-change terminals?
   - *H2a:* Arm 3 (LLM-authored, frozen) matches arm 6 (expert-written) in performance at lower human effort.
   - *H2b:* Both beat STGP with conventional terminals only.
3. **RQ3 — Maintenance.** Does maintaining the library between cycles (grow, prune, refine on usage and fitness evidence) beat a frozen library and a grow-only library?
   - *H3:* Arm 4-full beats arms 3 and 4-grow, with smaller libraries and less overfitting (a smaller gap between validation and test).
4. **RQ4 — Role of the LLM.** Is the LLM better used as a library author than as a tree operator (seeding, mutation, pruning) over a fixed grammar?
   - *H4:* Arm 4-full beats arm 5 at matched LLM-token and GP-evaluation budgets.

The primary outcome for every hypothesis is out-of-sample, net-of-cost Sharpe of the evolved rules, aggregated across assets with a fixed, simple portfolio (equal-weight across assets). It is fixed before any test-period run.

## Planned contributions

Six contributions, each phrased "to the best of our knowledge" and differentiated in the related-work section.

| # | Contribution | Must be differentiated from |
| --- | --- | --- |
| C1 | Top-down cross-domain mathematical operators, LLM-written as executable code from a predefined domain list, composed by STGP for trading | ALPHAS2 (bottom-up price/volume motifs); EvoQuantLab (literature terminals); CogAlpha (roughness proxies, Fisher z-transform); LLQ (whole strategies, no composition) |
| C2 | Per-asset boolean entry/exit rules across crypto, FX, indices and commodities | ALPHAS2 and EvoQuantLab (cross-sectional factors); GPTL (fixed vocabulary) |
| C3 | Library maintenance in both directions (grow, prune, refine) credited by GP usage, survival and contribution | ALPHAS2 (grow-only); EvoQuantLab (terminals, no operator code); PACE (no GP, no pruning) |
| C4 | Semantic types (series, histogram, path, regime, signal) so that operators compose correctly | ALPHAS2 (shape-based interfaces); Essex STGP and GPTL (fixed vocabularies) |
| C5 | A matched-budget comparison of granularity: whole LLM strategies vs signal series vs primitives | ProFiT, QuantEvolve, AlgoEvolve (whole-program evolution); LLQ (selection of whole strategies) |
| C6 | An open, tested library of typed mathematical trading primitives, with contracts, reference tests and a prefix-invariance harness | No equivalent released artefact found in the survey |

**Do not claim** firsts for: LLM + GP; evolving LLM-generated strategies; LLM-seeded GP; LLM mutation or repair in trading GP; an evolving GP vocabulary in finance; LLM-written typed GP operators; LLM/GP co-evolution; LLM-maintained primitive libraries; path signatures in trading. Each is pre-empted by a paper in the survey.

## Method

The system has three parts (a typed operator library, an STGP rule learner and an LLM library maintainer) plus a fixed evaluation layer.

*Architecture (diagram in the live doc):* top row, left to right: typed operator library (versioned contracts with semantic types, LLM-written from a fixed domain list) → STGP rule learner (entry and exit trees per asset, robustness composite fitness, training data only) → evaluation layer (best rule per asset, then a fixed equal-weight portfolio; no learned allocation). Bottom row, the maintenance loop run after each GP cycle: operator evidence (usage in elite trees, survival, knock-out contribution, stability across folds) → LLM maintainer (bounded patches: prune weak operators, refine as new version, grow missing signal families) → admission gates (compile, type check, finite output, prefix invariance, paired-seed check, size cap) → admitted operators return to the library.

**1. Operator library.** Each operator is a versioned contract:

- name and version (a modified implementation gets a new identity, never an overwrite);
- typed signature and parameters with legal ranges (e.g. window 10–120 bars);
- required lookback and earliest availability;
- mathematical definition, with a reference;
- executable implementation, plus a missing-data policy.

The seed library is written by the LLM from a predefined domain list, under the same contract and gates:

- **Cross-domain operators:** for example spectral entropy, Hurst R/S, Lévy area, Fisher–Rao distance between rolling histograms, Wasserstein-1 distance, rate–distortion compressibility, the Fisher-information trace, and volatility autocorrelation (critical slowing). Each domain gets a fixed quota of operators.
- **Conventional terminals:** technical and directional-change indicators, as used in the GP trading literature.
- **Optional seed variant:** components taken from LLQ's published strategies, disclosed as such and run only as a sensitivity check.

**2. Semantic types.** STGP uses meaning-level types so that only valid compositions are generated. For example:

- `Hist × Hist → Real` for Fisher–Rao distance;
- `Path × Path → Real` for Lévy area;
- `Series → Hist` for a rolling histogram;
- `Real × Real → Bool` for comparators;
- `Bool × Bool → Bool` for logic.

Adaptive thresholds (rolling percentile, mean + k·sd) are typed operators, because LLM-written strategies rely on them heavily.

**3. Rule representation.** Each individual is a pair of boolean trees, entry and exit, long-only, with a one-bar execution shift. Fitness is a robustness-oriented composite computed across development segments: median Sharpe, penalised by median drawdown, turnover and tree size. Weights are set on a pilot period and then frozen. NSGA-II is the alternative if return and risk are kept as separate objectives.

**4. Library maintenance (between GP cycles).** After each cycle, every operator receives an evidence record:

- usage in the elite trees;
- survival across generations;
- knock-out contribution (fitness change when the operator is replaced by a neutral constant);
- stability across development folds.

The LLM receives these records and proposes bounded patches:

- **Prune:** retire operators with low usage and low contribution for k consecutive cycles.
- **Refine:** issue a new version of a heavily used but unstable operator.
- **Grow:** add new operators, targeted at signal families the elite trees lack.

Every proposal passes automatic gates before admission: compilation, type check, finite and non-constant output, prefix invariance, and a paired-seed check against the previous library. Library size is capped.

**5. Evaluation layer.** The best evolved rule per asset is evaluated on its own. The rules are then combined in a fixed, simple portfolio (equal-weight across assets, with inverse-volatility as a robustness check). No learned allocation is used in the main results, so gains can be attributed to rule discovery. A learned allocator, such as LLQ's portfolio GA, can be reported as a secondary analysis.

## Experimental design

Ten arms isolate granularity, authorship, maintenance and the LLM's role. Everything else is held fixed: data, splits, harness, costs, the evaluation layer and the total search budget.

| Arm | Strategy source | Answers |
| --- | --- | --- |
| 1 | About 30 fresh LLM-written whole strategies; best per asset chosen on validation | RQ1 |
| 2a | STGP with those whole strategies as boolean terminals | RQ1 |
| 2b | STGP with their internal signal series as terminals | RQ1 |
| 2c | STGP with the seed library's parameterised operators | RQ1 |
| 3 | Frozen LLM-authored cross-domain library (all domains) | RQ2 |
| 4-grow | LLM library maintenance, growth only | RQ3 |
| 4-full | LLM library maintenance: grow, prune, refine | RQ3 |
| 5 | Fixed 2c grammar + LLM seeding, semantic mutation and pruning | RQ4 |
| 6 | Expert-written versions of arm 3's operators | RQ2 |
| 7 | Re-implemented comparators: ALPHAS2-style bottom-up distillation; EvoQuantLab-style terminal lifecycle (if feasible) | Positioning |

**Baselines:**

- GP: STGP with technical-analysis terminals, DC-GP, ActTrade.
- LLM as variation operator: a ProFiT- or CogAlpha-style code-evolution loop with the same budget.
- Existing systems: the LLQ pipeline (whole strategies plus its portfolio GA), run on the new splits.
- Passive: buy-and-hold.

**Data and splits.** Three tiers, daily bars, roughly 2005 to mid-2026 (agreed 30 Oct 2026):

| Tier | Contents | Purpose |
| --- | --- | --- |
| A. Cross-asset (primary) | About 30–40 liquid instruments: 8–10 equity indices (US, Europe, UK, Japan, Asia), 8 FX pairs, 6 commodities (gold, silver, Brent, WTI, natural gas, copper), 4–5 crypto, 2–3 government bond futures | Supports C2 (rules across asset classes); little survivorship bias |
| B. Stocks (breadth) | About 100 stocks, 25 each from the US, Europe, UK and Japan/Asia, chosen by a rule fixed at sample start (largest by market cap), with point-in-time constituents and delisted names kept | Statistical power; comparability with the stock-market GP literature |
| C. Essex datasets | The exact datasets of the DC-GP and ActTrade papers | Head-to-head comparison with published GP results |

Tier B needs survivorship-free data (e.g. WRDS/CRSP, Refinitiv or Bloomberg). Free sources are acceptable for the pilot only. Whether tier B evolves one rule per stock or one rule per market (fitness pooled across that market's stocks) is decided after the WP1 compute projection.

Use rolling walk-forward periods with 3 years of training and 1 year of out-of-sample test, designed from scratch for this paper. GP fitness and library maintenance use training data only. Admission gates use a validation year carved from training.

**Post-cutoff test.** Add a final period whose test year starts after the training cutoff of every LLM used (provisionally 2025-07 to 2026-06; set it once the models are chosen).

**Budgets.**

- The same number of GP fitness evaluations per arm.
- A fixed LLM token budget for every arm that uses an LLM.
- 30 independent GP runs per arm and period (re-check compute cost before committing).
- Report tokens, wall-clock time, failed and repaired proposals, and total backtests per arm.

## Evaluation and controls

**Primary outcome** (pre-registered): out-of-sample, net-of-cost Sharpe of the evolved rules in the fixed equal-weight portfolio, over the walk-forward test years. Each hypothesis's arms are compared pairwise.

**Secondary outcomes:**

- Sortino, Calmar, maximum drawdown and total return;
- results broken down by asset class and by regime;
- turnover and no-trade frequency;
- tree size and the overfitting gap between validation and test.

**Statistics.**

- Mann–Whitney U with Holm–Bonferroni correction, with bootstrap CIs and Cohen's d.
- A mixed-effects model with test period and asset as random effects. This separates market-period variance from seed variance; many seeds on one year are not many market histories.
- A matched-budget block-permutation test against selection bias.

**Leakage controls.**

- Prefix invariance for every operator: appending future bars must not change past values. Tested automatically at admission.
- A one-bar execution shift on every signal.
- Test data never enters prompts, library evidence or admission.
- LLM model names, versions and prompts are logged, and every call is archived for reproducibility.

**Costs.** Use per-asset spreads that are contemporaneous with the data where available, otherwise a documented broker-spread model. Add a sensitivity sweep at 0.5×, 1×, 2× and 3× the base cost.

**Library-lifecycle metrics:**

- operators proposed, admitted, retired and refined per cycle;
- reuse across assets and periods;
- library size over time;
- which mathematical domains survive.

## Work packages and timeline

*Timeline (diagram in the live doc; provisional dates):*

| Item | Dates |
| --- | --- |
| WP1 Library and harness | 2 Nov 2026 – 8 Jan 2027 |
| WP2 Strategy set, STGP pilot | 14 Dec 2026 – 12 Feb 2027 |
| Gate: pilot go/no-go | 12 Feb 2027 |
| WP3 LLM arms 3–5 | 25 Jan – 26 Mar 2027 |
| WP4 Full runs, all arms | 15 Mar – 14 May 2027 |
| WP5 Analysis and writing | 26 Apr – 25 Jun 2027 |
| arXiv preprint | 28 May 2027 |
| Journal submission | 30 Jun 2027 |

The February gate decides, on two pilot periods, whether primitive-level STGP is competitive with whole LLM strategies before the LLM maintenance arms are built. Deliverables:

- **WP1:** seed library written from the domain list, contracts, reference tests and harness.
- **WP2:** the fresh set of whole LLM strategies, plus STGP with arms 1–2.
- **WP3:** LLM authoring and maintenance (arms 3–5).
- **WP4:** all arms and baselines on all periods and all dataset tiers.
- **WP5:** statistics, analysis, library release and manuscript.

## Risks and mitigations

| Risk | Likelihood | Mitigation |
| --- | --- | --- |
| A competing paper closes C1–C3 before submission (Togelius/Khalifa group, ALPHAS2 authors, EvoQuantLab) | Medium | Monthly arXiv check; citation alerts on ALPHAS2, EvoQuantLab and GPTL; post an arXiv preprint as soon as the RQ1–RQ3 results exist |
| More search, not better search: gains come from extra trials | High | Matched budgets, capped library size, permutation test, reporting of the validation–test gap |
| Primitive-level STGP does not beat whole LLM strategies (H1 fails) | Medium | Still publishable as a controlled negative result; reframe around RQ2/RQ3 and the lifecycle analysis; GPEM or ESWA as venue |
| LLM contamination of historical periods | Medium | Post-cutoff test period; report it separately |
| Compute cost of 10 arms plus baselines × all periods × 30 runs × all dataset tiers | High | Vectorised (GPU) operators; pilot on 2 periods first; drop arm 7 if re-implementation is infeasible |
| Operators that are numerically fragile (histograms, OT, signatures) | Medium | Gate on finite and non-constant output; unit tests against reference implementations (e.g. POT, iisignature) |
| ALPHAS2 changes or is withdrawn during review | Low | Cite the OpenReview version with its access date; update at proofs |
| Reviewers read the paper as an LLQ follow-up | Low | General research question and title; library written from a domain list, not LLQ code; fresh strategy set; LLQ only in related work and as one baseline; no reused LLQ text |

## Paper outline and open decisions

**Draft outline** (journal length, about 25–30 pages):

1. Introduction: why GP trading vocabularies have stayed narrow; LLMs as authors and maintainers of primitives; RQ1–RQ4; C1–C6.
2. Related work: GP for trading; LLM + evolutionary computation; LLM alpha mining and LLM-written trading strategies (incl. LLQ); evolving vocabularies (ALPHAS2, EvoQuantLab, PACE, CAD); typed trading languages (GPTL).
3. Method: operator contracts, semantic types, the domain list and seed library, STGP rules, library maintenance, evaluation layer.
4. Experimental setup: arms, baselines, datasets, splits, budgets, statistics, controls.
5. Results: RQ1 to RQ4 in turn, then the post-cutoff period.
6. Analysis: library lifecycle, surviving mathematical domains, example evolved rules, cost and contamination checks.
7. The released library: contents, tests, how to extend it.
8. Discussion and limitations.
9. Conclusion.

**Decisions needed from co-authors:**

- [ ] Target journal: TEVC first, or GPEM?
- [ ] Authorship and roles: who leads implementation, statistics, writing?
- [ ] Which LLM(s) for operator authoring and maintenance; model cutoff for the post-cutoff period. Deferred to WP3; an Anthropic API key is needed from WP2/WP3, not for WP1.
- [x] Domain list: keep the seven domains, about 4 operators per domain (agreed 30 Oct 2026).
- [ ] Datasets: three tiers agreed (cross-asset, about 100 stocks, Essex datasets); still to confirm the data source for tier B.
- [ ] Composite single-objective fitness, or NSGA-II?
- [ ] Include the optional LLQ-component seed variant, or leave LLQ out of the library entirely?
- [ ] Keep arm 7 (ALPHAS2/EvoQuantLab re-implementations) or drop it if cost is high?
- [ ] Compute: laptop for WP1 (agreed); GPU budget and cluster time needed from WP4.
- [ ] Code hosting: private GitHub repository now, made public with a Zenodo DOI at submission or preprint (agreed); licence still to choose.
- [ ] Preprint policy: post on arXiv early to establish priority?
