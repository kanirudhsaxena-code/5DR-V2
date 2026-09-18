"""Write-free lifecycle / efficacy / Learning Lab shadow orchestration for 5DR V2.2.3.

Consumes a validated autonomous release candidate plus an externally supplied
lifecycle snapshot that is cryptographically bound to that exact candidate.
No persistence is performed here. Existing efficacy and Learning Lab modules
remain authoritative for assessment and governance.
"""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from typing import Any, Callable, Mapping

from experiments.data_contract import DataArchitectureError
from src.checkpoint_efficacy import build_efficacy_records
from src.learning_governance import hypothesis_gate
from src.learning_observations import build_learning_observations

LifecycleProvider = Callable[[dict], Mapping[str, Any]]

REQUIRED_CHECKPOINT_TYPES = tuple(f"D+{i}" for i in range(1, 6))


def _sha256(value: dict) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()
    ).hexdigest()


def _validate_release_candidate(candidate: dict) -> str:
    if not isinstance(candidate, dict):
        raise DataArchitectureError("lifecycle shadow release candidate invalid")
    if candidate.get("schema") != "5dr-v2-2-3-release-candidate-v1":
        raise DataArchitectureError("lifecycle shadow release candidate schema invalid")
    if candidate.get("status") != "RELEASE_CANDIDATE_VALIDATED":
        raise DataArchitectureError("lifecycle shadow requires validated release candidate")
    for flag in (
        "published",
        "production_5dr_write_enabled",
        "lifecycle_write_enabled",
        "learning_lab_write_enabled",
        "trading_execution_enabled",
        "methodology_changed",
    ):
        if candidate.get(flag) is not False:
            raise DataArchitectureError(f"lifecycle shadow safety boundary crossed: {flag}")
    return _sha256(candidate)


def _validate_snapshot(snapshot: Mapping[str, Any], expected_sha: str) -> tuple[list[dict], list[dict], list[dict]]:
    if snapshot.get("release_candidate_sha256") != expected_sha:
        raise DataArchitectureError("lifecycle snapshot release-candidate binding mismatch")
    forecasts = snapshot.get("forecasts")
    checkpoints = snapshot.get("checkpoints")
    recommendation_rows = snapshot.get("recommendation_rows")
    if not isinstance(forecasts, list) or len(forecasts) != 1:
        raise DataArchitectureError("lifecycle snapshot requires exactly one forecast row")
    if not isinstance(checkpoints, list):
        raise DataArchitectureError("lifecycle snapshot checkpoints missing")
    if not isinstance(recommendation_rows, list):
        raise DataArchitectureError("lifecycle snapshot recommendation rows missing")

    forecast_id = forecasts[0].get("forecast_id")
    if not isinstance(forecast_id, str) or not forecast_id.strip():
        raise DataArchitectureError("lifecycle snapshot forecast_id missing")
    if any(row.get("forecast_id") != forecast_id for row in checkpoints):
        raise DataArchitectureError("checkpoint forecast identity mismatch")
    if any(row.get("forecast_id") != forecast_id for row in recommendation_rows):
        raise DataArchitectureError("recommendation forecast identity mismatch")

    present = {row.get("checkpoint_type") for row in checkpoints}
    missing = [name for name in REQUIRED_CHECKPOINT_TYPES if name not in present]
    if missing:
        raise DataArchitectureError(f"lifecycle snapshot missing checkpoint slots: {missing}")

    return deepcopy(forecasts), deepcopy(checkpoints), deepcopy(recommendation_rows)


def run_lifecycle_learning_shadow(release_candidate: dict, provider: LifecycleProvider) -> dict:
    """Run deterministic outcome accounting and Learning Lab observation generation.

    Captured checkpoints are scored by the existing frozen efficacy implementation.
    Open, due, or incomplete checkpoints remain NOT_SCORABLE and therefore cannot
    become Learning Lab observations.
    """
    if not callable(provider):
        raise DataArchitectureError("lifecycle provider is not callable")

    candidate_sha = _validate_release_candidate(release_candidate)
    context = {
        "release_candidate_sha256": candidate_sha,
        "bundle_sha256": release_candidate.get("bundle_sha256"),
        "release_candidate": deepcopy(release_candidate),
    }
    supplied = provider(deepcopy(context))
    if not isinstance(supplied, Mapping):
        raise DataArchitectureError("lifecycle provider returned invalid payload")

    forecasts, checkpoints, recommendation_rows = _validate_snapshot(supplied, candidate_sha)
    efficacy_rows = build_efficacy_records(forecasts, checkpoints)
    observations = build_learning_observations(efficacy_rows, recommendation_rows)

    probability_gate = hypothesis_gate(observations, dimension="PROBABILITY_CALIBRATION")
    execution_gate = hypothesis_gate(observations, dimension="EXECUTION_EDGE")

    forecast_id = forecasts[0]["forecast_id"]
    return {
        "schema": "5dr-v2-2-3-lifecycle-learning-shadow-v1",
        "status": "LIFECYCLE_LEARNING_SHADOW_COMPLETE",
        "forecast_id": forecast_id,
        "release_candidate_sha256": candidate_sha,
        "persistence_plan": {
            "forecast_rows": 1,
            "checkpoint_rows": len(checkpoints),
            "recommendation_rows": len(recommendation_rows),
            "writes_enabled": False,
            "production_write_attempted": False,
        },
        "efficacy_rows": efficacy_rows,
        "learning_observations": observations,
        "learning_gates": {
            "PROBABILITY_CALIBRATION": probability_gate,
            "EXECUTION_EDGE": execution_gate,
        },
        "forecast_released": False,
        "production_5dr_write_enabled": False,
        "lifecycle_write_enabled": False,
        "learning_lab_write_enabled": False,
        "trading_execution_enabled": False,
        "methodology_changed": False,
        "production_change_allowed": False,
    }
