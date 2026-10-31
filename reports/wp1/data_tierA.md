# Data report — Tier A (cross-asset pilot)

Generated 2026-10-31 00:07 UTC from code `c41f2dd`. Counts only: no prices, return statistics or performance are shown for any date.

## Summary

- Instruments with data: 31 of 31 (bond 2, commodity 6, crypto 5, equity_index 10, fx 8).
- Raw series: 55 (latest downloads on 2026-10-30), 38.8 MB raw.
- Walk-forward periods: 18 (P01 fit 2005-07-01 … P18 test end 2026-07-01, exclusive). Eligibility needs 504 valid bars before the fit start and ≥ 95% of expected sessions in [fit start, test end).
- Eligible (instrument, period) pairs: **496**.

Eligible instruments per period:

| P01 | P02 | P03 | P04 | P05 | P06 | P07 | P08 | P09 | P10 | P11 | P12 | P13 | P14 | P15 | P16 | P17 | P18 |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 25 | 26 | 26 | 26 | 26 | 26 | 26 | 26 | 27 | 27 | 27 | 27 | 27 | 30 | 31 | 31 | 31 | 31 |

## Primary series

Coverage, missing and longest gap are against the instrument's expected sessions (exchange calendar, weekdays for ECB fixings, all days for crypto) between its first and last valid bar. *Invalid* = bars with a missing or non-positive close. *Jump flags* = |log return| > 8 trailing robust sds (63 bars).

