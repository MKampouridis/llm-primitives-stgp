# LLMs combined with GP and evolutionary algorithms for trading rules, strategies and forecasting (novelty check for extending "Large Language Quant")

Scope: works where LLMs and evolutionary computation together produce trading rules, strategies or signals, or time-series trading systems. Alpha-factor mining is out of scope and appears only as background.
Search date: 2026-10-30. [S] = retrieved and checked this session (abstract page, HTML or repository). [M] = recalled or seen only in a snippet or citation.
Tool limits: the Elicit search tool returned "no API access" and Consensus returned "monthly quota exhausted". All retrieval used WebSearch and WebFetch (about 25 calls).

## Q1. Do LLM+GP or LLM-guided evolutionary trading-strategy papers exist? What are their mechanisms, assets and evaluation?

### Takeaway
Yes. A fast-growing cluster (Oct 2025 to Oct 2026) evolves trading strategies with LLMs. All but one evolve **Python code directly, with the LLM as the mutation, variation or repair operator** (AlphaEvolve or FunSearch style). This is category C, applied to whole programs rather than to GP trees. The exception, LLM-GA (IEEE SMC 2025), uses a GA over combinations of signals, with the LLM doing seeding and crossover/mutation (categories B and C). **None found uses tree-based or strongly typed GP whose primitives or terminals are LLM-derived (category A), or co-evolves a GP program population with an LLM-grown primitive set (category D, first variant).** None uses advanced-mathematics indicators (spectral entropy, signatures, Fisher–Rao, Wasserstein and so on) as an explicit primitive basis. None evaluates on a 19-asset crypto/FX/index/commodity universe.

### Cited Findings (each paper with fields: authors / year / title / venue / ID / category / evolutionary method / LLM role / domain / representation / closeness 1–5 / [S] or [M])

