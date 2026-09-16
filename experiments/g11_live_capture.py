"""Exact-cutoff evidence capture boundary for G11 validation.

This module binds a live structured evidence bundle to the experiment-only G11
comparison window. It changes no forecasting/scoring methodology and enables no side
effects. The structured evidence may be interpreted later, but its pair identity,
cutoff, session and bundle fingerprint are frozen here.
"""
from __future__ import annotations

import hashlib
import json
import re
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from experiments.data_contract import DataArchitectureError

IST = ZoneInfo("Asia/Kolkata")
PROTOCOL_PATH = Path(__file__).with_name("g11_validation_protocol.json")
CAPTURE_SCHEMA = "5dr-v2-2-3-g11-structured-evidence-capture-v1"
HEX64 = re.compile(r"^[0-9a-f]{64}$")
DEFAULT_MAX_EARLY_SECONDS = 600
DEFAULT_MAX_LATE_SECONDS = 120
DEFAULT_MAX_FREEZE_LAG_SECONDS = 180


def load_protocol(path=PROTOCOL_PATH):
    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError) as error:
        raise DataArchitectureError("G11 validation protocol unavailable") from error
    if payload.get("schema") != "5dr-v2-2-3-g11-validation-protocol-v1":
        raise DataArchitectureError("G11 validation protocol schema invalid")
    targets = payload.get("target_sessions_ist")
    cutoff = payload.get("preferred_comparison_cutoff_ist")
    if not isinstance(targets, list) or not targets or not isinstance(cutoff, str):
        raise DataArchitectureError("G11 validation protocol incomplete")
    try:
        parsed_targets = tuple(date.fromisoformat(value) for value in targets)
    except (TypeError, ValueError) as error:
        raise DataArchitectureError("G11 target session invalid") from error
    return payload, parsed_targets, cutoff


def cutoff_for_session(session_date, cutoff_text):
    if not isinstance(session_date, date) or not isinstance(cutoff_text, str):
        raise DataArchitectureError("G11 cutoff request invalid")
    try:
        cutoff = datetime.fromisoformat(f"{session_date.isoformat()}T{cutoff_text}")
    except ValueError as error:
        raise DataArchitectureError("G11 cutoff invalid") from error
    if cutoff.tzinfo is None or cutoff.utcoffset() is None:
        raise DataArchitectureError("G11 cutoff timezone missing")
    return cutoff.astimezone(IST)


def schedule_capture(now, *, max_early_seconds=DEFAULT_MAX_EARLY_SECONDS,
                     max_late_seconds=DEFAULT_MAX_LATE_SECONDS):
    if not isinstance(now, datetime) or now.tzinfo is None or now.utcoffset() is None:
        raise DataArchitectureError("G11 capture time must be timezone-aware")
    for value in (max_early_seconds, max_late_seconds):
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise DataArchitectureError("G11 capture tolerance invalid")
    protocol, targets, cutoff_text = load_protocol()
    local = now.astimezone(IST)
    if local.date() not in targets:
        raise DataArchitectureError("G11 capture date is not an approved target session")
    cutoff = cutoff_for_session(local.date(), cutoff_text)
    lag = (local - cutoff).total_seconds()
    if lag < -max_early_seconds:
        raise DataArchitectureError("G11 capture started too early")
    if lag > max_late_seconds:
        raise DataArchitectureError("G11 capture started too late")
    pair_id = f"G11-{local.date().strftime('%Y%m%d')}-{cutoff.strftime('%H%M')}"
    return {
        "pair_id": pair_id,
        "session_date_ist": local.date().isoformat(),
        "evidence_cutoff_ist": cutoff.isoformat(),
        "wait_seconds": max(0.0, -lag),
        "capture_start_lag_seconds": max(0.0, lag),
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
                             *, max_freeze_lag_seconds=DEFAULT_MAX_FREEZE_LAG_SECONDS):
    if not isinstance(bundle, dict) or bundle.get("status") != "READY":
        raise DataArchitectureError("G11 structured bundle not READY")
    if not isinstance(schedule, dict):
        raise DataArchitectureError("G11 schedule missing")
    if isinstance(max_freeze_lag_seconds, bool) or not isinstance(max_freeze_lag_seconds, int) or max_freeze_lag_seconds < 1:
        raise DataArchitectureError("G11 freeze tolerance invalid")
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
    if start_lag < 0 or start_lag > DEFAULT_MAX_LATE_SECONDS:
        raise DataArchitectureError("G11 capture start outside cutoff tolerance")
    if freeze_lag < 0 or freeze_lag > max_freeze_lag_seconds:
        raise DataArchitectureError("G11 bundle freeze outside cutoff tolerance")
    runtime = bundle.get("runtime_context")
    if not isinstance(runtime, dict):
        raise DataArchitectureError("G11 runtime context missing")
    forbidden = (
        "forecast_released", "production_5dr_write_enabled", "lifecycle_write_enabled",
        "trading_enabled", "canonical_integration_enabled", "methodology_changed",
    )
    if any(runtime.get(flag) is not False for flag in forbidden):
        raise DataArchitectureError("G11 structured capture safety boundary crossed")
    capture = {
        "schema": CAPTURE_SCHEMA,
        "status": "EVIDENCE_FROZEN_PENDING_GOVERNED_JUDGMENT",
        "source_mode": "UPSTOX_STRUCTURED",
        "request_id": run_id.strip(),
        "comparison_window_id": schedule.get("pair_id"),
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