| Instrument | Class | Source | Close-only | First | Last | Bars | Coverage | Missing | Longest gap | Invalid | OHLC viol. | Stale runs | Jump flags | Volume share | Eligible periods |
|---|---|---|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| SPX | equity_index | yahoo:^GSPC | no | 1990-01-02 | 2026-06-30 | 9190 | 100.0% | 0 | 0 | 0 | 0 | 0 | 9 | 100% | P01–P18 (18) |
| NDX | equity_index | yahoo:^NDX | no | 1990-01-02 | 2026-06-30 | 9190 | 100.0% | 0 | 0 | 0 | 0 | 0 | 6 | 100% | P01–P18 (18) |
| SMI | equity_index | yahoo:^SSMI | no | 1990-11-09 | 2026-06-30 | 8946 | 99.8% | 19 | 1 | 0 | 0 | 0 | 8 | 66% | P01–P18 (18) |
| DAX | equity_index | yahoo:^GDAXI | no | 1990-01-02 | 2026-06-30 | 9232 | 99.5% | 44 | 1 | 0 | 0 | 0 | 4 | 73% | P01–P18 (18) |
| CAC | equity_index | yahoo:^FCHI | no | 1990-03-01 | 2026-06-30 | 9226 | 99.4% | 56 | 2 | 0 | 0 | 0 | 5 | 59% | P01–P18 (18) |
| UKX | equity_index | yahoo:^FTSE | no | 1990-01-02 | 2026-06-30 | 9217 | 99.9% | 5 | 1 | 0 | 0 | 0 | 5 | 75% | P01–P18 (18) |
| NKY | equity_index | yahoo:^N225 | no | 1990-01-04 | 2026-06-30 | 8954 | 98.9% | 99 | 4 | 0 | 0 | 0 | 7 | 66% | P01–P18 (18) |
| HSI | equity_index | yahoo:^HSI | no | 1990-01-02 | 2026-06-30 | 9004 | 99.9% | 6 | 1 | 0 | 0 | 0 | 5 | 68% | P01–P18 (18) |
| KOSPI | equity_index | yahoo:^KS11 | no | 1996-12-11 | 2026-06-30 | 7273 | 99.9% | 8 | 1 | 0 | 0 | 0 | 3 | 100% | P01–P18 (18) |
| AS51 | equity_index | yahoo:^AXJO | no | 1992-11-23 | 2026-06-30 | 8493 | 99.8% | 14 | 1 | 0 | 0 | 0 | 7 | 27% | P01–P18 (18) |
| EURUSD | fx | ecb:USD | yes | 1999-01-04 | 2026-06-30 | 7038 | 98.1% | 134 | 2 | 0 | 0 | 0 | 1 | 0% | P01–P18 (18) |
| GBPUSD | fx | ecb:USD/GBP | yes | 1999-01-04 | 2026-06-30 | 7038 | 98.1% | 134 | 2 | 0 | 0 | 0 | 1 | 0% | P01–P18 (18) |
| USDJPY | fx | ecb:JPY/USD | yes | 1999-01-04 | 2026-06-30 | 7038 | 98.1% | 134 | 2 | 0 | 0 | 0 | 9 | 0% | P01–P18 (18) |
| AUDUSD | fx | ecb:USD/AUD | yes | 1999-01-04 | 2026-06-30 | 7038 | 98.1% | 134 | 2 | 0 | 0 | 0 | 2 | 0% | P01–P18 (18) |
| USDCAD | fx | ecb:CAD/USD | yes | 1999-01-04 | 2026-06-30 | 7038 | 98.1% | 134 | 2 | 0 | 0 | 0 | 0 | 0% | P01–P18 (18) |
| USDCHF | fx | ecb:CHF/USD | yes | 1999-01-04 | 2026-06-30 | 7038 | 98.1% | 134 | 2 | 0 | 0 | 0 | 4 | 0% | P01–P18 (18) |
| NZDUSD | fx | ecb:USD/NZD | yes | 1999-01-04 | 2026-06-30 | 7038 | 98.1% | 134 | 2 | 0 | 0 | 0 | 1 | 0% | P01–P18 (18) |
| EURGBP | fx | ecb:GBP | yes | 1999-01-04 | 2026-06-30 | 7038 | 98.1% | 134 | 2 | 0 | 0 | 0 | 2 | 0% | P01–P18 (18) |
| WTI | commodity | eia:RWTC | yes | 1986-01-02 | 2026-06-30 | 9448 | 92.3% | 782 | 8 | 1 | 0 | 0 | 15 | 0% | P02–P18 (17) |
| BRENT | commodity | eia:RBRTE | yes | 1987-05-20 | 2026-06-30 | 9033 | 90.4% | 946 | 8 | 0 | 0 | 0 | 9 | 0% | P01–P18 (18) |
| NATGAS | commodity | eia:RNGWHHD | yes | 1997-01-07 | 2026-06-30 | 7402 | 99.4% | 44 | 10 | 0 | 0 | 2 | 31 | 0% | P01–P18 (18) |
| GOLD | commodity | yahoo:GC=F | no | 2000-08-30 | 2026-06-30 | 6482 | 97.3% | 181 | 3 | 0 | 441 | 0 | 7 | 94% | P01–P18 (18) |
| SILVER | commodity | yahoo:SI=F | no | 2000-08-30 | 2026-06-30 | 6483 | 97.3% | 180 | 2 | 0 | 243 | 0 | 8 | 89% | P01–P18 (18) |
| COPPER | commodity | yahoo:HG=F | no | 2000-08-30 | 2026-06-30 | 6486 | 97.3% | 179 | 2 | 0 | 300 | 0 | 3 | 99% | P01–P18 (18) |
| US10Y | bond | yahoo:IEF | no | 2002-07-30 | 2026-06-30 | 6018 | 100.0% | 0 | 0 | 0 | 0 | 0 | 0 | 100% | P01–P18 (18) |
| US20Y | bond | yahoo:TLT | no | 2002-07-30 | 2026-06-30 | 6018 | 100.0% | 0 | 0 | 0 | 0 | 0 | 0 | 100% | P01–P18 (18) |
| BTC | crypto | bitstamp:btcusd | no | 2011-08-18 | 2026-06-30 | 5431 | 100.0% | 0 | 0 | 0 | 0 | 3 | 37 | 99% | P09–P18 (10) |
| ETH | crypto | coinbase:ETH-USD | no | 2016-05-18 | 2026-06-30 | 3694 | 99.9% | 2 | 2 | 0 | 0 | 0 | 12 | 100% | P14–P18 (5) |
| LTC | crypto | coinbase:LTC-USD | no | 2016-08-17 | 2026-06-30 | 3604 | 100.0% | 1 | 1 | 0 | 0 | 0 | 14 | 100% | P14–P18 (5) |
| XRP | crypto | bitstamp:xrpusd | no | 2016-12-16 | 2026-06-30 | 3484 | 100.0% | 0 | 0 | 0 | 0 | 2 | 28 | 99% | P14–P18 (5) |
| BCH | crypto | bitstamp:bchusd | no | 2017-12-04 | 2026-06-30 | 3131 | 100.0% | 0 | 0 | 0 | 0 | 0 | 12 | 100% | P15–P18 (4) |

