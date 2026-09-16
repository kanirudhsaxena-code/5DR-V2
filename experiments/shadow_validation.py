"""Conservative G11 paired-shadow observation and multi-session review harness.

This module is deliberately observational. It records exact output differences between a
screenshot-assisted reference run and the structured-data shadow only when the two runs
share the same declared comparison window and evidence cutoff. It never invents an
acceptance threshold, changes 5DR methodology, publishes a forecast, writes lifecycle
state, or enables trading.
"""
from copy import deepcopy
from datetime import date
import re

from experiments.data_contract import DataArchitectureError
from experiments.shadow_pairing import assess_pair_comparability

PAIR_SCHEMA = "5dr-v2-2-3-g11-paired-observation-v1"
SERIES_SCHEMA = "5dr-v2-2-3-g11-validation-series-v1"
REQUIRED_SCENARIOS = ("BULL", "RANGE", "BEAR")
HEX64 = re.compile(r"^[0-9a-f]{64}$")


def _text(record, key, field):
    value = record.get(key) if isinstance(record, dict) else None
    if not isinstance(value, str) or not value.strip():
        raise DataArchitectureError(f"{field} {key} missing")
    return value.strip()


def _session_date(record, field):
    value = _text(record, "session_date_ist", field)
    try:
        date.fromisoformat(value)
    except ValueError as exc:
        raise DataArchitectureError(f"{field} session_date_ist invalid") from exc
    return value


def _fingerprint(record, field):
    value = _text(record, "evidence_fingerprint", field).lower()
    if not HEX64.fullmatch(value):
        raise DataArchitectureError(f"{field} evidence_fingerprint invalid")
    return value


def _engine_result(record, field):
    result = record.get("engine_result") if isinstance(record, dict) else None
    if not isinstance(result, dict):
        raise DataArchitectureError(f"{field} engine_result missing")
    for key in (
        "des5", "directional_label", "market_trust", "execution_edge",
        "probabilities", "tradeable",
    ):
        if key not in result:
            raise DataArchitectureError(f"{field} engine_result incomplete")
    probabilities = result.get("probabilities")
    if not isinstance(probabilities, dict) or any(name not in probabilities for name in REQUIRED_SCENARIOS):
        raise DataArchitectureError(f"{field} probabilities incomplete")
    try:
        float(result["des5"])
        float(result["market_trust"])
        float(result["execution_edge"])
        for name in REQUIRED_SCENARIOS:
            float(probabilities[name])
    except (TypeError, ValueError) as exc:
        raise DataArchitectureError(f"{field} numeric metric invalid") from exc
    if not isinstance(result["directional_label"], str) or not result["directional_label"].strip():
        raise DataArchitectureError(f"{field} directional_label invalid")
    if not isinstance(result["tradeable"], bool):
        raise DataArchitectureError(f"{field} tradeable invalid")
    return result


def _validate_capture(record, field, expected_source_mode):
    source_mode = _text(record, "source_mode", field)
    if source_mode != expected_source_mode:
        raise DataArchitectureError(f"{field} source_mode invalid")
    return {
        "source_mode": source_mode,
        "request_id": _text(record, "request_id", field),
        "comparison_window_id": _text(record, "comparison_window_id", field),
        "evidence_cutoff_ist": _text(record, "evidence_cutoff_ist", field),
        "session_date_ist": _session_date(record, field),
        "evidence_fingerprint": _fingerprint(record, field),
        "engine_result": _engine_result(record, field),
    }


