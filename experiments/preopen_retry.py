"""Fail-closed bounded retry helpers for 5DR pre-open market acquisition."""
from __future__ import annotations

import time as _time
from datetime import datetime, time
from zoneinfo import ZoneInfo

from experiments.data_contract import DataArchitectureError
from experiments.live_shadow_bundle import _stamp

IST = ZoneInfo("Asia/Kolkata")


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

    Empty/malformed provider candle arrays are treated as transient only for a
    small bounded retry window. No stale candle or synthetic value is ever
    substituted. A retry is never started at/after 09:00 IST.
    """
    if attempts < 1:
        raise ValueError("attempts must be >= 1")
    clock = clock or (lambda: datetime.now(IST))
    sleeper = sleeper or _time.sleep
    last_problem = "missing response"

    for attempt in range(1, attempts + 1):
        if attempt > 1:
            now = clock()
            if not isinstance(now, datetime) or now.tzinfo is None or now.utcoffset() is None:
                raise DataArchitectureError("preopen retry clock must be timezone-aware")
            local_clock = now.astimezone(IST).timetz().replace(tzinfo=None)
            if local_clock >= time(9, 0):
                break

        env = client.intraday(instrument_key, "minutes", 1)
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
            now = clock()
            if not isinstance(now, datetime) or now.tzinfo is None or now.utcoffset() is None:
                raise DataArchitectureError("preopen retry clock must be timezone-aware")
            local_clock = now.astimezone(IST).timetz().replace(tzinfo=None)
            if local_clock >= time(9, 0):
                break
            sleeper(sleep_seconds)

    raise DataArchitectureError(
        f"preopen intraday acquisition failed closed after bounded retries: {last_problem}"
    )
