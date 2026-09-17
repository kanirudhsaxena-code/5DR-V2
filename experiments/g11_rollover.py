"""Fail-closed next-session rollover validation for G11.

This module is intentionally pure: it performs no network, broker, database, forecast,
lifecycle, production or trading actions. It only validates already-captured evidence for
the lightweight G11 next-session rollover required by the approved validation protocol.
"""
from __future__ import annotations

import hashlib
import json
import re
from datetime import date, datetime
from zoneinfo import ZoneInfo

from experiments.data_contract import DataArchitectureError
from experiments.g11_live_capture import CAPTURE_SCHEMA
from experiments.upstox_session import OPEN_STATUSES, select_session_valid_expiry
from phase1.upstox import PipelineError

IST = ZoneInfo("Asia/Kolkata")
HEX64 = re.compile(r"^[0-9a-f]{64}$")
GATE_SCHEMA = "5dr-v2-2-3-gate-record-v1"
MANUAL_SERIES_GATE = "G11_MANUAL_SAME_SESSION_SERIES"
MANUAL_SERIES_STATUS = "MANUAL_SERIES_PASS_ROLLOVER_PENDING"
ROLLOVER_GATE = "G11_NEXT_SESSION_ROLLOVER"


def _iso_date(value, field):
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if not isinstance(value, str):
        raise DataArchitectureError(f"{field} invalid")
    try:
        return date.fromisoformat(value)
    except ValueError:
        raise DataArchitectureError(f"{field} invalid") from None


def _aware(value, field):
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            raise DataArchitectureError(f"{field} invalid") from None
    else:
        raise DataArchitectureError(f"{field} invalid")
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise DataArchitectureError(f"{field} timezone missing")
    return parsed


def _hex64(value, field):
    value = str(value or "").lower()
    if not HEX64.fullmatch(value):
        raise DataArchitectureError(f"{field} invalid")
    return value


def rollover_run_key(session_date):
    session = _iso_date(session_date, "rollover session date")
    return f"G11_ROLLOVER:{session.isoformat()}"


def _verify_capture_hash(capture):
    supplied = _hex64(capture.get("capture_sha256"), "G11 capture fingerprint")
    unsigned = dict(capture)
    unsigned.pop("capture_sha256", None)
    canonical = json.dumps(unsigned, sort_keys=True, separators=(",", ":"))
    calculated = hashlib.sha256(canonical.encode()).hexdigest()
    if supplied != calculated:
        raise DataArchitectureError("G11 capture fingerprint mismatch")
    return supplied


