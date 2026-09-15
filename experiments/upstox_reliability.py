"""Reliability controls for the isolated read-only Upstox experiment.

Pure validation only: no network, database, forecast, lifecycle or trading writes.
"""
import hashlib
import json
import re
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from phase1.upstox import PipelineError

IST = ZoneInfo("Asia/Kolkata")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
NORMAL_OPEN = "NORMAL_OPEN"
PREOPEN = {"PRE_OPEN_START", "PRE_OPEN_END"}
CLOSING = {"CLOSING_START", "CLOSING_END"}
NORMAL_CLOSE = "NORMAL_CLOSE"
KNOWN = {NORMAL_OPEN, NORMAL_CLOSE} | PREOPEN | CLOSING


def _aware(value, field):
    if not isinstance(value, str):
        raise PipelineError(f"{field} timestamp missing")
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        raise PipelineError(f"{field} timestamp invalid") from None
    if parsed.tzinfo is None:
        raise PipelineError(f"{field} timestamp naive")
    return parsed.astimezone(timezone.utc)


def _provenance(sample):
    provenance = sample.get("provenance")
    required = ("contracts", "market_status", "intraday", "option_chain")
    if not isinstance(provenance, dict):
        raise PipelineError("Provenance missing")
    for name in required:
        entry = provenance.get(name)
        if not isinstance(entry, dict):
            raise PipelineError("Provenance missing")
        digest = entry.get("sha256")
        if not isinstance(digest, str) or not SHA256_RE.fullmatch(digest):
            raise PipelineError("Provenance digest invalid")
        if not isinstance(entry.get("source_path"), str) or not entry["source_path"].startswith("/"):
            raise PipelineError("Provenance source invalid")
        _aware(entry.get("received_at"), f"{name} received")
    return provenance


