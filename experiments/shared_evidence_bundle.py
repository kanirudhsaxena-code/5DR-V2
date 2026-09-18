"""Consumer-aware frozen evidence bundle for the shared MDOS data backbone.

The shared bundle contains facts/evidence only. It does not score, forecast, recommend,
write canonical lifecycle state, call a broker, or trade. Existing 5DR production
bundles remain valid and unchanged while consumers migrate through a separate gate.
"""
import hashlib
import json
import re
from copy import deepcopy
from datetime import datetime, timezone

from experiments.consumer_namespace import consumer_namespace, normalize_consumer
from experiments.data_contract import DataArchitectureError
from experiments.data_requirements import requirements

SCHEMA = "shared-frozen-evidence-bundle-v1"
RECORD_SCHEMA = "market-evidence-data-contract-v1"
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
USABLE_EXTERNAL_SEMANTICS = frozenset({
    "WEB_RESEARCH", "OFFICIAL_WEB", "EXCHANGE", "REGULATORY",
    "REGISTRAR", "BROKER_RESEARCH", "SPECIALIST_SECONDARY",
})


def _aware_utc(value, field):
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value)
        except ValueError:
            raise DataArchitectureError(f"{field} invalid") from None
    else:
        raise DataArchitectureError(f"{field} missing")
    if parsed.tzinfo is None:
        raise DataArchitectureError(f"{field} naive")
    return parsed.astimezone(timezone.utc)


def _subject(subject):
    if not isinstance(subject, dict):
        raise DataArchitectureError("bundle subject invalid")
    out = {}
    for field in ("kind", "id", "name"):
        value = subject.get(field)
        if not isinstance(value, str) or not value.strip():
            raise DataArchitectureError(f"bundle subject {field} invalid")
        out[field] = value.strip()
    for field in ("exchange", "segment", "instrument_key", "symbol", "isin"):
        value = subject.get(field)
        if value is not None:
            if not isinstance(value, str) or not value.strip():
                raise DataArchitectureError(f"bundle subject {field} invalid")
            out[field] = value.strip()
    return out


def _consumer_variables(consumer):
    return {row["variable_id"] for row in requirements(consumer)}


def _validate_required_variables(consumer, required_variables):
    if required_variables is None:
        return ()
    if not isinstance(required_variables, (list, tuple, set, frozenset)):
        raise DataArchitectureError("required variable set invalid")
    values = tuple(sorted(set(required_variables)))
    if any(not isinstance(value, str) or not value for value in values):
        raise DataArchitectureError("required variable id invalid")
    unknown = sorted(set(values) - _consumer_variables(consumer))
    if unknown:
        raise DataArchitectureError(f"required variables outside consumer registry: {unknown}")
    return values


def _validate_record(record, *, consumer, subject_id):
    if not isinstance(record, dict) or record.get("schema_version") != RECORD_SCHEMA:
        raise DataArchitectureError("evidence record schema invalid")
    if record.get("consumer") != consumer:
        raise DataArchitectureError("cross-consumer evidence contamination")
    if record.get("eligible_for_consumer") is not True:
        raise DataArchitectureError("ineligible record in shared bundle")
    subject = record.get("subject")
    if not isinstance(subject, dict) or subject.get("id") != subject_id:
        raise DataArchitectureError("cross-subject evidence contamination")
    fingerprint = record.get("record_fingerprint")
    if not isinstance(fingerprint, str) or not SHA256_RE.fullmatch(fingerprint):
        raise DataArchitectureError("evidence record fingerprint invalid")
    variable_id = record.get("variable_id")
    if variable_id not in _consumer_variables(consumer):
        raise DataArchitectureError("evidence variable outside consumer registry")
    source_semantic = record.get("source_semantic")
    source_reference = record.get("source_reference")
    source_sha = record.get("source_sha256")
    if not isinstance(source_semantic, str) or not source_semantic:
        raise DataArchitectureError("evidence source semantic invalid")
    if not isinstance(source_reference, str) or not source_reference:
        raise DataArchitectureError("evidence source reference invalid")
    if not isinstance(source_sha, str) or not SHA256_RE.fullmatch(source_sha):
        raise DataArchitectureError("evidence source digest invalid")
    return {
        "variable_id": variable_id,
        "fingerprint": fingerprint,
        "source_semantic": source_semantic,
        "source_reference": source_reference,
        "source_sha256": source_sha,
    }