def validate_next_session_rollover(*, previous_series, current_capture,
                                   market_status, active_expiries,
                                   replay_bundle_sha256,
                                   completed_run_keys=()):
    """Validate one lightweight G11 next-session rollover and return an audit record.

    The caller supplies evidence already collected through approved read-only boundaries.
    Any stale-session reuse, prior-bundle reuse, fingerprint mutation, expiry failure,
    duplicate run key or side-effect flag fails closed.
    """
    if not isinstance(previous_series, dict):
        raise DataArchitectureError("G11 prior manual-series record missing")
    if previous_series.get("gate") != MANUAL_SERIES_GATE:
        raise DataArchitectureError("G11 prior manual-series gate invalid")
    if previous_series.get("status") != MANUAL_SERIES_STATUS:
        raise DataArchitectureError("G11 prior manual series not rollover-ready")
    if previous_series.get("g11_final_gate_status") != "PENDING_NEXT_SESSION_ROLLOVER":
        raise DataArchitectureError("G11 prior series final status invalid")
    runs = previous_series.get("runs")
    if not isinstance(runs, list) or len(runs) != 3 or any(row.get("status") != "PASS" for row in runs):
        raise DataArchitectureError("G11 prior manual series is not three-of-three PASS")

    prior_session = _iso_date(previous_series.get("session_date"), "G11 prior session date")

    if not isinstance(current_capture, dict) or current_capture.get("schema") != CAPTURE_SCHEMA:
        raise DataArchitectureError("G11 rollover capture schema invalid")
    if current_capture.get("source_mode") != "UPSTOX_STRUCTURED":
        raise DataArchitectureError("G11 rollover source mode invalid")
    if current_capture.get("status") != "EVIDENCE_FROZEN_PENDING_GOVERNED_JUDGMENT":
        raise DataArchitectureError("G11 rollover capture state invalid")

    current_session = _iso_date(current_capture.get("session_date_ist"), "G11 rollover session date")
    if current_session <= prior_session:
        raise DataArchitectureError("G11 rollover did not advance to a new session")

    run_key = rollover_run_key(current_session)
    if not isinstance(completed_run_keys, (list, tuple, set, frozenset)):
        raise DataArchitectureError("G11 completed rollover keys invalid")
    if run_key in completed_run_keys:
        raise DataArchitectureError("G11 rollover duplicate run blocked")

    cutoff = _aware(current_capture.get("evidence_cutoff_ist"), "G11 rollover evidence cutoff").astimezone(IST)
    started = _aware(current_capture.get("capture_started_at_ist"), "G11 rollover capture start").astimezone(IST)
    frozen = _aware(current_capture.get("bundle_frozen_at_ist"), "G11 rollover bundle freeze").astimezone(IST)
    for stamp, field in ((cutoff, "evidence cutoff"), (started, "capture start"), (frozen, "bundle freeze")):
        if stamp.date() != current_session:
            raise DataArchitectureError(f"G11 rollover {field} is from a stale session")

    bundle_sha = _hex64(current_capture.get("bundle_sha256"), "G11 rollover bundle fingerprint")
    evidence_sha = _hex64(current_capture.get("evidence_fingerprint"), "G11 rollover evidence fingerprint")
    if bundle_sha != evidence_sha:
        raise DataArchitectureError("G11 rollover evidence fingerprint mismatch")
    capture_sha = _verify_capture_hash(current_capture)

    prior_hashes = {
        _hex64(row.get("bundle_sha256"), "G11 prior bundle fingerprint")
        for row in runs
    }
    if bundle_sha in prior_hashes:
        raise DataArchitectureError("G11 prior-session bundle reused as current evidence")

    replay_sha = _hex64(replay_bundle_sha256, "G11 rollover replay fingerprint")
    if replay_sha != bundle_sha:
        raise DataArchitectureError("G11 rollover deterministic replay mismatch")

    if not isinstance(market_status, dict) or market_status.get("exchange") != "NFO":
        raise DataArchitectureError("G11 rollover NFO market status invalid")
    status = market_status.get("status")
    if status not in OPEN_STATUSES:
        raise DataArchitectureError("G11 rollover market session is not open")
    market_updated = _aware(market_status.get("last_updated"), "G11 market status timestamp").astimezone(IST)
    market_received = _aware(market_status.get("received_at"), "G11 market status receipt").astimezone(IST)
    if market_received.date() != current_session or market_updated.date() != current_session:
        raise DataArchitectureError("G11 market status is not from the rollover session")
    if market_received < market_updated:
        raise DataArchitectureError("G11 market status receipt precedes provider timestamp")

    if not isinstance(active_expiries, (list, tuple, set, frozenset)) or not active_expiries:
        raise DataArchitectureError("G11 rollover active expiries missing")
    try:
        selected_expiry = select_session_valid_expiry(list(active_expiries), current_session, status)
    except (PipelineError, ValueError, TypeError):
        raise DataArchitectureError("G11 rollover expiry identity invalid") from None
    if _iso_date(selected_expiry, "G11 selected expiry") < current_session:
        raise DataArchitectureError("G11 rollover selected expiry is stale")

    safety_fields = (
        "acceptance_decision_made",
        "production_activation_decision_made",
        "forecast_released",
        "production_5dr_write_enabled",
        "lifecycle_write_enabled",
        "trading_execution_enabled",
        "methodology_changed",
    )
    if any(current_capture.get(field) is not False for field in safety_fields):
        raise DataArchitectureError("G11 rollover safety boundary crossed")

    record = {
        "schema": GATE_SCHEMA,
        "gate": ROLLOVER_GATE,
        "status": "PASS",
        "prior_session_date": prior_session.isoformat(),
        "session_date": current_session.isoformat(),
        "rollover_run_key": run_key,
        "checks": {
            "new_session_identity": "PASS",
            "prior_session_evidence_rejected": "PASS",
            "current_session_date_bound": "PASS",
            "current_expiry_identity": "PASS",
            "deterministic_replay": "PASS",
            "capture_fingerprint_integrity": "PASS",
            "duplicate_idempotency_guard": "PASS",
            "side_effect_isolation": "PASS",
        },
        "evidence": {
            "market_exchange": "NFO",
            "market_status": status,
            "market_last_updated_ist": market_updated.isoformat(),
            "market_received_at_ist": market_received.isoformat(),
            "selected_expiry": selected_expiry,
            "bundle_sha256": bundle_sha,
            "capture_sha256": capture_sha,
            "replay_bundle_sha256": replay_sha,
        },
        "governance": {
            "published": False,
            "forecast_release_enabled": False,
            "production_5dr_write_enabled": False,
            "lifecycle_write_enabled": False,
            "trading_execution_enabled": False,
            "methodology_changed": False,
            "production_activation_allowed": False,
            "pr30_merge_allowed": False,
        },
        "next_if_pass": "G11_FINAL_CONSOLIDATION_AND_SCREENSHOT_RETIREMENT_READINESS_ASSESSMENT",
    }
    canonical = json.dumps(record, sort_keys=True, separators=(",", ":"))
    record["gate_sha256"] = hashlib.sha256(canonical.encode()).hexdigest()
    return record
