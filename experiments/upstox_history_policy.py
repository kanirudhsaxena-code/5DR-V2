"""Cost-aware historical retrieval planning for Upstox V3.

Provider limits are implemented conservatively: <=15 minute candles in 28-day chunks,
>15 minute/hour candles in 89-day chunks, and daily candles in <=3650-day chunks.
This is a planning layer only; it performs no network or storage writes.
"""
from datetime import date, timedelta

from experiments.data_contract import DataArchitectureError

TIMEFRAME_MAP = {"5m": ("minutes", 5), "15m": ("minutes", 15), "30m": ("minutes", 30), "1h": ("hours", 1), "1d": ("days", 1)}


def safe_chunk_days(unit, interval):
    if unit == "minutes" and isinstance(interval, int) and not isinstance(interval, bool) and 1 <= interval <= 15:
        return 28
    if unit == "minutes" and isinstance(interval, int) and not isinstance(interval, bool) and 16 <= interval <= 300:
        return 89
    if unit == "hours" and isinstance(interval, int) and not isinstance(interval, bool) and 1 <= interval <= 5:
        return 89
    if unit == "days" and interval == 1:
        return 3650
    raise DataArchitectureError("historical timeframe unsupported")


def plan_history_chunks(start, end, unit, interval):
    if not isinstance(start, date) or not isinstance(end, date) or start > end:
        raise DataArchitectureError("historical date range invalid")
    span = safe_chunk_days(unit, interval)
    chunks = []
    cursor = start
    while cursor <= end:
        chunk_end = min(end, cursor + timedelta(days=span - 1))
        chunks.append({"start": cursor, "end": chunk_end, "unit": unit, "interval": interval})
        cursor = chunk_end + timedelta(days=1)
    return chunks


def plan_requirement_history(requirement, as_of):
    if not isinstance(requirement, dict) or not isinstance(as_of, date):
        raise DataArchitectureError("history requirement invalid")
    lookbacks = requirement.get("lookback_days") or {}
    if not isinstance(lookbacks, dict):
        raise DataArchitectureError("history lookback invalid")
    plan = []
    for timeframe in requirement.get("timeframes", ()): 
        days = lookbacks.get(timeframe)
        if days is None:
            continue
        if timeframe not in TIMEFRAME_MAP or isinstance(days, bool) or not isinstance(days, int) or days <= 0:
            raise DataArchitectureError("history requirement timeframe invalid")
        unit, interval = TIMEFRAME_MAP[timeframe]
        start = as_of - timedelta(days=days - 1)
        plan.extend({"timeframe": timeframe, **chunk} for chunk in plan_history_chunks(start, as_of, unit, interval))
    return plan
