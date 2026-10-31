# Closest-work verification: LLM-generated primitive library for (ST)GP trading rules (claims A and D)

Candidate claim: (A) an LLM-written library of mathematically grounded primitives (spectral entropy, rate-distortion, signatures, Fisher-Rao, Hurst, Wasserstein, etc.) used as typed terminals/functions of a strongly typed tree GP that evolves trading rules; (D) the LLM grows, prunes and refines that primitive set during the GP run.
Markers: [S] = retrieved and read this session (2026-10-30); [M] = recalled only, not verified. Closeness: 1-5, where 5 = GP evolving trading rules over an LLM-generated primitive library.

Overall: none of the targets does A or D in finance. PACE (target 1) does a domain-general analogue of D: an LLM maintains a persistent library of reusable code primitives. But the LLM composes those primitives, not a GP tree, and PACE has no pruning step and no finance application. The only typed-tree trading GP with an LLM in the loop (The Time Value of Evolution, Siper et al.) uses the LLM as mutation operator and compiler into a typed trading language. I found no evidence that the LLM extends that language's primitive set.

## 1. PACE: Primitive-Aware Code Evolution (arXiv:2608.07395)

### Takeaway
PACE is the nearest methodological precedent for D, but outside finance and without GP. An LLM creates "Executable Algorithmic Primitives" (EAPs), which are Python functions kept in a persistent, growing set. Thompson sampling chooses which EAP to inject. The LLM, through prompted operators, writes the EAPs into whole programs. No typed tree GP is involved, and EAPs are never explicitly pruned. Closeness: 3/5.

