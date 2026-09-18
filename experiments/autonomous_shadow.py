"""Non-publishing V2.2.3 structured-data shadow runner.

This is an observation harness only. It proves that a READY frozen evidence bundle and
a bundle-bound governed judgment can execute the existing 5DR engine without enabling
forecast publication, production persistence, lifecycle writes or trading execution.
"""
from copy import deepcopy

from experiments.data_contract import DataArchitectureError
from experiments.engine_handoff import build_engine_request
from src.composed_engine import domain_execute
from src.orchestrator import execute

SCHEMA = "5dr-v2-2-3-structured-shadow-v1"
COMPARISON_SCHEMA = "5dr-v2-2-3-shadow-comparison-v1"


def run_structured_shadow(bundle, judgment):
    request = build_engine_request(bundle, judgment)
    result = execute(request, domain_execute)
    return {
        "schema": SCHEMA,
        "status": "SHADOW_COMPLETE",
        "request_id": request.request_id,
        "bundle_sha256": bundle["bundle_sha256"],
        "engine_result": deepcopy(result),
        "published": False,
        "forecast_release_enabled": False,
        "production_5dr_write_enabled": False,
        "lifecycle_write_enabled": False,
        "trading_execution_enabled": False,
        "methodology_changed": False,
    }


def _shadow_result(value, field):
    if not isinstance(value, dict) or value.get("schema") != SCHEMA or value.get("status") != "SHADOW_COMPLETE":
        raise DataArchitectureError(f"{field} shadow result invalid")
    for flag in (
        "published", "forecast_release_enabled", "production_5dr_write_enabled",
        "lifecycle_write_enabled", "trading_execution_enabled", "methodology_changed",
    ):
        if value.get(flag) is not False:
            raise DataArchitectureError(f"{field} shadow safety boundary crossed")
    result = value.get("engine_result")
    if not isinstance(result, dict):
        raise DataArchitectureError(f"{field} engine result missing")
    for key in ("des5", "directional_label", "market_trust", "probabilities", "execution_edge", "tradeable"):
        if key not in result:
            raise DataArchitectureError(f"{field} engine result incomplete")
    return result


def compare_shadow_runs(reference_shadow, structured_shadow):
    """Describe differences only; no acceptance ranking or methodology change is applied."""
    reference = _shadow_result(reference_shadow, "reference")
    structured = _shadow_result(structured_shadow, "structured")
    reference_probs = reference.get("probabilities")
    structured_probs = structured.get("probabilities")
    if not isinstance(reference_probs, dict) or not isinstance(structured_probs, dict):
        raise DataArchitectureError("shadow probabilities invalid")
    scenarios = ("BULL", "RANGE", "BEAR")
    if any(name not in reference_probs or name not in structured_probs for name in scenarios):
        raise DataArchitectureError("shadow probability scenario missing")

    return {
        "schema": COMPARISON_SCHEMA,
        "status": "OBSERVED_NOT_ACCEPTED",
        "reference_request_id": reference_shadow.get("request_id"),
        "structured_request_id": structured_shadow.get("request_id"),
        "directional_label_match": reference["directional_label"] == structured["directional_label"],
        "tradeable_semantics_match": reference["tradeable"] == structured["tradeable"],
        "des5_delta": round(float(structured["des5"]) - float(reference["des5"]), 6),
        "market_trust_delta": round(float(structured["market_trust"]) - float(reference["market_trust"]), 6),
        "execution_edge_delta": round(float(structured["execution_edge"]) - float(reference["execution_edge"]), 6),
        "probability_deltas": {
            name: round(float(structured_probs[name]) - float(reference_probs[name]), 6)
            for name in scenarios
        },
        "production_side_effects": False,
        "acceptance_decision_made": False,
    }
