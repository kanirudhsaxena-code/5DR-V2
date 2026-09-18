"""Exact instrument and provider-latency resolution for the 5DR Upstox experiment.

Pure validation only. No network, orders, portfolio/account access, forecasting or writes.
"""
from datetime import date, datetime, timezone

from phase1.upstox import NIFTY, PipelineError

GLOBAL_LATENCY = {
    "20 Seconds": ("DELAYED_20S", 20),
    "120 Seconds": ("DELAYED_120S", 120),
    "900 Seconds": ("DELAYED_15M", 900),
}

GLOBAL_TARGET_NAMES = {
    "gift_nifty": ("GIFT NIFTY",),
    "sp500": ("S&P 500", "S&P"),
    "dow_jones": ("DOW JONES",),
    "us_tech_100": ("US Tech 100",),
    "nikkei_225": ("NIKKEI 225",),
    "hang_seng": ("HANG SENG",),
    "dax": ("DAX",),
    "ftse_100": ("FTSE 100",),
    "brent": ("Oil (Brent)",),
    "wti": ("Oil (WTI)",),
    "usd_inr": ("USD INR",),
}


def parse_global_latency(value):
    if value not in GLOBAL_LATENCY:
        raise PipelineError("Global provider latency missing or unsupported")
    label, seconds = GLOBAL_LATENCY[value]
    return {"declared": value, "classification": label, "seconds": seconds}


def _global_identity(row):
    if not isinstance(row, dict):
        raise PipelineError("Global instrument row invalid")
    if row.get("exchange") != "GLOBAL":
        raise PipelineError("Global instrument exchange mismatch")
    if row.get("segment") not in {"GLOBAL_INDEX", "GLOBAL_INDICATOR"}:
        raise PipelineError("Global instrument segment mismatch")
    key = row.get("instrument_key")
    name = row.get("name")
    symbol = row.get("trading_symbol")
    if not all(isinstance(value, str) and value for value in (key, name, symbol)):
        raise PipelineError("Global instrument identity missing")
    latency = parse_global_latency(row.get("latency"))
    return {
        "name": name,
        "exchange": "GLOBAL",
        "segment": row["segment"],
        "instrument_key": key,
        "trading_symbol": symbol,
        "country": row.get("country") if isinstance(row.get("country"), str) else "",
        "provider_latency": latency,
        "start_time": row.get("start_time"),
        "end_time": row.get("end_time"),
        "week_days": row.get("week_days"),
    }


def resolve_global_instruments(rows, target_ids=None):
    if not isinstance(rows, list) or not rows:
        raise PipelineError("Global instrument master missing")
    targets = tuple(target_ids or GLOBAL_TARGET_NAMES)
    if not targets or any(target not in GLOBAL_TARGET_NAMES for target in targets):
        raise PipelineError("Unknown global target")
    result = {}
    for target in targets:
        allowed_names = set(GLOBAL_TARGET_NAMES[target])
        matches = []
        for row in rows:
            if isinstance(row, dict) and row.get("name") in allowed_names:
                matches.append(row)
        if len(matches) != 1:
            raise PipelineError(f"Global instrument identity ambiguous or missing: {target}")
        result[target] = _global_identity(matches[0])
    keys = [entry["instrument_key"] for entry in result.values()]
    if len(keys) != len(set(keys)):
        raise PipelineError("Duplicate global instrument identity")
    return result


def _expiry_date(value):
    if isinstance(value, bool) or value is None:
        raise PipelineError("Future expiry missing")
    if isinstance(value, int):
        if value <= 0:
            raise PipelineError("Future expiry invalid")
        return datetime.fromtimestamp(value / 1000, tz=timezone.utc).date()
    if isinstance(value, str):
        try:
            return date.fromisoformat(value[:10])
        except ValueError:
            pass
    raise PipelineError("Future expiry invalid")


def resolve_nearest_nifty_future(rows, as_of):
    if not isinstance(as_of, date) or isinstance(as_of, datetime):
        raise PipelineError("Future resolution date invalid")
    if not isinstance(rows, list) or not rows:
        raise PipelineError("BOD instrument master missing")
    candidates = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        if (row.get("segment") != "NSE_FO" or row.get("exchange") != "NSE"
                or row.get("instrument_type") != "FUT"
                or row.get("underlying_key") != NIFTY):
            continue
        expiry = _expiry_date(row.get("expiry"))
        if expiry < as_of:
            continue
        key = row.get("instrument_key")
        symbol = row.get("trading_symbol")
        if not isinstance(key, str) or not key or not isinstance(symbol, str) or not symbol:
            raise PipelineError("NIFTY future identity missing")
        candidates.append((expiry, key, symbol, row))
    if not candidates:
        raise PipelineError("No active NIFTY future")
    candidates.sort(key=lambda item: (item[0], item[1]))
    nearest_expiry = candidates[0][0]
    nearest = [item for item in candidates if item[0] == nearest_expiry]
    if len(nearest) != 1:
        raise PipelineError("NIFTY future identity ambiguous")
    expiry, key, symbol, _ = nearest[0]
    return {
        "name": "NIFTY FUTURE",
        "exchange": "NSE",
        "segment": "NSE_FO",
        "instrument_key": key,
        "trading_symbol": symbol,
        "underlying_key": NIFTY,
        "expiry": expiry.isoformat(),
        "instrument_type": "FUT",
    }