## Alternate series (comparison only, not used by default)

| Instrument | Class | Source | Close-only | First | Last | Bars | Coverage | Missing | Longest gap | Invalid | OHLC viol. | Stale runs | Jump flags | Volume share | Eligible periods |
|---|---|---|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| SMI | equity_index | yahoo:^STOXX50E | no | 2007-03-30 | 2026-06-30 | 4823 | 99.7% | 14 | 2 | 0 | 0 | 0 | 5 | 67% | P05–P18 (14) |
| EURUSD | fx | yahoo:EURUSD=X | no | 2003-12-01 | 2026-06-30 | 5858 | 99.4% | 34 | 11 | 0 | 127 | 0 | 10 | 0% | P02–P18 (17) |
| GBPUSD | fx | yahoo:GBPUSD=X | no | 2003-12-01 | 2026-06-30 | 5870 | 99.6% | 22 | 3 | 0 | 102 | 0 | 1 | 0% | P02–P18 (17) |
| USDJPY | fx | yahoo:JPY=X | no | 1996-10-30 | 2026-06-30 | 7692 | 99.4% | 48 | 11 | 0 | 272 | 0 | 8 | 0% | P01–P18 (18) |
| AUDUSD | fx | yahoo:AUDUSD=X | no | 2006-05-16 | 2026-06-30 | 5234 | 99.7% | 17 | 2 | 0 | 142 | 0 | 4 | 0% | P04–P18 (15) |
| USDCAD | fx | yahoo:CAD=X | no | 2003-09-17 | 2026-06-30 | 5926 | 99.7% | 19 | 2 | 0 | 113 | 0 | 1 | 0% | P02–P18 (17) |
| USDCHF | fx | yahoo:CHF=X | no | 2003-09-17 | 2026-06-30 | 5924 | 99.6% | 21 | 2 | 0 | 100 | 0 | 5 | 0% | P02–P18 (17) |
| NZDUSD | fx | yahoo:NZDUSD=X | no | 2003-12-01 | 2026-06-30 | 5859 | 99.4% | 33 | 3 | 0 | 363 | 0 | 0 | 0% | P02–P18 (17) |
| EURGBP | fx | yahoo:EURGBP=X | no | 1999-01-04 | 2026-06-30 | 7158 | 99.8% | 14 | 2 | 0 | 68 | 0 | 4 | 0% | P01–P18 (18) |
| WTI | commodity | yahoo:CL=F | no | 2000-08-23 | 2026-06-30 | 6489 | 99.8% | 16 | 1 | 1 | 7 | 0 | 7 | 100% | P01–P18 (18) |
| WTI | commodity | yahoo:USO | no | 2006-04-10 | 2026-06-30 | 5087 | 100.0% | 0 | 0 | 0 | 0 | 0 | 3 | 100% | P04–P18 (15) |
| BRENT | commodity | yahoo:BNO | no | 2010-06-02 | 2026-06-30 | 4044 | 97.7% | 93 | 2 | 0 | 0 | 1 | 3 | 99% | P08–P18 (11) |
| BRENT | commodity | yahoo:BZ=F | no | 2007-07-30 | 2026-06-30 | 4708 | 96.7% | 159 | 12 | 0 | 69 | 0 | 5 | 100% | P07–P18 (12) |
| NATGAS | commodity | yahoo:NG=F | no | 2000-08-30 | 2026-06-30 | 6487 | 99.8% | 15 | 1 | 0 | 32 | 0 | 3 | 100% | P01–P18 (18) |
| NATGAS | commodity | yahoo:UNG | no | 2007-04-18 | 2026-06-30 | 4831 | 100.0% | 0 | 0 | 0 | 0 | 0 | 2 | 100% | P05–P18 (14) |
| GOLD | commodity | yahoo:GLD | no | 2004-11-18 | 2026-06-30 | 5436 | 97.5% | 137 | 2 | 0 | 0 | 0 | 4 | 100% | P03–P18 (16) |
| SILVER | commodity | yahoo:SLV | no | 2006-04-28 | 2026-06-30 | 5074 | 97.5% | 128 | 2 | 0 | 0 | 0 | 4 | 100% | P04–P18 (15) |
| COPPER | commodity | yahoo:CPER | no | 2011-11-15 | 2026-06-30 | 3675 | 97.5% | 95 | 2 | 0 | 0 | 12 | 28 | 91% | P10–P18 (9) |
| US10Y | bond | yahoo:ZN=F | no | 2000-09-21 | 2026-06-30 | 6471 | 99.7% | 18 | 7 | 0 | 20 | 0 | 1 | 100% | P01–P18 (18) |
| US20Y | bond | yahoo:ZB=F | no | 2000-09-21 | 2026-06-30 | 6477 | 99.8% | 12 | 1 | 0 | 10 | 0 | 1 | 100% | P01–P18 (18) |
| BTC | crypto | coinbase:BTC-USD | no | 2015-07-20 | 2026-06-30 | 3999 | 100.0% | 0 | 0 | 0 | 0 | 0 | 23 | 100% | P13–P18 (6) |
| ETH | crypto | bitstamp:ethusd | no | 2017-08-16 | 2026-06-30 | 3241 | 100.0% | 0 | 0 | 0 | 0 | 0 | 5 | 100% | P15–P18 (4) |
| LTC | crypto | bitstamp:ltcusd | no | 2017-06-16 | 2026-06-30 | 3302 | 100.0% | 0 | 0 | 0 | 0 | 0 | 7 | 100% | P15–P18 (4) |
| XRP | crypto | coinbase:XRP-USD | no | 2019-02-26 | 2026-06-30 | 1778 | 66.3% | 904 | 904 | 0 | 0 | 0 | 8 | 100% | none |
| BCH | crypto | coinbase:BCH-USD | no | 2017-12-20 | 2026-06-30 | 3111 | 99.9% | 4 | 4 | 0 | 0 | 0 | 11 | 100% | P15–P18 (4) |

