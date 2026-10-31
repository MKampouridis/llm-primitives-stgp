# Citation verification: survey round 2 merged candidate list

Checked 2026-10-30. Methods: arXiv export API (`export.arxiv.org/api/query?id_list=...`) for all arXiv IDs (title, authors, first-version date, comments and journal-ref); Crossref REST API (`api.crossref.org/works/<doi>`) for every DOI; Crossref title search for venue DOIs; ACL Anthology, NeurIPS virtual site and PMLR via web search/fetch. OpenReview itself returned a bot-check page, so the NeurIPS virtual page was used for item 8 instead.

**Result: 61/61 records exist. No ID resolves to a different paper. 55 VERIFIED, 6 CORRECTED (items 8, 34, 52, 54, 55, 60; most of these are small fixes or added details).**

Where a topic line says "(from title/record)", Crossref had no abstract and none was retrieved, so the description is based on the title and venue only.

| # | Status | Corrected details (if any) | One-line topic description | Evidence URL |
|---|---|---|---|---|
| 1 | VERIFIED | Authors: Haolin Yang, Zhiqiang Qian, Chutian Chen et al. (10 authors); v1 2026-10-12 | Training-free framework with two nested self-improvement loops for LLM-driven alpha factor discovery, aimed at reducing backtest overfitting and keeping the research process auditable | https://arxiv.org/abs/2610.17130 |
| 2 | VERIFIED | Xintong Liu, Chenkai Zhang, Yanzhao Ma, Peng Yang; 2026-10-21 | Steers LLM-based evolutionary formulaic-factor search using parent/child lineage information, so search is more directed and structurally diverse than plain fitness selection | https://arxiv.org/abs/2610.29663 |
| 3 | VERIFIED | ACL 2026 long confirmed: 2026.acl-long.538, pp. 11715–11749. Authors Fengyuan Liu, Yi Huang, Sichun Luo, Yuqi Wang, Yazheng Yang, Xinye Li, Zefa Hu, Junlan Feng, Qi Liu | CogAlpha: alphas are represented as code, and LLMs act as reasoning agents that mutate, recombine and refine them, guided by financial feedback | https://aclanthology.org/2026.acl-long.538/ ; https://arxiv.org/abs/2511.18850 |
| 4 | VERIFIED | Current title "From Flat to Hierarchical: Evolving Tree-structured Thoughts for Fine-grained Alpha Mining" (v2). Authors Junji Ren, Junjie Zhao, Shengcai Liu, Peng Yang; v1 2025-08-22 | Evolves tree-structured LLM "thoughts" (hierarchical reasoning) to generate alpha formulas/code more efficiently than flat LLM generation | https://arxiv.org/abs/2508.16334 |
| 5 | VERIFIED | Yating Ling, Wenjing Cun, Zhitang Chen; 2026-08-26 | Wraps the PySR GP engine with LLM guidance. Parallel semantic and structural hints narrow the symbolic-regression search space; the LLM does not generate expressions directly | https://arxiv.org/abs/2608.25291 |
| 6 | VERIFIED | Jun Han, Shuo Zhang, Wei Li et al. (17 authors); 2026-02-06 | Evolutionary alpha-mining framework that treats each end-to-end LLM mining run as an individual, enabling controlled multi-round search and reuse of validated experience | https://arxiv.org/abs/2602.07085 |
| 7 | VERIFIED | Taian Guo, Haiyang Shen, Junyu Luo et al. (9 authors); 2026-02-12 | Models the factor pool as a graph and combines principled retrieval with graph-biased evolution, so mining has a global structural view rather than isolated or parent-child generation | https://arxiv.org/abs/2602.11917 |
| 8 | CORRECTED | Venue: **NeurIPS 2025 Workshop on Generative AI in Finance (poster), not the main track**. Authors: Haochen Luo, Ho Ko, David Sun, Yuan Zhang, Chen Liu | Uses LLMs as mutation, crossover and selection operators to evolve alpha factors with backtest feedback, evaluated on sparse portfolio performance | https://neurips.cc/virtual/2025/132561 (links OpenReview ALpLmURYWy; the OpenReview page itself showed a bot-check) |
| 9 | VERIFIED | Andrew Clayman, Michael Kampouridis, Tasos Papastylianou; 2026 IEEE CIFEr, pp. 171–180 | (from title/record) An agentic LLM that generates mathematical trading strategies by carrying ideas over from other domains | https://doi.org/10.1109/CIFEr67845.2026.11692403 |
| 10 | VERIFIED | ICLR 2025 (per arXiv comment) | LLEGO: genetic programming for decision-tree induction, with LLM-based crossover/mutation operators that are fitness- and diversity-aware | https://arxiv.org/abs/2503.14217 |
| 11 | VERIFIED | Azizjon Kobilov, Jianglin Lan; 2025-02-11 | Combines an LLM with GP to automatically build behaviour-tree task plans for robots | https://arxiv.org/abs/2502.07772 |
| 12 | VERIFIED | ICLR 2025 (Oral) | LLM-SR: LLM proposes equation skeletons as programs, and evolutionary search with parameter optimisation refines them for scientific equation discovery | https://arxiv.org/abs/2404.18400 |
| 13 | VERIFIED | Cristina Rossetti, Anna V. Kononova, Thomas Bäck, Fei Liu, Niki van Stein; 2026-09-28 | Multi-objective (accuracy versus complexity) LLM-driven evolution of symbolic-regression expressions, guided by informative substructures | https://arxiv.org/abs/2609.36187 |
| 14 | VERIFIED | KDD 2025 confirmed: DOI 10.1145/3711896.3736838, pp. 2813–2822 | LLM agent for alpha mining with regularisers for originality (AST similarity), hypothesis-factor alignment and complexity, to counter alpha decay | https://doi.org/10.1145/3711896.3736838 |
| 15 | VERIFIED | Yuante Li, Xu Yang, Xiao Yang et al.; NeurIPS 2025 (arXiv comment) | Multi-agent R&D loop that jointly optimises factors and predictive models for quant investment | https://arxiv.org/abs/2505.15155 |
| 16 | VERIFIED | EMNLP 2025 System Demonstrations (arXiv comment) | Interactive human-AI system in which an LLM helps users generate and refine formulaic alphas | https://arxiv.org/abs/2308.00016 |
| 17 | VERIFIED | Saizhuo Wang, Hang Yuan, Lionel M. Ni, Jian Guo | LLM trading agent that improves itself through an inner/outer loop of knowledge accumulation and real-world feedback | https://arxiv.org/abs/2402.03755 |
| 18 | VERIFIED | Findings of EMNLP 2025, pp. 18517–18533, DOI 10.18653/v1/2025.findings-emnlp.1005 | Three-stage, risk-aware multi-agent LLM pipeline: generate alpha candidates, filter them by agent evaluation, then combine them with dynamic weights | https://aclanthology.org/2025.findings-emnlp.1005/ |
| 19 | VERIFIED | Tianping Zhang, Yuanqi Li, Yifei Jin, Jian Li | Hierarchical GP-style evolutionary algorithm for efficiently mining formulaic alpha factors | https://arxiv.org/abs/2002.08245 |
| 20 | VERIFIED | Weizhe Ren, Yichen Qin, Yang Li | GP for alpha mining that is warm-started from well-designed seed alphas instead of random initialisation | https://arxiv.org/abs/2412.00896 |
| 21 | VERIFIED | KDD '23 (ADS), DOI 10.1145/3580305.3599831 | AlphaGen: RL generates formulaic alphas, with the reward based on the performance of the combined alpha set (synergy) | https://arxiv.org/abs/2306.12964 |
| 22 | VERIFIED | AAAI 2025 (arXiv comment) | Generative-predictive neural alpha mining plus dynamic, time-varying combination of the mined factors | https://arxiv.org/abs/2406.18394 |
| 23 | VERIFIED | Nature 625(7995):468–475; online 2023-12-14, issue 2024 | FunSearch: LLM-proposed programs plus evolutionary search find new constructions in mathematics (cap sets) and heuristics for bin packing | https://doi.org/10.1038/s41586-023-06924-6 |
| 24 | VERIFIED | — | ELM: LLMs trained on code serve as mutation operators in GP/MAP-Elites | https://arxiv.org/abs/2206.08896 |
| 25 | VERIFIED | Journal: ACM Trans. on Evolutionary Learning and Optimization 4(4):1–40, 2024 | LLMs used as crossover operators by few-shot prompting with parent genotypes | https://doi.org/10.1145/3694791 |
| 26 | VERIFIED | ICML 2024, PMLR 235:32201–32223 | EoH: co-evolves natural-language "thoughts" and code to design heuristics automatically, using far fewer LLM queries than FunSearch | https://proceedings.mlr.press/v235/liu24bs.html |
| 27 | VERIFIED | NeurIPS 2024 (arXiv comment) | ReEvo: LLM hyper-heuristic that adds short- and long-term reflection to evolutionary heuristic design | https://arxiv.org/abs/2402.01145 |
| 28 | VERIFIED | IEEE TEVC 29(2):331–345, 2025, DOI 10.1109/TEVC.2024.3497793 | LLaMEA: LLM-driven evolutionary loop that generates and refines metaheuristic code from performance feedback | https://doi.org/10.1109/TEVC.2024.3497793 |
| 29 | VERIFIED | GPEM 25(2), article 21, 2024 | Uses an LLM as the variation operator in a GP-like loop for evolving code (LLM_GP) | https://doi.org/10.1007/s10710-024-09494-2 |
| 30 | VERIFIED | SSBSE 2023, LNCS 14415, DOI 10.1007/978-3-031-48796-5_13 | LLM-generated edits used as mutation operators in genetic improvement of software | https://arxiv.org/abs/2310.19813 |
| 31 | VERIFIED | GECCO 2023, DOI 10.1145/3583131.3590481 | SEIDR: LLM synthesise-execute-debug loop with ranking/repair for autonomous program synthesis | https://arxiv.org/abs/2304.10423 |
| 32 | VERIFIED | Hengzhe Zhang, Qi Chen, Bing Xue, Wolfgang Banzhaf, Mengjie Zhang | LLM meta-evolves selection operators for GP symbolic regression | https://arxiv.org/abs/2505.18602 |
| 33 | VERIFIED | ECAI 2025 (arXiv comment) | Grammar-guided GP over prompt-editing programs, followed by local search, for discrete prompt optimisation | https://arxiv.org/abs/2507.10326 |
| 34 | CORRECTED | Applied Soft Computing **vol. 204, art. 116566; Crossref issue date Jan 2027** (published online in 2026). Authors Eva Christodoulaki, Michael Kampouridis | Strongly-typed GP for algorithmic trading that combines fundamental, sentiment and technical indicators, with an "active trading" operator | https://doi.org/10.1016/j.asoc.2026.116566 |
| 35 | VERIFIED | KBS vol. 311, art. 113054, Feb 2025 | Strongly-typed GP that combines sentiment and technical-analysis indicators in trading rules | https://doi.org/10.1016/j.knosys.2025.113054 |
| 36 | VERIFIED | PPSN XVII, LNCS, pp. 33–47 | GP that combines directional-change indicators into trading strategies across international stock markets | https://doi.org/10.1007/978-3-031-14721-0_3 |
| 37 | VERIFIED | EvoApplications 2015, LNCS, pp. 267–278 | GP evolving trading strategies from directional-change event features | https://doi.org/10.1007/978-3-319-16549-3_22 |
| 38 | VERIFIED | IJCIS 5(3):530 (2012) | Extends the grammar of EDDIE, a GP forecasting tool, for finding investment opportunities | https://doi.org/10.1080/18756891.2012.696918 |
| 39 | VERIFIED | JFQA 32(4):405 (1997) | GP-evolved FX technical trading rules and whether they are profitable out of sample | https://doi.org/10.2307/2331231 |
| 40 | VERIFIED | JFE 51(2):245–271 (1999) | GA/GP search for technical trading rules on the S&P 500, which found little excess return after costs | https://doi.org/10.1016/S0304-405X(98)00052-X |
| 41 | VERIFIED | GPEM 21(1–2):33–53; online 2019, issue 2020 | Survey of GP applications in finance and economics, with future directions | https://doi.org/10.1007/s10710-019-09359-z |
| 42 | VERIFIED | Owen Futter, Blanka Horvath, Magnus Wiese | Path signatures used to extend mean-variance portfolio optimisation to path-dependent trading with exogenous signals | https://arxiv.org/abs/2308.15135 |
| 43 | VERIFIED | Veronica Guidetti, Luca La Rocca, Fabrício Olivetti de França, Gabriel Kronberger; 2026-10-17 | Post-hoc pruning of oversized GP symbolic-regression expressions using Fisher-information geometry, to get parsimonious models | https://arxiv.org/abs/2610.24753 |
| 44 | VERIFIED | Alexander Novikov, Ngân Vũ, Marvin Eisenberger et al. | AlphaEvolve: Gemini-powered evolutionary coding agent for algorithmic and scientific discovery | https://arxiv.org/abs/2506.13131 |
| 45 | VERIFIED | Yu Shi, Yitong Duan, Jian Li | LLM-guided Monte Carlo tree search over formulaic alpha expressions, with backtest feedback | https://arxiv.org/abs/2505.11122 |
| 46 | VERIFIED | Junhyeog Yun, Hyoun Jun Lee, Insu Jeon; oral at the 2nd AI4F Workshop @ ACM ICAIF 2025 (non-archival) | Quality-diversity (feature-map) evolution plus a multi-agent LLM system for discovering trading strategies | https://arxiv.org/abs/2510.18569 |
| 47 | VERIFIED | Di Zhang, Zhengyong Jiang, Qiong Ji, Hengyan Liu, Tianshi Wang, Angelos Stefanidis…; IEEE SMC 2025, pp. 3665–3670 | (from title/record) LLM-guided evolutionary generation of quantitative trading strategies | https://doi.org/10.1109/SMC58881.2025.11343400 |
| 48 | VERIFIED | Jiandong Chen, Haochen Luo, Yuan Zhang, Chen Liu, Qingfu Zhang | LLM plus evolutionary search that generates and evolves alpha factors for selecting assets in sparse portfolios | https://arxiv.org/abs/2507.17211 |
| 49 | VERIFIED | Matthew Siper, Ahmed Khalifa, Julian Togelius; 2026-08-13 (comment: submitted to AAAI) | Formalises "delayed utility" of weak offspring in evolutionary search as a finite-horizon MDP, and controls search by long-term rather than immediate return | https://arxiv.org/abs/2608.13297 |
| 50 | VERIFIED | Zhuoliang Xie, Ruihao Zheng, Xiang Xu, Genghui Li, Zhengkun Wang | LLM-based algorithm design that evolves reusable code primitives/snippets instead of whole programs | https://arxiv.org/abs/2608.07395 |
| 51 | VERIFIED | Jie Mao, Changlun Li, Xiang Li et al. (9 authors) | Self-evolving LLM strategy rewriting, gated by verifiers to limit hallucinated edits, drift and overfitting | https://arxiv.org/abs/2607.12455 |
| 52 | CORRECTED | Title is **"Hubble: An LLM-Driven Agentic Framework for Safe, Diverse, and Reproducible Alpha Factor Discovery"** (not "Safe and Automated"). Authors Runze Shi, Shengyu Yan, Yuecheng Cai, Chengxi Lv (4 authors, so "et al." overstates it slightly). arXiv lists v1 as 2026-03-09 | Agentic LLM factor mining restricted to a domain-specific operator language with AST-sandboxed execution, for safety and reproducibility | https://arxiv.org/abs/2604.09601 |
| 53 | VERIFIED | Hang Yuan, Saizhuo Wang, Jian Guo | Human-in-the-loop LLM system that extends Alpha-GPT from alpha mining to modelling and analysis | https://arxiv.org/abs/2402.09746 |
| 54 | CORRECTED | Authors: **Shuo Yu, Hong-Yan Xue, Xiang Ao, Qing He**. Front. Comput. Sci. 20(2), art. 2002316; online 2025-10-17 (volume year 2026) | Hybrid formulaic-alpha discovery that combines LLM assistance with algorithmic (RL/search) alpha generation | https://doi.org/10.1007/s11704-025-41061-5 |
| 55 | CORRECTED | Authors: Matthew Siper, Ahmed Khalifa, Lisa Soros, **Muhammad (Umair) Nasir, Juyan (arXiv: Jay) Azhang**, Julian Togelius. GECCO 2026 pp. 727–734 confirmed. SSRN 5889762 (DOI 10.2139/ssrn.5889762) is dated 2025 | (from title/record) Program search, i.e. evolution of trading-strategy programs, for financial trading | https://doi.org/10.1145/3795095.3805175 |
| 56 | VERIFIED | Full title "AlgoEvolve: LLM-driven Meta-evolution of Algorithmic Trading Programs"; Dhruv Sharma, Gautam Shroff; 2026-06-24 | LLMs as semantic mutation operators in a meta-evolutionary loop that evolves algorithmic trading programs | https://arxiv.org/abs/2606.26173 |
| 57 | VERIFIED | Full title "MadEvolve: Evolutionary Optimization of Trading Systems with Large Language Models"; Yurii Kvasiuk, Tianyi Li, Owen Colegrove, Moritz Münchmeyer | Applies an AlphaEvolve-style LLM optimisation framework, first built for cosmology, to trading strategies and alpha generation | https://arxiv.org/abs/2605.23007 |
| 58 | VERIFIED | Siper, Nasir, Khalifa, Soros, Azhang, Togelius; 2026-02-07; also SSRN 10.2139/ssrn.6169788 | Learns a continuous latent program space in which distance tracks behaviour, and designs GP mutation operators in it; tested on a trading-strategy DSL | https://arxiv.org/abs/2602.07659 |
| 59 | VERIFIED | Arya Grayeli, Atharva Sehgal, Omar Costilla-Reyes, Miles Cranmer, Swarat Chaudhuri; NeurIPS 2024 | LaSR: symbolic regression that uses an LLM to build a library of abstract concepts, which then guides the evolutionary search | https://arxiv.org/abs/2409.09359 |
| 60 | CORRECTED | Full title: **"On Predictability and Profitability: Would GP Induced Trading Rules be Sensitive to the Observed Entropy of Time Series?"**. Book chapter in *Natural Computing in Computational Finance* (Studies in Computational Intelligence), 2008, pp. 197–210. **DOI 10.1007/978-3-540-77477-8_11** | Tests whether how profitable GP-evolved trading rules are relates to the measured entropy (predictability) of the price series | https://doi.org/10.1007/978-3-540-77477-8_11 |
| 61 | VERIFIED | Title: **"Multi-objective genetic programming-based algorithmic trading, using directional changes and a modified sharpe ratio score for identifying optimal trading strategies"**. Xinpeng Long, Michael Kampouridis, Tasos Papastylianou; AI Review 59(2), art. 39, 2026 | Multi-objective GP over directional-change features, using a modified Sharpe-ratio objective, for trading strategies | https://doi.org/10.1007/s10462-025-11390-9 |

