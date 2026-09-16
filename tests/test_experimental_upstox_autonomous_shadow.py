import unittest

from experiments.autonomous_shadow import compare_shadow_runs, run_structured_shadow
from experiments.data_contract import DataArchitectureError, build_record
from experiments.evidence_bundle import build_evidence_bundle


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


def bundle(run_id="shadow-run"):
    return build_evidence_bundle(
        run_id=run_id,
        frozen_at="2026-09-16T07:00:00+00:00",
        quantitative_records=[record()],
        chart_evidence=chart(),
        required_variables={"NIFTY_PRICE_CANDLES"},
    )


def normalized(price_score=50):
    return {
        "regime": "TREND",
        "component_scores": {
            "PRICE_STRUCTURE": price_score,
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


def judgment(evidence_bundle, price_score=50):
    return {
        "schema": "5dr-v2-2-3-governed-judgment-v1",
        "source": "5DR_INTELLIGENCE_LAYER_V2_2_3",
        "bundle_sha256": evidence_bundle["bundle_sha256"],
        "methodology_changed": False,
        "normalized_engine_inputs": normalized(price_score),
    }


class AutonomousShadowTests(unittest.TestCase):
    def test_structured_shadow_executes_without_side_effects(self):
        evidence_bundle = bundle()
        result = run_structured_shadow(evidence_bundle, judgment(evidence_bundle))
        self.assertEqual(result["status"], "SHADOW_COMPLETE")
        self.assertFalse(result["published"])
        self.assertFalse(result["forecast_release_enabled"])
        self.assertFalse(result["production_5dr_write_enabled"])
        self.assertFalse(result["lifecycle_write_enabled"])
        self.assertFalse(result["trading_execution_enabled"])
        self.assertFalse(result["methodology_changed"])
        self.assertIn("des5", result["engine_result"])

    def test_tampered_bundle_cannot_run_shadow(self):
        evidence_bundle = bundle()
        bound = judgment(evidence_bundle)
        evidence_bundle["quantitative_records"][0]["values"]["value"] = 999
        with self.assertRaises(DataArchitectureError):
            run_structured_shadow(evidence_bundle, bound)

    def test_shadow_comparison_observes_deltas_without_acceptance_decision(self):
        reference_bundle = bundle("reference-run")
        structured_bundle = bundle("structured-run")
        reference = run_structured_shadow(reference_bundle, judgment(reference_bundle, price_score=40))
        structured = run_structured_shadow(structured_bundle, judgment(structured_bundle, price_score=50))
        comparison = compare_shadow_runs(reference, structured)
        self.assertEqual(comparison["status"], "OBSERVED_NOT_ACCEPTED")
        self.assertNotEqual(comparison["des5_delta"], 0)
        self.assertFalse(comparison["production_side_effects"])
        self.assertFalse(comparison["acceptance_decision_made"])

    def test_comparison_rejects_any_shadow_with_enabled_side_effect(self):
        evidence_bundle = bundle()
        shadow = run_structured_shadow(evidence_bundle, judgment(evidence_bundle))
        unsafe = dict(shadow)
        unsafe["published"] = True
        with self.assertRaises(DataArchitectureError):
            compare_shadow_runs(shadow, unsafe)


if __name__ == "__main__":
    unittest.main()
