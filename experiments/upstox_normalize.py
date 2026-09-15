"""Normalized 5DR quantitative evidence contract for authenticated Upstox observations.

This contract is intentionally upstream of all 5DR reasoning. It never scores,
forecasts, recommends, writes Neon, or performs broker/account actions.
"""
import hashlib
import json
import re
from copy import deepcopy

from experiments.upstox_quality import ALL_CLASSES, USABLE_CLASSES, aware_utc
from phase1.upstox import PipelineError

SCHEMA_VERSION = "5dr-upstox-quant-evidence-v1"
SOURCE_SEMANTIC = "UPSTOX_AUTHENTICATED"
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
VALIDATION_STATES = {"VALID", "REJECTED"}


def _nonempty(value, field):
    if not isinstance(value, str) or not value.strip():
        raise PipelineError(f"{field} missing")
    return value.strip()


def _instrument(value):
    if not isinstance(value, dict):
        raise PipelineError("Instrument identity missing")
    required = ("name", "exchange", "segment", "instrument_key", "trading_symbol")
    out = {}
    for field in required:
        out[field] = _nonempty(value.get(field), f"instrument {field}")
    optional = ("expiry", "strike", "option_type", "underlying_key", "country")
    for field in optional:
        if value.get(field) is not None:
            out[field] = value[field]
    return out


def _latency(value):
    if not isinstance(value, dict):
        raise PipelineError("Latency metadata missing")
    classification = value.get("classification")
    if classification not in ALL_CLASSES:
        raise PipelineError("Latency classification invalid")
    seconds = value.get("seconds")
    if seconds is not None:
        if isinstance(seconds, bool) or not isinstance(seconds, (int, float)) or seconds < 0:
            raise PipelineError("Latency seconds invalid")
    declared = value.get("declared")
    if declared is not None and not isinstance(declared, str):
        raise PipelineError("Declared latency invalid")
    return {"classification": classification, "seconds": seconds, "declared": declared}


def build_observation(*, run_id, instrument, observation_type, values,
                      provider_timestamp, acquisition_timestamp, market_session,
                      source_endpoint, raw_response_sha256, latency,
                      freshness_classification, validation_status="VALID",
                      missing_fields=None, schema_version=SCHEMA_VERSION):
    run_id = _nonempty(run_id, "run id")
    observation_type = _nonempty(observation_type, "observation type")
    market_session = _nonempty(market_session, "market session")
    source_endpoint = _nonempty(source_endpoint, "source endpoint")
    if not (source_endpoint.startswith("/") or source_endpoint.startswith("https://")):
        raise PipelineError("Source endpoint invalid")
    if not isinstance(raw_response_sha256, str) or not SHA256_RE.fullmatch(raw_response_sha256):
        raise PipelineError("Raw response digest invalid")
    if validation_status not in VALIDATION_STATES:
        raise PipelineError("Validation status invalid")
    if freshness_classification not in ALL_CLASSES:
        raise PipelineError("Freshness classification invalid")
    if not isinstance(values, dict):
        raise PipelineError("Observation values missing")
    if not isinstance(missing_fields, (list, tuple, type(None))):
        raise PipelineError("Missing-field list invalid")
    missing_fields = list(missing_fields or [])
    if any(not isinstance(field, str) or not field for field in missing_fields):
        raise PipelineError("Missing-field entry invalid")
    if len(missing_fields) != len(set(missing_fields)):
        raise PipelineError("Duplicate missing field")

    acquired = aware_utc(acquisition_timestamp, "acquisition")
    provider = None
    if provider_timestamp is not None:
        provider = aware_utc(provider_timestamp, "provider")

    latency_meta = _latency(latency)
    if freshness_classification != latency_meta["classification"] and freshness_classification not in {"STALE", "UNAVAILABLE"}:
        raise PipelineError("Freshness and latency classification mismatch")
    if validation_status == "VALID":
        if missing_fields:
            raise PipelineError("Valid observation cannot have missing fields")
        if freshness_classification not in USABLE_CLASSES:
            raise PipelineError("Valid observation cannot be stale or unavailable")
        if provider is None and freshness_classification not in {"SESSION_FINAL", "HISTORICAL"}:
            raise PipelineError("Current observation provider timestamp missing")

    instrument_meta = _instrument(instrument)
    observation = {
        "schema_version": schema_version,
        "source_semantic": SOURCE_SEMANTIC,
        "run_id": run_id,
        "instrument": instrument_meta,
        "observation_type": observation_type,
        "provider_timestamp": provider.isoformat() if provider else None,
        "acquisition_timestamp": acquired.isoformat(),
        "market_session": market_session,
        "provider_latency": latency_meta,
        "source_endpoint": source_endpoint,
        "raw_response_sha256": raw_response_sha256,
        "values": deepcopy(values),
        "freshness_status": freshness_classification,
        "validation_status": validation_status,
        "missing_field_status": "MISSING_FIELDS" if missing_fields else "COMPLETE",
        "missing_fields": missing_fields,
        "eligible_for_5dr_quantitative_evidence": (
            validation_status == "VALID"
            and freshness_classification in USABLE_CLASSES
            and not missing_fields
        ),
    }
    stable = deepcopy(observation)
    stable.pop("acquisition_timestamp")
    encoded = json.dumps(stable, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    observation["observation_fingerprint"] = hashlib.sha256(encoded).hexdigest()
    return observation


def rejected_observation(**kwargs):
    kwargs = dict(kwargs)
    kwargs["validation_status"] = "REJECTED"
    kwargs.setdefault("freshness_classification", "UNAVAILABLE")
    return build_observation(**kwargs)
