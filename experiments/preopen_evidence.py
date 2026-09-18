"""Fail-closed PREOPEN evidence contract for 5DR V2.2.3.

This module validates only evidence identity/freshness/provenance. It does not score,
forecast, publish, write lifecycle/canonical state, call broker trading endpoints, or trade.
"""
import hashlib
import json
import re
from copy import deepcopy
from datetime import date, datetime, timedelta, timezone

from experiments.consumer_namespace import consumer_namespace
from experiments.data_contract import DataArchitectureError
from experiments.web_context import validate_web_context_item

SCHEMA = "5dr-preopen-evidence-bundle-v1"
HEX64 = re.compile(r"^[0-9a-f]{64}$")
REQUIRED_OVERNIGHT_VARIABLES = frozenset({
    "GLOBAL_RISK_INDICES",
    "CRUDE_USDINR",
})
REQUIRED_EXTERNAL_CATEGORIES = frozenset({
    "DXY_RATES",
    "MACRO_EVENTS_GEOPOLITICS",
})
SUBJECT_BY_VARIABLE = {
    "NIFTY_PRICE_CANDLES": "NIFTY_50",
    "GLOBAL_RISK_INDICES": "GLOBAL_RISK_INDICES",
    "CRUDE_USDINR": "CRUDE_USDINR",
}


def _date(value, field):
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
    return parsed.astimezone(timezone.utc)


def _hex(value, field):
    if not isinstance(value, str) or not HEX64.fullmatch(value.lower()):
        raise DataArchitectureError(f"{field} invalid")
    return value.lower()


def _record_identity(record, variable_id):
    if not isinstance(record, dict):
        raise DataArchitectureError(f"{variable_id} record invalid")
    if record.get("consumer") != "5DR":
        raise DataArchitectureError("preopen cross-consumer contamination")
    if record.get("variable_id") != variable_id:
        raise DataArchitectureError(f"{variable_id} identity mismatch")
    subject = record.get("subject")
    if not isinstance(subject, dict) or subject.get("id") != SUBJECT_BY_VARIABLE[variable_id]:
        raise DataArchitectureError(f"{variable_id} subject mismatch")
    if record.get("eligible_for_consumer") is not True:
        raise DataArchitectureError(f"{variable_id} record ineligible")
    _hex(record.get("record_fingerprint"), f"{variable_id} fingerprint")
    _hex(record.get("source_sha256"), f"{variable_id} source sha")
    return record


def _validate_prior_close(record, previous_session):
    record = _record_identity(record, "NIFTY_PRICE_CANDLES")
    if record.get("freshness_status") != "SESSION_FINAL":
        raise DataArchitectureError("preopen prior close must be SESSION_FINAL")
    provider = _aware(record.get("provider_timestamp"), "prior close provider timestamp")
    if provider.date() != previous_session:
        raise DataArchitectureError("preopen prior close session mismatch")
    values = record.get("values")
    if not isinstance(values, dict) or not isinstance(values.get("close"), (int, float)):
        raise DataArchitectureError("preopen prior close value missing")
    return record


def _validate_overnight(record, variable_id, frozen_at, previous_session,
                        max_age_seconds):
    record = _record_identity(record, variable_id)
    provider = _aware(record.get("provider_timestamp"), f"{variable_id} provider timestamp")
    acquired = _aware(record.get("acquisition_timestamp"), f"{variable_id} acquisition timestamp")
    if provider.date() < previous_session:
        raise DataArchitectureError(f"{variable_id} is older than previous session")
    if acquired > frozen_at + timedelta(seconds=60):
        raise DataArchitectureError(f"{variable_id} acquisition is in the future")
    age = (frozen_at - acquired).total_seconds()
    if age < 0 or age > max_age_seconds:
        raise DataArchitectureError(f"{variable_id} stale for preopen")
    if record.get("freshness_status") not in {
        "LIVE", "DELAYED_20S", "DELAYED_120S", "DELAYED_15M"
    }:
        raise DataArchitectureError(f"{variable_id} freshness invalid for preopen")
    return record


def _validate_external(item, frozen_at, max_age_seconds):
    validated = validate_web_context_item(
        item,
        frozen_at=frozen_at,
        max_age_seconds=max_age_seconds,
    )
    if validated["category"] not in REQUIRED_EXTERNAL_CATEGORIES:
        raise DataArchitectureError("preopen external category invalid")
    return validated