def _validate_external(item):
    if not isinstance(item, dict):
        raise DataArchitectureError("external evidence invalid")
    category = item.get("category")
    semantic = item.get("source_semantic")
    reference = item.get("source_reference")
    digest = item.get("source_sha256")
    if not isinstance(category, str) or not category.strip():
        raise DataArchitectureError("external evidence category invalid")
    if not isinstance(semantic, str) or not semantic.strip():
        raise DataArchitectureError("external evidence semantic invalid")
    semantic = semantic.strip().upper()
    if semantic not in USABLE_EXTERNAL_SEMANTICS:
        raise DataArchitectureError("external evidence semantic invalid")
    if not isinstance(reference, str) or not reference.strip():
        raise DataArchitectureError("external evidence reference invalid")
    if not isinstance(digest, str) or not SHA256_RE.fullmatch(digest):
        raise DataArchitectureError("external evidence digest invalid")
    retrieved = _aware_utc(item.get("retrieved_at"), "external evidence retrieval")
    if item.get("validation_status") != "VALID":
        raise DataArchitectureError("external evidence is not validated")
    return {
        "category": category.strip().upper(),
        "source_semantic": semantic,
        "source_reference": reference.strip(),
        "source_sha256": digest,
        "retrieved_at": retrieved.isoformat(),
    }