def build_pair_observation(reference_record, structured_record):
    """Create one G11 observation without making any acceptance decision."""
    reference = _validate_capture(reference_record, "reference", "SCREENSHOT_ASSISTED")
    structured = _validate_capture(structured_record, "structured", "UPSTOX_STRUCTURED")
    comparability = assess_pair_comparability(reference, structured)

    reasons = list(comparability["reasons"])
    if reference["session_date_ist"] != structured["session_date_ist"]:
        reasons.append("SESSION_DATE_MISMATCH")
    comparable = not reasons

    reference_result = reference["engine_result"]
    structured_result = structured["engine_result"]
    reference_probs = reference_result["probabilities"]
    structured_probs = structured_result["probabilities"]

    comparison = {
        "directional_label_match": reference_result["directional_label"] == structured_result["directional_label"],
        "tradeable_semantics_match": reference_result["tradeable"] == structured_result["tradeable"],
        "des5_delta": round(float(structured_result["des5"]) - float(reference_result["des5"]), 6),
        "market_trust_delta": round(float(structured_result["market_trust"]) - float(reference_result["market_trust"]), 6),
        "execution_edge_delta": round(float(structured_result["execution_edge"]) - float(reference_result["execution_edge"]), 6),
        "probability_deltas": {
            name: round(float(structured_probs[name]) - float(reference_probs[name]), 6)
            for name in REQUIRED_SCENARIOS
        },
    }

    return {
        "schema": PAIR_SCHEMA,
        "status": "COMPARABLE_OBSERVATION" if comparable else "OBSERVATIONAL_ONLY",
        "acceptance_eligible": comparable,
        "acceptance_decision_made": False,
        "production_activation_decision_made": False,
        "session_date_ist": reference["session_date_ist"] if comparable else None,
        "comparison_window_id": reference["comparison_window_id"] if comparable else None,
        "evidence_cutoff_ist": reference["evidence_cutoff_ist"] if comparable else None,
        "reference_request_id": reference["request_id"],
        "structured_request_id": structured["request_id"],
        "reference_evidence_fingerprint": reference["evidence_fingerprint"],
        "structured_evidence_fingerprint": structured["evidence_fingerprint"],
        "reasons": reasons,
        "comparison": comparison,
        "methodology_changed": False,
        "production_5dr_write_enabled": False,
        "lifecycle_write_enabled": False,
        "trading_execution_enabled": False,
    }


def _pair_record(value):
    if not isinstance(value, dict) or value.get("schema") != PAIR_SCHEMA:
        raise DataArchitectureError("G11 pair observation invalid")
    if value.get("acceptance_decision_made") is not False or value.get("production_activation_decision_made") is not False:
        raise DataArchitectureError("G11 pair observation contains forbidden decision")
    for flag in ("methodology_changed", "production_5dr_write_enabled", "lifecycle_write_enabled", "trading_execution_enabled"):
        if value.get(flag) is not False:
            raise DataArchitectureError("G11 safety boundary crossed")
    comparison = value.get("comparison")
    if not isinstance(comparison, dict):
        raise DataArchitectureError("G11 comparison missing")
    return value


def summarize_validation_series(observations, required_distinct_sessions=3):
    """Summarize evidence across sessions; REVIEW_READY is not an acceptance verdict."""
    if not isinstance(required_distinct_sessions, int) or required_distinct_sessions < 2:
        raise DataArchitectureError("required_distinct_sessions invalid")
    if not isinstance(observations, list):
        raise DataArchitectureError("observations must be list")

    validated = [_pair_record(item) for item in observations]
    comparable = [item for item in validated if item.get("acceptance_eligible") is True]
    session_dates = [item.get("session_date_ist") for item in comparable]
    if any(not isinstance(value, str) for value in session_dates):
        raise DataArchitectureError("comparable observation session date missing")
    if len(set(session_dates)) != len(session_dates):
        raise DataArchitectureError("duplicate comparable trading session")

    comparisons = [item["comparison"] for item in comparable]
    max_abs = lambda key: max((abs(float(item[key])) for item in comparisons), default=None)
    probability_max_abs = {
        name: max((abs(float(item["probability_deltas"][name])) for item in comparisons), default=None)
        for name in REQUIRED_SCENARIOS
    }
    distinct_sessions = len(set(session_dates))
    review_ready = distinct_sessions >= required_distinct_sessions

    return {
        "schema": SERIES_SCHEMA,
        "status": "REVIEW_READY" if review_ready else "EVIDENCE_COLLECTION_INCOMPLETE",
        "required_distinct_sessions": required_distinct_sessions,
        "total_observations": len(validated),
        "comparable_observations": len(comparable),
        "observational_only_count": len(validated) - len(comparable),
        "distinct_comparable_sessions": distinct_sessions,
        "session_dates_ist": sorted(set(session_dates)),
        "directional_label_matches": sum(1 for item in comparisons if item["directional_label_match"] is True),
        "tradeable_semantics_matches": sum(1 for item in comparisons if item["tradeable_semantics_match"] is True),
        "max_abs_des5_delta": max_abs("des5_delta"),
        "max_abs_market_trust_delta": max_abs("market_trust_delta"),
        "max_abs_execution_edge_delta": max_abs("execution_edge_delta"),
        "max_abs_probability_deltas": probability_max_abs,
        "acceptance_decision_made": False,
        "production_activation_decision_made": False,
        "methodology_changed": False,
        "note": "REVIEW_READY means the conservative observation count is satisfied; it is not a pass/fail or production-activation decision.",
        "observations": deepcopy(validated),
    }
