# Your task: four typed operators from $domain_title

You are an expert in **$domain_title** and in quantitative finance. Write **four** operators that
bring ideas from $domain_title to the analysis of daily financial price series. The field
covers $domain_scope You may use any mathematics from this field. Each operator must be a
genuine application of the field, not a conventional technical indicator under a new name, and the four
must rest on clearly different mathematical ideas.

## What the operators are for

Your operators become building blocks of a strongly typed genetic program that evolves long-only
daily trading rules, separately for each market: equity indices, currency pairs, commodities,
government bonds and cryptocurrencies, over two decades. A rule is a pair of boolean trees, entry
and exit. The program composes typed operators: data streams feed operators like yours, whose
**Real** features are then compared with each other or with adaptive thresholds, and combined
with logic. You do not write rules; you write features that the evolution can use. Features that
are general, robust and informative about the state of a market are the most useful; features
that are noisy, almost constant or redundant with one another are not.

The genetic program already has these data streams and this shared core (you may take their
outputs as inputs):

$core

$earlier

## What you write

Write four files in this folder, one operator each, named after the operator (for example
`my_operator.py`). Each file defines `OPERATOR = Operator(...)`. Read `operator_api.py` first: it
defines the semantic types, the parameter kinds and the contract, and lists the rules the checks
enforce. In short:

- Inputs are typed per-bar arrays (Series, Path, Hist, Real, Bool, Regime); the output is a
  **Real** per-bar feature that is scale-free.
- Parameters take values from fixed grids. Use the standard kinds (Window, LongWindow, Lag,
  Quantile, KSigma) where they fit; declare a new kind with `param_kind` only when needed.$kinds
- `lookback(**params)` must be exact (the output at bar t depends only on bars t-L+1 .. t,
  L <= $max_lookback). No look-ahead; appending bars never changes earlier outputs.
- Use numpy, scipy and math only; no randomness, files or network.
- Fill in `summary`, `definition` (the mathematics, with formulas) and `references` (real,
  verifiable sources).

## Your tools

You can read and write files in this folder, and you have two tools:

- **check** (`file`): runs the admission checks on one operator file and lists any problems.
  Up to $max_checks calls in total.
- **describe** (`file`): descriptive statistics of one operator's output on development data
  ($n_instruments instruments: $class_mix; daily bars, labelled I01, I02, …, no dates): finite
  share, quantiles, lag-1 autocorrelation, share of distinct values, and rank correlation with
  your other operator files. Up to $max_describes calls in total.

Neither tool reports trading performance, and none is available: choose operators for their
mathematical merit and the information they carry, not for a backtest.

## How to work

1. Read `operator_api.py`. Choose four distinct ideas from $domain_title.
2. Write each operator, run **check** until it passes, and use **describe** to see whether its
   output behaves as intended: not degenerate, not dominated by warm-up or missing values, and
   not a near-copy of another of your operators (a rank correlation above about 0.9 suggests
   redundancy).
3. Prefer simple, well-defined mathematics with few parameters.
4. Make sure all four files pass **check** and that their metadata describe the final versions.
   Leave no other `.py` files in the folder.

When you finish, reply with a short summary: each operator's name, signature and idea in one
sentence.
