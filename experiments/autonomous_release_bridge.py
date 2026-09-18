"""Validated write-free release-candidate bridge for autonomous 5DR V2.2.3.

The bridge owns no recommendation semantics. An approved assessment/recommendation
provider must bind its output to the exact evidence bundle and exact deterministic
engine result. The existing V2.1.2 output contract remains authoritative.
"""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from typing import Any, Callable, Mapping

from experiments.data_contract import DataArchitectureError
from src.output_contract import validate_output_contract

ReleaseProvider = Callable[[dict], Mapping[str, Any]]


def _engine_sha256(engine_result: dict) -> str:
    return hashlib.sha256(
        json.dumps(engine_result, sort_keys=True, separators=(",", ":"), default=str).encode()
    ).hexdigest()


def build_release_candidate(*, bundle_sha256: str, engine_result: dict, provider: ReleaseProvider) -> dict:
    if not isinstance(bundle_sha256, str) or len(bundle_sha256) != 64:
        raise DataArchitectureError("release bridge bundle SHA invalid")
    if not isinstance(engine_result, dict):
        raise DataArchitectureError("release bridge engine result invalid")
    if not callable(provider):
        raise DataArchitectureError("release provider is not callable")

    engine_sha = _engine_sha256(engine_result)
    context = {
        "bundle_sha256": bundle_sha256,
        "engine_result_sha256": engine_sha,
        "engine_result": deepcopy(engine_result),
    }
    supplied = provider(deepcopy(context))
    if not isinstance(supplied, Mapping):
        raise DataArchitectureError("release provider returned invalid payload")
    if supplied.get("bundle_sha256") != bundle_sha256:
        raise DataArchitectureError("release provider bundle binding mismatch")
    if supplied.get("engine_result_sha256") != engine_sha:
        raise DataArchitectureError("release provider engine binding mismatch")

    forecast_assessment = supplied.get("forecast_assessment")
    recommendation_assessment = supplied.get("recommendation_assessment")
    assessment_snapshot_complete = supplied.get("assessment_snapshot_complete") is True
    horizon_slots = supplied.get("horizon_slots")
    recommendation_ledger_complete = supplied.get("recommendation_ledger_complete") is True

    validate_output_contract(
        engine_result.get("model_version"),
        forecast_assessment,
        recommendation_assessment,
        engine_result.get("output_contract_version"),
        assessment_snapshot_complete=assessment_snapshot_complete,
        horizon_slots=horizon_slots,
        recommendation_ledger_complete=recommendation_ledger_complete,
    )

    return {
        "schema": "5dr-v2-2-3-release-candidate-v1",
        "status": "RELEASE_CANDIDATE_VALIDATED",
        "bundle_sha256": bundle_sha256,
        "engine_result_sha256": engine_sha,
        "engine_result": deepcopy(engine_result),
        "forecast_assessment": forecast_assessment,
        "recommendation_assessment": recommendation_assessment,
        "horizon_slots": deepcopy(horizon_slots),
        "recommendation": deepcopy(supplied.get("recommendation")),
        "assessment_snapshot_complete": True,
        "recommendation_ledger_complete": True,
        "published": False,
        "production_5dr_write_enabled": False,
        "lifecycle_write_enabled": False,
        "learning_lab_write_enabled": False,
        "trading_execution_enabled": False,
        "methodology_changed": False,
    }
