# Your task: one trading strategy built on $domain_title

You are an expert quantitative researcher. Design **one** long-only, daily trading strategy whose
core idea comes from **$domain_title**: $domain_scope You may use any mathematics from this field,
including ideas not named here; the strategy must be a genuine application of the field, not a
conventional technical indicator under a new name.

The finished strategy will be applied, unchanged, to many markets with their own trading costs:
equity indices, currency pairs, commodities, government bonds and cryptocurrencies. Favour ideas
that are general and robust over ideas that fit one market or one episode.

$earlier

## What you write

Write the file `strategy.py` in this folder. Read `strategy_api.py` first: it defines the contract
(signals with parameters on fixed grids, and a rule that returns entry and exit conditions) and a
few optional helpers. In short:

- 1 to $max_signals signals. Each is a function of past `log_price`, `log_return` and/or
  `abs_return` that returns one float per bar (NaN while it cannot be computed yet). Tunable
  parameters must use the grid types in `strategy_api.py`; the defaults are your choice.
- A rule that turns the signals into `entry` and `exit` arrays with values 1, 0 or NaN. The
  harness holds a long position from an entry until an exit and is flat otherwise. A condition
  true at the close of bar t changes the position at the close of bar t+$lag_bars; the harness
  applies this delay and the trading costs. Do not shift the arrays and do not track positions
  yourself.
- Values at bar t may use only bars up to t, must not change when later data arrive, and may not
  depend on more than the declared lookback (at most $max_lookback bars in total). Use numpy,
  scipy and math only; no randomness, files or network.
- Fill in the metadata: `hypothesis`, `definition` (the mathematics, with formulas), `references`
  (real, verifiable sources), `novelty` and `limitations`.

## Your tools

You can read and write files in this folder, and you have two tools:

- **check**: runs the admission checks on a file (contract, source rules, determinism,
  no look-ahead, lookback, finite and non-degenerate output) and lists any problems. It reports no
  performance. Free, up to $max_checks calls.
- **backtest**: evaluates a file on the development data and returns, per instrument and in
  aggregate, the metrics below. You have **$budget backtests**; every call counts.

The development data are daily bars of $n_instruments instruments ($class_mix), each up to
$years years long, with their trading costs. Instruments are labelled I01, I02, …; dates are not
shown. You cannot see the prices themselves.

**Objective** (higher is better), computed per instrument over six-month segments:

- net Sharpe ratio per segment (0 for a segment with fewer than $min_exposure bars in the market);
- maximum drawdown per segment divided by the instrument's annualised volatility;
- annualised turnover per segment;
- F = median Sharpe − $lambda_dd × median(drawdown / volatility) − $lambda_to × median turnover;
  an instrument on which the strategy enters fewer than $min_entries times per year of data
  (including never) scores $no_trade there.

The objective is the median of F across instruments. The backtest also reports, per instrument,
Sharpe, drawdown, total return, trades and time in the market.

## How to work

1. Read `strategy_api.py`. Then explore: within your first 10 backtests, try at least 3
   genuinely different hypotheses from the field (different mathematical ideas, not parameter
   variations of one idea).
2. Refine the most promising idea: look at which instruments and segments fail and why, and
   change one thing at a time. Prefer simple rules and few signals; a small gain from added
   complexity is usually overfitting.
3. Stop when the backtest budget is used, or when 10 backtests in a row (after at least 20) have
   not improved the objective.
4. Make sure the final `strategy.py` passes **check**, and that its metadata describe the final
   version. It is evaluated later on other data, not on the development data.

When you finish, reply with a short summary: the strategy's name, its idea in two sentences, the
best objective you reached and the number of backtests you used.
