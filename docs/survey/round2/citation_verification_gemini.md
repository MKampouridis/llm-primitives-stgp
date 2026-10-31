# Citation verification: Gemini candidate list (checked 2026-10-30)

Sources: arXiv export API (batch), Crossref REST API, ICLR virtual site / mlanthology, GitHub API. OpenReview API (api2 and api v1) returned a 403 bot challenge for every request.

| ID | Status | Corrected details | One-line topic | Evidence URL |
|---|---|---|---|---|
| G1 | NOT FOUND (could not access) | OpenReview API v1/v2 and the forum page all returned a 403 bot-challenge. Web searches for "ALPHAS2", "Semantic-Symbolic Co-Evolution" and the id QjycCr3zns found nothing. Existence, title and venue are unconfirmed. | (unverified) | https://openreview.net/forum?id=QjycCr3zns |
| G2 | CORRECTED | arXiv lists **one author only: Lang Cao** (v1, 8 Aug 2025). No Xi Z. or Liao L. v2 was removed by arXiv admins (license issue), so cite v1. | LLM dual-chain (generation + optimization) framework for fully automated formulaic alpha mining on A-shares | https://arxiv.org/abs/2508.06312v1 |
| G3 | VERIFIED | Wang Y., Xu J., Zhang H., Huang S.-L., Sun D.D., Zhang X.-P.; arXiv Feb 2026 | Self-evolving LLM agent with skills and experience memory that mines low-redundancy formulaic alpha factors | https://arxiv.org/abs/2602.14670 |
| G4 | VERIFIED | Guo J., Huang S., Gao Y., Li Z., Ge J., Liang S., Kuang X., Wang M.; arXiv Aug 2026 | Recursive self-improvement of LLM research systems for factor discovery and trading strategy research | https://arxiv.org/abs/2608.12841 |
| G5 | VERIFIED (partly) | Abhyankar N., Shojaee P., Reddy C.K.; arXiv Mar 2025. arXiv comment confirms "Accepted in TMLR". The 05/2026 date was not checked against the TMLR record. | LLMs used as evolutionary optimizers that generate feature-engineering programs for tabular data | https://arxiv.org/abs/2503.14434 |
| G6 | VERIFIED | Taga E.O., Zhuang Y., Ildiz M.E., Mol P., Das A., Duraisamy K., Oymak S.; arXiv Jul 2026 | LLM-based evolution of Python fit/transform preprocessing programs for structured data | https://arxiv.org/abs/2607.01548 |
| G7 | VERIFIED | Gurkan C., Stonedahl F., Wilensky U.; arXiv Jun 2026. Accepted to the GECCO '26 Workshop on LLMs for and with Evolutionary Computation (LLM4EC). | Shows that LLM mutation chains without selection converge and lose diversity in program evolution | https://arxiv.org/abs/2606.05408 |
| G8 | VERIFIED (ID found) | Tang Z(iyi), Yin X., Chen W., Chen Z., Zheng Y., Ye W., Wang K., Lin L.; ICLR 2026 poster; **OpenReview id lNmZrawUMu**; no arXiv version found | Agentic RL with hierarchical rewards that trains a small LLM to iteratively evolve alpha factors | https://mlanthology.org/iclr/2026/tang2026iclr-alphaagentevo/ ; https://iclr.cc/virtual/2026/poster/10007685 |
| G9 | VERIFIED (ID found) | **arXiv:2603.20247**, 10 Mar 2026; authors Weng Zhangyuhua, Zhang Shengli, Wang Taotao, Xia Yihan (4 authors) | Multi-agent system that mines and refines "market logic" libraries to guide interpretable factor generation | https://arxiv.org/abs/2603.20247 |
| G10 | CORRECTED (authors filled) | Authors: **Jiang P., Zhang F., Xu X., Chen T., Yang C.**; arXiv 11 Oct 2026 | Multi-turn tool-using LLM agent trained with RL for adaptive formulaic alpha mining | https://arxiv.org/abs/2610.15488 |
| G11 | VERIFIED | Yu X(inwei), Fu Y., Fan M., Li E., Gao Y., Xu S.; arXiv Aug 2026 | Survey/perspective on formulaic alpha discovery from an evolutionary computation viewpoint | https://arxiv.org/abs/2608.01789 |
| G12 | VERIFIED | Fernando, Banarse, Michalewski, Osindero, Rocktäschel; arXiv Sep 2023; ICML 2024 (PMLR 235) | Self-referential evolution of task prompts and mutation prompts for LLMs | https://arxiv.org/abs/2309.16797 |
| G13 | VERIFIED | Hollmann, Müller, Hutter; arXiv May 2023; NeurIPS 2023 | LLM generates semantically meaningful features with explanations for tabular AutoML (CAAFE) | https://arxiv.org/abs/2305.03403 |
| G14 | CORRECTED | The DOI resolves to the right title, but the authors are **Gudny Birna Saemundsdottir and Saemundur Oskar Haraldsson** (GECCO '24 Companion, pp. 727–730). Brownlee, Callan, Even-Mendoza et al. wrote *different* papers: "Enhancing Genetic Improvement Mutations Using LLMs" (SSBSE 2023, 10.1007/978-3-031-48796-5_13) and "LLM based mutations in GI" (ASE journal 2025, 10.1007/s10515-024-00473-6). | Using an LLM as a single operator for mutation/crossover in genetic improvement | https://api.crossref.org/works/10.1145/3638530.3654408 |
| G15 | CORRECTED | DOI **10.1002/fut.70075**. Authors: **Guo Zihao, Jin Hanqing, Kuang Jiaqi, Qian Zhongmin, Wang Jinghan** (Guo is first; Qian is missing from the claim). Published online 14 Dec 2025, issue 46(3) Mar 2026, pp. 582–603. | Path-signature decomposition applied to pair-trading signal construction | https://doi.org/10.1002/fut.70075 |
| G16 | VERIFIED (DOI found) | DOI **10.1109/CEC.2006.1688631**, pp. 2587–2592, 2006 IEEE CEC | Grammatical evolution with adaptive retraining of trading rules for changing markets | https://doi.org/10.1109/CEC.2006.1688631 |
| G17 | CORRECTED | The given DOI resolves to a **different paper** ("Congestion based resource sharing in multi-service networks"). The correct DOI is **10.1016/S0167-9236(03)00087-3**: DSS 37(4):559–565, Sep 2004. | GP-based EDDIE tool that automates financial forecasting rule induction | https://doi.org/10.1016/S0167-9236(03)00087-3 |
| G18 | VERIFIED | Comput. Oper. Res. 31(7):1033–1047, 2004 | Genetic programming that generates technical trading rules for stocks | https://doi.org/10.1016/S0305-0548(03)00063-7 |
| G19a | VERIFIED | FactorBench: A Portfolio-Aware Benchmark for Automated Factor Mining. Wang Zhuohan, Ventre Carmine; arXiv Oct 2026 | Benchmark that tests whether mined factors generalize and are useful at the portfolio level | https://arxiv.org/abs/2610.06947 |
| G19b | VERIFIED | AgenticEvolve: Evolutionary Program Search with Persistent Language Model Agents that Design and Run Experiments. Peng Z.-Y., Lan Q.-Y., Wang Z.-H., Zhang J., Piao Y.-S.; arXiv Oct 2026 | Evolutionary program search where each island is a persistent agent that runs its own experiments | https://arxiv.org/abs/2610.31326 |
| G19c | VERIFIED | QuantBench: Benchmarking AI Methods for Quantitative Investment. Wang Saizhuo et al. (incl. Ni L.M., Guo Jian); arXiv Apr 2025 | Industrial-grade benchmark platform for AI quant-investment methods | https://arxiv.org/abs/2504.18600 |
| G20 | VERIFIED | GitHub paperswithbacktest/pwb-alphaevolve, created 16 May 2025, "DeepMind's AlphaEvolve coding agent for trading strategies". It uses evolutionary LLM prompts (OpenAI o3) and Backtrader. | Open-source AlphaEvolve-style LLM evolution of Backtrader trading strategies | https://github.com/paperswithbacktest/pwb-alphaevolve |
| C1 | Resolved | AlphaPROBE (2602.11917) authors: **Guo Taian, Shen Haiyang, Luo Junyu, Chen Binqi, Ding Hongjun, Huang Jinsheng, Liu Luchen, Ma Yun, Zhang Ming**. "Guo, Shen, Luo et al." is correct; Gemini's "Han J., Zhang S., Li W." is wrong. | Alpha mining via principled retrieval plus graph-biased factor evolution | https://arxiv.org/abs/2602.11917 |
| C2 | Resolved | EFS (2507.17211) authors: **Chen Jiandong, Luo Haochen, Zhang Yuan, Liu Chen, Zhang Qingfu**. "Chen J., Luo H., Zhang Y. et al." is correct; Gemini dropped the first author. | LLM + evolutionary search for factors that drive sparse portfolio optimization | https://arxiv.org/abs/2507.17211 |
| C3 | CONFIRMED | AAAI 2026, Proc. AAAI 40(2):997–1005, DOI 10.1609/aaai.v40i2.37069. Authors Shi Y., Duan Y., Li J. The published title reads "...MCTS Framework for Formulaic **Alpha** Factor Mining"; arXiv says "Formulaic Factor Mining". | LLM-guided Monte Carlo tree search for formulaic alpha mining | https://doi.org/10.1609/aaai.v40i2.37069 |
| C4 | Noted | Confirmed: Findings of EMNLP 2025, pp. 18517–18533, DOI 10.18653/v1/2025.findings-emnlp.1005 (Kou Z. et al., 10 authors). Gemini's "arXiv only" is outdated. | Risk-aware multi-agent LLM framework that generates and selects alpha factors / strategies | https://doi.org/10.18653/v1/2025.findings-emnlp.1005 |
| C5 | CONFIRMED | The exact title matches: "AlgoEvolve: LLM-driven Meta-evolution of Algorithmic Trading Programs". Authors Sharma Dhruv, Shroff Gautam; arXiv 24 Jun 2026. | LLMs as semantic mutation operators for evolving algorithmic trading programs | https://arxiv.org/abs/2606.26173 |

## Summary of NOT FOUND and CORRECTED

**NOT FOUND**
- **G1 (ALPHAS2, OpenReview QjycCr3zns)**: OpenReview could not be accessed (403 bot challenge on api2, api v1 and the forum page). It is not indexed by web search under the title or the id. This is "could not access", not proof that it does not exist. A human should open the forum link in a browser.

**CORRECTED**
- **G2 Chain-of-Alpha**: the only author is Lang Cao. The extra authors "Xi Z., Liao L." appear fabricated. v2 was removed by arXiv admins, so cite v1.
- **G10 AlphaPilot**: authors are Jiang P., Zhang F., Xu X., Chen T., Yang C.
- **G14 "LLMs as All-in-one Operators for GI"**: wrong authors. The real authors are Saemundsdottir G.B. and Haraldsson S.O. (GECCO '24 Companion, 727–730). The Brownlee/Callan/Even-Mendoza group wrote related but different papers.
- **G15 Signature Decomposition / pair trading**: the author list is incomplete and in the wrong order. The correct list is Guo Z., Jin H., Kuang J., Qian Z., Wang J., with DOI 10.1002/fut.70075.
- **G17 EDDIE-Automation**: the given DOI belongs to a different paper. The correct DOI is 10.1016/S0167-9236(03)00087-3, DSS 37(4):559–565.
- **C1/C2**: Gemini's author lists are wrong. The "other source" is right in both cases.

**IDs supplied**: G8 OpenReview lNmZrawUMu (ICLR 2026, no arXiv); G9 arXiv:2603.20247; G15 10.1002/fut.70075; G16 10.1109/CEC.2006.1688631.

**Minor notes**: C3 is confirmed, and the AAAI title adds "Alpha". G5's TMLR acceptance is confirmed, but its May 2026 date is not.
