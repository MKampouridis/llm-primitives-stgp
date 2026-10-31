# Survey round 2 judgement: Claude vs ChatGPT

**Question.** Has genetic programming already been used to evolve LLM-generated trading strategies of the kind in *Large Language Quant* (Clayman, Kampouridis & Papastylianou, IEEE CIFEr 2026)? Categories: (A) LLM-derived primitives in GP, (B) LLM-seeded GP, (C) LLM as variation/repair operator, (D) co-evolution of programs and primitive set, or GP evolving specs an LLM implements.

**Inputs judged.** The Claude survey ([LLM GP trading strategy survey.md](LLM%20GP%20trading%20strategy%20survey.md), 153 rows) and the ChatGPT survey (45 rows, pasted 30 Oct 2026). Gemini was not available.

**Method.**
1. A separate agent checked every merged entry (61 papers) against primary records: arXiv API, Crossref, ACL Anthology, PMLR and NeurIPS. It saw only titles and IDs, not either survey's reasoning or verdicts.
2. A second agent read in full the seven papers ChatGPT found that changed or could change the verdict.

Notes are in `research_notes/Survey round 2 judging/`.

---

## 1. Bottom line

**The planned paper is still novel, but the gap is narrower than either survey alone suggested.** The key new paper is **EvoQuantLab** (arXiv:2610.17130, Oct 2026), found only by ChatGPT. It is a genuine typed tree GP for alpha mining. An LLM-assisted outer loop admits new terminals, and an LLM reviewer bans, activates or demotes them between cycles. This takes the general idea "LLM revises the typed-GP vocabulary between cycles, in finance".

What EvoQuantLab does **not** do, all confirmed from its full text and appendices:
1. **Primitives are not shown to be executable code.** Its terminals appear to be named precomputed series derived from literature "Reference Cards". The paper describes no mechanism for creating executable operators.
2. **Output is cross-sectional factors, not trading rules.** It produces IC-scored factors that feed a LightGBM ranker or an equal-weight book, not per-asset boolean entry/exit rules.
3. **No advanced-mathematics primitives.** It has no information-theoretic, information-geometric, optimal-transport, rough-path or fractal primitives.
4. **Weak evaluation.** Out-of-sample periods are only about 2.5–3.5 months, and equity results are gross of costs.

**Revised defensible core claim:** strongly typed GP that evolves per-asset entry/exit trading rules over **executable, parameterised operators** written by an LLM and drawn from advanced mathematics. The LLM revises that operator library between cycles using GP usage and fitness evidence. Evaluation uses walk-forward tests across asset classes, net of costs, and feeds the existing portfolio GA. Cite EvoQuantLab explicitly as the nearest work and differentiate on points 1–4.

---

## 2. Per-category verdict, reconciled

| Cat. | Claude survey | ChatGPT survey | **Judged verdict** | Deciding evidence |
|---|---|---|---|---|
| A: LLM-derived primitives in GP | Not found | Done (EvoQuantLab, InsightSR) | **Partially done.** Finance: LLM-proposed *terminals* (precomputed series) in typed GP (EvoQuantLab). Non-finance: LLM features in PySR (InsightSR). **Not found:** LLM-written *executable operators*, advanced-maths primitives, or trading-rule outputs. | ChatGPT overstated "Done": neither paper shows LLM-authored executable primitives. Claude's "Not found" missed EvoQuantLab. |
| B: LLM-seeded GP | Partially done | Done | **Done in general, partially done for trading GP.** Seeding a genuine GP is shown in robotics (Kobilov & Lan) and symbolic regression (InsightSR). In finance, seeding is shown in an LLM-run EA (LineageEvo, TreEvo, CogAlpha) or a GA (LLM-GA). No study seeds typed tree GP for trading rules. | LineageEvo and TreEvo seed LLM-operated EAs, not GP. |
| C: LLM as variation operator | Done | Done | **Done.** Both surveys agree. Examples include ProFiT, QuantEvolve, AlgoEvolve, MadEvolve, CogAlpha, LineageEvo, TreEvo, Time Value of Evolution (GPTL) and LLEGO. | Uncontested. |
| D: co-evolution / spec evolution | Partially done | Done (EvoQuantLab, TreEvo) | **Done for two variants, open for one.** (i) LLM revises a typed-GP terminal set between cycles in finance: done (EvoQuantLab). (ii) Evolving specifications the LLM implements: done (TreEvo thought-trees; AlgoEvolve prompt genome). (iii) LLM *writes and refines executable operators* during GP, credited by usage and fitness, for trading rules: **not found**. PACE does a non-GP, non-finance version. | ChatGPT is right that D is largely taken. The remaining slice is the executable-operator and trading-rule version. |

