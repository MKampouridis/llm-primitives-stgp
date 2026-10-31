# LLM-driven alpha factor mining and LLM-generated trading strategies, with a focus on evolutionary and GP coupling

Scope: whether prior work already does "GP evolving LLM-generated trading strategies" (extending Clayman, Kampouridis & Papastylianou, *Large Language Quant*, IEEE CIFEr 2026). Categories: (A) LLM-derived primitives as GP terminals or functions; (B) LLM-seeded GP populations; (C) LLM-in-the-loop GP, with the LLM as variation operator, repair operator or primitive generator; (D) hybrids or co-evolution. Closeness score: 1 to 5, where 5 means GP evolving LLM-derived trading strategies. Tags: [S] means retrieved and checked this session (abstract page, HTML full text, or official listing). [M] means recalled from memory and not re-verified. [S-cite] means the identifier was seen only in another paper's reference list.

Search log (2026-10-30):
1. WebSearch (extended): "LLM genetic programming alpha factor mining arXiv"
2. WebSearch (extended): "LLM evolutionary alpha mining AlphaEvolve finance factor 2025"
3. WebSearch: "AlphaAgent LLM alpha mining regularized exploration decay"
4. Elicit search_papers ("large language model guided genetic programming for formulaic alpha factor mining", 2023 onward). Failed because the plan has no API access.
5. WebFetch: arXiv 2608.01789 (abstract only, no reference list), arXiv HTML 2511.18850v2 (CogAlpha full text, about 60%), arXiv HTML 2602.07085v1 (QuantaAlpha)
6. WebSearch (extended): "LLM-initialized genetic programming population formulaic alpha seeding"
7. WebSearch: "EvoAlpha evolutionary alpha factor discovery large language models NeurIPS 2025 workshop"
8. WebSearch (extended): "large language model evolve trading strategy code genetic algorithm backtest arXiv 2025 2026"
9. WebFetch: arXiv abstract pages 2606.26173 (AlgoEvolve), 2605.23007 (MadEvolve), 2409.06289 (Kou et al.), 2507.17211 (EFS)
10. WebSearch: "Alpha-GPT 2.0 human-in-the-loop AI quantitative investment genetic programming"
11. WebSearch (extended): "LLM genetic programming trading rules hybrid GP primitives large language model financial forecasting"
12. Consensus search ("large language model genetic programming alpha factor mining stock", 2023 onward). Failed because the free quota is used up until 1 November.
13. WebFetch: arXiv PDF 2606.26173 (compressed, so only metadata and outline were readable), arXiv HTML 2604.09601v1 (Hubble), arXiv abstract 2603.16365 (FactorEngine)
14. WebSearch (extended): "LLM mutation crossover operator expression tree alpha factor genetic programming gplearn LLM-enhanced"

Limitations: Both semantic paper databases (Elicit and Consensus) were unavailable, so coverage depends on web search. SSRN, ICAIF proceedings and IEEE CIFEr proceedings were not searched directly. AlgoEvolve and MadEvolve were read at abstract level only.

---

## Q1. What does each LLM alpha-mining or LLM quant-agent work do, and does it have an evolutionary or GP component?

### Takeaway
The field has split into two strands.
- **Agentic or iterative LLM loops with no formal population:** Alpha-GPT, QuantAgent, Kou et al., RD-Agent-Q, AlphaAgent, Alpha Jungle (MCTS), Hubble and FactorEngine.
- **Evolution in the style of FunSearch or AlphaEvolve, with the LLM as the variation operator:** CogAlpha (ACL 2026), QuantaAlpha, EvoAlpha (NeurIPS 2025), EFS, AlgoEvolve and MadEvolve.

Classical tree-based GP (gplearn-style) shows up almost only as a baseline, or as a downstream "enhancement" tool in Alpha-GPT and Alpha-GPT 2.0.

### Cited Findings

**Master table.** Representation is abbreviated "Repr."; "Close." is the closeness score (1 to 5).

