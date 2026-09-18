"""Sanitized, deterministic audit manifest for the isolated Upstox experiment.

Pure transformation only. No network, database, forecast, lifecycle or trading writes.
The manifest intentionally contains no credentials, authorization headers or raw payloads.
"""
import hashlib
import json
import re
from datetime import datetime, timezone

from phase1.upstox import PipelineError

SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
SAFE_DIAGNOSTIC_RE = re.compile(r"^[A-Z0-9_]{1,64}$")
SCHEMA = "upstox-experimental-acquisition-manifest-v1"


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


def _safe_context(sample):
    audit = sample.get("audit")
    if not isinstance(audit, dict):
        raise PipelineError("Audit metadata missing")
    context = audit.get("context")
    if not isinstance(context, dict):
        context = {}
    result = {}
    for key in ("github_run_id", "github_run_attempt", "github_sha", "github_event_name"):
        value = context.get(key)
        if value is not None:
            result[key] = str(value)[:128]
    return result


def build_success_manifest(sample):
    if sample.get("read_only") is not True or sample.get("trading_enabled") is not False:
        raise PipelineError("Read-only boundary missing")
    if sample.get("production_5dr_write_enabled") is not False:
        raise PipelineError("Production write boundary missing")
    if sample.get("status") != "LIVE_SAMPLE_PASSED":
        raise PipelineError("Sample status is not successful")

    audit = sample.get("audit")
    reliability = sample.get("reliability")
    provenance = sample.get("provenance")
    session = sample.get("market_session")
    candle = sample.get("latest_intraday_candle")
    strikes = sample.get("sample_strikes")
    if not all(isinstance(value, dict) for value in (audit, reliability, provenance, session, candle)):
        raise PipelineError("Manifest source metadata missing")
    if not isinstance(strikes, list) or not strikes:
        raise PipelineError("Manifest strike sample missing")

    snapshot_fp = audit.get("snapshot_fingerprint")
    if not isinstance(snapshot_fp, str) or not SHA256_RE.fullmatch(snapshot_fp):
        raise PipelineError("Snapshot fingerprint invalid")

    sources = []
    received_times = []
    for name in sorted(provenance):
        entry = provenance[name]
        if not isinstance(entry, dict):
            raise PipelineError("Provenance entry invalid")
        digest = entry.get("sha256")
        path = entry.get("source_path")
        received = entry.get("received_at")
        if not isinstance(digest, str) or not SHA256_RE.fullmatch(digest):
            raise PipelineError("Provenance digest invalid")
        if not isinstance(path, str) or not path.startswith("/"):
            raise PipelineError("Provenance path invalid")
        parsed = _aware(received, f"{name} received")
        received_times.append(parsed)
        sources.append({
            "name": name,
            "source_path": path,
            "sha256": digest,
            "received_at": parsed.isoformat(),
        })

    instrument_keys = []
    for row in strikes:
        if not isinstance(row, dict):
            raise PipelineError("Strike row invalid")
        for side in ("CE", "PE"):
            leg = row.get(side)
            if not isinstance(leg, dict) or not isinstance(leg.get("instrument_key"), str):
                raise PipelineError("Option instrument identity missing")
            instrument_keys.append(leg["instrument_key"])
    if len(instrument_keys) != len(set(instrument_keys)):
        raise PipelineError("Duplicate option instrument identity")

    manifest = {
        "schema": SCHEMA,
        "status": "PASS",
        "read_only": True,
        "trading_enabled": False,
        "production_5dr_write_enabled": False,
        "transport": sample.get("transport"),
        "run_context": _safe_context(sample),
        "underlying": sample.get("underlying"),
        "selected_expiry": sample.get("selected_expiry"),
        "market_session": {
            "exchange": session.get("exchange"),
            "status": session.get("status"),
            "last_updated": session.get("last_updated"),
        },
        "freshness": {
            "status": reliability.get("status"),
            "mode": reliability.get("mode"),
            "forecast_freshness_ready": reliability.get("forecast_freshness_ready"),
            "latest_candle_timestamp": candle.get("timestamp"),
        },
        "coverage": {
            "source_count": len(sources),
            "sampled_strike_count": len(strikes),
            "option_leg_count": len(instrument_keys),
        },
        "sources": sources,
        "snapshot_fingerprint": snapshot_fp,
        "completed_at": max(received_times).isoformat(),
    }
    canonical = json.dumps(manifest, sort_keys=True, separators=(",", ":")).encode("utf-8")
    manifest["manifest_sha256"] = hashlib.sha256(canonical).hexdigest()
    return manifest


def build_failure_manifest(stage, diagnostic_code, context=None):
    if not isinstance(stage, str) or not stage or len(stage) > 64:
        raise PipelineError("Failure stage invalid")
    if not isinstance(diagnostic_code, str) or not SAFE_DIAGNOSTIC_RE.fullmatch(diagnostic_code):
        raise PipelineError("Failure diagnostic invalid")
    safe_context = {}
    for key in ("github_run_id", "github_run_attempt", "github_sha", "github_event_name"):
        value = (context or {}).get(key)
        if value is not None:
            safe_context[key] = str(value)[:128]
    manifest = {
        "schema": SCHEMA,
        "status": "BLOCKED",
        "stage": stage,
        "diagnostic_code": diagnostic_code,
        "read_only": True,
        "trading_enabled": False,
        "production_5dr_write_enabled": False,
        "run_context": safe_context,
    }
    canonical = json.dumps(manifest, sort_keys=True, separators=(",", ":")).encode("utf-8")
    manifest["manifest_sha256"] = hashlib.sha256(canonical).hexdigest()
    return manifest
