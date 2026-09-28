"""Fail-closed bounded retry helpers for 5DR pre-open market acquisition."""
from __future__ import annotations

import time as _time
from datetime import datetime, time
from zoneinfo import ZoneInfo

from experiments.data_contract import DataArchitectureError
from experiments.live_shadow_bundle import _stamp

IST = ZoneInfo("Asia/Kolkata")
NORMAL_OPEN = time(9, 15)


def _local_clock(clock):
    now = clock()
    if not isinstance(now, datetime) or now.tzinfo is None or now.utcoffset() is None:
        raise DataArchitectureError("preopen retry clock must be timezone-aware")
    return now.astimezone(IST).timetz().replace(tzinfo=None)


def latest_intraday_with_retry(
    client,
    instrument_key: str,
    *,
    attempts: int = 3,
    sleep_seconds: float = 2.0,
    clock=None,
    sleeper=None,
):
    """Return a non-empty validated 1-minute intraday candle response.

    P0-07: retries are meaningful only during the genuine NSE pre-open window.
    Empty/malformed provider candle arrays are treated as transient for a small
    bounded retry window. No stale candle or synthetic value is ever substituted.
    A request or response at/after the 09:15 IST normal-market boundary is never
    accepted as ordinary pre-open evidence.
    """
    if attempts < 1:
        raise ValueError("attempts must be >= 1")
    clock = clock or (lambda: datetime.now(IST))
    sleeper = sleeper or _time.sleep
    last_problem = "missing response"

    for attempt in range(1, attempts + 1):
        if attempt > 1 and _local_clock(clock) >= NORMAL_OPEN:
            break

        env = client.intraday(instrument_key, "minutes", 1)

        # A provider call can begin before 09:15 but return after the market opens.
        # Such a response is not contemporaneous pre-open evidence and must fail closed.
        if _local_clock(clock) >= NORMAL_OPEN:
            last_problem = "provider response crossed normal-market boundary"
            break

        try:
            candles = env["payload"]["data"]["candles"]
        except (KeyError, TypeError):
            candles = None

        if isinstance(candles, list) and candles:
            valid = [row for row in candles if isinstance(row, list) and len(row) == 7]
            if len(valid) == len(candles):
                latest = max(valid, key=lambda row: _stamp(row[0]))
                return env, latest
            last_problem = "malformed intraday candle row"
        else:
            last_problem = "empty intraday candle array"

        if attempt < attempts:
            if _local_clock(clock) >= NORMAL_OPEN:
                break
            sleeper(sleep_seconds)

    raise DataArchitectureError(
        f"preopen intraday acquisition failed closed after bounded retries: {last_problem}"
    )