def build_preopen_evidence_bundle(*, target_session_date, previous_session_date,
                                  frozen_at, prior_close_record,
                                  overnight_records, external_evidence,
                                  active_expiry, run_id,
                                  completed_run_keys=(),
                                  overnight_max_age_seconds=1800,
                                  external_max_age_seconds=1800):
    target = _date(target_session_date, "target session date")
    previous = _date(previous_session_date, "previous session date")
    if previous >= target:
        raise DataArchitectureError("preopen session ordering invalid")
    frozen = _aware(frozen_at, "preopen freeze")
    if frozen.date() != target:
        raise DataArchitectureError("preopen freeze not bound to target session")
    if not isinstance(run_id, str) or not run_id.strip():
        raise DataArchitectureError("preopen run id invalid")
    if not isinstance(active_expiry, str):
        raise DataArchitectureError("preopen expiry invalid")
    expiry = _date(active_expiry, "preopen expiry")
    if expiry < target:
        raise DataArchitectureError("preopen derivative expiry stale")
    run_key = f"5DR:{target.isoformat()}:PREOPEN"
    if not isinstance(completed_run_keys, (list, tuple, set, frozenset)):
        raise DataArchitectureError("preopen completed run keys invalid")
    if run_key in completed_run_keys:
        raise DataArchitectureError("preopen duplicate run blocked")

    prior_close = _validate_prior_close(prior_close_record, previous)
    if not isinstance(overnight_records, (list, tuple)):
        raise DataArchitectureError("preopen overnight records invalid")
    by_variable = {}
    for record in overnight_records:
        variable_id = record.get("variable_id") if isinstance(record, dict) else None
        if variable_id in by_variable:
            raise DataArchitectureError("preopen duplicate overnight variable")
        if variable_id not in REQUIRED_OVERNIGHT_VARIABLES:
            raise DataArchitectureError("preopen unexpected overnight variable")
        by_variable[variable_id] = _validate_overnight(
            record, variable_id, frozen, previous, overnight_max_age_seconds
        )
    missing_overnight = sorted(REQUIRED_OVERNIGHT_VARIABLES - set(by_variable))
    if missing_overnight:
        raise DataArchitectureError(f"preopen overnight variables missing: {missing_overnight}")

    if not isinstance(external_evidence, (list, tuple)):
        raise DataArchitectureError("preopen external evidence invalid")
    external = [_validate_external(item, frozen, external_max_age_seconds)
                for item in external_evidence]
    categories = {item["category"] for item in external}
    missing_external = sorted(REQUIRED_EXTERNAL_CATEGORIES - categories)
    if missing_external:
        raise DataArchitectureError(f"preopen external categories missing: {missing_external}")
    fingerprints = [item["research_sha256"] for item in external]
    if len(fingerprints) != len(set(fingerprints)):
        raise DataArchitectureError("preopen duplicate external evidence")

    provenance = [{
        "kind": "PRIOR_SESSION_CLOSE",
        "variable_id": prior_close["variable_id"],
        "record_fingerprint": prior_close["record_fingerprint"],
        "source_sha256": prior_close["source_sha256"],
    }]
    for variable_id in sorted(by_variable):
        record = by_variable[variable_id]
        provenance.append({
            "kind": "OVERNIGHT_MARKET",
            "variable_id": variable_id,
            "record_fingerprint": record["record_fingerprint"],
            "source_sha256": record["source_sha256"],
        })
    for item in sorted(external, key=lambda x: (x["category"], x["source_reference"])):
        provenance.append({
            "kind": "EXTERNAL_CONTEXT",
            "category": item["category"],
            "source_reference": item["source_reference"],
            "source_sha256": item["source_sha256"],
            "research_sha256": item["research_sha256"],
        })

    bundle = {
        "schema": SCHEMA,
        "consumer": "5DR",
        "subject": {"kind": "MARKET_INSTRUMENT", "id": "NIFTY_50", "name": "NIFTY 50"},
        "namespace": consumer_namespace("5DR", "NIFTY_50"),
        "run_id": run_id.strip(),
        "run_key": run_key,
        "target_session_date": target.isoformat(),
        "previous_session_date": previous.isoformat(),
        "frozen_at": frozen.isoformat(),
        "active_derivative_expiry": expiry.isoformat(),
        "status": "READY",
        "prior_close_record": deepcopy(prior_close),
        "overnight_records": [deepcopy(by_variable[key]) for key in sorted(by_variable)],
        "external_evidence": external,
        "provenance": provenance,
        "session_checks": {
            "target_date_bound": True,
            "previous_session_bound": True,
            "active_expiry_current": True,
            "duplicate_guard_passed": True,
        },
        "side_effects": {
            "forecast_release_enabled": False,
            "production_5dr_write_enabled": False,
            "lifecycle_write_enabled": False,
            "trading_enabled": False,
            "canonical_integration_enabled": False,
            "methodology_changed": False,
        },
    }
    encoded = json.dumps(bundle, sort_keys=True, separators=(",", ":"), default=str).encode()
    bundle["bundle_sha256"] = hashlib.sha256(encoded).hexdigest()
    return bundle


def verify_preopen_evidence_bundle(bundle):
    if not isinstance(bundle, dict) or bundle.get("schema") != SCHEMA:
        raise DataArchitectureError("preopen bundle schema invalid")
    digest = _hex(bundle.get("bundle_sha256"), "preopen bundle fingerprint")
    body = {k: v for k, v in bundle.items() if k != "bundle_sha256"}
    expected = hashlib.sha256(
        json.dumps(body, sort_keys=True, separators=(",", ":"), default=str).encode()
    ).hexdigest()
    if expected != digest:
        raise DataArchitectureError("preopen bundle fingerprint mismatch")
    if bundle.get("status") != "READY":
        raise DataArchitectureError("preopen bundle not READY")
    if bundle.get("consumer") != "5DR" or bundle.get("namespace") != "5DR:NIFTY_50":
        raise DataArchitectureError("preopen bundle identity invalid")
    side_effects = bundle.get("side_effects")
    if not isinstance(side_effects, dict) or any(value is not False for value in side_effects.values()):
        raise DataArchitectureError("preopen bundle crossed governance boundary")
    return {
        "status": "PREOPEN_EVIDENCE_READY",
        "run_key": bundle["run_key"],
        "target_session_date": bundle["target_session_date"],
        "bundle_sha256": digest,
    }
