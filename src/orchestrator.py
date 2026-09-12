"""Fail-closed 5DR orchestration boundary.

The orchestrator validates normalized input and production output. It will not
fabricate missing forecasts or assessments. Domain execution is injected so
existing 5DR modules can be composed behind this stable interface.
"""

from typing import Any, Callable, Dict

from .engine_contract import (
    EngineRequest,
    MODEL_VERSION,
    OUTPUT_CONTRACT_VERSION,
    REQUIRED_HORIZONS,
    validate_engine_request,
)
from .output_contract import validate_output_contract


DomainExecutor = Callable[[EngineRequest], Dict[str, Any]]


def execute(request: EngineRequest, domain_executor: DomainExecutor) -> Dict[str, Any]:
    validate_engine_request(request)
    result = domain_executor(request)
    if not isinstance(result, dict):
        raise ValueError("5DR execution blocked: domain executor returned invalid result")

    if result.get("model_version") != MODEL_VERSION:
        raise ValueError("5DR execution blocked: invalid model version")
    if result.get("output_contract_version") != OUTPUT_CONTRACT_VERSION:
        raise ValueError("5DR execution blocked: invalid output contract version")

    validate_output_contract(
        result.get("model_version"),
        result.get("forecast_assessment"),
        result.get("recommendation_assessment"),
        result.get("output_contract_version"),
        assessment_snapshot_complete=result.get("assessment_snapshot_complete", False),
        horizon_slots=result.get("horizon_slots"),
        recommendation_ledger_complete=result.get("recommendation_ledger_complete", False),
    )

    slots = result.get("horizon_slots", {})
    missing = [slot for slot in REQUIRED_HORIZONS if slot not in slots]
    if missing:
        raise ValueError(f"5DR execution blocked: missing horizon slots {missing}")

    return result
