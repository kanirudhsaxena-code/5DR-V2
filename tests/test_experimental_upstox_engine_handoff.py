import unittest

from experiments.data_contract import DataArchitectureError, build_record
from experiments.engine_handoff import build_engine_request
from experiments.evidence_bundle import build_evidence_bundle
from src.composed_engine import domain_execute
from src.orchestrator import execute


def record():
    return build_record(
        provider_id="UPSTOX",
        source_semantic="UPSTOX_AUTHENTICATED",
        variable_id="NIFTY_PRICE_CANDLES",
        consumer="5DR",
        subject={
            "kind": "MARKET_INSTRUMENT",
            "id": "NIFTY50",
            "name": "NIFTY 50",
            "exchange": "NSE",
            "instrument_key": "NSE_INDEX|Nifty 50",
        },
        metric="TEST",
        values={"value": 1},
        timeframe="1h",
        provider_timestamp="2026-09-16T06:00:00+00:00",
        acquisition_timestamp="2026-09-16T06:00:05+00:00",
        freshness_status="LIVE",
        source_reference="/v3/test",
        source_sha256="a" * 64,
    )


def chart():
    timeframes = {}
    for timeframe in ("1d", "1h", "30m", "15m", "5m"):
        timeframes[timeframe] = {
            "schema": "5dr-derived-chart-evidence-v1",
            "timeframe": timeframe,
            "directional_score_assigned": False,
            "forecast_released": False,
            "trading_enabled": False,
        }
    return {
        "schema": "5dr-multi-timeframe-chart-evidence-v1",
        "timeframes": timeframes,
        "directional_alignment_excluding_5m": "MIXED",
        "five_minute_execution_only": True,
        "directional_score_assigned": False,
        "forecast_released": False,
        "trading_enabled": False,
    }


def bundle():
    return build_evidence_bundle(
        run_id="run-v223",
        frozen_at="2026-09-16T07:00:00+00:00",
        quantitative_records=[record()],
        chart_evidence=chart(),
        required_variables={"NIFTY_PRICE_CANDLES"},
    )


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
        "event_shock": "LOW",
        "event_transmission": "TWO_SIDED",
        "convexity_warranted": False,
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
        "horizon_slots": {
            f"D+{i}": {
                "direction": "RANGE",
                "probabilities": {"BULL": 25.0, "RANGE": 50.0, "BEAR": 25.0},
                "zone_low": 23000 + i * 10,
                "zone_high": 23500 + i * 10,
                "basis": f"governed test horizon {i}",
            }
            for i in range(1, 6)
        },
    }


def judgment(evidence_bundle):
    return {
        "schema": "5dr-v2-2-3-governed-judgment-v1",
        "source": "5DR_INTELLIGENCE_LAYER_V2_2_3",
        "bundle_sha256": evidence_bundle["bundle_sha256"],
        "methodology_changed": False,
        "normalized_engine_inputs": normalized(),
    }


class EngineHandoffTests(unittest.TestCase):
    def test_ready_bundle_and_bound_judgment_execute_existing_engine(self):
        evidence_bundle = bundle()
        request = build_engine_request(evidence_bundle, judgment(evidence_bundle))
        self.assertEqual(request.provenance_mode, "AUTOMATED")
        self.assertEqual(request.request_id, "run-v223")
        self.assertEqual(len(request.evidence), 2)
        result = execute(request, domain_execute)
        self.assertEqual(result["model_version"], "5DR_V2_1")
        self.assertEqual(result["output_contract_version"], "5DR_V2_1_2")
        self.assertIn(result["directional_label"], {"STRONG_BULL", "BULL", "MILD_BULL", "RANGE", "MILD_BEAR", "BEAR", "STRONG_BEAR"})

    def test_bundle_digest_mismatch_blocks_judgment_reuse(self):
        evidence_bundle = bundle()
        bad = judgment(evidence_bundle)
        bad["bundle_sha256"] = "b" * 64
        with self.assertRaises(DataArchitectureError):
            build_engine_request(evidence_bundle, bad)

    def test_post_freeze_bundle_mutation_is_detected(self):
        evidence_bundle = bundle()
        bound = judgment(evidence_bundle)
        evidence_bundle["coverage"]["variables_present"].append("TAMPERED")
        with self.assertRaises(DataArchitectureError):
            build_engine_request(evidence_bundle, bound)

    def test_blocked_bundle_cannot_reach_engine(self):
        evidence_bundle = bundle()
        bound = judgment(evidence_bundle)
        evidence_bundle["status"] = "BLOCKED"
        with self.assertRaises(DataArchitectureError):
            build_engine_request(evidence_bundle, bound)

    def test_screenshot_dependency_blocks_v223_autonomous_handoff(self):
        evidence_bundle = bundle()
        bound = judgment(evidence_bundle)
        evidence_bundle["screenshot_policy"]["screenshot_dependency"] = True
        with self.assertRaises(DataArchitectureError):
            build_engine_request(evidence_bundle, bound)

    def test_methodology_change_flag_blocks_handoff(self):
        evidence_bundle = bundle()
        bad = judgment(evidence_bundle)
        bad["methodology_changed"] = True
        with self.assertRaises(DataArchitectureError):
            build_engine_request(evidence_bundle, bad)

    def test_missing_engine_input_blocks_handoff(self):
        evidence_bundle = bundle()
        bad = judgment(evidence_bundle)
        del bad["normalized_engine_inputs"]["component_scores"]
        with self.assertRaises(DataArchitectureError):
            build_engine_request(evidence_bundle, bad)


if __name__ == "__main__":
    unittest.main()
