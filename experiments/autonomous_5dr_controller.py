"""Write-free autonomous 5DR judgment + calculation controller.

This is the last-mile composition boundary between a READY structured evidence
bundle, an approved intelligence-layer judgment provider, and the existing frozen
5DR calculation engine. It intentionally does not publish forecasts, persist
lifecycle state, promote Learning Lab changes, or execute trades.
"""
from __future__ import annotations

from copy import deepcopy

from experiments.autonomous_judgment_bridge import build_governed_judgment
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