## Summary

**NOT FOUND:** none. Every arXiv ID resolves to the claimed paper, and every DOI resolves to the claimed work. No fabricated or garbled IDs were detected.

**CORRECTED:**
- **#8 EvoAlpha.** This is a NeurIPS 2025 *workshop* paper (Workshop on Generative AI in Finance, poster), not the main track. Authors are Luo, Ko, Sun, Zhang, Liu.
- **#34 Christodoulaki & Kampouridis (ASOC).** It is Vol. 204, art. 116566, and Crossref gives the issue date as January 2027 (it was online in 2026). Cite it as 2026 (online) or 2027 (issue), depending on the style guide.
- **#52 Hubble.** The title is "…for Safe, Diverse, and Reproducible Alpha Factor Discovery". The authors are Shi, Yan, Cai, Lv.
- **#54 Frontiers of CS.** The authors are Shuo Yu, Hong-Yan Xue, Xiang Ao, Qing He (the AlphaGen group). It is Vol. 20(2), art. 2002316.
- **#55 ProFiT.** The full author list is Siper, Khalifa, Soros, Nasir, Azhang, Togelius. Venue, pages and DOI are correct.
- **#60 Navet & Chen.** The full title starts "On Predictability and Profitability: …". It is a chapter in *Natural Computing in Computational Finance* (SCI, Springer, 2008), pp. 197–210, DOI 10.1007/978-3-540-77477-8_11.

**Notes on items marked VERIFIED (no action needed, but useful to know):**
- #3 CogAlpha: ACL 2026 long is confirmed as 2026.acl-long.538.
- #4: the current arXiv title is "From Flat to Hierarchical…".
- #14 AlphaAgent: KDD 2025 is confirmed, DOI 10.1145/3711896.3736838.
- #18: confirmed as Findings of EMNLP 2025.
- #28 LLaMEA: TEVC DOI 10.1109/TEVC.2024.3497793.
- #46 QuantEvolve: the ICAIF workshop is non-archival.
- #61: the claim left the title blank. The full title is given in the table.
- For #9, #47 and #55, Crossref has no abstract and none was retrieved, so their topic lines come from the titles only.
