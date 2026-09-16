"""Safe public-catalog diagnostic for the proposed Participation candidate.

No authenticated API is called. Output is restricted to the fixed candidate labels and
public NSE master identity fields so provider naming can be aligned without weakening
exact/unique resolution.
"""
import json
import re

from experiments.participation_candidate import HEAVYWEIGHT_SYMBOLS, SECTOR_INDEX_NAMES
from experiments.upstox_catalog import PublicInstrumentCatalog


def _text(row, *fields):
    for field in fields:
        value = row.get(field)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def _norm(value):
    return re.sub(r"[^a-z0-9]+", " ", value.casefold()).strip()


def run():
    envelope = PublicInstrumentCatalog().nse_instruments()
    records = envelope["records"]
    equities = {}
    for symbol in HEAVYWEIGHT_SYMBOLS:
        matches = []
        for row in records:
            if not isinstance(row, dict):
                continue
            key = _text(row, "instrument_key")
            if not key.startswith("NSE_EQ|"):
                continue
            ts = _text(row, "trading_symbol", "tradingsymbol")
            if ts.casefold() == symbol.casefold():
                matches.append({
                    "instrument_key": key,
                    "trading_symbol": ts,
                    "name": _text(row, "name"),
                    "segment": _text(row, "segment"),
                })
        equities[symbol] = matches[:5]

    sectors = {}
    for desired in SECTOR_INDEX_NAMES:
        desired_tokens = set(_norm(desired).split()) - {"nifty", "services", "and"}
        candidates = []
        for row in records:
            if not isinstance(row, dict):
                continue
            key = _text(row, "instrument_key")
            if not key.startswith("NSE_INDEX|"):
                continue
            ts = _text(row, "trading_symbol", "tradingsymbol")
            name = _text(row, "name")
            key_name = key.split("|", 1)[1] if "|" in key else ""
            combined = _norm(" ".join((ts, name, key_name)))
            tokens = set(combined.split())
            if desired_tokens and desired_tokens.issubset(tokens):
                candidates.append({
                    "instrument_key": key,
                    "trading_symbol": ts,
                    "name": name,
                    "segment": _text(row, "segment"),
                })
        sectors[desired] = candidates[:10]

    return {
        "status": "PARTICIPATION_CATALOG_DIAGNOSTIC_COMPLETE",
        "master_sha256": envelope["sha256"],
        "equities": equities,
        "sectors": sectors,
        "authenticated_api_called": False,
        "activation_enabled": False,
        "screening_enabled": False,
        "methodology_changed": False,
    }


if __name__ == "__main__":
    print(json.dumps(run(), sort_keys=True, separators=(",", ":")))
