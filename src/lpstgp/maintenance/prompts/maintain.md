# Your task: maintain a library of typed operators

You maintain a library of typed operators: building blocks of a strongly typed genetic program
that evolves long-only daily trading rules, separately for each market (equity indices, currency
pairs, commodities). A rule is a pair of boolean trees, entry and exit. Data streams feed the
library's operators, whose **Real** features are compared with each other or with adaptive
thresholds and combined with logic by a shared core. The library's operators come from seven
fields of mathematics:

$domains

The genetic program has just been run with the current library on training data
($n_runs runs: $n_instruments markets, $class_mix; $runs_per_instrument runs each). The evidence
below shows how the evolved rules used each operator. Your job this cycle: **$task**

$allowed

## The library

Each operator is a file in this folder, `<name>.py`, holding its current code. The shared data
streams and core (you cannot change them; your operators may take their outputs as inputs):

$core

The library's operators (GP node names in brackets, as they appear in the rules below):

$library

## Evidence from this cycle's runs (training data only)

$summary

$evidence

How to read it:

- **usage**: share of the runs' best rules (ten per run) whose entry or exit tree contains the
  operator.
- **survival**: mean share of generations in which the operator is in a run's best rule.
- **contribution**: mean drop in training fitness of the best rules that use the operator when
  the operator is replaced by a constant (its median): large = the rules rely on it; near 0 or
  negative = it adds little. `–` = no rule used it.
- **stability**: spread (interquartile range) of the contribution across markets and across
  half-year segments of the training data; large = it helps only in some markets or periods.
- **ms/call**: median computing time per call.
- **earlier**: usage / contribution in earlier cycles (most recent last).

The best evolved rules (one per run, top $n_elite by training fitness):

$elite

$last_outcome

## How to make changes

- **Grow**: write a new file, `<new_name>.py`, with one operator in the format of
  `operator_api.py` (read it first). Add a top-level line `DOMAIN = "<field>"` naming one of
  the seven fields above (the identifiers in backticks). The name must be new.$refine_prune
- Leave every other file unchanged. Use **check** on each new or changed file until it passes,
  **describe** to see how its output behaves and how it correlates with the library's other
  operators (above about 0.9 suggests redundancy), and **check_patch** to see how your changes
  will be read and whether they meet this cycle's bounds.
- The rules of `operator_api.py` apply: a scale-free **Real** output, exact lookback (at most
  $max_lookback bars), no look-ahead, numpy, scipy and math only, no randomness, files or
  network; `summary`, `definition` and `references` filled in.
- The host applies the patch only if every changed file passes check and the patch meets the
  bounds; then it reruns the genetic program with the patched library and keeps the patch
  unless the results get clearly worse on held-out data. Making no change is a valid choice.

## Your tools

- **check** (`file`): the admission checks on one operator file. Up to $max_checks calls.
- **describe** (`file`): descriptive statistics of one operator's output on separate
  development data (anonymised markets, no dates), with its rank correlation with the other
  operator files in the folder. Up to $max_describes calls.
- **check_patch**: how the host reads your changes. Up to $max_check_patch calls.

When you finish, reply with a short summary: what you changed and why, in a few sentences.
