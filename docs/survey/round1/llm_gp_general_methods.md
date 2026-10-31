# LLM + Genetic Programming / Evolutionary Program Search in General (Non-Finance) Domains

Scope: general-domain prior art for (A) LLM-created GP primitives/features, (B) LLM-seeded GP populations, (C) LLM-in-the-loop GP (variation/repair/primitive generation), (D) hybrids/co-evolution, as they bear on extending Clayman, Kampouridis & Papastylianou, "Large Language Quant" (CIFEr 2026) to GP that evolves LLM-written strategies.

Retrieval legend: [S] = title/authors/ID seen in a retrieved page this session; [M] = from memory only, NOT verified this session (verify before citing). Closeness: 1–5 (5 = GP evolving LLM-derived trading strategies).

Tool note: Consensus (free quota used up until 1 Nov) and Elicit (no API plan) both returned errors, so every retrieval was done with WebSearch/WebFetch. ACM DL pages returned HTTP 403.

## Q1. Core works and their exact mechanism

### Takeaway
The dominant 2023–2025 paradigm is an **LLM-only evolutionary loop over code**: FunSearch, ELM, EoH, ReEvo, LLaMEA, AlphaEvolve and LLM-SR all follow it. The LLM is the variation operator, and fitness comes from executing the program. There is no tree-GP genome and no fixed primitive set. Only a minority of papers put the LLM inside classical tree or grammar GP (LLM_GP, LLEGO, LMX on expressions, MaOG3P). "LLM as mutation/crossover over programs" is therefore firmly established and must be cited. It cannot be claimed as novel.

### Cited Findings (paper records)

