"""Non-binding candidate Participation universe for live acquisition proof only.

This is deliberately PROPOSED_NOT_APPROVED.  The names reflect the stable leading
NIFTY 50 heavyweights in the official NSE Indices factsheet and the largest sector
families relevant to the frozen 5DR Participation engine.  Resolution proves only
that Upstox can identify/fetch them; it does NOT activate this set or change 5DR.
"""
from __future__ import annotations

from experiments.data_contract import DataArchitectureError

STATUS = "PROPOSED_NOT_APPROVED"

# Stable leading names across recent official NIFTY 50 factsheet snapshots.  The
# exact set remains an explicit governance/configuration decision before activation.
HEAVYWEIGHT_SYMBOLS = (
    "HDFCBANK",
    "ICICIBANK",
    "RELIANCE",
    "BHARTIARTL",
    "LT",
    "SBIN",
    "INFY",
    "AXISBANK",
)

# Directly maps the largest broad sector families in the official NIFTY 50 factsheet.
SECTOR_INDEX_NAMES = (
    "Nifty Financial Services",
    "Nifty Oil & Gas",
    "Nifty IT",
    "Nifty Auto",
)


def _text(record, *fields):
    for field in fields:
        value = record.get(field)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def _equity_candidates(records, symbol):
    symbol_upper = symbol.upper()
    result = []
    for row in records:
        if not isinstance(row, dict):
            continue
        key = _text(row, "instrument_key")
        if not key.startswith("NSE_EQ|"):
            continue
        trading_symbol = _text(row, "trading_symbol", "tradingsymbol").upper()
        if trading_symbol == symbol_upper:
            result.append(row)
    return result


def _index_candidates(records, name):
    target = name.casefold()
    result = []
    for row in records:
        if not isinstance(row, dict):
            continue
        key = _text(row, "instrument_key")
        if not key.startswith("NSE_INDEX|"):
            continue
        values = {
            _text(row, "name").casefold(),
            _text(row, "trading_symbol", "tradingsymbol").casefold(),
            key.split("|", 1)[1].casefold() if "|" in key else "",
        }
        if target in values:
            result.append(row)
    return result


def _unique(rows, label):
    keys = {_text(row, "instrument_key") for row in rows if _text(row, "instrument_key")}
    if len(keys) != 1:
        raise DataArchitectureError(f"candidate identity not exact/unique: {label}")
    key = next(iter(keys))
    row = next(row for row in rows if _text(row, "instrument_key") == key)
    return {
        "instrument_key": key,
        "trading_symbol": _text(row, "trading_symbol", "tradingsymbol"),
        "name": _text(row, "name"),
        "segment": _text(row, "segment"),
    }


def resolve_candidate(records):
    if not isinstance(records, list) or not records:
        raise DataArchitectureError("NSE master records missing")
    heavyweights = {
        symbol: _unique(_equity_candidates(records, symbol), f"heavyweight:{symbol}")
        for symbol in HEAVYWEIGHT_SYMBOLS
    }
    sectors = {
        name: _unique(_index_candidates(records, name), f"sector:{name}")
        for name in SECTOR_INDEX_NAMES
    }
    keys = [row["instrument_key"] for row in heavyweights.values()] + [row["instrument_key"] for row in sectors.values()]
    if len(keys) != len(set(keys)):
        raise DataArchitectureError("candidate participation identities overlap")
    return {
        "status": STATUS,
        "heavyweights": heavyweights,
        "sectors": sectors,
        "instrument_keys": tuple(keys),
        "screening_enabled": False,
        "methodology_changed": False,
        "activation_enabled": False,
    }
