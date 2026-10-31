# Close-paper fact checks (2026-10-30)

## TASK 1: ALPHAS2, "Semantic-Symbolic Co-Evolution for Alpha Mining" (OpenReview QjycCr3zns)
STATUS: FULL TEXT NOT READ. NOT VERIFIED.
- api2.openreview.net/notes?id=QjycCr3zns -> HTTP 403 ChallengeRequiredError (bot check).
- api.openreview.net/notes?id=QjycCr3zns -> same 403 challenge.
- openreview.net/pdf?id=QjycCr3zns -> 403 HTML challenge page, no PDF.
- openreview.net/forum via the user's Chrome (Claude in Chrome) -> redirected to the "Verifying your browser" page. I did not attempt the check (bot-checks are off-limits to me).
- arXiv API title search ("Semantic Symbolic Co-Evolution") -> 0 hits. Three web searches (exact title, "ALPHAS2", the forum ID) -> no public preprint, no indexed abstract.
- So I cannot confirm questions (a)-(h). Its existence, venue, date and mechanism remain claims from the earlier (Gemini) survey and have no independent support.
- How to unblock: the user signs in to OpenReview or passes the check in their own browser, then saves the PDF locally. Alternatively, an OpenReview API call with a logged-in token.
- Nearby verified papers that turned up in search: QuantaAlpha (arXiv 2602.07085; semantic description -> symbolic expression -> code, with trajectory mutation and crossover), AlphaSchema (2607.26642), and LLM-assisted semantic pruning of GP alpha trees (Applied Sciences 2026, doi 10.3390/app16126231).

## TASK 2
### AlgoEvolve (arXiv 2606.26173v1, 24 Jun 2026; Dhruv Sharma & Gautam Shroff, IIIT Delhi)
- CONFIRMED. The paper has a Sec. 6.1 phase called the "Zero-Trade" Stagnation Trap (Gens 5-12) in its inner-loop baseline. Over 8 generations, with a static evolver prompt, the LLM kept adding conservative filters and making small threshold tweaks ("syntactic over-smoothing"). The programs never fired a single trade on the validation assets, so terminal return was 0.0%.
- The paper names this state "Alpha Silence": the given instructions can no longer produce executable logic that trades.
- Remedy: the meta-evolutionary outer loop evolves the prompt. In MG4 the evolved focus gene told the LLM to propose structurally diverse archetypes to escape the zero-trade stagnation, and a recovery followed.
- The abstract describes this as reducing zero-trade failures.

### CogAlpha (arXiv 2511.18850, v4 11 Jul 2026; Liu et al.; ACL 2026 long, 2026.acl-long.538)
- CONFIRMED for nested loops. Partly confirmed for vectorisation.
- The Judge Agent prompt (App. C.2, "Multi-Agent Quality Checker - Judger") has a checklist:
  - item 5 asks whether the code avoids unnecessary loops and uses vectorised operations;
  - item 6 asks whether it strictly avoids nested or potentially infinite loops, and states nested loops are forbidden at any depth (for-in-for, while-in-while, and mixes).
- The generation and repair prompts also say nested loops are "absolutely forbidden", ban while True, and ask the LLM to *prefer* vectorised pandas/numpy.
- Vectorisation is therefore a strong preference and a judge criterion, not a hard rule. Single loops are not banned.
- Other quality-checker agents: Code Quality, Code Repair, Logic Improvement, plus an execution/numerical-stability check and a temporal-leakage unit test.

### "Mutation Without Variation" (arXiv 2606.05408v1, 3 Jun 2026)
- Authors: Can Gurkan (Northwestern), Forrest Stonedahl (Augustana College), Uri Wilensky (Northwestern).
- Venue: GECCO '26 Workshop on LLMs for and with Evolutionary Computation.
- Setup: neutral LLM mutation chains with no selection, 300 accepted mutations each, in a DSL (NetLogo-style agent programs, per the lmca repo). Default model Gemini 3.1 Flash Lite, temp 1. Prompts, models and replicates were varied.
- Finding: LLM mutation converges to small attractor regions. In 87% of chains, more than 93% of mutations revisit an already-seen structural skeleton. Most variation is terminal substitution inside recurring templates, and short cycles and self-loops dominate.
- The median LLM chain sees about 10 unique skeletons in 300 steps.
- Baseline: classical GP subtree mutation (random node replaced by a random subtree, max depth 4) shows no comparable convergence and far higher unique program and skeleton counts.
- Only the least convergent prompts (over 250 unique programs) approach GP.
- The authors conclude the bias is intrinsic to LLM mutation, and that prompt wording and model choice change its rate.

## TASK 3
### EFE, Evolutionary Feature Engineering for Structured Data (arXiv 2607.01548, Jul 2026; Taga ... Oymak; U. Michigan & Google Research)
- An LLM evolves Python fit/transform programs. Each is inserted in front of a FIXED downstream model and scored on validation.
- EFE-Time evolves invertible per-dataset normalisations for time-series foundation models (Chronos-2 and others) on GIFT-Eval. Some of those datasets are finance or business series.
- EFE-Tab evolves compact feature sets for tabular models, especially decision trees.
- The evolved programs are not used as GP primitives. There is no GP and no trading application.

### LLM-FE (arXiv 2503.14434 v3, May 2026; Abhyankar, Shojaee, Reddy; Virginia Tech; reviewed on OpenReview qvI35hkpOO)
- LLM-driven evolutionary search (multi-island, with an experience buffer) over feature-transformation programs for tabular data.
- Features are consumed by fixed predictors (XGBoost by default, also MLP and TabPFN), and fitness is that predictor's validation score.
- Baselines are classical FE tools (OpenFE, AutoFeat) and LLM FE methods (CAAFE, FeatLLM, OCTree).
- No GP over the evolved features as primitives. No finance or trading application.