def build_shared_evidence_bundle(*, consumer, subject, run_id, frozen_at,
                                 quantitative_records=(), external_evidence=(),
                                 derived_evidence=None, required_variables=None,
                                 required_external_categories=(),
                                 require_screenshot_free=True):
    consumer = normalize_consumer(consumer)
    subject = _subject(subject)
    if not isinstance(run_id, str) or not run_id.strip():
        raise DataArchitectureError("evidence bundle run id invalid")
    frozen = _aware_utc(frozen_at, "evidence freeze")
    if not isinstance(quantitative_records, (list, tuple)):
        raise DataArchitectureError("quantitative evidence list invalid")
    if not isinstance(external_evidence, (list, tuple)):
        raise DataArchitectureError("external evidence list invalid")
    if not isinstance(require_screenshot_free, bool):
        raise DataArchitectureError("screenshot-free gate invalid")

    required_variables = _validate_required_variables(consumer, required_variables)
    record_meta = [
        _validate_record(record, consumer=consumer, subject_id=subject["id"])
        for record in quantitative_records
    ]
    fingerprints = [row["fingerprint"] for row in record_meta]
    if len(fingerprints) != len(set(fingerprints)):
        raise DataArchitectureError("duplicate quantitative evidence record")
    variables_present = {row["variable_id"] for row in record_meta}
    missing_variables = sorted(set(required_variables) - variables_present)

    external = [_validate_external(item) for item in external_evidence]
    external_categories = {item["category"] for item in external}
    if not isinstance(required_external_categories, (list, tuple, set, frozenset)):
        raise DataArchitectureError("required external categories invalid")
    required_external = {
        str(value).strip().upper()
        for value in required_external_categories
        if str(value).strip()
    }
    missing_external = sorted(required_external - external_categories)

    screenshot_semantics = sorted({
        row["source_semantic"] for row in record_meta if "SCREENSHOT" in row["source_semantic"]
    })
    screenshot_dependency = bool(screenshot_semantics)
    blocked_reasons = []
    if missing_variables:
        blocked_reasons.append("MISSING_REQUIRED_VARIABLES")
    if missing_external:
        blocked_reasons.append("MISSING_EXTERNAL_CONTEXT")
    if require_screenshot_free and screenshot_dependency:
        blocked_reasons.append("SCREENSHOT_DEPENDENCY_PRESENT")

    provenance = [
        {
            "kind": "QUANTITATIVE_RECORD",
            "variable_id": row["variable_id"],
            "record_fingerprint": row["fingerprint"],
            "source_semantic": row["source_semantic"],
            "source_reference": row["source_reference"],
            "source_sha256": row["source_sha256"],
        }
        for row in sorted(record_meta, key=lambda x: (x["variable_id"], x["fingerprint"]))
    ]
    provenance.extend(
        {
            "kind": "EXTERNAL_EVIDENCE",
            "category": item["category"],
            "source_semantic": item["source_semantic"],
            "source_reference": item["source_reference"],
            "source_sha256": item["source_sha256"],
            "retrieved_at": item["retrieved_at"],
        }
        for item in sorted(external, key=lambda x: (x["category"], x["source_reference"]))
    )

    bundle = {
        "schema": SCHEMA,
        "consumer": consumer,
        "subject": subject,
        "namespace": consumer_namespace(consumer, subject["id"]),
        "run_id": run_id.strip(),
        "frozen_at": frozen.isoformat(),
        "status": "READY" if not blocked_reasons else "BLOCKED",
        "blocked_reasons": blocked_reasons,
        "quantitative_records": deepcopy(list(quantitative_records)),
        "derived_evidence": deepcopy(derived_evidence),
        "external_evidence": external,
        "coverage": {
            "required_variables": list(required_variables),
            "variables_present": sorted(variables_present),
            "missing_variables": missing_variables,
            "required_external_categories": sorted(required_external),
            "external_categories_present": sorted(external_categories),
            "missing_external_categories": missing_external,
        },
        "provenance": provenance,
        "screenshot_policy": {
            "require_screenshot_free": require_screenshot_free,
            "screenshot_dependency": screenshot_dependency,
            "screenshot_semantics": screenshot_semantics,
        },
        "methodology_applied": False,
        "directional_score_assigned": False,
        "forecast_released": False,
        "lifecycle_write_enabled": False,
        "trading_enabled": False,
    }
    encoded = json.dumps(bundle, sort_keys=True, separators=(",", ":"), default=str).encode()
    bundle["bundle_sha256"] = hashlib.sha256(encoded).hexdigest()
    return bundle


def verify_shared_evidence_bundle(bundle):
    if not isinstance(bundle, dict) or bundle.get("schema") != SCHEMA:
        raise DataArchitectureError("shared bundle schema invalid")
    consumer = normalize_consumer(bundle.get("consumer"))
    subject = _subject(bundle.get("subject"))
    if bundle.get("namespace") != consumer_namespace(consumer, subject["id"]):
        raise DataArchitectureError("shared bundle namespace mismatch")
    digest = bundle.get("bundle_sha256")
    if not isinstance(digest, str) or not SHA256_RE.fullmatch(digest):
        raise DataArchitectureError("shared bundle digest invalid")
    body = {key: value for key, value in bundle.items() if key != "bundle_sha256"}
    encoded = json.dumps(body, sort_keys=True, separators=(",", ":"), default=str).encode()
    if hashlib.sha256(encoded).hexdigest() != digest:
        raise DataArchitectureError("shared bundle fingerprint mismatch")
    for record in bundle.get("quantitative_records", []):
        _validate_record(record, consumer=consumer, subject_id=subject["id"])
    for flag in (
        "methodology_applied", "directional_score_assigned", "forecast_released",
        "lifecycle_write_enabled", "trading_enabled",
    ):
        if bundle.get(flag) is not False:
            raise DataArchitectureError("shared bundle crossed intelligence/execution boundary")
    return {
        "consumer": consumer,
        "subject_id": subject["id"],
        "run_id": bundle.get("run_id"),
        "status": bundle.get("status"),
        "bundle_sha256": digest,
        "namespace": bundle.get("namespace"),
    }
