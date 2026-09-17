"""Conservative G11 paired-shadow observation and same-session review harness.

Three distinct manual run ids from one live NSE session can satisfy the primary migration
evidence count. Screenshot and structured records may differ slightly in timestamp but
must share the same manual comparison id and remain inside the approved tolerance.
A separate next-session rollover validation covers stale prior-day/session-transition risk.
No acceptance or production decision is made automatically.
"""
from copy import deepcopy
from datetime import date
import re

from experiments.data_contract import DataArchitectureError
from experiments.shadow_pairing import assess_pair_comparability

PAIR_SCHEMA = "5dr-v2-2-3-g11-paired-observation-v2"
SERIES_SCHEMA = "5dr-v2-2-3-g11-validation-series-v2"
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
    for key in ("des5", "directional_label", "market_trust", "execution_edge", "probabilities", "tradeable"):
        if key not in result:
            raise DataArchitectureError(f"{field} engine_result incomplete")
    probabilities = result.get("probabilities")
    if not isinstance(probabilities, dict) or any(name not in probabilities for name in REQUIRED_SCENARIOS):
        raise DataArchitectureError(f"{field} probabilities incomplete")
    try:
        float(result["des5"]); float(result["market_trust"]); float(result["execution_edge"])
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
    reference = _validate_capture(reference_record, "reference", "SCREENSHOT_ASSISTED")
    structured = _validate_capture(structured_record, "structured", "UPSTOX_STRUCTURED")
    comparability = assess_pair_comparability(reference, structured)
    reasons = list(comparability["reasons"])
    if reference["session_date_ist"] != structured["session_date_ist"]:
        reasons.append("SESSION_DATE_MISMATCH")
    comparable = not reasons
    rr = reference["engine_result"]; sr = structured["engine_result"]
    rp = rr["probabilities"]; sp = sr["probabilities"]
    comparison = {
        "directional_label_match": rr["directional_label"] == sr["directional_label"],
        "tradeable_semantics_match": rr["tradeable"] == sr["tradeable"],
        "des5_delta": round(float(sr["des5"]) - float(rr["des5"]), 6),
        "market_trust_delta": round(float(sr["market_trust"]) - float(rr["market_trust"]), 6),
        "execution_edge_delta": round(float(sr["execution_edge"]) - float(rr["execution_edge"]), 6),
        "probability_deltas": {n: round(float(sp[n]) - float(rp[n]), 6) for n in REQUIRED_SCENARIOS},
    }
    return {
        "schema": PAIR_SCHEMA,
        "status": "COMPARABLE_OBSERVATION" if comparable else "OBSERVATIONAL_ONLY",
        "acceptance_eligible": comparable,
        "acceptance_decision_made": False,
        "production_activation_decision_made": False,
        "session_date_ist": reference["session_date_ist"] if comparable else None,
        "comparison_window_id": reference["comparison_window_id"] if comparable else None,
        "reference_evidence_cutoff_ist": comparability["reference_evidence_cutoff_ist"],
        "structured_evidence_cutoff_ist": comparability["structured_evidence_cutoff_ist"],
        "pair_delta_seconds": comparability["pair_delta_seconds"],
        "timing_quality": comparability["timing_quality"],
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
    if not isinstance(value.get("comparison"), dict):
        raise DataArchitectureError("G11 comparison missing")
    return value


def summarize_validation_series(observations, required_comparable_runs=3, *, require_same_session=True):
    if not isinstance(required_comparable_runs, int) or required_comparable_runs < 2:
        raise DataArchitectureError("required_comparable_runs invalid")
    if not isinstance(observations, list):
        raise DataArchitectureError("observations must be list")
    validated = [_pair_record(item) for item in observations]
    comparable = [item for item in validated if item.get("acceptance_eligible") is True]
    run_ids = [item.get("comparison_window_id") for item in comparable]
    if any(not isinstance(value, str) or not value for value in run_ids):
        raise DataArchitectureError("comparable observation run id missing")
    if len(set(run_ids)) != len(run_ids):
        raise DataArchitectureError("duplicate comparable manual run")
    session_dates = [item.get("session_date_ist") for item in comparable]
    if any(not isinstance(value, str) for value in session_dates):
        raise DataArchitectureError("comparable observation session date missing")
    distinct_sessions = len(set(session_dates))
    if require_same_session and comparable and distinct_sessions != 1:
        raise DataArchitectureError("primary G11 series must use one trading session")
    comparisons = [item["comparison"] for item in comparable]
    max_abs = lambda key: max((abs(float(item[key])) for item in comparisons), default=None)
    probability_max_abs = {name: max((abs(float(item["probability_deltas"][name])) for item in comparisons), default=None) for name in REQUIRED_SCENARIOS}
    review_ready = len(comparable) >= required_comparable_runs
    return {
        "schema": SERIES_SCHEMA,
        "status": "REVIEW_READY" if review_ready else "EVIDENCE_COLLECTION_INCOMPLETE",
        "required_comparable_runs": required_comparable_runs,
        "same_session_required": bool(require_same_session),
        "total_observations": len(validated),
        "comparable_observations": len(comparable),
        "observational_only_count": len(validated) - len(comparable),
        "distinct_comparable_runs": len(set(run_ids)),
        "distinct_comparable_sessions": distinct_sessions,
        "session_dates_ist": sorted(set(session_dates)),
        "max_pair_delta_seconds_observed": max((float(item["pair_delta_seconds"]) for item in comparable), default=None),
        "directional_label_matches": sum(1 for item in comparisons if item["directional_label_match"] is True),
        "tradeable_semantics_matches": sum(1 for item in comparisons if item["tradeable_semantics_match"] is True),
        "max_abs_des5_delta": max_abs("des5_delta"),
        "max_abs_market_trust_delta": max_abs("market_trust_delta"),
        "max_abs_execution_edge_delta": max_abs("execution_edge_delta"),
        "max_abs_probability_deltas": probability_max_abs,
        "acceptance_decision_made": False,
        "production_activation_decision_made": False,
        "methodology_changed": False,
        "note": "REVIEW_READY means three distinct comparable manual runs were collected in one session; rollover and governed review remain separate gates.",
        "observations": deepcopy(validated),
    }
