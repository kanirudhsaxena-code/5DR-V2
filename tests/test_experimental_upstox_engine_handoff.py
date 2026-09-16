import unittest

from experiments.data_contract import DataArchitectureError
from experiments.engine_handoff import build_engine_request
from src.composed_engine import domain_execute
from src.orchestrator import execute

BUNDLE_SHA = "a" * 64


def bundle():
    return {
        "schema": "5dr-frozen-evidence-bundle-v1",
        "run_id": "run-v223",
        "frozen_at": "2026-09-16T07:00:00+00:00",
        "status": "READY",
        "bundle_sha256": BUNDLE_SHA,
        "screenshot_policy": {
            "require_screenshot_free": True,
            "screenshot_dependency": False,
            "screenshot_semantics": [],
        },
        "directional_score_assigned": False,
        "forecast_released": False,
        "trading_enabled": False,
        "production_5dr_write_enabled": False,
    }


def normalized():
    return {
        "regime": "TREND",
        "component_scores": {
            "PRICE_STRUCTURE": 50,
            "PVPO": 40,
            "PARTICIPATION": 30,
            "MACRO_CATALYSTS": 20,
        },
        "market_trust_inputs": {
            "price_confirmation": 80,
            "pvpo_confirmation": 75,
            "participation_confirmation": 70,
            "cross_engine_consistency": 65,
            "closing_confirmation": 80,
            "evidence_freshness_completeness": 90,
        },
        "event_shock": "NORMAL",
        "execution_inputs": {
            "rr_score": 80,
            "premium_iv_theta_score": 70,
            "strike_expiry_fit_score": 80,
            "liquidity_spread_score": 80,
            "entry_invalidation_score": 75,
        },
        "data_adequate": True,
        "event_kill_switch": False,
        "expected_rr": 2.5,
        "horizon_slots": {f"D+{i}": {} for i in range(1, 6)},
    }


def judgment():
    return {
        "schema": "5dr-v2-2-3-governed-judgment-v1",
        "source": "5DR_INTELLIGENCE_LAYER_V2_2_3",
        "bundle_sha256": BUNDLE_SHA,
        "methodology_changed": False,
        "normalized_engine_inputs": normalized(),
    }


class EngineHandoffTests(unittest.TestCase):
    def test_ready_bundle_and_bound_judgment_execute_existing_engine(self):
        request = build_engine_request(bundle(), judgment())
        self.assertEqual(request.provenance_mode, "AUTOMATED")
        self.assertEqual(request.request_id, "run-v223")
        self.assertEqual(len(request.evidence), 2)
        result = execute(request, domain_execute)
        self.assertEqual(result["model_version"], "5DR_V2_1")
        self.assertEqual(result["output_contract_version"], "5DR_V2_1_2")
        self.assertIn(result["directional_label"], {"STRONG_BULL", "BULL", "MILD_BULL", "RANGE", "MILD_BEAR", "BEAR", "STRONG_BEAR"})

    def test_bundle_digest_mismatch_blocks_judgment_reuse(self):
        bad = judgment()
        bad["bundle_sha256"] = "b" * 64
        with self.assertRaises(DataArchitectureError):
            build_engine_request(bundle(), bad)

    def test_blocked_bundle_cannot_reach_engine(self):
        bad_bundle = bundle()
        bad_bundle["status"] = "BLOCKED"
        with self.assertRaises(DataArchitectureError):
            build_engine_request(bad_bundle, judgment())

    def test_screenshot_dependency_blocks_v223_autonomous_handoff(self):
        bad_bundle = bundle()
        bad_bundle["screenshot_policy"]["screenshot_dependency"] = True
        with self.assertRaises(DataArchitectureError):
            build_engine_request(bad_bundle, judgment())

    def test_methodology_change_flag_blocks_handoff(self):
        bad = judgment()
        bad["methodology_changed"] = True
        with self.assertRaises(DataArchitectureError):
            build_engine_request(bundle(), bad)

    def test_missing_engine_input_blocks_handoff(self):
        bad = judgment()
        del bad["normalized_engine_inputs"]["component_scores"]
        with self.assertRaises(DataArchitectureError):
            build_engine_request(bundle(), bad)


if __name__ == "__main__":
    unittest.main()
