"""Guarded production scheduling metadata for the V2.2.3 structured-evidence runtime.

This layer classifies only the already-approved live evidence windows and proves that
a frozen bundle is production-eligible as evidence. It does not score, publish,
persist forecasts, write lifecycle state, or trade.
"""
from __future__ import annotations

from datetime import datetime, time
from zoneinfo import ZoneInfo

from experiments.data_contract import DataArchitectureError

IST = ZoneInfo("Asia/Kolkata")

WINDOWS = (
    {
        "label": "PRIOR_CLOSE_REFRESH",
        "run_class": "CANONICAL_CANDIDATE",
        "evidence_mode": "LIVE_MARKET",
        "start": time(15, 20),
        "end": time(15, 35),
    },
    {
        "label": "LATE_MORNING_SNAPSHOT",
        "run_class": "INTRADAY_SNAPSHOT",
        "evidence_mode": "LIVE_MARKET",
        "start": time(10, 25),
        "end": time(10, 40),
    },
)

FORBIDDEN_RUNTIME_FLAGS = (
    "forecast_release_enabled",
    "production_5dr_write_enabled",
    "lifecycle_write_enabled",
    "trading_enabled",
    "canonical_integration_enabled",
    "methodology_changed",
)


def classify_production_window(now: datetime) -> dict:
    if not isinstance(now, datetime) or now.tzinfo is None or now.utcoffset() is None:
        raise DataArchitectureError("production evidence time must be timezone-aware")
    local = now.astimezone(IST)
    if local.weekday() >= 5:
        raise DataArchitectureError("production evidence outside weekday NSE schedule")
    clock = local.timetz().replace(tzinfo=None)
    for row in WINDOWS:
        if row["start"] <= clock < row["end"]:
            return {
                "label": row["label"],
                "run_class": row["run_class"],
                "evidence_mode": row["evidence_mode"],
                "session_date_ist": local.date().isoformat(),
                "captured_at_ist": local.isoformat(),
                "window_start_ist": row["start"].isoformat(),
                "window_end_exclusive_ist": row["end"].isoformat(),
                "target_trading_date_resolution": "GOVERNANCE_LAYER_REQUIRED",
            }
    raise DataArchitectureError("production evidence outside approved live run windows")


def build_production_evidence_audit(bundle: dict, now: datetime) -> dict:
    window = classify_production_window(now)
    if not isinstance(bundle, dict) or bundle.get("status") != "READY":
        raise DataArchitectureError("production evidence bundle not READY")
    digest = bundle.get("bundle_sha256")
    if not isinstance(digest, str) or len(digest) != 64:
        raise DataArchitectureError("production evidence bundle fingerprint invalid")

    screenshot_policy = bundle.get("screenshot_policy")
    if not isinstance(screenshot_policy, dict) or screenshot_policy.get("screenshot_dependency") is not False:
        raise DataArchitectureError("production evidence still depends on screenshots")

    runtime = bundle.get("runtime_context")
    if not isinstance(runtime, dict):
        raise DataArchitectureError("production evidence runtime context missing")
    if any(runtime.get(flag) is not False for flag in FORBIDDEN_RUNTIME_FLAGS):
        raise DataArchitectureError("production evidence crossed release/write/trading boundary")

    if bundle.get("forecast_released") is not False:
        raise DataArchitectureError("production evidence bundle released a forecast")
    if bundle.get("production_5dr_write_enabled") is not False:
        raise DataArchitectureError("production evidence bundle enabled production writes")
    if bundle.get("trading_enabled") is not False:
        raise DataArchitectureError("production evidence bundle enabled trading")

    return {
        "schema": "5dr-v2-2-3-production-evidence-audit-v1",
        "status": "PRODUCTION_EVIDENCE_READY",
        "bundle_sha256": digest,
        "bundle_run_id": bundle.get("run_id"),
        **window,
        "structured_evidence_primary": True,
        "routine_screenshot_required": False,
        "diagnostic_screenshot_fallback": True,
        "preopen_refresh_enabled": False,
        "preopen_refresh_status": "FAIL_CLOSED_UNTIL_CARRY_FORWARD_REFRESH_PATH_IS_SEPARATELY_VALIDATED",
        "forecast_release_enabled": False,
        "production_5dr_write_enabled": False,
        "lifecycle_write_enabled": False,
        "trading_execution_enabled": False,
        "methodology_changed": False,
    }