| # | Authors (first 3 et al.), year | Exact title | Venue / ID | Cat. | Evolutionary method | LLM role | Domain / data | Repr. | Close. | Tag |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | Wang S., Yuan H., Zhou L. et al., 2023 | Alpha-GPT: Human-AI Interactive Alpha Mining for Quantitative Investment | arXiv:2308.00016 (later version cited by QuantaAlpha as Wang et al. 2025) | B (loose) | GP-based search module refines LLM-proposed alphas | Turns user ideas into seed alpha formulas, then interprets results | Chinese A-shares (M) | Formula strings | 3 | [S] (ID, GP search module); authors [M] |
| 2 | Yuan H., Wang S., Guo J., 2024 | Alpha-GPT 2.0: Human-in-the-Loop AI for Quantitative Investment | arXiv:2402.09746 (draft) | B / D | GP-based "enhancement" tool applied after LLM generation | Multi-agent: mining, modelling, analysis | Not verified | Formulas | 3 | [S] |
| 3 | Wang S., Yuan H., Ni L. M., Guo J., 2024 | QuantAgent: Seeking Holy Grail in Trading by Self-Improving Large Language Model | arXiv:2402.03755 | Background | None (inner and outer self-improvement loop with a knowledge base) | Writes and refines alpha code | Not verified | Code or formula | 2 | [M] |
| 4 | Kou Z., Yu H., Luo J. et al., 2024 | Automate Strategy Finding with LLM in Quant Investment | arXiv:2409.06289 (v4, Nov 2025); EMNLP Findings 2025 not confirmed on the arXiv page | Background | None (generate, then multi-agent filter, then dynamic weighting) | Prompted generation of executable alpha candidates | SSE50, Chinese and US regimes | Executable factors | 2 | [S] |
| 5 | Tang Z., Chen Z., Yang J. et al., 2025 | AlphaAgent: LLM-Driven Alpha Mining with Regularized Exploration to Counteract Alpha Decay | arXiv:2502.16789; KDD 2025 recalled, not verified | Background | None. Iterative Idea, Factor and Eval agents with AST-similarity originality penalty and complexity control | Hypothesis, then formula, then evaluation | CSI 500 and S&P 500, 2021–2024 | Operator-library formulas parsed to AST | 2 | [S]; authors and venue [M] |
| 6 | Li Y. et al. (Microsoft), 2025 | R&D-Agent-Quant (RD-Agent(Q)) | arXiv:2505.15155 | Background | None (research and development loop; factor–model co-optimisation) | Proposes hypotheses and implements code | CSI 300 (M) | Code | 2 | [S-cite]; title [M] |
| 7 | Shi Y., Duan Y., Li J., 2025 | Navigating the Alpha Jungle: An LLM-Powered MCTS Framework for Formulaic Factor Mining | arXiv:2505.11122 | Background | MCTS, not GP | LLM expands and refines tree nodes from backtest feedback | Chinese A-shares (M) | Formulas | 2 | [S] (ID, MCTS); authors [M] |
| 8 | Shi H. et al., 2025 | AlphaForge: A Framework to Mine and Dynamically Combine Formulaic Alpha Factors | AAAI 2025 | Background | Generative-predictive neural network, no LLM | n/a | CSI 300 / CSI 500 (M) | Formulas | 1 | [S-cite] |
| 9 | Liu F., Huang Y., Luo S. et al., 2025/2026 | Cognitive Alpha Mining via LLM-Driven Code-Based Evolution (CogAlpha) | arXiv:2511.18850; ACL 2026 Long (2026.acl-long.538) | **C** | GA-style: 80 seeds from 21 agents, parent pool 32, child pool 96, LLM mutation and crossover agents, percentile-based selection, 2-elite carry-over, 24 generations | Generates the initial population; acts as mutation and crossover operators in natural language and code; multi-agent quality and leakage checking | CSI 300 (main), CSI 500, S&P 500, HSI, HSCI; Qlib backtest | **Python code functions** | **4** | [S] |
| 10 | Han J., Zhang S., Li W. et al., 2026 | QuantaAlpha: An Evolutionary Framework for LLM-Driven Alpha Mining | arXiv:2602.07085 (q-fin.ST) | **C** | Trajectory-level mutation (rewrite the weakest step) and crossover (splice high-reward segments of parent trajectories) | Plans diverse hypotheses, writes expressions and code, self-reflects | CSI 300; zero-shot to CSI 500 and S&P 500 | Operator-library expression, then AST, then code | 3–4 | [S] |
| 11 | Luo H., Ko H., Sun D. et al., 2025 | EvoAlpha: Evolutionary Alpha Factor Discovery with Large Language Models | NeurIPS 2025 (virtual listing 132561; track unconfirmed) | **C** | LLM-guided evolution: mutation, crossover and selection done by the LLM | LLM as "intelligent operator" | Multiple real markets; sparse (ℓ0) portfolio | Factors (not verified) | 4 | [S] (listing only) |
| 12 | Chen J., Luo H., Zhang Y. et al., 2025 | Evolutionary Factor Searching for Sparse Portfolio Optimization Using Large Language Models (EFS) | arXiv:2507.17211 (q-fin.PM; v2 Aug 2026) | **C** | LLM plus EA feedback loop refining a factor pool by portfolio performance | Generates and evolves factors | Fama-French benchmarks; US, HK and CN equities | Factors (not verified) | 4 | [S] |
| 13 | Sharma D., Shroff G., 2026 | AlgoEvolve: LLM-driven Meta-evolution of Algorithmic Trading Programs | arXiv:2606.26173 (cs.AI; IJCAI-2026 template, acceptance unconfirmed) | **C / D** | Bi-level: inner evolution of Python trading programs with the LLM as "semantic mutation operator"; outer loop evolves the prompts (PromptBreeder-style) | Mutation operator and prompt meta-evolution | Not stated in the abstract | **Python trading programs** | **5** (highest) | [S] (abstract) |
| 14 | Kvasiuk Y., Li T., Colegrove O., Münchmeyer M., 2026 | MadEvolve: Evolutionary Optimization of Trading Systems with Large Language Models | arXiv:2605.23007 (q-fin.TR) | **C** | AlphaEvolve-inspired evolution of feature pipelines, signal and execution components; p-hacking analysis | LLM code evolution | Bitcoin | Code | **4–5** | [S] (abstract) |
| 15 | Shi R., Yan S., Cai Y., Lv C., 2026 | Hubble: An LLM-Driven Agentic Framework for Safe and Automated Alpha Factor Discovery | arXiv:2604.09601 | C (weak) | Feedback loop only (3 rounds × 40 candidates, top 5 fed back); no population or crossover; "formal evolutionary operators" left as future work | "Directed mutation engine" | 30 US equities, 2022–2024 | DSL expression trees, then AST sandbox | 3 | [S] |
| 16 | Lin Q., Feng R., Feng Y. et al., 2026 | FactorEngine: A Program-level Knowledge-Infused Factor Mining Framework for Quantitative Investment | arXiv:2603.16365; IEEE ICDM 2026 | Background / D | No EA. LLM directional search plus Bayesian hyperparameter search; experience knowledge base | Logic revision; extracts factors from financial reports | OHLCV (market unnamed) | Turing-complete code | 2–3 | [S] |
| 17 | (authors not retrieved), 2025 | A hybrid approach to formulaic alpha discovery with large language model assistance | *Frontiers of Computer Science*, DOI 10.1007/s11704-025-41061-5 | **B (to RL, not GP)** | LLM seeds the initial alpha pool, which RL refines and gradually replaces; gplearn GP is a baseline | Seed generator | Not verified | Formulas | 3 | [S] (snippet) |
| 18 | (authors not retrieved), 2026 | AlphaAgentEvo: Evolution-Oriented Alpha Mining via Self-Evolving Agentic Reinforcement Learning | ICLR 2026 poster | Background / C | "Evolution" through agentic RL training, not a GA (unverified) | Self-evolving agent | Not verified | Formulas (M) | 3 | [S] (listing) |
| 19 | (not retrieved), 2026 | AlphaPROBE: Alpha Mining via Principled Retrieval and On-graph biased evolution | arXiv:2602.11917 | C? | Biased evolution over a graph of factors | Not verified | Not verified | Not verified | 3 | [S] (title only) |
| 20 | (not retrieved), 2026 | AlphaPareto: Formulaic Alpha Discovery with LLM-Guided Multi-Objective Reinforcement Learning | arXiv:2609.34188 | Background | MORL; GP is a baseline | Guides RL | Not verified | Formulas | 2 | [S] (title and snippet) |
| 21 | Chen et al., 2025 | AlphaSAGE (structure-aware mining via GFlowNets) | arXiv:2509.25055 | Background | GFlowNet | Not verified | Not verified | Formulas | 1 | [S-cite] |
| 22 | (not retrieved), 2025 | Chain-of-Alpha (dual-chain LLM generation and optimisation) | arXiv:2508.06312 | Background | None | Generation and optimisation chains | Not verified | Formulas | 2 | [S-cite] |
| 23 | (not retrieved), 2026 | FactorMiner (self-evolving agent with experience memory) | arXiv:2602.14670 | Background | Memory-based "self-evolution", not a GA | Agent | Not verified | Not verified | 2 | [S-cite] |
| 24 | Li et al., 2024 | Neural-symbolic factor mining agent | ACL Findings 2024 | Background | Not verified | Agent | Not verified | Formulas | 2 | [S-cite] |
| 25 | Ding et al., 2025 | AlphaEval: A Comprehensive and Efficient Evaluation Framework for Formula Alpha Mining | arXiv:2508.13174 | Background (evaluation) | n/a | n/a | n/a | Formulas | 1 | [S] (title) |
| 26 | Yu X., Fu Y., Fan M. et al., 2026 | Towards Autonomous Formulaic Alpha Discovery: An Evolutionary Computation Perspective | arXiv:2608.01789 (cs.NE) | Survey | Treats alpha discovery as noisy, dynamic, multi-objective symbolic EC; six-component and eight-dimension frameworks | Covers LLM and agentic methods | n/a | Symbolic | n/a (key survey to cite) | [S] (abstract) |
| 27 | (not retrieved), 2026 | FaVOR: LLM-Based Agentic Framework for Factor Mining via Empirical Validation | arXiv:2608.30192 | Background | Not verified | Agent | Not verified | Not verified | 2 | [S] (title only) |
| 28 | (not retrieved), 2026 | AlphaDiverse: Post-Training Local Quantitative Research Agents for Diverse Exploration in Alpha Factor Mining | arXiv:2609.29014 | Background | Not verified | Post-trained agent | Not verified | Not verified | 2 | [S] (title only) |
| 29 | (not retrieved), 2026 | AlphaLogics: A Market Logic-Driven Multi-Agent System for Scalable and Interpretable Alpha Factor Generation | arXiv:2603.20247 | Background | Not verified | Multi-agent | Not verified | Not verified | 2 | [S] (title only) |
| 30 | (CityU group), 2025/26 | AlphaBench: Benchmarking Large Language Models in [formulaic alpha mining] | CityU PDF; venue not verified | Background (benchmark) | n/a | n/a | n/a | n/a | 1 | [S] (title only) |
| 31 | Cui C., Wang W., Zhang M. et al., 2021 | AlphaEvolve: A Learning Framework to Discover Novel Alphas in Quantitative Investment | SIGMOD 2021 (M) | Background (pre-LLM GP/EA) | Evolutionary search over formula alphas | None | Chinese stocks (M) | Formulas | 1 | [S] (ResearchGate title); authors and venue [M]. Name clash with DeepMind's AlphaEvolve (Novikov et al. 2025, arXiv:2506.13131) |
| 32 | (not retrieved), 2026 | GA-Contemplation (GAC): "An innovative hybrid investment model using large language models and genetic algorithms" | *Investment Analysts Journal*, DOI 10.1080/10293523.2026.2644790 | A (loose) | GA selects LLM-extracted factors and thresholds | Extracts predictive factors from news | Taiwan equities | Factor set and thresholds | 3 | [S] (snippet) |
| 33 | (not retrieved), 2025 | Agent-Based Genetic Algorithm for Crypto Trading Strategy Optimization (CGA-Agent) | arXiv:2510.07943 | D (parameter tuning) | GA tunes strategy parameters with multi-agent coordination | Agents coordinate the GA | Crypto | Parameter vectors | 2–3 | [S] (snippet) |
| 34 | vincent212 (GitHub), n.d. | llm-assisted-trading-strategy-search (LATSS) | GitHub, not peer reviewed | C | FunSearch-style: LLM writes and mutates strategy code; numerical optimiser fits parameters; out-of-sample and luck-baseline tests | Code writer and mutator | Yahoo Finance tickers | Python code | 4 | [S] (README snippet) |

