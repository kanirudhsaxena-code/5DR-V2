"""Anytime user-invocation evidence-state planning for MDOS 5DR.

G5.1 governance amendment:
- user invocation is permitted at any time;
- clock/session state selects the evidence path, not invocation permission;
- authoritative NSE/NFO session validation remains an acquisition-layer duty;
- scheduled PREOPEN benchmark orchestration remains separate and unchanged.

This module performs no network access, scoring, forecast release, persistence,
lifecycle mutation, Learning Lab mutation, or trading.
"""
from __future__ import annotations

from datetime import datetime, time
from zoneinfo import ZoneInfo

from experiments.data_contract import DataArchitectureError

IST = ZoneInfo("Asia/Kolkata")

CLOSED_SESSION = "CLOSED_SESSION"
PREOPEN = "PREOPEN"
LIVE_INTRADAY = "LIVE_INTRADAY"
SESSION_FINAL = "SESSION_FINAL"


def classify_user_invocation_evidence_state(now: datetime) -> dict:
    """Return the preliminary evidence mode for an explicit user invocation.

    The result never grants freshness to data. The acquisition layer must verify
    the actual NSE/NFO session state with broker-authoritative market status/timings
    and may downgrade LIVE/PREOPEN to CLOSED_SESSION on holidays or provider-confirmed
    exchange closure.

    Weekend classification is deterministically CLOSED_SESSION. On weekdays, clock
    boundaries only select the intended acquisition path.
    """
    if not isinstance(now, datetime) or now.tzinfo is None or now.utcoffset() is None:
        raise DataArchitectureError("user invocation time must be timezone-aware")

    local = now.astimezone(IST)
    clock = local.timetz().replace(tzinfo=None)

    if local.weekday() >= 5:
        mode = CLOSED_SESSION
        label = "WEEKEND_CLOSED_SESSION"
    elif time(9, 10) <= clock < time(9, 15):
        mode = PREOPEN
        label = "USER_PREOPEN_SNAPSHOT"
    elif time(9, 15) <= clock < time(15, 30):
        mode = LIVE_INTRADAY
        label = "USER_LIVE_INTRADAY_SNAPSHOT"
    elif clock >= time(15, 30):
        mode = SESSION_FINAL
        label = "USER_SESSION_FINAL_SNAPSHOT"
    else:
        mode = CLOSED_SESSION
        label = "USER_OVERNIGHT_CLOSED_SESSION"

    return {
        "label": label,
        "run_class": "USER_CANONICAL_SNAPSHOT",
        "trigger_type": "USER",
        "evidence_mode": mode,
        "benchmark_role": "NONE",
        "requested_at_ist": local.isoformat(),
        "session_validation": "ACQUISITION_LAYER_AUTHORITATIVE",
        "target_trading_date_resolution": "GOVERNANCE_LAYER_REQUIRED",
        "live_freshness_may_be_inferred": False,
    }
