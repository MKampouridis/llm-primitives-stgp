"""Tier B (stocks): survivorship-free selection rule and the loader interface.

No data are downloaded in WP1. The final source must be survivorship-free (point-in-time
constituents and market caps, delisted names and delisting returns), e.g. WRDS/CRSP (+ Compustat
Global), Refinitiv or Bloomberg; credentials are read from the environment only.

Selection rule (fixed in advance): at each selection date, per market, the ``per_market`` largest
eligible securities by USD market capitalisation *as of the last session before the selection
date*; primary listings of common equity only; one share class per issuer (the largest);
deterministic tie-break on security id. Securities delisted later stay selected (their data end at
delisting). ``mode = "once"`` selects at the sample start only; ``"per_period"`` re-applies the
rule point-in-time at every period's fit start.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date
from typing import Literal, Protocol

import pandas as pd

from lpstgp.splits import Period

MARKETS = ("US", "EUROPE", "UK", "JAPAN_ASIA")

# Provisional country -> market mapping (open question for WP2: composition of "Japan/Asia").
DEFAULT_COUNTRY_MARKET = {
    "US": "US",
    "GB": "UK",
    **{
        c: "EUROPE"
        for c in (
            "AT",
            "BE",
            "CH",
            "DE",
            "DK",
            "ES",
            "FI",
            "FR",
            "IE",
            "IT",
            "NL",
            "NO",
            "PT",
            "SE",
        )
    },
    **{c: "JAPAN_ASIA" for c in ("JP", "HK", "KR", "SG", "TW")},
}


@dataclass(frozen=True)
class SecurityRecord:
    """One security in a point-in-time universe snapshot."""

    security_id: str
    issuer_id: str
    name: str
    country: str
    market_cap_usd: float  # as of the snapshot date
    primary_listing: bool
    common_equity: bool
    listed: date
    delisted: date | None = None  # may lie after the snapshot date: the name is still selectable


@dataclass(frozen=True)
class Delisting:
    security_id: str
    date: date
    reason: str
    delisting_return: float | None  # e.g. CRSP DLRET; None if the vendor has none


class TierBSource(Protocol):
    """What a survivorship-free vendor adapter must provide."""

    def snapshot(self, as_of: date) -> Sequence[SecurityRecord]:
        """All securities alive on ``as_of`` with market caps known on that date (no hindsight)."""
        ...

    def bars(self, security_id: str, start: date, horizon: date) -> pd.DataFrame:
        """Raw prices + events in schema v1 for ``start <= date < horizon``."""
        ...

    def delisting(self, security_id: str) -> Delisting | None: ...


@dataclass(frozen=True)
class SelectionRule:
    per_market: int = 25
    markets: tuple[str, ...] = MARKETS
    country_market: Mapping[str, str] = field(default_factory=lambda: dict(DEFAULT_COUNTRY_MARKET))
    mode: Literal["once", "per_period"] = "once"

    def selection_dates(self, periods: Sequence[Period]) -> list[date]:
        starts = sorted({p.fit_start for p in periods})
        return starts[:1] if self.mode == "once" else starts

    def select(self, universe: Sequence[SecurityRecord], as_of: date) -> dict[str, list[str]]:
        """Apply the rule to a point-in-time snapshot; returns market -> security ids (largest first)."""
        candidates = [
            s
            for s in universe
            if s.primary_listing
            and s.common_equity
            and s.listed <= as_of
            and (s.delisted is None or s.delisted > as_of)
            and s.market_cap_usd == s.market_cap_usd  # not NaN
            and s.market_cap_usd > 0
            and self.country_market.get(s.country) in self.markets
        ]
        largest_class: dict[str, SecurityRecord] = {}
        for s in sorted(candidates, key=lambda s: (-s.market_cap_usd, s.security_id)):
            largest_class.setdefault(s.issuer_id, s)
        selected: dict[str, list[str]] = {m: [] for m in self.markets}
        for s in sorted(largest_class.values(), key=lambda s: (-s.market_cap_usd, s.security_id)):
            market = self.country_market[s.country]
            if len(selected[market]) < self.per_market:
                selected[market].append(s.security_id)
        return selected

    def run(
        self, source: TierBSource, periods: Sequence[Period]
    ) -> dict[date, dict[str, list[str]]]:
        """Selections keyed by selection date; snapshots are taken as of each date (point in time)."""
        return {d: self.select(source.snapshot(d), d) for d in self.selection_dates(periods)}


class InMemoryTierBSource:
    """Test double: snapshots, bars and delistings supplied in memory."""

    def __init__(
        self,
        snapshots: Mapping[date, Sequence[SecurityRecord]],
        bars: Mapping[str, pd.DataFrame] | None = None,
        delistings: Mapping[str, Delisting] | None = None,
    ) -> None:
        self._snapshots = dict(snapshots)
        self._bars = dict(bars or {})
        self._delistings = dict(delistings or {})

    def snapshot(self, as_of: date) -> Sequence[SecurityRecord]:
        known = [d for d in self._snapshots if d <= as_of]
        if not known:
            return []
        return self._snapshots[max(known)]

    def bars(self, security_id: str, start: date, horizon: date) -> pd.DataFrame:
        frame = self._bars[security_id]
        dates = pd.to_datetime(frame["date"])
        return frame[(dates >= pd.Timestamp(start)) & (dates < pd.Timestamp(horizon))].reset_index(
            drop=True
        )

    def delisting(self, security_id: str) -> Delisting | None:
        return self._delistings.get(security_id)


class _VendorStub:
    vendor = "unspecified"
    env_vars: tuple[str, ...] = ()

    def _missing(self) -> NotImplementedError:
        return NotImplementedError(
            f"{self.vendor} adapter not implemented in WP1; credentials will come from {self.env_vars}"
        )

    def snapshot(self, as_of: date) -> Sequence[SecurityRecord]:
        raise self._missing()

    def bars(self, security_id: str, start: date, horizon: date) -> pd.DataFrame:
        raise self._missing()

    def delisting(self, security_id: str) -> Delisting | None:
        raise self._missing()


class WRDSSource(_VendorStub):
    vendor = "WRDS (CRSP + Compustat Global)"
    env_vars = ("WRDS_USERNAME", "PGPASSFILE")


class RefinitivSource(_VendorStub):
    vendor = "Refinitiv / LSEG"
    env_vars = ("REFINITIV_APP_KEY",)


class BloombergSource(_VendorStub):
    vendor = "Bloomberg"
    env_vars = ("BLOOMBERG_HOST",)