| # | Paper | Cat. | Evo method | LLM role | Domain | Representation | Close. | Ret. |
|---|---|---|---|---|---|---|---|---|
| 1 | Lehman, J., Gordon, J., Jain, S. et al. (2022/2023). "Evolution through Large Models." arXiv:2206.08896 (later a chapter in *Handbook of Evolutionary Machine Learning*, Springer 2024 [M]) | C / Background | MAP-Elites (QD) over code. Baseline: Tiny GP tree mutation | Diff-trained code LLM is the mutation operator | Sodarace robot morphologies (Python) | Python programs | 2 | [S] (ID, title, Tiny GP baseline seen) |
| 2 | Bradley, H., Fan, H., et al. (2024). "OpenELM: A Library for Evolution through Large Models." In *Handbook of Evolutionary Machine Learning* | C (tooling) | QD / GA library | LLM mutation/crossover | Generic | Code/text | 2 | [M] |
| 3 | Meyerson, E., Nelson, M. J., Bradley, H. et al. (2023/2024). "Language Model Crossover: Variation through Few-Shot Prompting." arXiv:2302.12170 (ACM TELO 2024 [M]) | C | GA. The LLM's few-shot completion acts as a k-parent crossover | Recombination operator | Binary strings, **symbolic regression expressions**, sentiment text, image prompts, Python Sodarace | Text-serialised genotypes | 3 | [S] (ID; SR seeded from benchmark expressions with a 1.3B GALACTICA model) |
| 4 | Romera-Paredes, B., Barekatain, M., Novikov, A. et al. (2024). "Mathematical discoveries from program search with large language models." *Nature* 625. DOI 10.1038/s41586-023-06924-6 | C | Island-model evolutionary loop, LLM-only (no tree GP). Evolves only a "priority" function inside a fixed skeleton | Mutation via best-shot prompting with 2 prior programs | Cap set, bin packing | Python function | 2 | [M] (DOI from memory; an NYU critique describes FunSearch as LLM-as-mutation inside a GP-like algorithm [S]) |
| 5 | Liu, F., Tong, X., Yuan, M. et al. (2024). "Evolution of Heuristics: Towards Efficient Automatic Algorithm Design Using Large Language Model." ICML 2024, arXiv:2401.02051 | C | LLM-only EA. Co-evolves a natural-language "thought" and code, with 5 prompt strategies (E1/E2 exploration, M1–M3 mutation) | Init + crossover + mutation | Combinatorial optimisation heuristics (TSP, bin packing, FSSP) | NL description + Python code | 3 (thought+code is analogous to spec+strategy) | [M] |
| 6 | Ye, H., Wang, J., Cao, Z. et al. (2024). "ReEvo: Large Language Models as Hyper-Heuristics with Reflective Evolution." NeurIPS 2024, arXiv:2402.01145 | C | GA over code plus short- and long-term "reflection" (verbal gradients) | Generator + reflector LLM | Combinatorial-optimisation heuristics, ACO, GLS | Python code | 3 | [M] |
| 7 | van Stein, N., Bäck, T. (2024/2025). "LLaMEA: A Large Language Model Evolutionary Algorithm for Automatically Generating Metaheuristics." IEEE TEVC, arXiv:2405.20132 | C | (1+1)/(μ+λ) ES over whole algorithm code. Error traces are fed back to the LLM for repair | Generator + mutation + repair | Continuous black-box optimisation (BBOB) | Python classes | 2 | [M] |
| 8 | Novikov, A. + 17 co-authors (2025). "AlphaEvolve: A coding agent for scientific and algorithmic discovery." arXiv:2506.13131 | C | LLM-ensemble evolutionary coding agent with program database, diff edits, multiple evaluators and evaluation cascades | Diff mutation of whole codebases | Matrix multiplication (4x4 complex, 48 mults), maths, data-centre scheduling | Code diffs | 2 | [S] |
| 9 | Shojaee, P., Meidani, K., Gupta, S. et al. (2025). "LLM-SR: Scientific Equation Discovery via Programming with Large Language Models." ICLR 2025 (oral), arXiv:2404.18400 | C | LLM-only evolutionary loop with experience buffer. The LLM proposes equation skeletons as programs, and numeric parameters are fitted by optimiser | Skeleton generator/mutator using domain priors | Physics, biology, materials SR | Python equation programs | 3 | [S] |
| 10 | Grayeli, A., Sehgal, A., Costilla-Reyes, O. et al. (2024). "Symbolic Regression with a Learned Concept Library" (LaSR). NeurIPS 2024, arXiv:2409.09359 | **D** (+C) | **Classical GP SR (PySR)** plus LLM-guided operators. The LLM abstracts natural-language "concepts" from elite hypotheses, evolves that concept library, and uses it to bias mutation/crossover/init | Concept abstraction, concept evolution, guided variation | Feynman equations, synthetic tasks, LLM scaling laws | Expression trees + NL concept library | **4** (closest co-evolution analogue: GP genome plus an evolving LLM knowledge library) | [S] |
| 11 | Hemberg, E., Moskal, S., O'Reilly, U.-M. (2024). "Evolving code with a large language model." *GPEM* 25, art. 21. DOI 10.1007/s10710-024-09494-2, arXiv:2401.07102 | B + C | GP-style EA in which **all operators (init, mutation, crossover, selection-aid) are LLM prompts**. Explicitly framed as LLM_GP versus conventional GP | Initialiser + variation operators | Program-synthesis benchmarks (HumanEval/MBPP-type, per arXiv keywords) | Python code (text) | 3 | [S] |
| 12 | Liu, T., Huynh, N., van der Schaar, M. (2025). "Decision Tree Induction Through LLMs via Semantically-Aware Evolution" (LLEGO). ICLR 2025, arXiv:2503.14217 | C | **Tree-based GP** over decision trees. LLM fitness-guided crossover and diversity-guided mutation (log-prob based) | Semantic variation operators | Tabular classification/regression | Decision trees serialised as text | **4** (tree GP with LLM operators over interpretable rule trees, close to entry/exit rules) | [S] |
| 13 | Guo, Q., Liu, R., Wang, R. et al. (2024). "Connecting LLMs with Evolutionary Algorithms Yields Powerful Prompt Optimizers" (EvoPrompt). ICLR 2024, arXiv:2309.08532 | D (GP evolves prompts) | GA and DE over prompts. The LLM performs crossover/mutation in text | Variation over prompts | NLP tasks | Discrete prompts | 2 (precedent for evolving specs/prompts) | [M] |
| 14 | Jimeno Yepes, A., Barnard, P. (2025). "Evolutionary thoughts: integration of large language models and evolutionary algorithms." arXiv:2505.05756 (cs.NE) | C | Evolutionary search over **tree-structured programs built from predefined primitives** (list read/write, boolean, branching), with an efficient evaluation framework that keeps individuals valid | LLM proposes the search strategy / candidates (Qwen2.5-Coder-32B) | Program synthesis (details not confirmed) | Primitive trees | 3 | [S] (abstract only; mechanism partly inferred) |
| 15 | Hernandez, J. G., Saini, A. K., Ketron, G., Moore, J. H. (2025). "GP and LLMs for Program Synthesis: No Clear Winners." arXiv:2508.03966 | Background (B/C motivation) | PushGP versus GPT-4o | Comparator | PSB2 (25 tasks) | Push / Python | 2 | [S]: the union of PushGP and GPT-4o (data+text prompt) solved 23/25 tasks, and some tasks were solved by only one of the two. This is complementary-strengths evidence for hybrids |

