"""Point-in-time evidence boundary for BT100 replay.

Forecast construction may consume only evidence that was both observed and available
no later than the replay cutoff. Outcome evidence is forbidden in forecast manifests.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime


class LeakageError(ValueError):
    pass


FORECAST_ROLES = {"PRICE_STRUCTURE", "PVPO", "PARTICIPATION", "MACRO_CATALYSTS", "EXECUTION_EDGE"}
FORBIDDEN_FORECAST_ROLES = {"OUTCOME", "EFFICACY", "FUTURE_PRICE", "POST_CUTOFF"}


def _aware(stamp, field):
    if not isinstance(stamp, str) or not stamp:
        raise LeakageError(f"{field} missing")
    value = datetime.fromisoformat(stamp)
    if value.tzinfo is None:
        raise LeakageError(f"{field} must be timezone-aware")
    return value


def validate_record(record, cutoff):
    if not isinstance(record, dict):
        raise LeakageError("evidence record invalid")
    cutoff_dt = _aware(cutoff, "cutoff")
    observed = _aware(record.get("observed_at"), "observed_at")
    available = _aware(record.get("available_at"), "available_at")
    role = record.get("role")
    if role in FORBIDDEN_FORECAST_ROLES:
        raise LeakageError(f"forbidden forecast evidence role: {role}")
    if role not in FORECAST_ROLES:
        raise LeakageError(f"unknown forecast evidence role: {role}")
    if observed > cutoff_dt:
        raise LeakageError("evidence observed after cutoff")
    if available > cutoff_dt:
        raise LeakageError("evidence available after cutoff")
    if not isinstance(record.get("source_ref"), str) or not record["source_ref"].strip():
        raise LeakageError("source_ref missing")
    if not isinstance(record.get("content_sha256"), str) or len(record["content_sha256"]) != 64:
        raise LeakageError("content_sha256 invalid")
    return True


def freeze_manifest(records, cutoff):
    if not isinstance(records, list) or not records:
        raise LeakageError("evidence manifest empty")
    for record in records:
        validate_record(record, cutoff)
    normalized = sorted(
        records,
        key=lambda row: (row["role"], row["available_at"], row["source_ref"], row["content_sha256"]),
    )
    payload = {
        "schema": "bt100-evidence-manifest-v1",
        "cutoff": cutoff,
        "records": normalized,
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    payload["manifest_sha256"] = hashlib.sha256(encoded).hexdigest()
    return payload