Supporting citations for the rows above:
- **CogAlpha** uses Python code alphas, an 80-alpha initial pool from 21 agents across 7 hierarchy levels, LLM mutation and crossover agents, 65th and 80th percentile qualified and elite thresholds, a temporal-leakage checker, gpt-oss-120b, Qlib top-50 backtests, and baselines AutoAlpha and AlphaAgent plus ML and DL models. It does not use gplearn or AlphaGen as baselines. — [CogAlpha HTML](https://arxiv.org/html/2511.18850v2). ACL 2026 acceptance — [ACL Anthology 2026.acl-long.538](https://aclanthology.org/2026.acl-long.538/)
- **QuantaAlpha** applies trajectory-level mutation and crossover, uses AST redundancy and complexity control, trains on CSI 300 with transfer to CSI 500 and S&P 500, compares against RD-Agent and AlphaAgent, and cites no GP alpha papers. — [QuantaAlpha HTML](https://arxiv.org/html/2602.07085v1)
- **EvoAlpha** uses the LLM as an intelligent operator for mutation, crossover and selection, applied to sparse portfolios. — [NeurIPS 2025 listing](https://neurips.cc/virtual/2025/132561)
- **EFS** couples an LLM with an EA, using portfolio-performance feedback and RMT-denoised weighting. — [arXiv 2507.17211](https://arxiv.org/abs/2507.17211)
- **AlgoEvolve** evolves Python trading code with the LLM as a semantic mutation operator and runs outer-loop prompt meta-evolution. It reports regime-adaptive logic and fewer zero-trade failures. — [arXiv 2606.26173](https://arxiv.org/abs/2606.26173). A search snippet reports a peak annualised Sharpe of 5.60 and a future direction of "Modular Program Synthesis" (evolving reusable subroutines); these are unverified against the full text. — [arXiv PDF 2606.26173](https://arxiv.org/pdf/2606.26173)
- **MadEvolve** is AlphaEvolve-inspired, trades Bitcoin, evolves the feature pipeline and execution jointly, compares against Claude Code, and analyses p-hacking probability. — [arXiv 2605.23007](https://arxiv.org/abs/2605.23007). A third-party blog reports roughly 7.1× validation PnL using Claude Sonnet 4.6, about 58% of that retained on 2025 test data, and that the forecasting layer overfit; these figures are unverified. — [jiripik.com](https://jiripik.com/2026/07/11/llm-designing-trading-strategies/)
- **Hubble** uses an LLM feedback loop with no formal EA operators; those are future work. — [Hubble HTML](https://arxiv.org/html/2604.09601v1)
- **FactorEngine** represents factors as Turing-complete code and uses LLM directional search with Bayesian hyperparameter search (ICDM 2026). — [arXiv 2603.16365](https://arxiv.org/abs/2603.16365)
- **Kou et al.** use generate, filter and weight with no evolutionary step, and report a 53.17% cumulative return on SSE50 for 2023–2024. — [arXiv 2409.06289](https://arxiv.org/abs/2409.06289)
- **AlphaAgent** uses three agents with AST originality, hypothesis alignment and complexity control, tested on CSI 500 and S&P 500 for 2021–2024. — [arXiv 2502.16789](https://arxiv.org/pdf/2502.16789)
- **Alpha-GPT 2.0** includes a GP-based enhancement tool in a multi-agent pipeline. — [arXiv 2402.09746](https://arxiv.org/pdf/2402.09746). A secondary summary claims the IC of top-20 style alphas nearly doubled after GP enhancement (e.g., Momentum from 0.0095 to 0.0276); this is unverified and comes from an AI-generated summary. — [emergentmind](https://www.emergentmind.com/topics/alphagpt)
- **Alpha-GPT** has a search module that uses LLM-guided GP. — [arXiv 2308.00016](https://arxiv.org/pdf/2308.00016)
- **Frontiers CS hybrid paper:** the LLM seeds the initial pool for an RL generator and gplearn GP is a baseline. — [Frontiers of CS](https://journal.hep.com.cn/fcs/EN/10.1007/s11704-025-41061-5)
- **CGA-Agent, AlgoEvolve, MadEvolve and LATSS** come from a single search. — [CGA-Agent](https://arxiv.org/html/2510.07943v1); [LATSS GitHub](https://github.com/vincent212/llm-assisted-trading-strategy-search)
- **GAC** has the LLM extract factors from news and a GA select factors and thresholds, on Taiwan equities. — [Investment Analysts Journal](https://www.tandfonline.com/doi/abs/10.1080/10293523.2026.2644790)
- **Evolutionary-computation survey** of formulaic alpha discovery. — [arXiv 2608.01789](https://arxiv.org/abs/2608.01789)

### Inferences
- The closest prior works to "evolving LLM-written trading strategies" are AlgoEvolve (2026), MadEvolve (2026) and CogAlpha (ACL 2026). All three use the LLM *itself* as the code-level variation operator, in the FunSearch/AlphaEvolve style. None uses classical tree GP over a primitive set.
- Classical GP appears only in three roles: as a downstream refiner of LLM formulas (Alpha-GPT and 2.0, close to category B), as a baseline (gplearn in the Frontiers CS paper and AlphaPareto), or as pre-LLM history (the 2021 AlphaEvolve).

### Gaps
- AlgoEvolve and MadEvolve were read at abstract level only; the PDF text was compressed. Their assets, LLMs, signal format and baselines are unknown, so a full-text read is the top priority.
- Venues for AlphaAgent (KDD 2025?), Kou et al. (EMNLP Findings?) and Alpha-GPT (later venue) were not confirmed this session.
- Author lists for rows 17–23 and 27–30 were not retrieved.

---

## Q2. Which works seed GP/GA with LLM factors, use the LLM as mutation or crossover operator, or have the LLM propose primitives for a downstream evolutionary miner?

### Takeaway
- **LLM as mutation or crossover operator (category C)** is well populated: CogAlpha, QuantaAlpha, EvoAlpha, EFS, AlgoEvolve, MadEvolve, LATSS, and Hubble in a weak form.
- **LLM seeding of a classical GP population (category B)** exists only loosely: Alpha-GPT and Alpha-GPT 2.0 run GP enhancement on LLM alphas, and the Frontiers CS paper seeds RL rather than GP.
- **LLM-generated primitives used as terminals or functions by a downstream tree-GP (category A)** has no direct finance precedent in any search this session.

### Cited Findings
- **Seeding:**
  - CogAlpha seeds an 80-alpha initial population from 21 LLM agents. — [CogAlpha](https://arxiv.org/html/2511.18850v2)
  - QuantaAlpha uses "Diversified Planning Initialization". — [QuantaAlpha](https://arxiv.org/html/2602.07085v1)
  - The Frontiers CS paper seeds an RL generator. — [FCS](https://journal.hep.com.cn/fcs/EN/10.1007/s11704-025-41061-5)
  - Outside finance, MultiGA seeds a GA from several heterogeneous LLMs. — [arXiv 2512.04097](https://www.arxiv.org/pdf/2512.04097)
- **LLM as variation operator:**
  - CogAlpha's mutation agent edits one alpha's code; its crossover agent merges the logic of two parents. — [CogAlpha](https://arxiv.org/html/2511.18850v2)
  - QuantaAlpha mutates by rewriting the lowest-contributing trajectory step with the prefix fixed, and crosses over by splicing high-reward segments. — [QuantaAlpha](https://arxiv.org/html/2602.07085v1)
  - EvoAlpha uses the LLM for mutation, crossover and selection. — [NeurIPS](https://neurips.cc/virtual/2025/132561)
  - AlgoEvolve uses the LLM as a semantic mutation operator on Python programs, with prompt meta-evolution. — [arXiv 2606.26173](https://arxiv.org/abs/2606.26173)
- **LLM-derived inputs to a GA, not GP:** GAC uses LLM-extracted news factors that a GA selects. — [IAJ](https://www.tandfonline.com/doi/abs/10.1080/10293523.2026.2644790)
- **Tree-GP with LLM operators outside finance:** LLEGO (decision trees) does fitness-guided LLM crossover and diversity-guided mutation, with about 86–88% of offspring valid. — [arXiv 2503.14217](https://arxiv.org/html/2503.14217)
- **Search for gplearn plus LLM operators for alphas:** no paper found. — [search 14 summary](https://www.emergentmind.com/topics/llm-driven-genetic-programming) (generic overview only)

### Inferences
- Category A (an LLM-authored library of mathematically grounded primitives such as spectral entropy, Hurst exponent or Wasserstein distance, recombined by typed tree-GP into boolean entry/exit rules) is the least occupied and most defensible novelty claim.
- Category C is crowded for factor formulas and code. Novelty there would have to come from the strategy-level boolean-signal representation, multi-asset portfolio GA co-evolution (category D), and the cross-domain mathematics, rather than from "LLM as mutation operator" itself.
- AlgoEvolve's stated future work (modular subroutines) points toward category A/D, so it is a race risk worth monitoring.

### Gaps
- No systematic DBLP or Google Scholar sweep was possible because Elicit and Consensus were unavailable. GECCO/EuroGP 2025–2026 LLM-GP finance papers may be missed; a dedicated GECCO search is recommended.

---

## Q3. Representation, markets, evaluation and baselines

### Takeaway
- **Representation:** Most LLM alpha miners use operator-library formula strings parsed to ASTs (AlphaAgent, QuantaAlpha, Hubble, Alpha Jungle). The newer evolutionary ones move to Python code (CogAlpha, FactorEngine, AlgoEvolve, MadEvolve).
- **Markets:** Chinese A-shares dominate, especially CSI 300 and CSI 500, often with S&P 500 transfer.
- **Evaluation:** Cross-sectional IC, RankIC, ICIR and RankICIR, plus Qlib top-k backtests (ARR, IR, MDD, Calmar).
- **Baselines:** Mostly Alpha158/Alpha360, ML and DL models, and LLM agents (AlphaAgent, RD-Agent). gplearn GP is a baseline only in some papers.
- **Single-asset strategies:** Single-asset time-series strategies with boolean signals, as in *Large Language Quant*, are rare; only AlgoEvolve and MadEvolve (Bitcoin) and LATSS are of that type.

### Cited Findings
- **CogAlpha:** CSI 300 training 2011–2019, testing 2021–2024; also CSI 500, S&P 500, HSI and HSCI; LightGBM over alphas; fitness from IC, ICIR, RankIC, RankICIR and MI. — [CogAlpha](https://arxiv.org/html/2511.18850v2)
- **QuantaAlpha:** CSI 300 for 2016–2025; metrics IC, ICIR, RankIC, RankICIR, IR, Calmar, ARR and MDD; baselines include DoubleEnsemble and TRA. — [QuantaAlpha](https://arxiv.org/html/2602.07085v1)
- **Hubble:** 30 US equities with OHLCV; RankIC, IR and turnover composite score; no baselines. — [Hubble](https://arxiv.org/html/2604.09601v1)
- **AlphaAgent:** CSI 500 and S&P 500. — [AlphaAgent](https://arxiv.org/pdf/2502.16789)
- **Kou et al.:** SSE50 cumulative return. — [arXiv 2409.06289](https://arxiv.org/abs/2409.06289)
- **MadEvolve:** Bitcoin trading system. — [arXiv 2605.23007](https://arxiv.org/abs/2605.23007)
- **gplearn GP as a baseline:** in the Frontiers CS hybrid paper and in AlphaPareto. — [FCS](https://journal.hep.com.cn/fcs/EN/10.1007/s11704-025-41061-5); [AlphaPareto](https://arxiv.org/html/2609.34188v1)

### Inferences
- An extension evaluated on per-asset entry/exit strategies with trading metrics (Sharpe, return, MDD), across multiple asset classes, differs in its evaluation regime from the IC-centred, cross-sectional, CSI-focused mainstream. It should still report against at least one LLM-evolution baseline (CogAlpha-style LLM mutation, or an OpenEvolve/AlphaEvolve-style loop) and a plain GP baseline.

### Gaps
- AlgoEvolve's assets and metrics are unknown.
- Whether AlphaGen is used as a baseline in CogAlpha or QuantaAlpha: it is not mentioned in either.

---

## Q4. Does any work target cross-domain advanced mathematics rather than price/volume operator recombination?

### Takeaway
No retrieved work explicitly grounds factors or strategies in information theory, information geometry, rough paths or optimal transport. Every operator library seen is the standard math, time-series, cross-sectional and logical set over OHLCV. The nearest cases each use only one such idea:
- CogAlpha uses mutual information as a *fitness* metric.
- EFS uses random-matrix-theory denoising for *weighting*.
- FactorEngine extracts knowledge from financial reports.

### Cited Findings
- Hubble's DSL has four operator families (math, time-series, cross-sectional, logic) over OHLCV. — [Hubble](https://arxiv.org/html/2604.09601v1)
- AlphaAgent and QuantaAlpha use a standardised operator library with AST control. — [QuantaAlpha](https://arxiv.org/html/2602.07085v1)
- CogAlpha uses MI in fitness and spans seven hierarchy levels of agent prompts; their topics were not fully read. — [CogAlpha](https://arxiv.org/html/2511.18850v2)
- EFS uses RMT denoising in its weighting module. — [EFS](https://arxiv.org/abs/2507.17211)
- AlgoEvolve's abstract mentions no advanced mathematics. — [AlgoEvolve](https://arxiv.org/abs/2606.26173)

### Inferences
Grounding in advanced mathematics (spectral entropy, rate-distortion, signatures, Fisher–Rao, Wasserstein, Hurst, phase transitions) appears to be a real differentiator of the *Large Language Quant* line. Combined with GP over such primitives (category A) or LLM-guided GP that preserves the mathematical semantics (category C), it is likely novel. That claim rests on absence of evidence from about 14 searches.

### Gaps
- CogAlpha's seven agent hierarchy levels might include "physics/information-inspired" agents; this was not checked (about 40% of the full text was unread).
- MadEvolve's evolved feature sets were not inspected.

---

## Q5. 2025–2026 works closest to "GP evolving LLM-generated trading strategies"

### Takeaway
Ranked closest first:
1. AlgoEvolve (Sharma & Shroff, arXiv:2606.26173, June 2026)
2. MadEvolve (Kvasiuk et al., arXiv:2605.23007, May 2026)
3. CogAlpha (Liu et al., ACL 2026)
4. EvoAlpha (Luo et al., NeurIPS 2025) and EFS (Chen et al., arXiv:2507.17211)
5. QuantaAlpha (Han et al., arXiv:2602.07085)

None uses tree-based GP over LLM-derived primitives, none evolves strategies built from advanced-mathematics components, and none co-evolves a portfolio-level GA selecting strategies per asset.

### Cited Findings
- AlgoEvolve: LLM-evolved Python trading programs with bi-level prompt meta-evolution. — [arXiv 2606.26173](https://arxiv.org/abs/2606.26173)
- MadEvolve: AlphaEvolve-style evolution of a BTC trading system with p-hacking analysis. — [arXiv 2605.23007](https://arxiv.org/abs/2605.23007)
- CogAlpha: LLM-driven code-based GA of alphas. — [ACL Anthology](https://aclanthology.org/2026.acl-long.538/)
- EvoAlpha: LLM evolutionary operators for factors. — [NeurIPS 2025](https://neurips.cc/virtual/2025/132561)
- The EC survey frames the whole area as noisy, dynamic, multi-objective symbolic evolution. — [arXiv 2608.01789](https://arxiv.org/abs/2608.01789)
- Background, pre-LLM GP for trading strategies: Vectorial GP. — [arXiv 2504.05418](https://arxiv.org/pdf/2504.05418)

### Inferences
- Recommended positioning: "unlike AlgoEvolve, MadEvolve and CogAlpha, where the LLM *is* the variation operator over free-form code, we use typed GP over an LLM-authored library of mathematically grounded primitives (A), optionally with LLM repair or mutation (C), co-evolved with the portfolio-level GA (D)." This should be checked against the full texts of AlgoEvolve and MadEvolve before any claim is made.
- The novelty claim must not be "first to evolve LLM-generated trading strategies"; AlgoEvolve and MadEvolve already do that in the LLM-operator sense.

### Gaps
- No ICAIF 2025, GECCO 2026 or IEEE CIFEr 2026 proceedings were searched directly, and SSRN was not searched. A follow-up on those venues is recommended.
