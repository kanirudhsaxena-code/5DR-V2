import hashlib
import json

import pytest

from experiments.autonomous_5dr_controller import run_autonomous_calculation
from experiments.autonomous_judgment_bridge import build_governed_judgment
from experiments.data_contract import DataArchitectureError


def _bundle():
    body = {
        "schema": "5dr-frozen-evidence-bundle-v1",
        "status": "READY",
        "run_id": "AUTO-TEST-1",
        "frozen_at": "2026-09-18T10:30:00+05:30",
        "screenshot_policy": {"screenshot_dependency": False},
        "directional_score_assigned": False,
        "forecast_released": False,
        "trading_enabled": False,
        "production_5dr_write_enabled": False,
    }
    digest = hashlib.sha256(
        json.dumps(body, sort_keys=True, separators=(",", ":"), default=str).encode()
    ).hexdigest()
    return {**body, "bundle_sha256": digest}


def _normalized():
    return {
        "regime": "TRANSITION",
        "component_scores": {
            "PRICE_STRUCTURE": 10.0,
            "PVPO": 20.0,
            "PARTICIPATION": 10.0,
            "MACRO_CATALYSTS": 0.0,
        },
        "market_trust_inputs": {
            "price_confirmation": 70.0,
            "pvpo_confirmation": 70.0,
            "participation_confirmation": 65.0,
            "cross_engine_consistency": 60.0,
            "closing_confirmation": 60.0,
            "evidence_freshness_completeness": 95.0,
        },
        "event_shock": "NORMAL",
        "execution_inputs": {
            "rr_score": 70.0,
            "premium_iv_theta_score": 70.0,
            "strike_expiry_fit_score": 70.0,
            "liquidity_spread_score": 80.0,
            "entry_invalidation_score": 70.0,
        },
        "data_adequate": True,
        "event_kill_switch": False,
        "expected_rr": 2.0,
        "horizon_slots": {f"D+{i}": {"status": "PENDING_RELEASE"} for i in range(1, 6)},
    }


def _provider(bundle):
    return {
        "bundle_sha256": bundle["bundle_sha256"],
        "normalized_engine_inputs": _normalized(),
        "judgment_audit": {"provider": "TEST_INTELLIGENCE_LAYER"},
    }


def test_bridge_binds_provider_to_exact_bundle():
    bundle = _bundle()
    judgment = build_governed_judgment(bundle, _provider)
    assert judgment["bundle_sha256"] == bundle["bundle_sha256"]
    assert judgment["methodology_changed"] is False
    assert judgment["release_complete"] is False


def test_bridge_rejects_provider_bound_to_other_bundle():
    bundle = _bundle()

    def wrong_provider(_):
        return {
            "bundle_sha256": "0" * 64,
            "normalized_engine_inputs": _normalized(),
        }

    with pytest.raises(DataArchitectureError, match="bundle binding mismatch"):
        build_governed_judgment(bundle, wrong_provider)


def test_bridge_fails_closed_on_missing_engine_input():
    bundle = _bundle()

    def incomplete_provider(value):
        normalized = _normalized()
        normalized.pop("execution_inputs")
        return {
            "bundle_sha256": value["bundle_sha256"],
            "normalized_engine_inputs": normalized,
        }

    with pytest.raises(DataArchitectureError, match="missing engine inputs"):
        build_governed_judgment(bundle, incomplete_provider)


def test_autonomous_controller_executes_existing_engine_without_side_effects():
    result = run_autonomous_calculation(_bundle(), _provider)
    assert result["status"] == "AUTONOMOUS_JUDGMENT_AND_CALCULATION_COMPLETE"
    assert set(result["engine_result"]["probabilities"]) == {"BULL", "RANGE", "BEAR"}
    assert result["forecast_released"] is False
    assert result["production_5dr_write_enabled"] is False
    assert result["lifecycle_write_enabled"] is False
    assert result["learning_lab_write_enabled"] is False
    assert result["trading_execution_enabled"] is False
    assert result["methodology_changed"] is False