---

## 3. Coverage: what each survey found that the other missed

Both surveys covered the general LLM+EC lineage (FunSearch, ELM, LMX, EoH, ReEvo, LLaMEA, AlphaEvolve, LLM-SR, LLEGO) and the main LLM alpha-mining systems (CogAlpha, QuantaAlpha, AlphaPROBE, AlphaAgent, R&D-Agent-Q, Alpha-GPT, QuantAgent, Kou et al., Alpha Jungle, AlphaForge, AutoAlpha).

**Found only by ChatGPT (17), all verified:**

| Paper | ID / DOI | Judged closeness (1–5) | Why it matters |
|---|---|---|---|
| **EvoQuantLab** (Yang, Qian, Chen et al., 2026) | arXiv:2610.17130 | **4** (nearest work) | Typed GP with LLM-assisted terminal admission and between-cycle terminal revision, for alpha |
| LineageEvo (Liu, Zhang, Ma, Yang, 2026) | arXiv:2610.29663 | 3 | LLM-EA with seeding and lineage-aware LLM variation over a fixed Qlib DSL |
| TreEvo (Ren, Zhao, Liu, Yang, 2025/26) | arXiv:2508.16334 | 3 | Evolves NL thought-trees that the LLM implements (spec-evolution, D-ii) |
| InsightSR (Ling, Cun, Chen, 2026) | arXiv:2608.25291 | 3 | LLM seeds PySR GP and accumulates LLM features; nearest non-finance A+B+D |
| EvoMO-SR (Rossetti, Kononova, Bäck et al., 2026) | arXiv:2609.36187 | 2 | LLM-EA symbolic regression with a substructure archive |
| Kobilov & Lan (2025) | arXiv:2502.07772 | 2 | LLM-seeded genuine behaviour-tree GP (B, robotics) |
| Ren, Qin, Li, Warm-start GP alpha (2024) | arXiv:2412.00896 | 2 | Non-LLM warm-start GP for alpha (seeding precedent) |
| Brownlee et al., LLM GI mutations (SSBSE 2023) | arXiv:2310.19813 | 2 | LLM edits in genetic improvement |
| Liventsev et al., Fully Autonomous Programming (GECCO 2023) | arXiv:2304.10423 | 1 | LLM synthesis-repair with a GP comparator |
| Hazman et al., Grammar-guided prompt optimisation (ECAI 2025) | arXiv:2507.10326 | 1 | Grammar-guided GP over prompt edits |
| Christodoulaki, Kampouridis, Kyropoulou (KBS 2025) | 10.1016/j.knosys.2025.113054 | 2 | STGP trading baseline (own group) |
| Long, Kampouridis, Kanellopoulos (PPSN 2022) | 10.1007/978-3-031-14721-0_3 | 2 | DC-indicator GP baseline (own group) |
| Kampouridis & Tsang (IJCIS 2012) | 10.1080/18756891.2012.696918 | 1 | EDDIE grammar extension: a pre-LLM "grow the vocabulary" precedent |
| Guidetti et al., Fisher-geometric pruning for SR (2026) | arXiv:2610.24753 | 1 | Fisher geometry used for pruning GP expressions, not as trading primitives |
| AlphaGen (Yu et al., KDD 2023) | arXiv:2306.12964 | 1 | Already in Claude's table via DOI; counted for completeness |
| Brabazon, Kampouridis, O'Neill survey (GPEM 2020) | 10.1007/s10710-019-09359-z | 1 | Already in Claude's notes without DOI |
| Hemberg et al., arXiv version | arXiv:2401.07102 | 2 | Same work as Claude's GPEM DOI |

