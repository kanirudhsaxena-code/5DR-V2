"""Select 100 independent, fully matured NIFTY target sessions from read-only history."""
from __future__ import annotations

import json
import os
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from experiments.upstox_quant_client import QuantReadOnlyClient
from phase1.upstox import NIFTY, PipelineError

IST = ZoneInfo("Asia/Kolkata")
TARGET_COUNT = 100
HORIZONS = ("D+1", "D+2", "D+3", "D+4", "D+5")


def run(token):
    if not isinstance(token, str) or not token.strip():
        raise PipelineError("UPSTOX_ANALYTICS_TOKEN is missing")

    # Use completed calendar days only. Four later trading sessions are reserved so
    # every selected target has a complete D+1...D+5 outcome path.
    end = datetime.now(IST).date() - timedelta(days=1)
    start = end - timedelta(days=240)
    client = QuantReadOnlyClient(token, {NIFTY})
    envelope = client.historical(NIFTY, "days", 1, start, end)
    candles = envelope.get("payload", {}).get("data", {}).get("candles")
    if not isinstance(candles, list):
        raise PipelineError("NIFTY daily history missing")

    dates = []
    for candle in candles:
        if not isinstance(candle, list) or not candle:
            raise PipelineError("NIFTY daily candle invalid")
        stamp = datetime.fromisoformat(candle[0])
        if stamp.tzinfo is None:
            raise PipelineError("NIFTY daily timestamp naive")
        dates.append(stamp.date().isoformat())
    dates = sorted(set(dates))
    required = TARGET_COUNT + 4
    if len(dates) < required:
        raise PipelineError(f"insufficient trading sessions: {len(dates)} < {required}")

    eligible = dates[-required:]
    sessions = []
    for index in range(TARGET_COUNT):
        horizon_dates = dict(zip(HORIZONS, eligible[index:index + 5]))
        sessions.append({
            "target_date": eligible[index],
            "horizon_dates": horizon_dates,
        })

    return {
        "schema": "bt100-target-sessions-v0",
        "source_semantic": "UPSTOX_AUTHENTICATED_NIFTY_DAILY",
        "requested_calendar_start": start.isoformat(),
        "requested_calendar_end": end.isoformat(),
        "target_count": len(sessions),
        "latest_outcome_session": eligible[-1],
        "sessions": sessions,
        "read_only": True,
        "production_writes": 0,
        "production_neuron_calls": 0,
        "trading_enabled": False,
    }


def main():
    try:
        print(json.dumps(run(os.environ.get("UPSTOX_ANALYTICS_TOKEN", "")), sort_keys=True, indent=2))
        return 0
    except Exception as error:
        print(json.dumps({
            "schema": "bt100-target-sessions-v0",
            "status": "BLOCKED",
            "error_type": type(error).__name__,
            "read_only": True,
            "production_writes": 0,
            "production_neuron_calls": 0,
            "trading_enabled": False,
        }, sort_keys=True, indent=2))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
