# Your task: propose trading rules for a genetic program

A strongly typed genetic program evolves long-only daily trading rules, separately for each
market (equity indices, currency pairs, commodities). A rule is a pair of boolean trees, entry
and exit, built from typed nodes: data streams feed operators from seven fields of mathematics,
whose **Real** features are compared with each other or with adaptive thresholds and combined
with logic. The fields:

$domains

The genetic program has just been run on training data ($n_runs runs: $n_instruments markets,
$class_mix; $runs_per_instrument runs each). Your job this cycle: **propose up to $max_rules
entry/exit rule pairs.** They replace $max_rules of the $population random rules in the initial
population of every run in the next cycle. They may be new rules, variations of the evolved
rules below that should work better, or simplifications of them. The library itself is fixed:
you cannot change it.

## The nodes

Data streams and core (GP node names as they appear in the rules):

$core

The library's operators:

$library

Parameter values are nodes too, one per value of each kind:

$params

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
  half-year segments of the training data.
- **ms/call**: median computing time per call.
- **earlier**: usage / contribution in earlier cycles (most recent last).

The best evolved rules (one per run, top $n_elite by training fitness):

$elite

$last_outcome

## How to propose

Write `rules.json` in this folder: a JSON list of up to $max_rules objects
`{"entry": "<tree>", "exit": "<tree>", "note": "<optional, one line>"}`, each tree in the printed
form used above (node names, arguments in brackets, separated by commas). Trees must be
well-typed and boolean at the root, at most depth $max_depth and $max_nodes nodes, with a lookback
of at most $max_lookback bars. Use **check_rules** to see which pairs would be discarded and why;
fix them. The host keeps your proposals unless the next cycle's results get clearly worse on
held-out data. Proposing fewer pairs is a valid choice.

## Your tool

- **check_rules**: parses and type-checks `rules.json`. Up to $max_check_rules calls.

When you finish, reply with a short summary: what kinds of rules you proposed and why.