**Found only by Claude (selected; ChatGPT missed them all):**

| Paper | ID / DOI | Closeness | Why it matters |
|---|---|---|---|
| **The Time Value of Evolution** (Siper, Khalifa, Togelius, 2026) | arXiv:2608.13297 | 3 | LLM mutates policies compiled to a **typed tree trading language (GPTL)** with boolean entry/exit outputs. Nearest *representation* to the planned paper. |
| **ProFiT** (Siper, Khalifa, Soros, Nasir, Azhang, Togelius) | GECCO 2026, 10.1145/3795095.3805175 | 2–3 | LLM code-evolution of trading strategies at GECCO, the venue's own prior art |
| Continuous Program Search (same group, 2026) | arXiv:2602.07659 | 2 | Learned mutation over a trading DSL |
| **PACE** (Xie et al., 2026) | arXiv:2608.07395 | 3 | LLM-maintained library of *executable* primitives with Thompson-sampling credit (non-GP, non-finance). Nearest analogue for the executable-operator part of the claim. |
| AlgoEvolve (Sharma, Shroff, 2026) | arXiv:2606.26173 | 2 | LLM code mutation plus prompt-genome evolution; names "modular program synthesis" as future work |
| MadEvolve (Kvasiuk et al., 2026) | arXiv:2605.23007 | 2 | Joint feature and strategy code evolution, BTC |
| QuantEvolve (Yun, Lee, Jeon, 2025) | arXiv:2510.18569 | 3 | Quality-diversity LLM evolution of strategy code |
| LLM-GA (Zhang D. et al., IEEE SMC 2025) | 10.1109/SMC58881.2025.11343400 | 3 | LLM seeds and varies a trading GA |
| EvoQuant, EFS, Hubble, Alpha-GPT 2.0, Frontiers hybrid | see main report | 2–3 | LLM alpha/strategy evolution variants |
| LaSR (Grayeli et al., NeurIPS 2024) | arXiv:2409.09359 | 2–3 | LLM concept library co-evolved with GP (ChatGPT's lookup failed) |
| Navet & Chen (2008); Futter et al. (2023); Long, Kampouridis, Papastylianou (AI Review 2026) | see main report | 1–2 | Entropy and GP; signatures in trading; most recent own-group GP baseline |
| Vella Zarb et al. (GECCO 2025); GE grammar-specialisation line | see main report | 2 | LLM-designed grammars for GE (A-adjacent) |

**Assessment.** The surveys largely complement each other. ChatGPT's search, driven by arXiv and citation-chasing, found the newest Chinese alpha-mining lineage (Oct 2026), including the single most important paper. Claude's search found the trading-specific line from the Togelius group (GECCO 2026), PACE, and most of the trading-strategy (rather than alpha-factor) work. Either survey alone would have produced a wrong verdict: Claude would have overclaimed A/D, and ChatGPT would have missed the GECCO prior art a reviewer is most likely to raise.

---

## 4. Citation accuracy

All 61 merged entries exist, and **no fabricated or misattributed citations were found in either survey.** Corrections:

| Paper | Correction |
|---|---|
| EvoAlpha | NeurIPS 2025 **Workshop on Generative AI in Finance** poster, not main track. Authors: Luo, Ko, Sun, Zhang, Liu. OpenReview ALpLmURYWy. |
| Christodoulaki & Kampouridis, ASOC | Vol. 204, art. 116566. Issue dated Jan 2027, online 2026. |
| Hubble | Title ends "…for Safe, Diverse, and Reproducible Alpha Factor Discovery". Authors: Shi, Yan, Cai, Lv. |
| Frontiers of Computer Science hybrid alpha paper | Authors Yu, Xue, Ao, He; vol. 20(2), art. 2002316 (2025). |
| ProFiT | Full author list: Siper, Khalifa, Soros, Nasir, Azhang, Togelius. GECCO 2026 pp. 727–734 confirmed. |
| Navet & Chen | "On Predictability and Profitability: Would GP Induced Trading Rules be Sensitive to the Observed Entropy of Time Series?", in *Natural Computing in Computational Finance*, Springer 2008, pp. 197–210, 10.1007/978-3-540-77477-8_11. |
| Long, Kampouridis, Papastylianou (AI Review 2026) | Title: "Multi-objective genetic programming-based algorithmic trading, using directional changes and a modified sharpe ratio score for identifying optimal trading strategies". |

Venues confirmed: CogAlpha (ACL 2026 Long), AlphaAgent (KDD 2025), Kou et al. (Findings of EMNLP 2025), EoH (ICML 2024), LLaMEA (IEEE TEVC 29(2)), and QuantEvolve (ICAIF 2025 workshop, non-archival).

**Closeness scores I disagree with in the ChatGPT table:**
- LineageEvo, CogAlpha and TreEvo at 5 → **3–4**. They are LLM-operated EAs over factors, with no GP and no primitive library.
- Alpha Jungle at 4 → **2**. It uses MCTS, not evolution.
- InsightSR at 4 → **3**. It is outside finance and uses features, not operators.

---

## 5. Revised gap statement

Each claim should be phrased "to the best of our knowledge" and differentiated from the named papers.

1. **LLM-authored executable operators for typed GP in trading.** The LLM writes typed, parameterised operators (e.g. `SpectralEntropy(series, window)`, `LevyArea(path_x, path_y, window)`, `FisherRao(hist_a, hist_b)`, `W1(window_short, window_long)`). STGP then composes them, instantiating them on different inputs and windows. *Differentiate from:* EvoQuantLab (precomputed terminals from literature), InsightSR (precomputed features, untyped, non-finance), PACE (LLM composes, no GP, non-finance), LLQ (whole strategies, no recombination).
2. **Decomposing LLM strategies into recombinable components** (ChatGPT's strongest suggestion, which I endorse). The research question is whether exposing the internal mathematical building blocks of LLQ strategies lets GP recombine them better than treating each strategy as an indivisible signal. Key ablation, at matched budgets: (a) whole LLQ strategies as boolean terminals, (b) precomputed LLQ indicator series as terminals, (c) parameterised LLQ operators.
3. **Usage- and fitness-driven library revision for trading GP.** Between cycles, operators are credited by GP usage, survival and contribution, then pruned or refined by the LLM. *Differentiate from:* EvoQuantLab's evidence-gated terminal bans (closest; your novelty lies in executable operators and trading-rule outputs) and PACE's Thompson sampling (non-GP).
4. **Advanced-mathematics primitive families in trading GP at all.** No GP/GE trading paper using entropy, Hurst/fractal, signatures, Fisher information or Fisher–Rao, or Wasserstein as primitives was found by either survey, *even without an LLM*. Note that CogAlpha's "fractal" and "Fisher" agents are roughness proxies and the Fisher z-transform, not Hurst or Fisher information. Futter et al. already use signatures in trading, without GP.
5. **Rigorous multi-asset, net-of-cost, walk-forward evaluation feeding the portfolio GA.** This is an empirical rather than algorithmic contribution. EvoQuantLab's short gross-of-cost OOS makes it a fair point of contrast.

**Claims that will not survive review** (both surveys agree):
- "first LLM+GP"
- "first evolutionary optimisation of LLM-generated strategies or factors" (ProFiT, CogAlpha, QuantEvolve, LLM-GA)
- "first LLM-seeded GP population" (Kobilov & Lan, InsightSR)
- "first LLM mutation or crossover for alpha or trading"
- "first evolving primitive vocabulary for financial GP" (**EvoQuantLab**)
- "first evolution of specs an LLM implements" (TreEvo, AlgoEvolve)
- "first use of signatures in trading" (Futter et al.)

---

## 6. Threats and things to monitor

- **EvoQuantLab group** (HKUST/Microsoft/Tsinghua; Sirui Han, Yike Guo et al.). Adding LLM-written operator code would close gap 1. This is the most urgent group to watch and to cite.
- **Togelius/Khalifa group (NYU).** GPTL is already a typed tree trading language with an LLM in the loop. Letting the LLM extend GPTL primitives is one step away.
- **SUSTech (Peng Yang et al.: TreEvo, LineageEvo)** and **AlgoEvolve** (stated "modular program synthesis" future work).
- **Experimental-design threats raised by ChatGPT that are worth adopting:**
  - LLM pretraining contamination of historical periods: record model versions and include a genuinely post-cutoff test period.
  - Report full search cost (LLM tokens, rejected programs, repairs).
  - Include an expert-written version of the same mathematical operators, to test whether the LLM adds anything beyond implementation convenience.

---

## 7. Remaining limitations

- **Full texts not read:** ProFiT (403 on ACM and SSRN) and the GPTL primitive list.
- **EvoQuantLab ambiguities:** the paper leaves unclear whether its LLM ever writes terminal code and how its hypotheses seed GP. Read it yourself before submission, since it is the paper reviewers will compare against.
- **Not searched:** subscription databases (Scopus, Web of Science, IEEE Xplore, ACM DL), and the GECCO/EuroGP/EvoApps 2026 tables of contents.
- **Pending:** Gemini's survey has not yet been judged. Consensus's free quota resets on 1 Nov 2026, if one more index pass is wanted.
- **Moving field:** two of the most relevant papers (EvoQuantLab, LineageEvo) appeared in the last three weeks, so re-run a targeted arXiv search shortly before submission.

---

## Addendum: Gemini survey (judged 30 Oct 2026)

**Verdict impact: major. ALPHAS2 takes the core mechanism (A and D) for alpha mining.** Gemini's other 49 rows overlap heavily with the merged list. Notes are in `citation_verification_gemini.md` and `gemini_close_papers.md`.

### ALPHAS2: verified from the PDF the user supplied

**"AlphaS²: Semantic–Symbolic Co-Evolution for Alpha Mining with Coding Agents".** Anonymous double-blind ICLR 2027 submission (OpenReview QjycCr3zns), 26 pp. Read in full: method, experiments, ablations and Appendix A. Closeness to the planned paper is **5**, now the nearest work, ahead of EvoQuantLab.

**What it does:**
- **Semantic evolution agent.** An LLM (DeepSeek) runs an island-model evolution of executable alpha programs from financial hypotheses. Factors go into a shared archive capped at 300 entries, ranked by RankICIR and kept behaviourally diverse by correlation.
- **Operator construction agent.** An LLM reads high-scoring factor programs and the existing primitive library. It **writes new executable operators**: code, a typed signature, a financial rationale, and links to its source factors.
  - Each operator is checked automatically for syntax, interface compliance, look-ahead, output shape, finite and non-constant values, and scale. Failing operators are repaired or discarded.
  - There are four typed interfaces. Unary and binary operators act on (dates × stocks) panels; rolling and pairwise-rolling operators act on trailing windows.
  - The example operator, FlowDecaySkew, generalises a VWAP-deviation decay and adds skewness modulation. It is written in torch and is a genuinely new numerical routine, not a copied subtree.
- **Symbolic evolution agent.** A genuine typed tree GP (population 1,000, 500 generations) runs over the expanded grammar. It rebinds the learned operators to new inputs and windows and nests them recursively. The operator set is fixed within each GP stage and grows between stages.
- **Feedback loop.** GP descendants return to the archive as executable parents and references for the next LLM stage. On CSI500, 26 of the 50 final factors came from GP. All 23 LLM continuation factors reference GP output, and 15 have a direct GP parent.
- **Evaluation.**
  - Markets: cross-sectional alpha on CSI500 (search 2011–19, validation 2020, test 2021–24, next-day target) and CSI1000 (test 2022–Jun 2025, 10-day target).
  - Pipeline: factors go to LightGBM, then a Qlib TopK/Drop portfolio, with transaction costs included.
  - Results: CSI500 ICIR 0.209, AER 13.2%, IR 1.61. CSI1000 ICIR 0.517, AER 16.6%, IR 1.92.
  - Baselines are copied from other papers, not rerun.
  - The ablations are mixed. Without operator construction, IC is higher (0.0725 vs 0.0701) but IR is lower (1.74 vs 1.92).

**Effect on the categories:**
- **A (LLM-authored executable primitives in typed GP, finance): done** by ALPHAS2.
- **D (LLM grows the GP operator set between stages; GP results feed back to the LLM): done** by ALPHAS2, for the growth and feedback variant.
- **What remains open:**
  1. **Top-down versus bottom-up operators.** ALPHAS2 distils operators bottom-up from recurring motifs in successful price/volume factors (VWAP deviation, skewness, ranks, volume confirmation). The planned paper imports operators top-down from mathematical theory outside finance: information geometry, optimal transport, rough paths, rate-distortion, spectral entropy, statistical physics.
  2. **Output.** Per-asset boolean entry/exit trading rules across crypto, FX, indices and commodities, instead of cross-sectional stock ranking passed through LightGBM.
  3. **Library maintenance.** ALPHAS2's library only grows; it describes no pruning or usage-based credit. EvoQuantLab bans *terminals* using evidence. Combining usage- and fitness-based credit, pruning and refinement of *executable operators* is not shown by either paper.
  4. **Type system.** ALPHAS2 types by array shape. Typing by meaning (series, distribution/histogram, path, regime state, boolean signal) lets STGP compose operators such as Fisher–Rao distance (histogram → histogram → real) or Lévy area (path × path → real) correctly.
  5. **Decomposing existing strategies.** Turning LLQ's eight strategies into operators and comparing whole-strategy, indicator-series and operator granularity at matched budget is not done anywhere.
  6. **Integration with the portfolio GA** and multi-asset walk-forward evaluation.
- **Claims that no longer survive review:**
  - "first to have an LLM write typed operators for GP"
  - "first co-evolution of LLM factor search and the GP primitive set"
  - "first GP-to-LLM feedback loop in alpha mining"

Cite ALPHAS2 as an anonymous ICLR 2027 submission (OpenReview QjycCr3zns) until it is de-anonymised.

**New and verified (none above closeness 3):**

| Paper | ID / DOI | Closeness | Note |
|---|---|---|---|
| Chen & Qi, "LLM-Assisted Semantic Pruning for Genetic Programming-Based Alpha Factor Discovery" | Applied Sciences 2026, 10.3390/app16126231 | 3 | Genuine GP over alpha trees. The LLM flags and prunes redundant or implausible branches (category C, repair/simplification). Uses high-frequency crypto data and DeepSeek. Found via follow-up, not by any survey. |
| AlphaSchema (Yi, Yang, Jin, Li, Li) | arXiv:2607.26642 | 2 | Surrogate-guided search over semantic "schema plans" that an LLM implements (spec-evolution, D-ii-like). No GP. |
| Chain-of-Alpha (Lang Cao, sole author) | arXiv:2508.06312 | 2 | LLM generation and optimisation chains; no GP |
| FactorMiner; AQuA; AlphaPilot (Jiang et al.); AlphaLogics (arXiv:2603.20247); AlphaAgentEvo (ICLR 2026, OpenReview lNmZrawUMu) | — | 2 | LLM alpha agents or RL; no GP |
| LLM-FE (Abhyankar, Shojaee, Reddy; TMLR); EFE (Taga et al.); CAAFE (NeurIPS 2023) | 2503.14434; 2607.01548; 2305.03403 | 2 | LLM-evolved feature code consumed by a fixed ML model, not GP; no trading |
| Gurkan, Stonedahl, Wilensky, "Mutation Without Variation" | arXiv:2606.05408, GECCO '26 LLM4EC workshop | 2 | **Useful as motivation.** Without selection, iterated LLM mutation collapses onto a few program structures: in 87% of chains, more than 93% of mutations revisit an earlier structure. Classical subtree mutation does not converge this way. This supports using GP for the combinatorial search. |
| Promptbreeder (ICML 2024) | 2309.16797 | 1 | Prompt evolution |
| Guo, Jin, Kuang, Qian, Wang, "Signature Decomposition Method Applying to Pair Trading" | J. Futures Markets 46(3):582–603, 10.1002/fut.70075 | 2 | Path signatures in trading without GP. Cite alongside Futter et al. |
| Dempsey, O'Neill, Brabazon, "Adaptive Trading with Grammatical Evolution" | IEEE CEC 2006, 10.1109/CEC.2006.1688631 | 1 | GE trading background |
| Tsang, Yung, Li, "EDDIE-Automation" | DSS 37(4):559–565, 2004, **10.1016/S0167-9236(03)00087-3** | 1 | Gemini's DOI pointed to an unrelated paper |
| pwb-alphaevolve (Papers With Backtest) | GitHub, May 2025 | 1 | Practitioner AlphaEvolve-style LLM evolution of Backtrader strategies |

**Claims about other papers, checked:**
- **AlgoEvolve, "Alpha Silence": confirmed.** Under a fixed prompt, LLM mutation drifts into zero-trade programs ("syntactic over-smoothing"). A further citable motivation for structural GP.
- **CogAlpha: partly confirmed.** Its agents forbid nested loops at any depth and *prefer* vectorised operations, but single loops are allowed. Phrase it as "forbids nested loops; strongly prefers vectorised operations". This limits genuinely iterative maths such as Sinkhorn/OT or geodesic computations.
- **Christodoulaki et al. (KBS 2025; ASOC 2026):** Gemini frames these as category A precursors, with LM-derived sentiment terminals in STGP. Present them as the group's own path towards LLM-authored primitives.

**Gemini citation accuracy: the lowest of the three surveys.** Errors:
- Wrong co-authors for Chain-of-Alpha (the listed co-authors do not exist), AlphaPROBE (actually Guo, Shen, Luo et al.), EFS (first author missing), and the GECCO'24 GI paper (actually Saemundsdottir & Haraldsson, not Brownlee et al.).
- Incomplete author list for the signature pairs-trading paper.
- A DOI resolving to an unrelated paper (EDDIE-Automation).
- On the other hand, Gemini alone found ALPHAS2, the single most important paper. Its description of the paper was accurate.

---

## Addendum: Undermind report (judged 30 Oct 2026)

**Verdict impact: none on A–D.** Undermind says its search returned 36 papers, but the report cites only 13. It is a curated synthesis plus an experimental design, not a full table. Every citation is real and correctly attributed: 11 were already verified, and the 2 new ones were checked here via the arXiv API. It did not surface ALPHAS2, LineageEvo, TreEvo or Time Value of Evolution. Its nearest-work pick was EvoQuantLab, which was correct before ALPHAS2 appeared.

**New and verified:**

| Paper | ID | Closeness | Note |
|---|---|---|---|
| Siper, Khalifa, Togelius, "Procedural Content Metageneration via Program Search and Continual Abstraction Discovery" (CAD) | arXiv:2608.17947 (18 Aug 2026) | 3 | An LLM evolves Python programs by mutation and crossover. CAD extracts reusable primitives from high-fitness programs into a run-specific helper module, which later programs widely adopt. In a 2×2 design it raises best fitness in all 8 comparisons. Domain is game level generation, not finance. **This is a threat signal:** the same group already has LLM trading-strategy search (ProFiT) and a typed trading tree language (GPTL). |
| Guo, Zhang, Lin, "CoEvo: Continual Evolution of Symbolic Solutions Using Large Language Models" | arXiv:2412.18890 | 2 | LLM evolutionary search with a dynamic knowledge library. The library stores ideas in several representations, not callable GP primitives. |

**Undermind's contribution to the experimental design.** It is the most useful part of its report, and it is consistent with ChatGPT's decomposition suggestion. The design has five arms, with the portfolio GA, harness, costs and splits held fixed:
1. The original LLQ pipeline.
2. Fixed-library typed GP over the LLQ mathematical features, with no LLM.
3. A frozen library proposed once by the LLM.
4. A library the LLM maintains between cycles, evidence-gated, which gives a direct comparison with EvoQuantLab and ALPHAS2.
5. LLM tree operations (seeding, semantic mutation or pruning) over a fixed grammar.

Other recommendations worth adopting:
- **Versioned primitive contracts:** types, lookback, earliest availability, missing-data behaviour, and a new identity for every modified implementation.
- **Prefix-invariance tests:** adding future data must not change values already computed for the past.
- **Matched LLM and GP budgets**, with token, time and failure counts reported.
- **A pre-registered primary outcome.**
- **Lifecycle metrics:** primitive admission, survival, reuse and transfer.

**Critique of the original LLQ paper, relevant to the extension.**
- The 50 GA seeds measure optimiser variance on the same market years, not independent market histories.
- The transaction-cost sample (Oct 2025–Jan 2026) postdates the historical tests, so a cost-sensitivity analysis is needed.
- Undermind recommends a selection-aware robustness test, such as a matched-budget block-permutation search.

---

## Addendum: Kimi survey (judged 30 Oct 2026)

**Verdict impact: none beyond ALPHAS2.**
- **Kimi found ALPHAS2 independently.** It was not on Kimi's "already known" list, and Kimi reached it through indexed passages. Its description agrees with the full text read above, and it flagged honestly that its method evidence came from snippets.
- **Kimi's narrowed claim matches the one here:** typed per-asset entry/exit GP over LLM-written advanced-mathematics operators, with addition, pruning and refinement between runs driven by usage and fitness.
- **Chinese-language sources:** the targeted CNKI/Wanfang/VIP and thesis searches found no LLM-generated GP primitives. The only Chinese-language hits were two Huatai brokerage reports.

**New items (citations checked here via Crossref, arXiv and ICLR proceedings unless noted):**

| Paper | ID | Closeness | Note |
|---|---|---|---|
| Wu, Lou, Zhang, Chen, Yang, "EvoAlpha: An LLM-Enhanced Evolutionary Framework for Formulaic Alpha Mining" | ICASSP 2026, 10.1109/ICASSP55912.2026.11463591 | 3 | LLM crossover and mutation over alphas (C); CSI300/500. **Different paper from the NeurIPS 2025 workshop "EvoAlpha"** (Luo, Ko, Sun et al.), despite the shared name. |
| Yu, Zheng, Gan, Pan, Liu, Wang, He, "AlphaMemo: Structured Search-Process Memory for Self-Evolving Alpha Mining Agents" | arXiv:2606.20625 | 3 | LLM edits over typed ASTs with a fixed operator grammar. Memory learns which edit motifs succeed or fail. CSI500 and S&P 500. |
| Luo, Ko, Chen, Sun, Zhang, Liu, "AlphaBench: Benchmarking Large Language Models in Formulaic Alpha Factor Mining" | ICLR 2026 (OpenReview d97Q8r7ZKZ) | 2 | A benchmark with an LLM-mutation/crossover EA baseline. Useful as an implementation baseline. |
| Li, Shi, Li, "Genetic Programming with Wavelet-Based Indicators for Financial Forecasting" | Trans. Inst. Measurement & Control 28(3), 2006, 10.1191/0142331206tim177oa | 2 | Wavelet-scale indicators feed GP. A near-miss for "advanced maths in GP". Whether the wavelet scales are executable nodes is unverified. |
| Lin & He (Huatai Securities), "GPT因子工厂" / "GPT Factor Factory" 1.0 and 2.0 | Sell-side reports, Feb and Sep 2024 | 1–2 | LLM multi-agent factor generation with no GP. Not peer-reviewed. **Not independently verified here.** |
| Liu, Ji, Jin (Entropy 2016) | already listed | — | Kimi confirms wavelets are used for preprocessing only, and that the GP evolves boolean/real entry/exit trees. Useful precedent for the representation. |

**Advanced-maths screen.** Kimi's negative result agrees with Claude's, run with independent Chinese and English queries. No work uses signatures, rough paths, information geometry, Fisher information, Wasserstein/OT, spectral entropy or Hurst as executable GP primitives for trading or alpha. Wavelets come closest (Li et al. 2006).

**Kimi citation accuracy: high.** Every checked item resolves with matching authors and venue. Kimi was the only survey to give ICASSP EvoAlpha, AlphaMemo and AlphaBench.
- Confirmed: Alpha Jungle is AAAI 2026, 40(2):997–1005, DOI 10.1609/aaai.v40i2.37069. Kou et al. is Findings of EMNLP 2025, DOI 10.18653/v1/2025.findings-emnlp.1005.
