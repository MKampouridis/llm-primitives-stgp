# GP for trading: foundations, non-LLM alpha mining, and advanced mathematical primitives in GP (category A without LLMs)

Legend: [S] = retrieved/verified this session (search result, abstract page, gpbib entry, or reference list of a retrieved paper); [M] = recalled from memory only, not verified this session (treat bibliographic details as provisional). Closeness = closeness to the proposed extension (GP evolving strategies whose primitives are exotic mathematical signals), 1 = background only, 5 = essentially the same idea.

Tooling note: Elicit (no API plan) and Consensus (monthly quota exhausted) were unavailable; all retrieval was via WebSearch/WebFetch plus local text extraction of one open-access PDF (Long, Kampouridis & Papastylianou, AIR 2026), whose reference list was used to verify the Kampouridis-group citations.

## Q1. Canonical GP-for-trading foundations and surveys

### Takeaway
GP for trading-rule induction is a 25+-year-old field anchored by Neely et al. (1997, FX) and Allen & Karjalainen (1999, S&P 500), with strong Essex lineage (EDDIE, directional changes). In all the canonical and recent works we checked, the GP terminal sets are technical indicators, DC (event-based) indicators, sentiment, or fundamentals — never information-theoretic/geometric/rough-path quantities.

### Cited Findings
Foundational empirical GP papers
- Neely, C.J., Weller, P., Dittmar, R. (1997) "Is Technical Analysis in the Foreign Exchange Market Profitable? A Genetic Programming Approach", J. Financial and Quantitative Analysis 32(4) (CEPR DP1480 working-paper version). GP; FX (six rates, 1981–95); tree of technical rules (MAs, max/min); no advanced math. Background; closeness 1. Bibliographic existence [S] (working paper page); JFQA venue/DOI 10.2307/2331231 [M]. Reported economically significant out-of-sample excess returns not explained by systematic risk — [CEPR DP1480 summary](https://causalclaims.trfetzer.com/paper/DP1480.html)
- Allen, F., Karjalainen, R. (1999) "Using genetic algorithms to find technical trading rules", J. Financial Economics 51(2):245–271, DOI 10.1016/S0304-405X(98)00052-X. GP (despite title); S&P 500 daily 1928–1995; boolean rule trees of price/MA/max/min; after costs no excess over buy-and-hold. Background; closeness 1. [S] — [ScienceDirect](https://www.sciencedirect.com/science/article/pii/S0304405X9800052X); [Lohpetch & Corne 2009 abstract](https://gpbib.cs.ucl.ac.uk/gp-html/Lohpetch_2009_NaBIC.html)
- Potvin, J.-Y., Soriano, P., Vallée, M. (2004) "Generating trading rules on the stock markets with genetic programming", Computers & Operations Research 31(7), DOI 10.1016/S0305-0548(03)00063-7. GP; individual Canadian stocks; boolean rule trees over technical indicators; rules help in falling/flat markets, lag buy-and-hold in rising ones. Background; closeness 1. [S] (PII) — [ScienceDirect](https://www.sciencedirect.com/science/article/abs/pii/S0305054803000637)
- Chen, S.-H., Yeh, C.-H. (1997) "Toward a computable approach to the efficient market hypothesis: An application of genetic programming", J. Economic Dynamics & Control 21. GP; stock index; Background; closeness 1. [M]
- EDDIE (Tsang and colleagues): e.g., Tsang, E., Li, J., Butler, J.M. (1998) "EDDIE beats the bookies", Software: Practice and Experience; Tsang, E., Yung, P., Li, J. (2004) "EDDIE-Automation, a decision support tool for financial forecasting", Decision Support Systems 37(4). GP over technical-indicator conditions for forecasting. Background; closeness 1. [M] (not retrieved this session)
- Grammatical evolution (Brabazon, O'Neill and colleagues): O'Neill, M., Brabazon, A., Ryan, C., Collins, J.J. (2001) "Developing a Market Timing System using Grammatical Evolution", GECCO 2001 — [ResearchGate](https://www.researchgate.net/publication/2388943_Developing_a_Market_Timing_System_using_Grammatical_Evolution) [S title]; Dempsey, I., O'Neill, M., Brabazon, A. (2004) "Live Trading with Grammatical Evolution" — [gpbib](https://gpbib.cs.ucl.ac.uk/gp-html/dempsey_2004_gew_idem.html) [S]; Bradley, R., Brabazon, A., O'Neill, M. (2010) "Evolving Trading Rule-Based Policies" (EvoFIN; GE on intraday US stocks with costs) — [gpbib](https://gpbib.cs.ucl.ac.uk/gp-html/bradley_2010_evofin.html) [S]; Brabazon & O'Neill (2006) book "Biologically Inspired Algorithms for Financial Modelling", Springer [M]. GE; grammars over technical indicators. Background; closeness 1–2 (GE grammar is a natural vehicle for injecting new primitives).
- Lohpetch, D., Corne, D. (2009) "Discovering effective technical trading rules with genetic programming: towards robustly outperforming buy-and-hold", NaBIC 2009. GP; technical indicators. Background; closeness 1. [S] — [gpbib](https://gpbib.cs.ucl.ac.uk/gp-html/Lohpetch_2009_NaBIC.html)
- Menoita, R., Silva, S. (2025) "Evolving Financial Trading Strategies with Vectorial Genetic Programming", arXiv 2504.05418. Vectorial GP / strongly-typed VGP; three instruments; vector-valued terminals (price windows); strongly-typed VGP consistently among best, standard GP among worst. Background (recent representation work); closeness 2. [S] — [arXiv](https://arxiv.org/abs/2504.05418)

Surveys and books
- Chen, S.-H. (ed.) (2002) "Genetic Algorithms and Genetic Programming in Computational Finance", Kluwer/Springer. Background. [S] — [Springer listing](https://www.springerprofessional.de/genetic-algorithms-and-genetic-programming-in-computational-fina/13797898); [gpbib overview chapter](https://gpbib.cs.ucl.ac.uk/gp-html/ChenAO_2002_gagpcf.html)
- Aguilar-Rivera, R., Valenzuela-Rendón, M., Rodríguez-Ortiz, J.J. (2015) "Genetic algorithms and Darwinian approaches in financial applications: A survey", Expert Systems with Applications 42(21):7684–7697, DOI 10.1016/j.eswa.2015.06.001. Covers GA, GP, MOEA, LCS, co-evolution, EDA; GA most popular; identifies unexplored problem–method pairs. Background. [S] — [gpbib](https://gpbib.cs.ucl.ac.uk/gp-html/AguilarRivera_2015_ESA.html); [Peeref](https://www.peeref.com/works/501230)
- Brabazon, A., Kampouridis, M., O'Neill, M. (2020) "Applications of genetic programming to finance and economics: past, present, future", Genetic Programming and Evolvable Machines 21:33–53. Background; key self-citation. [S] — [Lero](https://lero.ie/content/applications-genetic-programming-finance-and-economics-past-present-future); reference list of [Long et al. 2026](https://repository.essex.ac.uk/41752/1/s10462-025-11390-9.pdf)

Directional-changes (DC) GP line (Kampouridis group) — all [S] via the reference list of Long, Kampouridis & Papastylianou (2026) unless noted
- Gypteau, J., Otero, F.E.B., Kampouridis, M. (2015) "Generating directional change based trading strategies with genetic programming", EvoApplications 2015, LNCS pp. 267–278, DOI 10.1007/978-3-319-16549-3_22. GP; FX; DC event-based terminals. Background; closeness 2. — [Springer](https://link.springer.com/chapter/10.1007/978-3-319-16549-3_22)
- Kampouridis, M., Otero, F.E.B. (2017) "Evolving trading strategies using directional changes", Expert Systems with Applications 73. GP; FX; DC indicators. Closeness 2. [M] (not in retrieved reference list)
- Adegboye, A., Kampouridis, M. (2021) "Machine learning classification and regression models for predicting directional changes trend reversal in FX markets", ESWA 173:114645. [S]
- Adegboye, A., Kampouridis, M., Otero, F. (2021) "Improving trend reversal estimation in forex markets under a directional changes paradigm with classification algorithms", Int. J. Intelligent Systems 36(12). [S]
- Adegboye, A., Kampouridis, M., Otero, F. (2023) "Algorithmic trading with directional changes", Artificial Intelligence Review 56(6):5619–5644. [S]
- Long, X., Kampouridis, M., Kanellopoulos, P. (2022) "Genetic programming for combining directional changes indicators in international stock markets", PPSN XVII, pp. 33–47. [S]
- Long, X., Kampouridis, M., Jarchi, D. (2022) "An in-depth investigation of genetic programming and nine other machine learning algorithms in a financial forecasting problem", CEC 2022. [S]
- Long, X., Kampouridis, M., Kanellopoulos, P. (2023) "Multi-objective optimisation and genetic programming for trading by combining directional changes and technical indicators", CEC 2023. [S]
- Long, X., Kampouridis, M. (2024) "α-dominance two-objective optimization genetic programming for algorithmic trading under a directional changes environment", CIFEr 2024. [S] — [PDF](http://kampouridis.net/papers/CIFEr_2024_paper_56.pdf)
- Long, X., Kampouridis, M., Papastylianou, T. (2026; online 2025) "Multi-objective genetic programming-based algorithmic trading, using directional changes and a modified sharpe ratio score for identifying optimal trading strategies", Artificial Intelligence Review 59:39, DOI 10.1007/s10462-025-11390-9. GP + NSGA-II; stocks; tree rooted at If-Then-Else (Buy/Hold), functions AND/OR/>/<, terminals = 28 DC indicators + 28 physical-time TA indicators + ERC, all normalised to [0,1]; no entropy/fractal/signature features. Background, most natural GP baseline/self-citation; closeness 2. [S] full text — [Essex repository](https://repository.essex.ac.uk/41752/1/s10462-025-11390-9.pdf)
- Christodoulaki, E., Kampouridis, M., Kanellopoulos, P. (2022) "Technical and sentiment analysis in financial forecasting with genetic programming", CIFEr 2022. [S]
- Christodoulaki, E., Kampouridis, M., Kyropoulou, M. (2023) "Enhanced strongly typed genetic programming for algorithmic trading", GECCO 2023, pp. 1055–1063. STGP; Closeness 2. [S]
- Christodoulaki, E., Kampouridis, M. (2026) "Strongly-typed genetic programming with an active trading operator for algorithmic trading using fundamental, sentiment, and technical analysis", Applied Soft Computing, DOI 10.1016/j.asoc.2026.116566. STGP; fundamental + sentiment + technical terminals. Background/baseline; closeness 2. [S] — [kampouridis.net](https://kampouridis.net/)
- Salman, O., Kampouridis, M., Jarchi, D. (2022) "Trading strategies optimization by genetic algorithm under the directional changes paradigm", CEC 2022 [S]; Salman, O., Melissourgos, T., Kampouridis, M. (2026) "A genetic algorithm for the optimization of multi-threshold trading strategies in the directional changes paradigm", Artificial Intelligence Review 59:2, DOI 10.1007/s10462-025-11419-z [S] — GA (not GP). — [kampouridis.net](https://kampouridis.net/)
- Rayment, G., Kampouridis, M. (2023, SSCI; 2024, ICMLA) deep RL HFT under DC sampling — RL not GP; possible related self-citations. [S]
- The target paper itself: "Large Language Quant: Cross-Domain Mathematical Trading Strategy Generation with an Agentic LLM", IEEE CIFEr 2026, DOI 10.1109/cifer67845.2026.11692403 [S, DOI from kampouridis.net news].

### Inferences
- The Essex DC-GP pipeline (Long et al. 2026; Christodoulaki & Kampouridis 2026) provides a ready-made boolean If-Then-Else Buy/Hold tree with normalised indicator terminals; adding the LLM-derived mathematical signals as extra normalised terminals is a direct, low-friction extension and gives an obvious ablation (TA+DC vs TA+DC+math terminals).
- STGP (Christodoulaki et al. 2023/2026) and vectorial GP (Menoita & Silva 2025) are the most suitable representations for typed or window-valued math primitives (e.g., a signature/Lévy-area operator that takes a window and returns a scalar).

### Gaps
- EDDIE, Chen & Yeh 1997, Kampouridis & Otero 2017 and Brabazon & O'Neill 2006 book details were not re-retrieved; DOIs not verified.
- Did not retrieve Kampouridis' 2019–2021 full publication list (site /publications page not fetched).

## Q2. Non-LLM GP/RL formulaic alpha mining

### Takeaway
Non-LLM alpha mining (AutoAlpha, AlphaEvolve-2021, AlphaGen, AlphaForge) evolves/generates formulaic factors over OHLCV operators (ts_mean, ts_corr, rank, delta, etc.) for cross-sectional return prediction on Chinese/US equities; none of the verified works use entropy, signature, information-geometric or optimal-transport operators.

### Cited Findings
- Zhang, T., Li, Y., Jin, Y., et al. (2020) "AutoAlpha: an Efficient Hierarchical Evolutionary Algorithm for Mining Alpha Factors in Quantitative Investment", arXiv 2002.08245. Hierarchical GP/evolutionary; Chinese A-shares; formula trees over price-volume operators; addresses sparsity of good alphas. Background (non-LLM); closeness 2. [S existence/abstract; author list M] — [arXiv](https://ar5iv.arxiv.org/html/2002.08245)
- Cui, C., Wang, W., Zhang, M., et al. (2021) "AlphaEvolve: A Learning Framework to Discover Novel Alphas in Quantitative Investment", SIGMOD 2021, DOI 10.1145/3448016.3457324, arXiv 2103.16196. AutoML-style evolutionary search evolving alphas (incl. learned components) with redundancy pruning; distinct from DeepMind's 2025 LLM AlphaEvolve. Closeness 2. [S] — [arXiv](https://arxiv.org/abs/2103.16196v2)
- Yu, S., Xue, H., Ao, X., et al. (2023) "Generating Synergistic Formulaic Alpha Collections via Reinforcement Learning" (AlphaGen), KDD 2023, DOI 10.1145/3580305.3599831. RL (PPO) builds RPN formula token by token, optimising the combined alpha pool. Closeness 2. [S existence via AlphaForge/AlphaEval descriptions and public repo; exact title/DOI M] — [AlphaForge paper](https://arxiv.org/html/2406.18394v5); [repo](https://gitee.com/prg/alphagen)
- Shi, H., et al. (2025) "AlphaForge: A Framework to Mine and Dynamically Combine Formulaic Alpha Factors", AAAI 2025, arXiv 2406.18394. Generator–predictor neural miner + dynamic combination; CSI 300/500. Closeness 2. [S] — [AAAI](https://ojs.aaai.org/index.php/AAAI/article/view/33365)
- AlphaEval (2025) arXiv 2508.13174 — evaluation framework classifying GP-style, RL-style and LLM-style formula miners. Background. [S] — [arXiv](https://arxiv.org/html/2508.13174v1)

### Inferences
- These works optimise IC/rank-IC of cross-sectional factors, not boolean entry/exit timing rules per asset; their operator libraries (Alpha101-style) are the "standard" baseline against which an exotic-math primitive set could be contrasted.

### Gaps
- No peer-reviewed gplearn-based factor-mining paper was retrieved (gplearn is widely used in practitioner/Chinese broker research, but I found no citable academic paper this session). "Learning to mine alpha" title not located.

## Q3. Have GP/GE/evolutionary trading systems used advanced mathematical features as primitives?

### Takeaway
Across targeted searches for each feature family, I found NO paper in which GP/GE evolves trading rules using spectral/permutation/approximate/transfer entropy, rate-distortion, path signatures/Lévy area, Fisher information/Fisher–Rao geometry, or Wasserstein distance as terminals or functions. The only near-misses are (i) entropy used as an external analysis variable to explain GP profitability (Navet & Chen), (ii) wavelet denoising as GP preprocessing, and (iii) a Hurst/fractal trading-signal paper that names GP only as future work. Category A therefore appears novel even without the LLM (subject to the gaps below).

### Cited Findings (near-misses and the non-GP literature on each feature)
Entropy
- Navet, N., Chen, S.-H. (2008; CIEF 2007 version) "On Predictability and Profitability: Would GP Induced Trading Rules Be Sensitive to the Observed Entropy of Time Series?" (in Natural Computing in Computational Finance, Springer [M for venue]). GP rules on NYSE US 100 stocks 2000–2006; entropy rate is computed per series and correlated with GP-vs-lottery performance — entropy is NOT a GP primitive. Category: Background/near-miss; closeness 2. [S] — [NCCU](https://ah.lib.nccu.edu.tw/handle/140.119/78849); [HAL](https://hal-univ-tlse3.archives-ouvertes.fr/INRIA/inria-00168347); [later review arXiv 1310.5540](https://arxiv.org/pdf/1310.5540)
- Permutation entropy in finance exists without GP (e.g., symbolic descriptions of FX data) — [PMC7516788](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC7516788/); [arXiv 1407.5254](https://arxiv.org/pdf/1407.5254). Transfer entropy used as ML features for US stock direction (non-GP) — [ResearchGate](https://www.researchgate.net/publication/342252903_Predicting_the_Direction_of_US_Stock_Prices_Using_Effective_Transfer_Entropy_and_Machine_Learning_Techniques). No GP usage found [S negative].
Wavelets (not in target list, but closest "advanced signal processing + GP")
- Liu, H., Ji, P., Jin, J. (2016) "Intra-Day Trading System Design Based on the Integrated Model of Wavelet De-Noise and Genetic Programming", Entropy 18(12). GP over technical indicators computed on wavelet-denoised CSI 300 intraday data; wavelet is preprocessing, not a primitive. Closeness 2. [S title/abstract via PDF link; authors/issue M] — [PDF](https://pdfs.semanticscholar.org/9c6e/c8eacc5d290f887e5d9bb5b1ec2ba5eb9349.pdf)
Hurst / fractal
- "Hurst Exponent and Trading Signals Derived from Market Time Series" (2018, SCITEPRESS conference paper; authors not captured). Hurst/fractal trading signals, weak correlations near H≈0.5; explicitly lists GP as future work — i.e., no GP. Closeness 2. [S] — [SCITEPRESS PDF](https://www.scitepress.org/papers/2018/66670/66670.pdf)
- No GP/GE paper using Hurst or fractal dimension as a terminal found [S negative]; GE+fractal search returned nothing relevant — [search results incl. GE ensembles](https://www.researchgate.net/publication/335218645_Grammatical_Evolution-based_ensembles_for_algorithmic_trading)
Path signatures / Lévy area
- Futter, O., Horvath, B., Wiese, M. (2023) "Signature Trading: A Path-Dependent Extension of the Mean-Variance Framework with Exogenous Signals", arXiv 2308.15135. Strategy = linear functional of the signature; no evolutionary search. Category: Background (math side); closeness 3 for the math, 1 for GP. [S] — [arXiv](https://ar5iv.labs.arxiv.org/html/2308.15135)
- Levin, D., Lyons, T., Ni, H. (2013) "Learning from the past, predicting the statistics for the future, learning an evolving system", arXiv 1309.0260 — signature features for regression; no GP. [S] — [RePEc](https://ideas.repec.org/p/arx/papers/1309.0260.html)
- No GP/symbolic-regression work over signature features found [S negative].
Fisher information / information geometry / Wasserstein
- Wasserstein appears in evolutionary computation only as an algorithmic device (e.g., Wasserstein crossover in topology optimisation, arXiv 2510.02870), not as a trading primitive — [arXiv](https://arxiv.org/pdf/2510.02870). No GP trading paper with Fisher information, Fisher–Rao, or Wasserstein features found [S negative].
Rate-distortion, statistical-physics phase transitions
- Not specifically searched beyond the combined queries; no hits surfaced in any GP-trading search [weak negative].
Symbolic regression on time series (context)
- Kaboudan, M. (1998) "Statistical Evaluation of Symbolic Regression Forecasting of Time Series" — GP symbolic regression; complexity inversely related to predictability. Background; closeness 1. [S] — [gpbib](https://gpbib.cs.ucl.ac.uk/gp-html/kaboudan_1998_sesrfts.html)

### Inferences
- Novelty claim for category A (without LLM) looks defensible: "first GP/STGP system whose primitive set includes information-theoretic, rough-path, information-geometric, optimal-transport and fractal operators for trading-rule evolution" — but phrase it as "to the best of our knowledge" because indexed search coverage was limited (Elicit/Consensus unavailable; gpbib not exhaustively queried).
- Strongest prior-art risks to cite/differentiate: Navet & Chen (entropy as diagnostic of GP profitability), Liu et al. 2016 (signal-processing preprocessing + GP), Futter et al. 2023 (signature-based strategies without evolution).

### Gaps
- Not checked: gpbib keyword search for "entropy", "Hurst", "fractal"; Chinese-language GP factor-mining literature (which may include entropy-like operators); GECCO/EvoApps proceedings tables of contents; practitioner gplearn operator libraries.
- Possible missed: GP using Hurst as input in FX/crypto in lower-tier venues; neuroevolution papers with entropy inputs (not GP).

## Q4. GP-evolved regime-switching / multi-mode rules with such features

### Takeaway
No GP work evolving regime-switching rules driven by entropy/Hurst/signature-type regime indicators was found. Regime handling in the closest literature is via (a) HMM regime detection with DC indicators feeding fixed (non-evolved) strategies, or (b) GE ensembles/dynamic rule switching under structural change using technical indicators.

### Cited Findings
- HMM over DC indicators to detect FX regime changes and switch trading rules (no GP) — [Physica A, ScienceDirect](https://www.sciencedirect.com/science/article/abs/pii/S0378437123003655); [arXiv 2309.15383](https://arxiv.org/pdf/2309.15383) [S]
- GE-based ensembles for S&P 500 under structural change and dynamic switching between an active and candidate rule — [ResearchGate](https://www.researchgate.net/publication/335218645_Grammatical_Evolution-based_ensembles_for_algorithmic_trading) [S; authors not captured]
- Essex DC-GP trees use a single If-Then-Else Buy/Hold root, not multi-mode trees — [Long et al. 2026](https://repository.essex.ac.uk/41752/1/s10462-025-11390-9.pdf) [S]

### Inferences
- A GP design where a regime primitive (e.g., Hurst, spectral entropy, volatility-phase indicator) gates typed sub-trees (STGP "regime-If" node) would be novel relative to everything retrieved.

### Gaps
- Did not search EDDIE/Essex older work on "market regime" GP (e.g., Kampouridis' earlier GP market-microstructure/regime studies) — may contain regime-aware GP without exotic features.

## Q5. Recent (2023–2026) Kampouridis-group GP trading papers for baselines/self-citation

### Takeaway
The most natural baselines are Long, Kampouridis & Papastylianou (AIR 2026, MOO GP with DC+TA terminals) and Christodoulaki & Kampouridis (ASOC 2026, STGP with fundamental/sentiment/technical terminals); supporting self-citations are Long et al. CEC 2023, Long & Kampouridis CIFEr 2024, Christodoulaki et al. GECCO 2023, Adegboye et al. AIR 2023, Salman et al. AIR 2026 (GA), and Brabazon, Kampouridis & O'Neill GPEM 2020 survey.

### Cited Findings
- Full entries listed under Q1 (DC GP line) — verified via [Long et al. 2026 reference list](https://repository.essex.ac.uk/41752/1/s10462-025-11390-9.pdf) and [kampouridis.net](https://kampouridis.net/) [S]

### Inferences
- Baseline set suggestion: (1) TA-only GP; (2) DC+TA GP (Long et al. 2026); (3) STGP TA+sentiment+fundamental (Christodoulaki & Kampouridis 2026) where data allow; (4) LLQ (CIFEr 2026) fixed LLM strategies + portfolio GA; (5) GP with LLQ math terminals (proposed).

### Gaps
- Kampouridis 2019–2022 non-DC GP work (e.g., EDDIE extensions, GP in weather derivatives) not enumerated.
