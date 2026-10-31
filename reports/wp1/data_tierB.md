# Data report — Tier B (stocks)

Generated 2026-10-31 00:07 UTC from code `c41f2dd`.

**Status: no data.** WP1 implements the selection rule and the loader interface only. The final source must be survivorship-free (point-in-time constituents and market caps, delisted names and delisting returns), e.g. WRDS/CRSP + Compustat Global, Refinitiv or Bloomberg; to be provided by the PI.

Files currently in `tierB/`: 0.

## Selection rule (fixed in advance)

- 25 largest securities per market by USD market capitalisation as of the last session before the selection date; primary listings of common equity; one share class per issuer (the largest); ties broken by security id; names delisted later stay selected.
- Mode `once` (selection at the sample start, 2005-07-01) or `per_period` (point-in-time re-selection at every fit start); both implemented, choice open for WP2.
- Markets (provisional country mapping): EUROPE: AT, BE, CH, DE, DK, ES, FI, FR, IE, IT, NL, NO, PT, SE; JAPAN_ASIA: HK, JP, KR, SG, TW; UK: GB; US: US.

Coverage, gaps and date ranges will be reported here once the vendor data are loaded.
