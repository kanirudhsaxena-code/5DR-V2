"""Write-free autonomous 5DR controller through lifecycle/Learning Lab shadow.

This composes the existing frozen evidence handoff and calculation engine with
approval-gated provider interfaces. It never publishes forecasts, persists lifecycle
state, promotes Learning Lab changes, or executes trades.
"""
from __future__ import annotations

from copy import deepcopy

from experiments.autonomous_judgment_bridge import build_governed_judgment
from experiments.autonomous_lifecycle_shadow import run_lifecycle_learning_shadow
from experiments.autonomous_release_bridge import build_release_candidate
from experiments.autonomous_persistence_bridge import persist_release_candidate
from experiments.autonomous_shadow import run_structured_shadow


def run_autonomous_calculation(bundle: dict, judgment_provider) -> dict:
    judgment = build_governed_judgment(bundle, judgment_provider)
    shadow = run_structured_shadow(bundle, judgment)
    if shadow.get("status") != "SHADOW_COMPLETE":
        raise ValueError("autonomous 5DR calculation did not complete")

    engine_result = deepcopy(shadow["engine_result"])
    return {
        "schema": "5dr-v2-2-3-autonomous-calculation-v1",
        "status": "AUTONOMOUS_JUDGMENT_AND_CALCULATION_COMPLETE",
        "request_id": shadow["request_id"],
        "bundle_sha256": shadow["bundle_sha256"],
        "engine_result": engine_result,
        "next_gate": "ASSESSMENT_RECOMMENDATION_RELEASE_PACKAGE",
        "forecast_released": False,
        "production_5dr_write_enabled": False,
        "lifecycle_write_enabled": False,
        "learning_lab_write_enabled": False,
        "trading_execution_enabled": False,
        "methodology_changed": False,
    }


def run_autonomous_release_candidate(bundle: dict, judgment_provider, release_provider) -> dict:
    calculated = run_autonomous_calculation(bundle, judgment_provider)
    candidate = build_release_candidate(
        bundle_sha256=calculated["bundle_sha256"],
        engine_result=calculated["engine_result"],
        provider=release_provider,
    )
    return {
        "schema": "5dr-v2-2-3-autonomous-release-candidate-v1",
        "status": "AUTONOMOUS_RELEASE_CANDIDATE_COMPLETE",
        "request_id": calculated["request_id"],
        "bundle_sha256": calculated["bundle_sha256"],
        "release_candidate": candidate,
        "next_gate": "PERSISTENCE_LIFECYCLE_LEARNING_ACTIVATION",
        "forecast_released": False,
        "production_5dr_write_enabled": False,
        "lifecycle_write_enabled": False,
        "learning_lab_write_enabled": False,
        "trading_execution_enabled": False,
        "methodology_changed": False,
    }


def run_autonomous_full_shadow(bundle: dict, judgment_provider, release_provider, lifecycle_provider) -> dict:
    """Execute the complete write-free autonomous 5DR chain."""
    released = run_autonomous_release_candidate(bundle, judgment_provider, release_provider)
    lifecycle = run_lifecycle_learning_shadow(released["release_candidate"], lifecycle_provider)
    return {
        "schema": "5dr-v2-2-3-autonomous-full-shadow-v1",
        "status": "AUTONOMOUS_FULL_SHADOW_COMPLETE",
        "request_id": released["request_id"],
        "bundle_sha256": released["bundle_sha256"],
        "release_candidate": deepcopy(released["release_candidate"]),
        "lifecycle_learning_shadow": lifecycle,
        "next_gate": "CONTROLLED_PERSISTENCE_AND_PROMPT_TRIGGER_VALIDATION",
        "forecast_released": False,
        "production_5dr_write_enabled": False,
        "lifecycle_write_enabled": False,
        "learning_lab_write_enabled": False,
        "trading_execution_enabled": False,
        "methodology_changed": False,
    }


def run_autonomous_production(bundle: dict, judgment_provider, release_provider, persistence_provider) -> dict:
    """Execute autonomous calculation + validated release + governed canonical persistence."""
    released = run_autonomous_release_candidate(bundle, judgment_provider, release_provider)
    persisted = persist_release_candidate(released["release_candidate"], persistence_provider)
    return {
        "schema": "5dr-v2-2-3-autonomous-production-v1",
        "status": "AUTONOMOUS_PRODUCTION_PERSISTED",
        "request_id": released["request_id"],
        "bundle_sha256": released["bundle_sha256"],
        "forecast_id": persisted["forecast_id"],
        "release_candidate": deepcopy(released["release_candidate"]),
        "persistence_receipt": persisted,
        "next_gate": "OUTCOME_CHECKPOINT_AND_LEARNING_LIFECYCLE",
        "forecast_released": True,
        "production_5dr_write_enabled": True,
        "lifecycle_write_enabled": False,
        "learning_lab_write_enabled": False,
        "trading_execution_enabled": False,
        "methodology_changed": False,
    }