1. **ProFiT** – Siper, Khalifa, Soros, et al. (also Nasir, Togelius); 2026; "ProFiT: Program Search for Financial Trading"; GECCO '26 (ACM), pp. 727–734; DOI 10.1145/3795095.3805175; SSRN preprint Dec 2025 (abstract_id 5889762). **Category C.** It is an LLM-driven evolutionary algorithm. Each strategy is an independent program mutated at code level on a "complexifying representation", with self-analysis and walk-forward validation in a closed loop. The authors claim it beats Random in 100% of cases and Buy-and-Hold in more than 77% of evolved strategy–asset combinations. Domain: multiple assets; the exact list was not retrieved. Representation: Python strategy code. Closeness **4**: same venue community (GECCO), code-level evolution of trading strategies, but no GP trees or primitive set. [S] (ACM DOI and SSRN listing via search; no full text) — [ACM DOI](https://doi.org/10.1145/3795095.3805175); [SSRN](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=5889762)
   - Community reproduction (not by the authors). An LLM "Analyst" reviews backtest performance and an LLM "Developer" proposes code changes. A separate LLM repair step fixes errors from the traceback. Strategies are Python classes for backtesting.py with 0.2% commission and 5 seed strategies (Bollinger seed by default). Defaults: 15 generations, 5-fold time-series split, gpt-4o, Bitcoin data from CoinMarketCap. The README notes it differs from the paper. [S] — [GitHub JulesLscx/ProFiT](https://github.com/JulesLscx/ProFiT)
   - Follow-up by the same group: Siper, Khalifa, Togelius (Aug 2026), "The Time Value of Evolution", arXiv:2608.13297. It credits mutation lineages in automated discovery of trading policies using an RL actor-critic over "multi-step mutation trees". The abstract does not mention LLMs, only a "shared generative backbone", and reports a +0.394 Sharpe-unit improvement in validation AUC. Category: Background/C. Closeness 3. [S] (abstract only) — [arXiv 2608.13297](https://arxiv.org/abs/2608.13297)

2. **QuantEvolve** – Yun, Lee, Jeon (Qraft Technologies); 2025; "QuantEvolve: Automating Quantitative Strategy Discovery through Multi-Agent Evolutionary Framework"; arXiv:2510.18569, oral at the ACM ICAIF 2025 AI4F workshop (non-archival). **Category C (plus quality diversity).**
   - Method: a MAP-Elites-like feature map over strategy category, trading frequency, MDD, Sharpe, Sortino and return (16 bins), plus islands that migrate the top 10%.
   - LLM roles: a Research agent writes hypotheses from parent and "cousin" strategies, a Coding team implements and debugs them, and an Evaluation team analyses results and curates insights. Models are Qwen3-30B-A3B and Qwen3-Next-80B.
   - Representation: Python Zipline code (`initialize` and `handle_data`), run on daily OHLCV.
   - Assets: 6 US large-cap stocks (AAPL, NVDA, AMZN, GOOGL, MSFT, TSLA) and ES/NQ futures. Equities split train 2015–20, val 2020–22, test 2022–25. Fitness is Sharpe + IR + MDD.
   - Closeness **4**. [S] — [arXiv HTML](https://arxiv.org/html/2510.18569v1)

3. **AlgoEvolve** – Sharma, Shroff (IIIT Delhi); 2026; "AlgoEvolve: LLM-driven Meta-evolution of Algorithmic Trading Programs"; arXiv:2606.26173 (cs.AI, 24 Jun 2026). **Category C+D.**
   - Method: the inner loop evolves Python strategies with the LLM as "semantic mutation operator". The outer loop evolves the *prompt* that guides evolution, encoded as a 4-gene "Prompt Genome" with elitism, uniform crossover and LLM mutation of genes.
   - LLMs: Gemini Flash (inner loop) and Gemini Pro (meta loop).
   - Representation: a Python function from features to a (short, long) horizon action in {0..4}. It explicitly does not use GP trees and contrasts itself with classical GP.
   - Data: 5-minute intraday OHLCV for obfuscated stocks on the NUMIN platform, with walk-forward evaluation.
   - Results: a headline Sharpe of 5.60 for the elite. Its own Table 1 shows inner-loop-only evolution at a higher Sharpe (5.71) than the AlgoEvolve row (5.08).
   - Closeness **4**. The closest example of "evolving the spec or prompt the LLM implements", one variant of category D. [S] — [arXiv HTML](https://arxiv.org/html/2606.26173)

4. **MadEvolve** – Kvasiuk, Li, Colegrove, Münchmeyer; 2026; "MadEvolve: Evolutionary Optimization of Trading Systems with Large Language Models"; arXiv:2605.23007 (q-fin.TR, 21 May 2026). **Category C.**
   - Method: AlphaEvolve-style. MAP-Elites grid (code length, embedding diversity, score), 5 islands with ring migration, an elite archive, and diff, rewrite or crossover mutations restricted to EVOLVE-BLOCKs.
   - LLMs: an ensemble of 5 across OpenAI, Anthropic, Google and DeepSeek.
   - What is evolved: the target-position function, the order-placement function, and the feature set for a ridge predictor. Run 5 evolves features and execution jointly.
   - Data: BTCUSD 1-minute bars. Validation 2024, out-of-sample test 2025. Test Sharpe rose from 3.82 to 5.65, with a p-hacking analysis.
   - Also compares against Claude Code as an agentic baseline.
   - Closeness **3–4**. Run 4 evolves the *feature/indicator* pipeline jointly with the strategy, the closest analogue to evolving LLM-derived indicators, but it is single-asset and high-frequency. [S] — [arXiv HTML](https://arxiv.org/html/2605.23007v1)

5. **LLM-GA** – Zhang D., Jiang Z., Ji Q., et al. (XJTLU); 2025; "LLM-Guided Evolutionary Strategy Generation for Quantitative Trading"; IEEE SMC 2025, pp. 3665–3670; DOI 10.1109/SMC58881.2025.11343400. **Categories B+C.**
   - Method: a GA combines technical, fundamental and sentiment signals into strategies. The LLM initializes seed strategies and performs "semantically-aware" crossover and mutation.
   - Data: Chinese stocks 2020–24. Results: annualized excess return 12.3% and MDD 35.2%.
   - Ablations: LLM initialization improves starting quality by 215%, and semantic crossover cuts invalid strategies by 83.5%. It is 2–3% below RL methods on AER.
   - Closeness **4**. The nearest *GA-over-signal-combinations with LLM seeding and variation*. Its primitives are standard signals, not LLM-derived. [S] (abstract page) — [XJTLU](https://scholar.xjtlu.edu.cn/en/publications/llm-guided-evolutionary-strategy-generation-for-quantitative-trad/)

6. **EvoQuant** – Mao, Li C., Li X., et al.; 2026; "EVOQUANT: Self-Evolving Verifier-Guided Strategy Optimization for Robust Quantitative Trading"; arXiv:2607.12455 (v3, Sep 2026). **Category C-like (LLM edit loop).**
   - Method: the LLM diagnoses bottlenecks and proposes semantically controlled edits. A multi-stage verifier and backtester accept or reject them, and experience is distilled into reusable knowledge.
   - Evaluation: 7 strategies (4 A-share, 3 crypto). Mean test Sharpe rose from −0.298 to 0.538.
   - The abstract does not show whether a population-based EA is used.
   - Closeness **3**. [S] (abstract) — [arXiv](https://arxiv.org/abs/2607.12455)

7. **TradeGrad** – Yang C., Wang Q., Zhu F., et al.; 2026; "Trading Strategy Optimization via Textual Gradient"; arXiv:2610.03128 (Oct 2026). **Background.** It optimizes trading programs by LLM textual gradients, not evolution, on A-share and US equities, with a cross-period robust objective. A search snippet says it compares against AlphaEvolve-style baselines; this is unverified on the abstract page. Closeness **2**. [S] — [arXiv](https://arxiv.org/abs/2610.03128)

8. **ELfolio** (ECNU and Emoney); year not confirmed; "ELfolio: strategy evolution via large language models for portfolio…"; venue not retrieved. **Category C, for portfolio heuristics** (not timing rules). The LLM plus an EA generates and evolves portfolio-optimization heuristic strategies. Related items in the same results: "Evolving portfolio heuristics: a self-correcting LLM framework" (UNNC) and LLMDE (arXiv:2609.16846, LLM-driven differential evolution for portfolio optimization). Closeness **2**. [M] (titles and snippets only) — [ECNU Pure](https://pure.ecnu.edu.cn/en/publications/elfolio-strategy-evolution-via-large-language-models-for-portfoli/); [UNNC](https://research.nottingham.edu.cn/en/publications/evolving-portfolio-heuristics-a-self-correcting-llm-framework-for/); [LLMDE arXiv](https://arxiv.org/pdf/2609.16846)

9. **EvolveTrade** – arXiv:2609.17632, "Experience-Driven Policy Refinement for Self-Evolving LLM Trading Agents". "Self-evolving" here appears to mean agent experience refinement, not an EA. Not fetched. Closeness **1–2**. [M] — [arXiv](https://arxiv.org/pdf/2609.17632)

10. **Survey** – "Agentic Quantitative Trading: A Survey of Workflows, Systems, and Evaluation", arXiv:2608.31041. A search snippet says it cites a crypto "constrained hypothesis-to-factor pipeline" (Huang et al., 2026c). Not fetched. A useful place to check for missed items. [M] — [arXiv](https://arxiv.org/pdf/2608.31041)

11. Informal: a DEV Community blog, "The Evolving Trader: Autonomous Strategy Evolution". Not scholarly; the author reports that diversity mattered more than exploitation. [M] — [DEV](https://dev.to/jestersimpps/the-evolving-trader-autonomous-strategy-evolution-m1e)

### Inferences
- The field has converged on **LLM-as-mutation-operator over raw Python strategy code** (ProFiT, QuantEvolve, AlgoEvolve, MadEvolve, EvoQuant). Since the LLQ extension's strategies are already Python `compute_signals(df)`, a plain "AlphaEvolve over LLQ strategies" is **not novel per se**. ProFiT (GECCO'26) and QuantEvolve are the direct prior art reviewers will cite.
- What remains open is a **GP-native** design:
  - (A) LLM-generated advanced-math indicators wrapped as typed GP terminals or functions inside a strongly typed or tree GP of boolean entry/exit rules.
  - (D) co-evolution, where GP evolves rule trees while the LLM grows or prunes the primitive library based on GP usage statistics.
  - Evaluation on a heterogeneous multi-asset universe (crypto, FX, indices, commodities) with GA portfolio selection on top.
  - Nothing retrieved does any of these.
- Code-evolution papers show serious validation-to-test decay (MadEvolve's retention gap; AlgoEvolve's elite versus mean Sharpe). The interpretable GP-tree angle combined with LLM primitives gives a defensible framing: interpretability, controllable search space, overfitting control.

### Gaps
- ProFiT's exact asset list, LLM model and selection scheme in the paper (not the reproduction) were not retrieved; the full text is behind ACM/SSRN.
- The EvoQuant and TradeGrad full texts were not read; their representation and search type are unconfirmed.
- The ELfolio venue and year are unconfirmed.
- Consensus and Elicit semantic search were unavailable, so peer-reviewed journal coverage (ESWA, ASOC, GPEM) relies on web search only.

## Q2. Has any work used LLMs to generate NEW technical indicators or features that GP/GA/evolutionary trading systems then use?

### Takeaway
No direct instance was found of LLM-generated indicators populating a GP terminal or function set for trading rules. The nearest are MadEvolve Run 4/5 (LLM evolves feature-calculation code jointly with the strategy) and LLM-GA (GA over signals, with LLM seeding and variation, but the signals are conventional). In GP generally, LLMs have been used to seed or propose trees (robotics behaviour trees, GP hyper-heuristics), but not as primitive-set generators in finance.

### Cited Findings
- A web search for "LLM generated technical indicators genetic programming terminal set" returned only classical GP terminal-set work: Essex strongly typed GP with technical and sentiment terminal sets on 35 stocks (GECCO 2023, DOI 10.1145/3583131.3590359), and DC-indicator terminals (PPSN 2022). No LLM-generated terminals. — [Essex STGP](https://repository.essex.ac.uk/35413/1/T1___conference_paper.pdf); [DC GP PPSN](https://repository.essex.ac.uk/32960/1/PPSN_2022.pdf)
- MadEvolve evolves `default_calcset`, the feature set for a ridge alpha predictor. The validation composite rose from 0.085 to 0.128 and test IC from 0.059 to 0.099, but better prediction did not automatically raise PnL. — [MadEvolve](https://arxiv.org/html/2605.23007v1)
- Non-finance GP hybrids: an LLM supervises GP of behaviour trees (proposing trees and mutation rates) in *Robotics* 2026, DOI 10.3390/robotics15050098. LLM-GPHH has an LLM generate tree heuristics from elites, merged with GP offspring (AJCAI 2024). HyGenar uses an LLM to initialize a GA population (arXiv:2505.16978). None generates primitives. — [Robotics](https://doi.org/10.3390/robotics15050098); [LLM-GPHH](https://homepages.ecs.vuw.ac.nz/foswiki/pub/Users/HMa/Here/2024_Zhengxin_AJCAI_LLM.pdf); [HyGenar](https://arxiv.org/html/2505.16978)
- Adjacent (alpha domain, background only):
  - "A hybrid approach to formulaic alpha discovery with large language model assistance" (Frontiers of Computer Science, 2026, DOI 10.1007/s11704-025-41061-5) combines LLM assistance with GP alpha expressions. [M]
  - "Cognitive Alpha Mining via LLM-Driven Code-Based Evolution" (arXiv:2511.18850). [M]
  - "Sentiment-Aware Stock Price Prediction with Transformer and LLM-Generated Formulaic Alpha" (arXiv:2508.04975): LLM alphas used as Transformer features, no GP. [M]
  - Sources: [FCS](https://journal.hep.com.cn/fcs/EN/10.1007/s11704-025-41061-5); [CogAlpha](https://arxiv.org/pdf/2511.18850); [2508.04975](https://arxiv.org/html/2508.04975v2)
- A GitHub master's-thesis repository (LLM-Predict-Stock) has an LLM score news-derived factors (up, down or undetermined) and a GA select the factor combination. Not peer-reviewed. Category A-like, but with news factors rather than math indicators. Closeness 2. [M] — [GitHub](https://github.com/bofrankbo/LLM-Predict-Stock)

### Inferences
- Category A for trading rules (LLM-authored, mathematically grounded indicators as typed GP primitives) appears **unoccupied**. The closest analogue sits in alpha-factor mining (the FCS 2026 hybrid), which another researcher covers.

### Gaps
- The Frontiers of Computer Science hybrid paper's mechanism (whether LLM outputs become GP terminals or seeds) was not verified. The alpha-mining researcher should confirm it.

## Q3. Do known GP-for-finance groups (Kampouridis/Essex, Tsang/EDDIE, Brabazon/O'Neill, Chen, Christodoulaki, Long, Adegboye) have LLM-incorporating work?

### Takeaway
None was found. Recent Essex output is GP-only: multi-objective GP with directional changes and a modified Sharpe ratio (AI Review 2026), and physical-time versus DC GP (IEEE Access 2025). Grammatical evolution in finance (Brabazon/O'Neill) shows no LLM hybrid. The LLM+evolution trading work comes from outside the classical GP-finance community: Togelius' NYU group (ProFiT), Qraft (QuantEvolve), IIIT Delhi (AlgoEvolve), XJTLU (LLM-GA) and HKUST(GZ) (EvoQuant).

### Cited Findings
- The search "Kampouridis large language model genetic programming finance 2025 2026" returned only GP-without-LLM papers: Long, Kampouridis, Papastylianou, "Multi-objective GP-based algorithmic trading using directional changes and a modified Sharpe ratio", *Artificial Intelligence Review* 59(2), 2026; and the IEEE Access 2025 physical-time versus DC GP paper. — [Essex repository](https://repository.essex.ac.uk/41752/); [Springer](https://link.springer.com/article/10.1007/s10462-025-11390-9)
- Christodoulaki and Kampouridis, technical and sentiment analysis with GP (CIFEr 2022): sentiment terminals versus technical terminals, no LLM. — [GP bibliography](http://gpbib.cs.ucl.ac.uk/gp-html/Christodoulaki_2022_CIFEr.html)
- The search "LLM-assisted genetic programming trading rules grammatical evolution" returned only classical grammatical-evolution and GP trading-rule papers (O'Neill et al. on the FTSE 100; Potvin et al. 2004) plus AlgoEvolve. No GE+LLM trading paper. — [GE FTSE](https://link.springer.com/chapter/10.1007/3-540-45365-2_36); [Potvin et al.](https://www.sciencedirect.com/science/article/abs/pii/S0305054803000637)
- Related GP-trading baseline without LLMs: Menoita and Silva, "Evolving Financial Trading Strategies with Vectorial Genetic Programming", arXiv:2504.05418. — [arXiv](https://arxiv.org/html/2504.05418v1)

### Inferences
- An Essex paper that brings the group's GP-trading lineage (strongly typed GP, DC, sentiment terminals) together with LLM-generated primitives would be the first from this community. That positioning is credible.

### Gaps
- Tsang/EDDIE, Chen Shu-Heng and Adegboye were not searched individually by name because of the call budget. Generic queries surfaced no LLM work from them.

## Q4. Is there LLM-based evolutionary search over Python trading-strategy code with backtest fitness? Is there GP or GA evolving portfolios of LLM-generated strategies beyond LLQ?

### Takeaway
Code-level LLM evolution with backtest fitness is now well established: ProFiT, QuantEvolve, AlgoEvolve, MadEvolve and EvoQuant (see Q1). No paper was found that uses GP or GA to evolve portfolios or allocations *over a library of LLM-generated strategies*, as LLQ's portfolio GA does. QuantEvolve releases a strategy archive but does not GA-allocate across it. ELfolio, EPH and LLMDE evolve portfolio *heuristics or weights* with LLMs, not combinations of LLM-generated timing strategies.

### Cited Findings
- QuantEvolve evolves Zipline Python strategies with backtest fitness and releases a dataset of evolved strategies. — [arXiv 2510.18569](https://arxiv.org/html/2510.18569v1)
- MadEvolve compares its LLM evolution against Claude Code-driven agentic search. This is directly relevant to LLQ's Claude Code generation baseline. — [arXiv 2605.23007](https://arxiv.org/html/2605.23007v1)
- AlgoEvolve uses composite fitness 0.7·return + 0.3·cross-asset consistency, with walk-forward windows. — [arXiv 2606.26173](https://arxiv.org/html/2606.26173)
- LLM plus EA for portfolio heuristics (ELfolio, EPH) and LLM-driven differential evolution for portfolio optimization (LLMDE, arXiv:2609.16846). [M] — [ECNU](https://pure.ecnu.edu.cn/en/publications/elfolio-strategy-evolution-via-large-language-models-for-portfoli/); [LLMDE](https://arxiv.org/pdf/2609.16846)

### Inferences
- **Negative-result log** (queries that returned nothing matching A or D for trading):
  - "LLM generated technical indicators GP terminal set trading"
  - "Kampouridis LLM GP finance"
  - "LLM-assisted GP trading rules grammatical evolution"
  - "LLM-seeded GP financial forecasting / GPT indicators GA trading"
  - "GP with LLM-generated primitive set"
  - "GP + LLM algorithmic trading hybrid EvoApps/GECCO/CEC 2026"
  - "LLM evolves trading code crypto forex multi-asset"
  - The GECCO '26 search surfaced only ProFiT. No EvoApps or CEC 2026 hit was found.
- **Verdict:**
  - Categories B and C for trading strategies are **taken**: LLM-GA (SMC 2025) for GA seeding and variation; ProFiT, QuantEvolve, AlgoEvolve and MadEvolve for code-level LLM mutation.
  - Category D, the prompt/spec-evolution variant, is **partially taken** by AlgoEvolve's meta-evolved prompt genome.
  - **Not found:** (A) GP trees over LLM-authored advanced-math primitives for boolean entry/exit rules; (D) GP–LLM co-evolution of the primitive library; and any of these on a 19-asset cross-class universe with a portfolio GA layer. The extension should be framed as GP-native with LLM-derived primitives, contrasted explicitly with ProFiT, QuantEvolve, AlgoEvolve, MadEvolve and LLM-GA.

### Gaps
- Fresh arXiv items from the last 4–6 weeks may not be indexed by web search.
- The agentic-quant survey (arXiv:2608.31041) and the LLM-agents trading survey (arXiv:2605.19337) were not fetched. Their reference lists should be scanned before submission.