Surveys:
- Wu, X., Wu, S.-H., Wu, J., Feng, L., Tan, K. C. (2024). "Evolutionary Computation in the Era of Large Language Model: Survey and Roadmap." arXiv:2401.10034. Later surveys list it as IEEE TEVC 2024, but I did not confirm the IEEE Xplore details. Background. [S] — [arXiv](https://www.arxiv.org/abs/2401.10034)
- "A Systematic Survey on Large Language Models for Evolutionary Optimization: From Modeling to Solving," arXiv:2509.08269. Authors were not captured. [S, title only] — [arXiv](https://arxiv.org/html/2509.08269v3)
- Chao, W., Zhao, J., Jiao, L. et al. (2024). "A match made in consistency heaven: when large language models meet evolutionary algorithms," arXiv:2401.12273. [M, verify]
- "LLM-Driven Evolutionary Program Search: From FunSearch to Automated Scientific Discovery" (ResearchGate). Authors and venue unverified. [S, title only] — [ResearchGate](https://www.researchgate.net/publication/407540701_LLM-Driven_Evolutionary_Program_Search_From_FunSearch_to_Automated_Scientific_Discovery)

Source links for [S] items:
- ELM uses Tiny GP tree-based mutation as its baseline — [arXiv 2206.08896](https://arxiv.org/html/2206.08896v1)
- LMX: SR initial population built from benchmark expressions; GALACTICA 1.3B — [arXiv 2302.12170](https://arxiv.org/pdf/2302.12170)
- AlphaEvolve ID, date (16 Jun 2025) and authorship — [arXiv 2506.13131](https://arxiv.org/abs/2506.13131.pdf)
- LLM-SR at ICLR 2025 (oral) — [ICLR proceedings](https://proceedings.iclr.cc/paper_files/paper/2025/hash/28df8e730c054c5331855fd4d5403ba9-Abstract-Conference.html); [arXiv 2404.18400](https://arxiv.org/abs/2404.18400v3)
- LaSR: LLM concept library guiding a genetic search, NeurIPS 2024 — [arXiv 2409.09359](https://arxiv.org/html/2409.09359v3); [NeurIPS](https://neurips.cc/virtual/2024/poster/96212)
- LLM_GP in GPEM 2024 — [GP bibliography](https://gpbib.cs.ucl.ac.uk/gp-html/Hemberg_2024_GPEM.html); [arXiv 2401.07102](https://arxiv.org/pdf/2401.07102)
- LLEGO at ICLR 2025 — [arXiv 2503.14217](https://arxiv.org/abs/2503.14217)
- Evolutionary thoughts — [arXiv 2505.05756](https://arxiv.org/abs/2505.05756)
- GP vs LLMs, no clear winner — [arXiv 2508.03966](https://arxiv.org/abs/2508.03966)
- Wu et al. survey — [arXiv 2401.10034](https://arxiv.org/html/2401.10034v3)

### Inferences
- Mechanism (C) has heavy prior art on two fronts. LLM-as-mutation/crossover over raw code (ELM, FunSearch, EoH, ReEvo, LLaMEA, AlphaEvolve, LLM_GP) and LLM operators inside tree GP (LLEGO, LaSR, LMX-SR) are both established. A trading extension should differentiate on what is evolved (typed entry/exit strategy programs built on advanced-maths primitives), the fitness regime (noisy and non-stationary), and the coupling with the existing portfolio GA. Using an LLM as a GP operator is not novel in itself.
- EoH's co-evolution of thought and code, and LaSR's concept library, are the closest analogues to the "GP evolves specs/prompts that the LLM implements" variant of (D). Both must be cited.

### Gaps
- FunSearch, EoH, ReEvo, LLaMEA, OpenELM, EvoPrompt and Chao et al. are [M]. Their IDs, DOIs and venues should be spot-checked; I ran out of tool budget before verifying them.

## Q2. LLM generating NEW primitives/terminals/building blocks (or grammars/features) for tree- or grammar-based GP

### Takeaway
I found **no verified paper in which an LLM writes executable primitive functions that are then added to a tree-GP function or terminal set**. That is, nothing with exactly the "A/D: LLM grows or prunes the primitive set" mechanism. The nearest neighbours fall into four groups:
- LLM-generated *grammars* for grammatical evolution (GE)
- LLM *concept libraries* steering GP (LaSR)
- LLM-proposed *features* followed by a GP feature-construction stage
- LLM-suggested *keywords/functions added to a GE grammar*

This looks like the most defensible novelty gap, although my search coverage was limited.

### Cited Findings
- Vella Zarb et al. (GECCO '25), "Program Synthesis with LLM-Predicted Minimal Specialized Grammars," DOI 10.1145/3712256.3726430. In-context learning produces problem-specific minimal sub-grammars of a larger BNF, which GE then searches. The authors claim it is the first use of in-context learning for program synthesis within GE. Category A (LLM defines the GP search space/grammar). Domain: program synthesis. Closeness 3. [S, via search snippet; ACM page 403] — [ACM DL](https://dl.acm.org/doi/10.1145/3712256.3726430)
- A GECCO 2024 paper specialises a GE grammar from the LLM's own output in order to improve LLM-generated code. It reports significant gains across 25 problems and 5 LLMs. An Ital-IA 2025 follow-up, "Improving LLM-Generated Code via Genetic Improvement," extracts keywords and function names from the LLM output and adds them to a base grammar. Category A+B. Closeness 3. [S; authors not captured] — [CEUR Ital-IA 2025](https://ceur-ws.org/Vol-4121/Ital-IA_2025_paper_111.pdf); [Springer 978-3-031-56957-9_7 "Enhancing Large Language Models-Based Code Generation by Leveraging Genetic Improvement"](https://dl.acm.org/doi/10.1007/978-3-031-56957-9_7). This Springer DOI is a EuroGP 2024 LNCS chapter [M]
- "Embedding Domain-Specific Knowledge from LLMs into the Feature Engineering Pipeline" (arXiv:2503.21155). Step 1: an LLM injects domain-knowledge feature combinations into the dataset. Step 2: GP performs feature selection and construction. The LLM pre-processes data and does **not** define GP primitives. Category A (weak). Tabular ML. Closeness 3. [S, snippet] — [arXiv](https://arxiv.org/pdf/2503.21155)
- Nourbakhsh, A., Alcaraz, B., Schommer, C. (2025). "Feature Generation Using LLMs: An Evolutionary Algorithm Approach." CALM 2024, CCIS vol. 2471, Springer. DOI 10.1007/978-3-031-89103-8_4; preprint arXiv:2607.16255. The LLM writes feature-generating functions that are not restricted to a predefined operator set, with GA-style selection. Category A. Closeness 3. [S] — [arXiv](https://arxiv.org/html/2607.16255v1)
- "SymboLLM-FE: LLM-Accelerated Symbolic Regression for Automated Feature Engineering on Tabular Data" (arXiv:2608.28408). SR runs first, and the LLM translates, explains and deduplicates the rules downstream. It reportedly beats GP variants on most datasets. The LLM sits downstream of GP, not upstream. Category A-adjacent. Closeness 2. [S, snippet] — [arXiv](https://arxiv.org/pdf/2608.28408)
- LaSR's LLM-evolved concept library is a soft, natural-language "building block" library rather than executable primitives. Category D. [S] — [arXiv 2409.09359](https://arxiv.org/pdf/2409.09359)
- HyGenar (ACL Findings 2025) is an LLM-driven hybrid GA for few-shot BNF grammar generation. It is about grammar induction, not GP primitives. A secondary summary's 56% vs 39% figure was not verified. [S] — [ACL Anthology](https://aclanthology.org/2025.findings-acl.701.pdf)
- "PACE: Primitive-Aware Code Evolution for Automated Algorithm Design" (arXiv:2608.07395) surfaced in search. From the title it concerns primitives in LLM code evolution, but I did **not** read it. It is a high-priority check for the (A/D) novelty claim. [S, title only] — [arXiv](https://arxiv.org/pdf/2608.07395)
- In the scheduling-heuristics area, EvoDR (arXiv:2601.15738) evolves dispatching rules with an LLM and positions itself against GP. EvoSpeak (arXiv:2510.02686) uses LLMs to interpret GP-evolved tree heuristics. A 2026 paper (arXiv:2607.27698) guides LLMs with GP-evolved heuristic knowledge for dynamic multi-mode project scheduling, which is the GP→LLM direction. None was confirmed to have the LLM define the GP terminal set. [S, snippets] — [EvoDR](https://arxiv.org/html/2601.15738); [EvoSpeak](https://arxiv.org/html/2510.02686v1); [2607.27698](https://arxiv.org/pdf/2607.27698)

### Inferences
- An "LLM-authored, mathematically grounded primitive library (spectral entropy, signatures, Fisher–Rao, …) used as typed terminals/functions in strongly-typed GP, grown or pruned by the LLM during the run" appears not to be established in general-domain literature as of this search. The closest work to differentiate from is grammar specialisation (Vella Zarb GECCO'25; the Ital-IA/EuroGP GI line), LaSR concept libraries, and LLM feature generation followed by GP.

### Gaps
- PACE (2608.07395) and "Evolutionary thoughts" (2505.05756) were not read in full. Either could contain an LLM-generates-primitives mechanism.
- I could not access the GECCO 2025/2026 companion proceedings (ACM 403) to check workshop papers, e.g. the "LLMs for and with EC" workshop at GECCO 2025 [S that it existed: [GECCO 2025 tracks](https://gecco-2025.sigevo.org/Tracks)].

## Q3. Seeding tree-based / strongly-typed GP or GE with LLM-written programs: does it help?

### Takeaway
Seeding grammar-guided GP with LLM output is established for program synthesis (the Tao/Ventresque/Nallur/Saber MaOG3P line, 2023–2025), and LLM_GP uses LLM initialisation. Evidence that it helps is positive but narrow: mostly program synthesis benchmarks with similarity objectives. Classical SR literature also cautions that, at equal diversity, the initialisation method matters little to final GP results. I found no strongly-typed-GP seeding study.

### Cited Findings
- Tao, N., Ventresque, A., Nallur, V., Saber, T. (2024). "Enhancing Program Synthesis with Large Language Models Using Many-Objective Grammar-Guided Genetic Programming." *Algorithms* 17(7):287, DOI 10.3390/a17070287. ChatGPT-generated programs are mapped into a BNF grammar and seed the G3P population. Code-similarity-to-LLM-output is used as an extra objective. Category B. Grammar-guided GP. Closeness 3. [S] — [GP bib](https://gpbib.cs.ucl.ac.uk/gp-html/tao_2024_Algorithms.html); [Crossref](https://api.crossref.org/works/10.3390%2FA17070287)
- Precursor: Tao, Ventresque, Saber (2023), "Many-objective Grammar-guided Genetic Programming with Code Similarity Measurement for Program Synthesis," IEEE LA-CCI 2023. MaOG3P beat the bi-objective variants. [S] — [Galway repository](https://research.universityofgalway.ie/en/publications/many-objective-grammar-guided-genetic-programming-with-code-simil/)
- Follow-up: "Grammar-obeying program synthesis: A novel approach using large language models and many-objective genetic programming," *Computer Standards & Interfaces* (2025). It uses programs from multiple LLMs both as seeds and as similarity targets. Category B. [S] — [GP bib](https://gpbib.pmacs.upenn.edu/gp-html/Tao_2025_CSI.html)
- LMX's SR experiments seeded from known benchmark expressions, so part of the gain may come from seeding rather than from LLM variation (secondary interpretation in search summary). [S] — [arXiv 2302.12170](https://arxiv.org/pdf/2302.12170)
- DIGEST (arXiv:2610.33880, 2026 preprint) repurposes a pretrained decoder block from a lightweight LLM as a symbolic policy for GP population seeding in SR. It is trained online from GP results and includes a random-seeding ablation. Category B. [S, snippet] — [arXiv](https://arxiv.org/html/2610.33880)
- Non-LLM precedent: Mundhenk et al. (NeurIPS 2021), "Symbolic Regression via Neural-Guided Genetic Programming Population Seeding," arXiv:2111.00053. An RNN seeds GP. [S] — [NeurIPS](https://proceedings.neurips.cc/paper/2021/file/d073bb8d0c47f317dd39de9c9f004e9d-Paper.pdf)
- "GP and LLMs: No Clear Winners" found complementary solve-sets, which supports hybrid seeding. [S] — [arXiv 2508.03966](https://arxiv.org/abs/2508.03966)
- A related 2026 preprint benchmarks zero-shot LLM-generated *parent-selection* operators in GP SR. It keeps ramped half-and-half initialisation, so it does not test seeding. [S] — [arXiv 2607.23505](https://arxiv.org/html/2607.23505v1)

### Inferences
- Seeding typed GP with the existing LLQ strategies (category B) has direct methodological precedent in G3P (MaOG3P) and SR (DIGEST, neural seeding). It needs citation, but transferring it to strongly-typed trading-rule GP with advanced-maths primitives is not covered by these works.

### Gaps
- I found no study on seeding *strongly-typed* tree GP with LLM programs, nor any on whether LLM seeds survive or dominate under noisy fitness.

## Q4. Which approaches handle noisy, non-stationary fitness?

### Takeaway
Essentially none of the core LLM-evolution works target noisy or non-stationary fitness. Their benchmarks (maths constructions, combinatorial-optimisation heuristics, SR, program synthesis) have deterministic or near-deterministic evaluators. "Non-stationarity" in 2025–2026 LLM-evolution papers refers to the *search dynamics* (operator or LLM usefulness drifting over time), not to a drifting fitness landscape. This is a genuine differentiator for a trading application.

### Cited Findings
- AdaEvolve (arXiv:2602.20133) argues that LLM-evolution systems such as OpenEvolve use static schedules that ignore the non-stationary dynamics of the search. It proposes an adaptive controller. This concerns search dynamics, not noisy fitness. [S] — [arXiv](https://arxiv.org/html/2602.20133v1)
- ShinkaEvolve (arXiv:2509.19349) adapts LLM sampling probabilities each generation to cope with non-stationarity in which model is most useful. [S] — [arXiv](https://arxiv.org/pdf/2509.19349)
- PACEvolve++ (arXiv:2605.07039) adapts its strategy across evolutionary phases under non-stationary feedback. [S] — [arXiv](https://arxiv.org/html/2605.07039v1)
- AlphaEvolve-style evaluation cascades (cheap check, then larger evaluation, then full re-evaluation) are used for cost and reliability. One OpenEvolve-based paper reports about 8x compute savings from cascade gating. [S] — [arXiv 2608.14555](https://arxiv.org/pdf/2608.14555)
- A secondary summary describes AlphaEvolve as relying on deterministic fitness functions. Commentary notes that it requires programmatically checkable problems. [S, secondary] — [Emergent Mind](https://www.emergentmind.com/topics/alphaevolve-framework)
- Adjacent finance work (non-LLM) surfaced: Siper, Nasir, Khalifa, Soros, Azhang, Togelius (2026), "Continuous Program Search," arXiv:2602.07659 (cs.LG, q-fin.ST). It runs a (μ+λ) ES in a learned latent space of a trading-strategy DSL (long/short entry/exit) with a learned flow-based mutation operator. It reports about 10x fewer evaluations to reach strong strategies and the best median out-of-sample Sharpe across 5 assets. No LLM is used. This is relevant to the finance-side researcher. Closeness 4. [S] — [arXiv](https://arxiv.org/abs/2602.07659)

### Inferences
- A trading extension can legitimately claim to address an under-studied regime for LLM+GP: noisy, non-stationary fitness with walk-forward/out-of-sample validation and overfitting control. This is an inference from the absence of such work in the core papers, not a confirmed literature gap.

### Gaps
- I did not search for "noisy fitness" + LLM evolution specifically (e.g. LLM-evolved RL policies, game agents, or stochastic simulators), so there may be work on stochastic evaluators in ELM-style RL/game settings.

## Q5. 2025–2026 preprints / GECCO, EuroGP, CEC, PPSN papers on "LLM-guided/assisted GP"

### Takeaway
There is a clear 2025–2026 wave of activity, but it centres on LLM evolutionary code search (heuristic design, scheduling, SR) and LLM operators in specific GP sub-settings. Fully "LLM-in-tree-GP" papers are fewer: LLEGO at ICLR'25, LaSR at NeurIPS'24, and Vella Zarb at GECCO'25. One 2025 position paper explicitly calls for LLM-guided genetic improvement.

### Cited Findings
- "LLM-Guided Genetic Improvement: Envisioning Semantic Aware Automated Software Evolution," arXiv:2508.18089 (2025). Vision/position paper. Category C. [S, title] — [arXiv](https://arxiv.org/abs/2508.18089)
- "Mutation Without Variation: Convergence Dynamics in LLM-Driven Program Evolution," arXiv:2606.05408 (2026). Judging by the title, it studies diversity collapse in LLM-driven program evolution, which is relevant as a known risk for LLM mutation. Not read. [S, title only] — [arXiv](https://arxiv.org/pdf/2606.05408)
- "Automating Parent Selection Configuration in Genetic Programming with Agentic AI," arXiv:2608.17172 (2026). An agentic LLM configures GP selection. Category C (meta-level). [S, title only] — [arXiv](https://arxiv.org/pdf/2608.17172)
- "Benchmarking Zero-Shot LLM-Generated Parent Selection in Genetic Programming for Symbolic Regression," arXiv:2607.23505 (2026). [S] — [arXiv](https://arxiv.org/html/2607.23505v1)
- "Genetic Programming with Transformer-Based Mutation …" (arXiv:2605.21055, 2026) uses a transformer mutation operator for Cartesian GP in circuit approximation. "Multi-Objective Coevolution of Prompts and Templates for Circuit Approximation" (arXiv:2606.13089, 2026) co-evolves prompts and templates, which matches category D (evolving prompts/specs). [S, titles/snippets] — [2605.21055](https://arxiv.org/pdf/2605.21055); [2606.13089](https://arxiv.org/pdf/2606.13089)
- "Large Language Model-Powered Evolutionary Code" (arXiv:2601.14523) and TIDE (arXiv:2601.21239, LLM-based automated heuristic design) surfaced as 2026 preprints. Not read. [S, title only] — [2601.14523](https://arxiv.org/pdf/2601.14523); [2601.21239](https://arxiv.org/pdf/2601.21239)
- GECCO 2025 (Málaga, 14–18 July 2025) hosted a workshop on LLMs for and with evolutionary computation. Its GP-track feature-construction papers in the proceedings were non-LLM. [S] — [GECCO 2025 tracks](https://gecco-2025.sigevo.org/Tracks); [dblp GECCO 2025](https://dblp.org/db/conf/gecco/gecco2025c.html)
- "An LLM-Based Genetic Algorithm for Prompt Engineering," GECCO '25 Companion, DOI 10.1145/3712255.3726633. Category D (evolving prompts). [S, title] — [ACM DL](https://dl.acm.org/doi/10.1145/3712255.3726633)

### Inferences
- The field is moving quickly and many 2026 preprints exist. A reviewer could cite LLEGO, LaSR, LLM_GP, Vella Zarb GECCO'25 and the MaOG3P line against B and C claims. The novelty case should rest on four things: (i) LLM-authored advanced-maths primitive libraries as typed GP building blocks that are adapted during the run; (ii) trading-specific noisy, non-stationary fitness; (iii) integration with the existing portfolio-level GA; and (iv) interpretability of the evolved entry/exit rules.

### Search log
Tools: WebSearch (standard/extended), WebFetch. Consensus search failed (monthly quota exhausted). Elicit search_papers failed (no API plan).
1. WebSearch: "LLM-guided genetic programming tree-based primitives arXiv 2025"
2. Elicit: "large language model generates primitives or features for tree-based genetic programming" (failed)
3. Consensus: "large language models as mutation and crossover operators in genetic programming" (failed)
4. WebSearch: "LLM seeded initial population genetic programming symbolic regression"
5. WebSearch: "LLM feature construction genetic programming GECCO 2025"
6. WebSearch: "survey evolutionary computation large language models era Wu 2024 TEVC"
7. WebFetch: arxiv.org/abs/2505.05756
8. WebSearch: Hemberg Moskal O'Reilly "Evolving Code with A Large Language Model" GPEM
9. WebSearch: LLM generated primitive set grammar GP grammatical evolution LLM 2025
10. WebSearch: LLM evolutionary program search noisy fitness non-stationary AlphaEvolve OpenEvolve
11. WebFetch: arxiv.org/abs/2508.03966
12. WebSearch: LLM GP dispatching rules job shop scheduling terminals
13. WebSearch: LaSR / LLM-SR Shojaee ICLR 2025
14. WebSearch: "genetic programming" "large language model" mutation operator tree-based GP 2026 arXiv
15. WebFetch: dl.acm.org/doi/10.1145/3712256.3726430 (403)
16. WebSearch: LLM-SR exact title
17. WebSearch: LLM generates building blocks for GP function set / feature engineering
18. WebFetch: arxiv.org/abs/2602.07659
19. WebSearch: MaOG3P authors
20. WebFetch: arxiv.org/abs/2503.14217
21. WebSearch: AlphaEvolve arXiv 2506.13131

### Gaps
- Not verified this session: FunSearch DOI, EoH, ReEvo, LLaMEA, OpenELM, EvoPrompt, Chao et al. survey, LMX TELO venue.
- Not read: PACE (2608.07395), Mutation Without Variation (2606.05408), 2601.14523, TIDE, DIGEST full text. PACE is the top priority for the primitive-generation novelty question.
- I did not search EuroGP 2025/2026, CEC 2025 or PPSN 2024/2026 proceedings directly, nor GPEM special issues on LLM+GP.