### Cited Findings
- [S] Bibliographic: Zhuoliang Xie, Ruihao Zheng, Xiang Xu, Genghui Li, Zhengkun Wang. "PACE: Primitive-Aware Code Evolution for Automated Algorithm Design". arXiv:2608.07395v1 [cs.SE], submitted 7 Aug 2026. Preprint, no venue listed. Affiliations: SUSTech and Shenzhen University. — [arXiv abs](https://arxiv.org/abs/2608.07395)
- [S] Motivation: LLM-based automated algorithm design (AAD) usually evolves whole programs, so useful local code fragments are hard to isolate and keep. PACE stores them as reusable components in a dynamic set. — [arXiv abs](https://arxiv.org/abs/2608.07395)
- [S] Creation is done by the LLM through three prompts. E1 initialises helper functions from the task description. E2 extracts a complex internal computation from the current best algorithm. E3 generates a new function conditioned on the top-k EAPs, with a novelty requirement. At most one EAP is added per generation, and extraction takes priority over generation. — [arXiv HTML](https://arxiv.org/html/2608.07395)
- [S] Credit: each EAP has a Beta posterior over its success rate. A transfer counts as a success when the child beats its parent. Thompson sampling uses these posteriors to pick the EAP to inject, without a separate evaluation set. — [arXiv HTML](https://arxiv.org/html/2608.07395)
- [S] Pruning: the paper describes no explicit pruning. EAPs persist even after their source algorithm leaves the population. Poor EAPs are simply sampled less often. — [arXiv HTML](https://arxiv.org/html/2608.07395)
- [S] Composition: four LLM-prompted operators act on each parent's set of EAP calls (insertion, replacement, refinement of usage, and crossover of EAPs between parents). An AST verifier checks the structural contract. The EAP implementation stays fixed when transferred. — [arXiv HTML](https://arxiv.org/html/2608.07395)
- [S] Tasks: Racing Car, Bipedal Walker, TSP-Construct and TSP-ACO. Main LLM: GPT-4o-mini (ablations use DeepSeek-v4-flash and Gemini-3.1-flash-lite). Baselines: EoH, ReEvo, MCTS-AHD, HSEvo and MLES, plus PPO, DeepACO, greedy construction and ACO. — [arXiv HTML](https://arxiv.org/html/2608.07395)
- [S] There is no finance application. Related work cites Koza's primitive sets and automatically defined functions, and DreamCoder and LILO as library learning. PACE positions itself as different from these. — [arXiv HTML](https://arxiv.org/html/2608.07395)

### Inferences
- How our extension differs: PACE is "LLM-maintained primitive library plus LLM-as-composer" for generic algorithm design. Our extension has five differences:
  - Composition is done by a strongly typed tree GP, so the LLM is not the search operator over rules. This gives typed, interpretable, cheap-to-evaluate rule trees and a far larger number of evaluations per LLM call.
  - Primitives are domain-specific and mathematically grounded financial signals with typed signatures (series to scalar, regime, boolean).
  - Primitives are pruned and refined, not only added.
  - The application is trading, with a portfolio-level GA.
  - Library credit is based on GP usage and fitness contribution, not parent-child improvement after LLM insertion.

  PACE should be cited as the closest analogue for D and for usage-based primitive credit. Note also that it explicitly contrasts itself with Koza-style primitive sets.

### Gaps
- The last ~40k characters of the HTML (appendix and later sections) were not read. They could contain a pruning or capacity mechanism, but the main method sections state none.

## 2. AlgoEvolve (arXiv:2606.26173)

### Takeaway
AlgoEvolve is LLM-as-mutation-operator over whole Python intraday trading programs (category C), with an outer loop that meta-evolves the prompts. It has no primitive or subroutine library and no GP baseline. Its conclusion explicitly names "Modular Program Synthesis ... evolving discrete, reusable sub-routines" as future work, which is a direction close to A and D. Closeness: 2/5.

### Cited Findings
- [S] Bibliographic: Dhruv Sharma, Gautam Shroff. "AlgoEvolve: LLM-driven Meta-evolution of Algorithmic Trading Programs". arXiv:2606.26173v1 [cs.AI], 24 Jun 2026. Preprint, no venue listed. — [arXiv abs](https://arxiv.org/abs/2606.26173)
- [S] Two loops:
  - Inner loop: Gemini Flash generates and refines strategies. The top-2 best and top-2 worst prior programs go into the context, and the best program becomes the next parent.
  - Outer loop: Gemini Pro meta-evolves "prompt genomes" using elitism, tournament-style selection, uniform meta-crossover, and a Meta-LLM that rewrites one gene per child.
  - No island model or MAP-Elites. — [arXiv HTML](https://arxiv.org/html/2606.26173)
- [S] Data: the NUMIN intraday paper-trading platform. Anonymised equities, 5-minute OHLCV bars with technical indicators, over 200 trading days, and 5 obfuscated symbols per day. The strategy is a Python function that outputs a short-horizon and a long-horizon signal, each in {0..4}. Positions exit after 10 candles, with a 10 bps cost. Fitness is 0.7 × PnL + 0.3 × consistency. Evaluation is walk-forward (fixed 13-day windows compared with 5-day sliding windows). — [arXiv HTML](https://arxiv.org/html/2606.26173)
- [S] No reusable subroutines or primitive library are described. GP (Koza; Potvin et al.) appears only in related work. Baselines are a seed heuristic, Standard Evol, an LSTM, a random forest and frozen champions. Table 1 reports annualised Sharpe of 5.60 for AlgoEvolve and 5.71 for Standard Evol. The population-mean Sharpe is about 1.21. — [arXiv HTML](https://arxiv.org/html/2606.26173)
- [S] Future work (conclusion): explore Modular Program Synthesis to overcome the observed complexity ceiling by evolving discrete, reusable sub-routines. — [arXiv HTML](https://arxiv.org/html/2606.26173)

### Inferences
- How our extension differs: AlgoEvolve evolves monolithic LLM-written programs and prompts, with no reusable components, and on intraday anonymised equities. It names reusable sub-routines only as future work. Our extension does three things it does not:
  - It realises that modularity explicitly, as an LLM-authored typed primitive library.
  - It hands composition to STGP rather than the LLM.
  - It grounds primitives in specific mathematics, applied to daily multi-asset OHLCV with portfolio allocation.

  AlgoEvolve's future-work sentence can be cited as an independent call for exactly this direction.

## 3. ProFiT, The Time Value of Evolution, Continuous Program Search (Siper, Khalifa, Soros, Nasir, Azhang, Togelius)

### Takeaway
These three papers come from one group (Siper, Khalifa, Togelius, with Soros, Nasir and Azhang). ProFiT, as described secondarily, evolves source-level trading programs with LLM feedback (category C). Continuous Program Search learns a latent space over a fixed trading DSL. The Time Value of Evolution is the only typed-tree trading-GP work found with an LLM in the loop: a fine-tuned Qwen3-8B mutates natural-language policies and compiles them into a typed tree language, GPTL. No evidence was found that any of them lets the LLM create primitives. Closeness: ProFiT 2/5; Time Value of Evolution 3/5 (typed tree trading GP with an LLM, but the LLM is the mutation operator and compiler, not a primitive author); Continuous Program Search 2/5.

### Cited Findings
- [S] ProFiT bibliographic, as cited in arXiv:2608.13297: M. Siper, A. Khalifa, L. B. Soros, M. U. Nasir, J. Azhang, J. Togelius (2026). "ProFiT: program search for financial trading". Proceedings of GECCO 2026, pp. 727–734. DOI 10.1145/3795095.3805175. That paper describes ProFiT as evolving source-level trading programs with language-model feedback. — [arXiv:2608.13297 HTML](https://arxiv.org/html/2608.13297)
- [S] ProFiT method, from secondary sources: LLMs generate and mutate strategy source code on hourly data from 2008. Each backtest report goes back to the LLM. Strategies above a minimum acceptable score enter the population. A co-author claims ProFiT beat buy-and-hold in more than 77% of runs (self-reported). — [search summary of a LinkedIn post by M. U. Nasir and of arXiv:2610.03128](https://arxiv.org/html/2610.03128v1)
- [S] Time Value of Evolution bibliographic: Matthew Siper, Ahmed Khalifa, Julian Togelius. "The Time Value of Evolution". arXiv:2608.13297v1 [cs.LG], 13 Aug 2026. — [arXiv abs](https://arxiv.org/abs/2608.13297)
- [S] Time Value of Evolution method:
  - It proposes Lineage-Value Policy Gradients (LVPG), an actor-critic method for assigning credit along lineages and setting mutation intensity in evolutionary trading-policy search.
  - Over 90 paired runs, it reports +0.394 Sharpe units in validation best-so-far AUC. — [arXiv abs](https://arxiv.org/abs/2608.13297)
- [S] Time Value of Evolution representation and setup:
  - The search representation is a natural-language policy. The execution representation is GPTL ("Genetic Programming Trading Language"), a typed tree language that outputs Boolean long-entry, long-exit, short-entry and short-exit signals.
  - The LLM is Qwen3-8B, multitask fine-tuned (44,736 examples) for mutation, language-to-GPTL compilation and the reverse translation, then aligned with Offset DPO and given LoRA actor and critic heads.
  - Data: hourly continuous futures (ES, silver, 30Y Treasury), about 24k bars each, 10 rolling folds.
  - The paper does not list GPTL primitives and does not say the LLM can add indicators. Only numeric leaves are tuned during validation. — [arXiv HTML](https://arxiv.org/html/2608.13297)
- [S] Continuous Program Search bibliographic: M. Siper, M. U. Nasir, A. Khalifa, L. Soros, J. Azhang, J. Togelius. "Continuous Program Search". arXiv:2602.07659 (cs.LG/cs.AI/q-fin.ST), 7 Feb 2026. — [arXiv abs](https://arxiv.org/abs/2602.07659)
- [S] Continuous Program Search method:
  - It learns a behaviour-aligned continuous latent space for programs in a compact trading DSL with four components (long and short entry and exit).
  - It compares isotropic Gaussian mutation with a learned "geometry-compiled" mutation that uses a flow model.
  - Across five assets, the learned operator needs about 10× fewer evaluations and gives the best median out-of-sample Sharpe. It is a GP-locality motivation, with no LLM-generated primitives. — [arXiv abs](https://arxiv.org/abs/2602.07659)

### Inferences
- How our extension differs:
  - This group's line of work keeps the primitive vocabulary of the trading language fixed. It improves how the search moves through the space: LLM mutation (ProFiT, Time Value of Evolution), a learned latent geometry (Continuous Program Search) and lineage credit (LVPG).
  - Our extension changes what the search is built from. The LLM authors and curates the typed primitive set, grounded in advanced mathematics, while classical STGP does the composition.
  - These approaches are complementary. GPTL (Time Value of Evolution) is the closest representation to ours, a typed tree with Boolean entry and exit outputs, and should be cited as such.

### Gaps
- ProFiT full text could not be read (SSRN and ACM DL returned 403, and the Semantic Scholar API returned 429). Its LLM, asset list, selection scheme and whether it has any primitive library are unverified beyond secondary descriptions. Recommend reading the GECCO PDF directly.
- The GPTL primitive list was not visible on the HTML page read (it may be in an appendix).

## 4. MadEvolve (arXiv:2605.23007)

### Takeaway
MadEvolve, an AlphaEvolve-style system applied to BTC trading, evolves feature code as one mutable function (`default_calcset()`) feeding a fixed ridge regression. In joint runs the feature function sits in the same mutable block as the execution logic. It is not a separate reusable library shared across strategies. Closeness: 2/5.

### Cited Findings
- [S] Bibliographic: Yurii Kvasiuk, Tianyi Li, Owen Colegrove, Moritz Münchmeyer. "MadEvolve: Evolutionary Optimization of Trading Systems with Large Language Models". arXiv:2605.23007 [q-fin.TR], 21 May 2026. — [arXiv abs](https://arxiv.org/abs/2605.23007)
- [S] Features are LLM-written code inside one mutable function that maps OHLCV to a feature matrix. The feature set grew from 3 to 77 and 79 features in runs 4 and 5 (momentum, volatility, volume and mean-reversion). There is no predefined primitive library and no reuse across multiple strategies. — [arXiv HTML](https://arxiv.org/html/2605.23007)
- [S] Data and evaluation: BTCUSD 1-minute bars from Polygon (train 2022–23, validation 2024, test 2025 to 10 Oct). The ensemble has five LLMs from OpenAI, Anthropic, Google and DeepSeek. Search uses MAP-Elites and 5 ring-topology islands, with about 70% diff mutations. Fitness is impact-adjusted PnL. The feature-only run uses 0.4·R² + 0.3·IC + 0.3·ICIR/5. Section 6 compares against Claude Code. No GP baseline is visible. — [arXiv HTML](https://arxiv.org/html/2605.23007)

### Inferences
- How our extension differs: MadEvolve's evolved "feature pipeline" is the closest finance analogue to an LLM-grown indicator set. However, it is a single code block tied to one linear model and one asset, and all composition and mutation are done by the LLM. Our extension makes the LLM-written signals first-class typed GP primitives. They are reused across many evolved rule trees and assets and managed as a library (grow, prune, refine) according to their usage and contribution in the GP.

### Gaps
- The second half of the HTML (Claude Code comparison results, p-hacking analysis) was not read.

## 5. Survey reference mining (arXiv:2608.01789, arXiv:2608.31041, arXiv:2509.08269)

### Takeaway
None of the three surveys reports a paper in which an LLM generates or extends GP primitives, function sets or grammars, whether in finance or elsewhere. The nearest "evolving library" items are FactorMiner, which has reusable agent skills plus experience memory and no GP, and grammar-guided alpha search, where the grammar is not LLM-designed. This absence is evidence of novelty, not proof of it. Closeness of every hit: at most 2/5.

### Cited Findings
- [S] Survey on formulaic alpha discovery: Xinwei Yu, Yiyang Fu, Mingcheng Fan, Enqi Li, Yilin Gao, Shugong Xu. "Towards Autonomous Formulaic Alpha Discovery: An Evolutionary Computation Perspective". arXiv:2608.01789v1 [cs.NE], 3 Aug 2026. The full HTML was read, including the references and the future-directions sections (V-E to V-J). — [arXiv HTML](https://arxiv.org/html/2608.01789)
  - No cited work has an LLM generate operators, primitives, function sets or grammars for GP. The future directions do not mention LLM-designed operator sets.
  - LLM-based items it lists:
    - [15] Shi, Duan, Li, "Navigating the Alpha Jungle", AAAI 2026, doi:10.1609/aaai.v40i2.37069 (MCTS)
    - [16] Tang et al., "AlphaAgent", KDD 2025, doi:10.1145/3711896.3736838
    - [17] Wang et al., "FactorMiner", arXiv:2602.14670
    - [50] Wang et al., "Alpha-GPT", EMNLP Demo 2025
    - [51] Li et al., FAMA, Findings of ACL 2024
    - [52] Li et al., "R&D-Agent-Quant", arXiv:2505.15155
    - [53] Zhang et al., RL fine-tuning for alpha discovery, arXiv:2605.15412
    - [95] Weng et al., "AlphaLogics", arXiv:2603.20247
  - Grammar-guided alpha search: [49] Yang et al., "Alpha discovery via grammar-guided learning and search", arXiv:2601.22119. The grammar is not LLM-designed. — [arXiv HTML](https://arxiv.org/html/2608.01789)
- [S] Survey on agentic quant trading: Fengrui Hua et al. "Agentic Quantitative Trading: A Survey of Workflows, Systems, and Evaluation". arXiv:2608.31041v1, 31 Aug 2026. — [arXiv HTML](https://arxiv.org/html/2608.31041)
  - LLM-plus-evolution systems it cites:
    - QuantEvolve (arXiv:2510.18569)
    - QuantaAlpha (arXiv:2602.07085)
    - AlphaPROBE (arXiv:2602.11917)
    - AlphaAgentEvo (ICLR 2026)
    - FactorMiner (arXiv:2602.14670): accumulated skills plus experience memory, the closest to an evolving tool set
    - Hubble (arXiv:2604.09601): constrained tools
    - XALPHA (arXiv:2607.08332)
  - The survey does not say any of them has an LLM generate GP primitives. — [arXiv HTML](https://arxiv.org/html/2608.31041)
- [S] Survey on LLMs for evolutionary optimisation: Yisong Zhang, Ran Cheng, Guoxing Yi, Kay Chen Tan. "A Systematic Survey on Large Language Models for Evolutionary Optimization: From Modeling to Solving". arXiv:2509.08269 (v7, 19 Aug 2026), accepted at IEEE Computational Intelligence Magazine. — [arXiv abs](https://arxiv.org/abs/2509.08269)
  - The first third of the HTML was read. It contains no LLM-generated GP primitive sets, grammars or library learning.
  - Nearest items: FunSearch, AEL/EoH, LLaMEA, and LLM-GA (enzyme mutant libraries, a GA, not GP). De et al. use an LLM for initial portfolios. — [arXiv HTML](https://arxiv.org/html/2509.08269v7)

### Inferences
- Within these three surveys, the finance LLM-plus-EC literature is entirely about LLM-as-generator or LLM-as-mutation of formulas and code (category C) or agent memory. A versus D: none matches.
- FactorMiner's "skills" library is worth one sentence of differentiation. It is a skill and memory library for an agent, not a typed primitive set searched by GP. That characterisation is based on the survey descriptions only.

### Gaps
- About two-thirds of the arXiv:2509.08269 HTML, including the full reference list, was not read, so LLM-plus-GP items further down cannot be excluded.
- The full texts of FactorMiner, Hubble and grammar-guided alpha search were not read.

## 6. Targeted searches (last ~6 months) and adjacent non-finance work

### Takeaway
None of the five searches found a paper in which an LLM generates the primitive or function set of a GP. This holds in finance and, among the results returned, outside it. The adjacent non-finance work found is:
- LaSR, the closest precedent for a library: an LLM-learned library of natural-language concepts that guides GP symbolic regression, not executable primitives.
- LLM-for-GP operator work: initialisation, crossover and mutation, and parent selection.
- LLM-seeded grammar-guided GP. Closeness: at most 2/5.

### Cited Findings
- [S] LaSR: "Symbolic Regression with a Learned Concept Library", arXiv:2409.09359 (2024). It adds to GP an LLM-induced library of natural-language concepts that evolves over the run ("ConceptEvolution"). The concepts are text hints, not new GP operators. — [arXiv HTML](https://arxiv.org/html/2409.09359v2)
- [S] Other LLM-plus-GP work, mostly for symbolic regression:
  - A 2026 Springer chapter, "From Evolution to Generation: Leveraging LLMs to Redefine Genetic Programming for Symbolic Regression" (LLMs in initialisation, crossover and mutation) — [Springer](https://link.springer.com/chapter/10.1007/978-981-95-7072-0_6)
  - LLM-Meta-SR, arXiv:2505.18602, which evolves selection operators — [arXiv](https://arxiv.org/pdf/2505.18602)
  - "Benchmarking Zero-Shot LLM-Generated Parent Selection in GP for SR", arXiv:2607.23505 — [arXiv](https://arxiv.org/pdf/2607.23505)
  - "Hybrid LLM-Genetic Programming ... Behavior Trees", Robotics 15(5):98, which uses LLM-generated trees inside a constrained grammar — [MDPI](https://doi.org/10.3390/robotics15050098)
  - MaOG3P, grammar-guided GP seeded from LLM code — [ResearchGate](https://www.researchgate.net/publication/381913458_Enhancing_Program_Synthesis_with_Large_Language_Models_Using_Many-Objective_Grammar-Guided_Genetic_Programming)
- [S] The STGP trading baseline literature that the extension builds on:
  - "Enhanced Strongly typed Genetic Programming for Algorithmic Trading", GECCO 2023, doi:10.1145/3583131.3590359 (Essex) — [ACM](https://dl.acm.org/doi/10.1145/3583131.3590359)
  - Christodoulaki & Kampouridis, STGP combining technical and sentiment analysis — [Bristol](https://research-information.bris.ac.uk/en/publications/using-strongly-typed-genetic-programming-to-combine-technical-and/)
  - Menoita & Silva, "Evolving Financial Trading Strategies with Vectorial GP", GECCO '25 Companion, arXiv:2504.05418: the strongly typed vectorial GP was the best of their variants — [arXiv](https://arxiv.org/pdf/2504.05418)
  - Michell & Kristjanpoller, STGP with fuzzy inference, ASC 2020 — [ScienceDirect](https://www.sciencedirect.com/science/article/abs/pii/S1568494620301095)
  - None of these uses an LLM.
- [S] Also surfaced, all category C or explanation:
  - CogAlpha, "Cognitive Alpha Mining via LLM-Driven Code-Based Evolution", arXiv:2511.18850 — [arXiv](https://arxiv.org/pdf/2511.18850)
  - "Trading Strategy Optimization via Textual Gradient", arXiv:2610.03128 — [arXiv](https://arxiv.org/html/2610.03128v1)
  - EvoSpeak, arXiv:2510.02686, which uses an LLM to explain GP heuristics — [arXiv](https://arxiv.org/pdf/2510.02686)

### Inferences
- Novelty assessment:
  - A (LLM-written, mathematically grounded primitive library as typed STGP terminals and functions for trading rules): no prior instance was found in finance or in GP generally. LaSR (text concepts) and PACE (code primitives composed by an LLM) are the nearest conceptual neighbours.
  - D (the LLM grows, prunes and refines the primitive set during the GP run): PACE does grow and credit code primitives during an LLM-driven evolutionary search, so "LLM-maintained primitive library during evolution" is not novel in general AAD. What remains novel is doing it for a typed GP, in trading, with pruning or refinement driven by GP usage and fitness attribution.
  - Recommended framing: "first to use LLMs as authors of a domain-grounded typed primitive library for STGP trading-rule evolution, with library co-evolution". Cite PACE, LaSR, DreamCoder and LILO as the library-learning lineage, and ProFiT, AlgoEvolve, MadEvolve, QuantEvolve and CogAlpha as LLM-as-mutation work in finance. Cite the Time Value of Evolution/GPTL as the nearest typed-tree LLM trading system.

### Gaps
- The searches were web-engine based (5 queries). Google Scholar, DBLP and GECCO/EvoStar 2026 proceedings tables of contents were not systematically checked. A GECCO '26 or EuroGP '26 paper on LLM-generated GP primitives could exist without appearing in these results.

## Search log
1. WebFetch arXiv abs 2608.07395 (PACE): metadata and abstract.
2. WebFetch arXiv abs 2606.26173 (AlgoEvolve): metadata and abstract.
3. WebFetch arXiv abs 2605.23007 (MadEvolve): metadata and abstract.
4. WebFetch arXiv abs 2608.13297 (Time Value of Evolution): metadata and abstract.
5. WebFetch arXiv abs 2602.07659 (Continuous Program Search): metadata and abstract.
6. WebFetch arXiv html 2608.07395 (PACE full text, first 100k characters): method, tasks, baselines.
7. WebFetch arXiv html 2606.26173 (AlgoEvolve full text): method, data, future-work sentence.
8. WebFetch arXiv html 2605.23007 (MadEvolve, first 100k characters): feature evolution.
9. WebSearch "ProFiT Program Search for Financial Trading Siper GECCO": ProFiT not found; returned VGP and STGP literature.
10. WebFetch arXiv html 2608.01789 (alpha survey, characters 0–100k).
11. WebFetch arXiv html 2608.31041 (agentic quant survey): references.
12. WebFetch SSRN 5889762: 403.
13. WebFetch arXiv html 2608.01789 (offset 100k): references and future directions.
14. WebFetch arXiv abs 2509.08269: metadata.
15. WebFetch arXiv html 2509.08269v7 (first 100k characters).
16. WebSearch "LLM-generated primitive set genetic programming" (extended).
17. WebSearch "large language model generated indicators genetic programming trading rules 2026" (extended).
18. WebFetch ACM DL DOI 10.1145/3795095.3805175: 403.
19. WebSearch "ProFiT LLM trading strategies program search Siper Khalifa Soros" (extended): secondary descriptions.
20. WebSearch "LLM evolves function set genetic programming library learning symbolic regression primitives 2026" (extended): LaSR and related.
21. WebFetch Semantic Scholar API search for ProFiT: 429.
22. WebSearch "strongly typed genetic programming large language model trading primitives" (extended): GPTL hit.
23. WebFetch arXiv html 2608.13297: GPTL, Qwen3-8B, data; ProFiT reference entry.
