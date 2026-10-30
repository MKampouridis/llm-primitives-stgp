"""Pilot-only free data sources. ``fetch`` touches the network; ``parse`` is pure and offline."""

from lpstgp.data.sources import bitstamp, coinbase, ecb, eia, yahoo

SOURCES = {"yahoo": yahoo, "ecb": ecb, "eia": eia, "bitstamp": bitstamp, "coinbase": coinbase}

__all__ = ["SOURCES"]
