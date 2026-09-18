"""Provider-neutral normalized evidence contract for 5DR / EDGE data acquisition.

This module contains no network access, broker/account actions, scoring, forecasting,
or production persistence. Providers are adapters; consumers depend on this contract.
"""
import hashlib
import json
import re
from copy import deepcopy
from datetime import datetime, timezone


class DataArchitectureError(ValueError):
    pass


SCHEMA_VERSION = "market-evidence-data-contract-v1"
USABLE_FRESHNESS = {
    "LIVE", "DELAYED_20S", "DELAYED_120S", "DELAYED_15M",
    "SESSION_FINAL", "HISTORICAL",
}
ALL_FRESHNESS = USABLE_FRESHNESS | {"STALE", "UNAVAILABLE"}
VALIDATION_STATES = {"VALID", "REJECTED"}
SUBJECT_KINDS = {"MARKET_INSTRUMENT", "STOCK", "IPO", "MACRO", "INSTITUTIONAL"}
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
ID_RE = re.compile(r"^[A-Z0-9][A-Z0-9_.:-]{1,79}$")


def _nonempty(value, field):
    if not isinstance(value, str) or not value.strip():
        raise DataArchitectureError(f"{field} missing")
    return value.strip()


def _utc(value, field):
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value)
        except ValueError:
            raise DataArchitectureError(f"{field} timestamp invalid") from None
    else:
        raise DataArchitectureError(f"{field} timestamp missing")
    if parsed.tzinfo is None:
        raise DataArchitectureError(f"{field} timestamp naive")
    return parsed.astimezone(timezone.utc)


def _subject(subject):
    if not isinstance(subject, dict):
        raise DataArchitectureError("subject missing")
    kind = subject.get("kind")
    if kind not in SUBJECT_KINDS:
        raise DataArchitectureError("subject kind invalid")
    stable_id = _nonempty(subject.get("id"), "subject id")
    name = _nonempty(subject.get("name"), "subject name")
    out = {"kind": kind, "id": stable_id, "name": name}
    for key in ("exchange", "segment", "instrument_key", "symbol", "isin"):
        value = subject.get(key)
        if value is not None:
            out[key] = _nonempty(value, f"subject {key}")
    return out


def build_record(*, provider_id, source_semantic, variable_id, consumer,
                 subject, metric, values, timeframe, provider_timestamp,
                 acquisition_timestamp, freshness_status, source_reference,
                 source_sha256, provider_latency_seconds=None,
                 validation_status="VALID", missing_fields=None,
                 schema_version=SCHEMA_VERSION):
    provider_id = _nonempty(provider_id, "provider id").upper()
    source_semantic = _nonempty(source_semantic, "source semantic").upper()
    variable_id = _nonempty(variable_id, "variable id").upper()
    consumer = _nonempty(consumer, "consumer").upper()
    metric = _nonempty(metric, "metric")
    source_reference = _nonempty(source_reference, "source reference")
    if not ID_RE.fullmatch(provider_id) or not ID_RE.fullmatch(source_semantic):
        raise DataArchitectureError("provider/source semantic id invalid")
    if validation_status not in VALIDATION_STATES:
        raise DataArchitectureError("validation status invalid")
    if freshness_status not in ALL_FRESHNESS:
        raise DataArchitectureError("freshness status invalid")
    if not isinstance(values, dict):
        raise DataArchitectureError("values missing")
    if not isinstance(source_sha256, str) or not SHA256_RE.fullmatch(source_sha256):
        raise DataArchitectureError("source digest invalid")
    if timeframe is not None and (not isinstance(timeframe, str) or not timeframe.strip()):
        raise DataArchitectureError("timeframe invalid")
    if provider_latency_seconds is not None:
        if isinstance(provider_latency_seconds, bool) or not isinstance(provider_latency_seconds, (int, float)) or provider_latency_seconds < 0:
            raise DataArchitectureError("provider latency invalid")
    missing = list(missing_fields or [])
    if any(not isinstance(item, str) or not item for item in missing) or len(missing) != len(set(missing)):
        raise DataArchitectureError("missing fields invalid")

    acquired = _utc(acquisition_timestamp, "acquisition")
    provider = _utc(provider_timestamp, "provider") if provider_timestamp is not None else None
    if provider is not None and (provider - acquired).total_seconds() > 60:
        raise DataArchitectureError("provider timestamp future")
    if validation_status == "VALID":
        if missing:
            raise DataArchitectureError("valid record cannot have missing fields")
        if freshness_status not in USABLE_FRESHNESS:
            raise DataArchitectureError("valid record cannot be stale/unavailable")
        if provider is None and freshness_status not in {"SESSION_FINAL", "HISTORICAL"}:
            raise DataArchitectureError("current record provider timestamp missing")

    record = {
        "schema_version": schema_version,
        "provider_id": provider_id,
        "source_semantic": source_semantic,
        "variable_id": variable_id,
        "consumer": consumer,
        "subject": _subject(subject),
        "metric": metric,
        "timeframe": timeframe.strip() if isinstance(timeframe, str) else None,
        "values": deepcopy(values),
        "provider_timestamp": provider.isoformat() if provider else None,
        "acquisition_timestamp": acquired.isoformat(),
        "provider_latency_seconds": provider_latency_seconds,
        "freshness_status": freshness_status,
        "validation_status": validation_status,
        "missing_fields": missing,
        "source_reference": source_reference,
        "source_sha256": source_sha256,
        "eligible_for_consumer": validation_status == "VALID" and freshness_status in USABLE_FRESHNESS and not missing,
    }
    stable = deepcopy(record)
    stable.pop("acquisition_timestamp")
    payload = json.dumps(stable, sort_keys=True, separators=(",", ":"), default=str).encode()
    record["record_fingerprint"] = hashlib.sha256(payload).hexdigest()
    return record
