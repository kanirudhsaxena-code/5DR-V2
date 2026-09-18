"""Manual-trigger evidence capture boundary for G11 validation.

Each capture starts only after an explicit user-approved trigger. The current IST time
becomes the structured evidence cutoff and a unique manual pair id. No forecast/scoring
methodology changes and no production, lifecycle or trading side effects are enabled.
"""
from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, time as dtime
from pathlib import Path
from zoneinfo import ZoneInfo

from experiments.data_contract import DataArchitectureError

IST = ZoneInfo("Asia/Kolkata")
PROTOCOL_PATH = Path(__file__).with_name("g11_validation_protocol.json")
CAPTURE_SCHEMA = "5dr-v2-2-3-g11-structured-evidence-capture-v2"
HEX64 = re.compile(r"^[0-9a-f]{64}$")
DEFAULT_MAX_START_LAG_SECONDS = 15
DEFAULT_MAX_FREEZE_LAG_SECONDS = 300
REGULAR_OPEN = dtime(9, 15)
REGULAR_CLOSE = dtime(15, 30)


def load_protocol(path=PROTOCOL_PATH):
    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError) as error:
        raise DataArchitectureError("G11 validation protocol unavailable") from error
    if payload.get("schema") != "5dr-v2-2-3-g11-validation-protocol-v2":
        raise DataArchitectureError("G11 validation protocol schema invalid")
    if payload.get("required_manual_runs") != 3 or payload.get("manual_trigger_required") is not True:
        raise DataArchitectureError("G11 validation protocol incomplete")
    return payload


def schedule_capture(now, *, manual_run_id=None):
    if not isinstance(now, datetime) or now.tzinfo is None or now.utcoffset() is None:
        raise DataArchitectureError("G11 capture time must be timezone-aware")
    protocol = load_protocol()
    local = now.astimezone(IST)
    local_time = local.timetz().replace(tzinfo=None)
    if local.weekday() >= 5:
        raise DataArchitectureError("G11 manual capture is outside a weekday NSE session")
    if local_time < REGULAR_OPEN or local_time > REGULAR_CLOSE:
        raise DataArchitectureError("G11 manual capture is outside regular NSE hours")
    suffix = (manual_run_id or local.strftime("%H%M%S")).strip()
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,32}", suffix):
        raise DataArchitectureError("G11 manual run id invalid")
    pair_id = f"G11-{local.date().strftime('%Y%m%d')}-{suffix}"
    return {
        "pair_id": pair_id,
        "manual_run_id": pair_id,
        "session_date_ist": local.date().isoformat(),
        "evidence_cutoff_ist": local.isoformat(),
        "wait_seconds": 0.0,
        "capture_start_lag_seconds": 0.0,
        "protocol_schema": protocol["schema"],
    }


def _aware(value, field):
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError as error:
            raise DataArchitectureError(f"{field} invalid") from error
    else:
        raise DataArchitectureError(f"{field} missing")
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise DataArchitectureError(f"{field} timezone missing")
    return parsed


def build_structured_capture(bundle, schedule, capture_started_at,
                             *, max_start_lag_seconds=DEFAULT_MAX_START_LAG_SECONDS,
                             max_freeze_lag_seconds=DEFAULT_MAX_FREEZE_LAG_SECONDS):
    if not isinstance(bundle, dict) or bundle.get("status") != "READY":
        raise DataArchitectureError("G11 structured bundle not READY")
    if not isinstance(schedule, dict):
        raise DataArchitectureError("G11 schedule missing")
    digest = str(bundle.get("bundle_sha256", "")).lower()
    if not HEX64.fullmatch(digest):
        raise DataArchitectureError("G11 bundle fingerprint invalid")
    run_id = bundle.get("run_id")
    if not isinstance(run_id, str) or not run_id.strip():
        raise DataArchitectureError("G11 bundle run id missing")
    started = _aware(capture_started_at, "G11 capture_started_at").astimezone(IST)
    cutoff = _aware(schedule.get("evidence_cutoff_ist"), "G11 evidence_cutoff_ist").astimezone(IST)
    frozen = _aware(bundle.get("frozen_at"), "G11 bundle frozen_at").astimezone(IST)
    if started.date().isoformat() != schedule.get("session_date_ist"):
        raise DataArchitectureError("G11 capture session mismatch")
    start_lag = (started - cutoff).total_seconds()
    freeze_lag = (frozen - cutoff).total_seconds()
    if start_lag < 0 or start_lag > max_start_lag_seconds:
        raise DataArchitectureError("G11 capture start outside manual-trigger tolerance")
    if freeze_lag < 0 or freeze_lag > max_freeze_lag_seconds:
        raise DataArchitectureError("G11 bundle freeze outside cutoff tolerance")
    runtime = bundle.get("runtime_context")
    if not isinstance(runtime, dict):
        raise DataArchitectureError("G11 runtime context missing")
    forbidden = ("forecast_release_enabled", "production_5dr_write_enabled", "lifecycle_write_enabled",
                 "trading_enabled", "canonical_integration_enabled", "methodology_changed")
    if any(runtime.get(flag) is not False for flag in forbidden):
        raise DataArchitectureError("G11 structured capture safety boundary crossed")
    pair_id = schedule.get("pair_id")
    capture = {
        "schema": CAPTURE_SCHEMA,
        "status": "EVIDENCE_FROZEN_PENDING_GOVERNED_JUDGMENT",
        "source_mode": "UPSTOX_STRUCTURED",
        "request_id": run_id.strip(),
        "manual_run_id": pair_id,
        "comparison_window_id": pair_id,
        "evidence_cutoff_ist": cutoff.isoformat(),
        "session_date_ist": schedule.get("session_date_ist"),
        "capture_started_at_ist": started.isoformat(),
        "bundle_frozen_at_ist": frozen.isoformat(),
        "capture_start_lag_seconds": round(start_lag, 3),
        "bundle_freeze_lag_seconds": round(freeze_lag, 3),
        "evidence_fingerprint": digest,
        "bundle_sha256": digest,
        "acceptance_decision_made": False,
        "production_activation_decision_made": False,
        "forecast_released": False,
        "production_5dr_write_enabled": False,
        "lifecycle_write_enabled": False,
        "trading_execution_enabled": False,
        "methodology_changed": False,
    }
    canonical = json.dumps(capture, sort_keys=True, separators=(",", ":"))
    capture["capture_sha256"] = hashlib.sha256(canonical.encode()).hexdigest()
    return capture
