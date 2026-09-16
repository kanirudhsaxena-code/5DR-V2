"""Bounded 5DR candle-history inventory for the isolated data-backbone experiment.

The identities below are the exact Upstox keys already live-proven on 16 Sep 2026.
Only 5DR series are enabled here. EDGE Stock and IPO EDGE remain outside background
collection and cannot be introduced through this inventory.
"""
from experiments.data_contract import DataArchitectureError
from phase1.upstox import NIFTY

INDIA_VIX = "NSE_INDEX|India VIX"

GLOBAL_RISK = {
    "GIFT_NIFTY": "GLOBAL_INDEX|SGX NIFTY",
    "SP500": "GLOBAL_INDEX|^GSPC",
    "DOW_JONES": "GLOBAL_INDEX|^DJI",
    "US_TECH_100": "GLOBAL_INDEX|IXIX",
    "DAX": "GLOBAL_INDEX|^GDAXI",
    "FTSE_100": "GLOBAL_INDEX|^FTSE",
    "NIKKEI_225": "GLOBAL_INDEX|^N225",
    "HANG_SENG": "GLOBAL_INDEX|^HSI",
}

GLOBAL_MACRO = {
    "BRENT": "GLOBAL_INDICATOR|BZUSD",
    "WTI": "GLOBAL_INDICATOR|CLUSD",
    "USD_INR": "GLOBAL_INDICATOR|USDINR",
}


def _series(variable_id, subject_id, instrument_key, timeframe, lookback_days, retention_days=400):
    return {
        "consumer": "5DR",
        "variable_id": variable_id,
        "subject_id": subject_id,
        "instrument_key": instrument_key,
        "timeframe": timeframe,
        "lookback_days": lookback_days,
        "retention_days": retention_days,
    }


SERIES = [
    _series("NIFTY_PRICE_CANDLES", "NIFTY_50", NIFTY, "5m", 30),
    _series("NIFTY_PRICE_CANDLES", "NIFTY_50", NIFTY, "15m", 180),
    _series("NIFTY_PRICE_CANDLES", "NIFTY_50", NIFTY, "30m", 180),
    _series("NIFTY_PRICE_CANDLES", "NIFTY_50", NIFTY, "1h", 365),
    _series("NIFTY_PRICE_CANDLES", "NIFTY_50", NIFTY, "1d", 365),
    _series("INDIA_VIX", "INDIA_VIX", INDIA_VIX, "1h", 365),
    _series("INDIA_VIX", "INDIA_VIX", INDIA_VIX, "1d", 365),
]
SERIES.extend(
    _series("GLOBAL_RISK_INDICES", subject, key, timeframe, 365)
    for subject, key in GLOBAL_RISK.items()
    for timeframe in ("1h", "1d")
)
SERIES.extend(
    _series("CRUDE_USDINR", subject, key, timeframe, 365)
    for subject, key in GLOBAL_MACRO.items()
    for timeframe in ("1h", "1d")
)
SERIES = tuple(SERIES)


def series_id(row):
    return ":".join((row["consumer"], row["variable_id"], row["subject_id"], row["timeframe"]))


def validate_inventory(rows=SERIES):
    if not isinstance(rows, (tuple, list)) or not rows:
        raise DataArchitectureError("backfill inventory missing")
    seen = set()
    allowed_timeframes = {"5m", "15m", "30m", "1h", "1d"}
    for row in rows:
        if not isinstance(row, dict) or row.get("consumer") != "5DR":
            raise DataArchitectureError("backfill consumer outside 5DR")
        identity = series_id(row)
        if identity in seen:
            raise DataArchitectureError("duplicate backfill series")
        seen.add(identity)
        for field in ("variable_id", "subject_id", "instrument_key"):
            if not isinstance(row.get(field), str) or not row[field].strip():
                raise DataArchitectureError("backfill series identity invalid")
        if row.get("timeframe") not in allowed_timeframes:
            raise DataArchitectureError("backfill timeframe invalid")
        for field in ("lookback_days", "retention_days"):
            value = row.get(field)
            if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
                raise DataArchitectureError("backfill horizon invalid")
    return len(rows)
