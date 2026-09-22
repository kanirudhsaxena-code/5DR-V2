"""Fail-closed 5DR calculation orchestration boundary.

The orchestrator validates normalized input and deterministic calculation output.
It does not fabricate missing forecasts or lifecycle assessments. Production release
validation is intentionally performed only after the release package has been built.
"""

from typing import Any, Callable, Dict

from .engine_contract import (
    EngineRequest,
    MODEL_VERSION,
    OUTPUT_CONTRACT_VERSION,
    REQUIRED_HORIZONS,
    validate_engine_request,
    validate_horizon_slots,
)


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

    slots = result.get("horizon_slots", {})
    validate_horizon_slots(slots)

    return result