def snapshot_fingerprint(sample):
    """Stable fingerprint of provider payload identity, independent of receipt time."""
    provenance = _provenance(sample)
    selected_expiry = sample.get("selected_expiry")
    underlying = sample.get("underlying")
    candle = sample.get("latest_intraday_candle")
    session = sample.get("market_session")
    if not isinstance(selected_expiry, str) or not isinstance(underlying, str):
        raise PipelineError("Snapshot identity missing")
    if not isinstance(candle, dict) or not isinstance(candle.get("timestamp"), str):
        raise PipelineError("Snapshot candle identity missing")
    if not isinstance(session, dict) or session.get("status") not in KNOWN:
        raise PipelineError("Snapshot session identity missing")
    stable = {
        "schema": "upstox-experimental-snapshot-v1",
        "underlying": underlying,
        "selected_expiry": selected_expiry,
        "market_status": session["status"],
        "candle_timestamp": candle["timestamp"],
        "source_sha256": {name: provenance[name]["sha256"] for name in sorted(provenance)},
    }
    encoded = json.dumps(stable, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def validate_freshness(sample, now=None, max_receipt_age_seconds=300):
    """Fail closed on stale receipts or session-inconsistent intraday data."""
    now = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    if now.tzinfo is None:
        raise PipelineError("Reliability clock must be timezone aware")
    provenance = _provenance(sample)
    receipt_ages = {}
    for name, entry in provenance.items():
        received = _aware(entry["received_at"], f"{name} received")
        age = (now - received).total_seconds()
        if age < -60:
            raise PipelineError("Source receipt timestamp is in the future")
        if age > max_receipt_age_seconds:
            raise PipelineError("Source receipt is stale")
        receipt_ages[name] = round(max(0.0, age), 3)

    session = sample.get("market_session")
    candle = sample.get("latest_intraday_candle")
    if not isinstance(session, dict) or not isinstance(candle, dict):
        raise PipelineError("Freshness context missing")
    status = session.get("status")
    if status not in KNOWN:
        raise PipelineError("Unknown NFO market status")
    session_updated = _aware(session.get("last_updated"), "market status")
    candle_time = _aware(candle.get("timestamp"), "intraday candle")
    candle_age = (now - candle_time).total_seconds()
    if candle_age < -60:
        raise PipelineError("Intraday candle timestamp is in the future")

    now_ist = now.astimezone(IST)
    candle_ist = candle_time.astimezone(IST)
    session_ist = session_updated.astimezone(IST)
    if status == NORMAL_OPEN:
        if candle_ist.date() != now_ist.date() or candle_age > 300:
            raise PipelineError("Open-market intraday candle is stale")
        mode = "LIVE_OPEN"
        forecast_freshness_ready = True
    elif status in CLOSING:
        if candle_ist.date() != now_ist.date() or candle_age > 900:
            raise PipelineError("Closing-session intraday candle is stale")
        mode = "LIVE_CLOSING"
        forecast_freshness_ready = True
    elif status == NORMAL_CLOSE:
        # On weekends/holidays, exchange status can legitimately retain the last
        # trading session. Tie the candle to that session transition rather than
        # to wall-clock date so closed-market snapshots are not falsely rejected.
        if candle_ist.date() != session_ist.date():
            raise PipelineError("Closed-session candle does not match market session")
        mode = "CLOSED_SESSION_FINAL"
        forecast_freshness_ready = False
    else:  # PREOPEN
        if candle_time > now or (now - candle_time).total_seconds() > 7 * 24 * 3600:
            raise PipelineError("Pre-open candle context is stale")
        mode = "PREOPEN_CONTEXT"
        forecast_freshness_ready = False

    return {
        "status": "FRESHNESS_PASS",
        "mode": mode,
        "forecast_freshness_ready": forecast_freshness_ready,
        "latest_candle_timestamp": candle_time.isoformat(),
        "latest_candle_age_seconds": round(max(0.0, candle_age), 3),
        "source_receipt_age_seconds": receipt_ages,
    }


def annotate_sample(sample, now=None, audit_context=None):
    """Attach deterministic reliability metadata without changing market values."""
    report = validate_freshness(sample, now=now)
    fingerprint = snapshot_fingerprint(sample)
    context = dict(audit_context or {})
    safe_context = {}
    for key in ("github_run_id", "github_run_attempt", "github_sha", "github_event_name"):
        value = context.get(key)
        if value is not None:
            safe_context[key] = str(value)[:128]
    sample["reliability"] = report
    sample["audit"] = {
        "schema": "upstox-experimental-snapshot-v1",
        "snapshot_fingerprint": fingerprint,
        "context": safe_context,
    }
    return sample


def compare_snapshots(first, second, elapsed_seconds):
    """Classify duplicates; reject non-advancing open-market snapshots."""
    if isinstance(elapsed_seconds, bool) or not isinstance(elapsed_seconds, (int, float)) or elapsed_seconds < 0:
        raise PipelineError("Invalid snapshot comparison interval")
    first_fp = snapshot_fingerprint(first)
    second_fp = snapshot_fingerprint(second)
    duplicate = first_fp == second_fp
    first_session = first.get("market_session", {}).get("status")
    second_session = second.get("market_session", {}).get("status")
    if first_session not in KNOWN or second_session not in KNOWN:
        raise PipelineError("Snapshot session identity missing")

    if duplicate and second_session == NORMAL_OPEN and elapsed_seconds >= 65:
        raise PipelineError("Open-market snapshot did not advance")
    if duplicate and second_session in CLOSING and elapsed_seconds >= 65:
        raise PipelineError("Closing-session snapshot did not advance")

    if duplicate:
        classification = "EXPECTED_STATIC_NONTRADING_SESSION" if second_session != NORMAL_OPEN else "SHORT_INTERVAL_DUPLICATE"
    else:
        classification = "ADVANCED"
    return {
        "status": "DUPLICATE_POLICY_PASS",
        "duplicate": duplicate,
        "classification": classification,
        "elapsed_seconds": round(float(elapsed_seconds), 3),
        "first_fingerprint": first_fp,
        "second_fingerprint": second_fp,
        "first_market_status": first_session,
        "second_market_status": second_session,
    }