## Known issues of the pilot sources (pilot only; see docs/decisions.md)

- **Yahoo Finance (yfinance):** indices are price indices, not total return. Raw OHLC are split-adjusted
  by the vendor (multiplicative). Daily timestamps are exchange-local. Data are "for personal use"
  under Yahoo's terms and are never redistributed. Rate limits per IP; occasional duplicated last rows.
  Continuous futures (`=F`) are unadjusted front-month splices: roll days carry the contract spread as a
  spurious return (see the jump-flag counts of the futures alternates vs the roll-free primaries).
- **ECB reference rates:** a daily fixing at 14:15 CET on TARGET business days, not a market close;
  USD crosses are ratios of two EUR rates on the same date. Close only.
- **EIA spot prices:** official assessments, close only, U.S. federal holiday calendar; the files are
  not range-limited (later rows are dropped at build). WTI printed a negative price on 2020-04-20,
  which the schema marks invalid. The WTI history has real gaps (about 113 missing sessions in
  2003, 67 in 2004, 48 in 2005, 25 in 2006 and 40 in 2011), which makes WTI ineligible for P01.
- **Bitstamp / Coinbase:** exchange-specific prices (not composite), UTC days, native 7-day calendar;
  exchange outages appear as gaps. Coinbase XRP has a trading suspension (2021–2023).
- **Close times differ across markets** (Asia, Europe, US, crypto at 00:00 UTC): irrelevant for
  per-asset rules, relevant for the portfolio layer (WP4).
