import unittest

from experiments.console_preopen_evidence import (
    SCHEMA,
    build_console_preopen_payload,
)


def fake_bundle():
    return {
        "schema": "5dr-preopen-evidence-bundle-v1",
        "status": "READY",
        "bundle_sha256": "a" * 64,
        "frozen_at": "2026-10-05T03:41:00+00:00",
        "target_session_date": "2026-10-05",
        "previous_session_date": "2026-10-01",
        "active_derivative_expiry": "2026-10-08",
        "prior_close_record": {
            "values": {
                "open": 24700.0,
                "high": 24820.0,
                "low": 24610.0,
                "close": 24750.0,
                "volume": 0,
                "open_interest": 0,
            }
        },
        "overnight_records": [{"variable_id": "GLOBAL_RISK_INDICES"}],
        "external_evidence": [{"category": "DXY_RATES"}],
        "side_effects": {
            "forecast_release_enabled": False,
            "production_5dr_write_enabled": False,
            "lifecycle_write_enabled": False,
            "trading_enabled": False,
            "canonical_integration_enabled": False,
            "methodology_changed": False,
        },
    }


def fake_chain():
    return {
        "selected_expiry": "2026-10-08",
        "underlying_spot_price": 24800.0,
        "intraday_availability": "UNAVAILABLE_MARKET_CLOSED",
        "sample_strikes": [
            {
                "strike": 24800,
                "CE": {"instrument_key": "CE", "trading_symbol": "NIFTYCE", "ltp": 100.0, "oi": 1000, "volume": 10},
                "PE": {"instrument_key": "PE", "trading_symbol": "NIFTYPE", "ltp": 90.0, "oi": 1100, "volume": 12},
            }
        ],
    }


class ConsolePreopenEvidenceTests(unittest.TestCase):
    def test_preopen_payload_is_ready_without_normal_session_intraday(self):
        payload = build_console_preopen_payload(
            "5drreq_test",
            bundle=fake_bundle(),
            sanitized_chain=fake_chain(),
            daily_context={"last_close": 24750.0, "ten_session_high": 25000.0, "ten_session_low": 24000.0},
            source_sha256="b" * 64,
        )
        self.assertEqual(payload["schema"], SCHEMA)
        self.assertEqual(payload["status"], "AUTOMATED_MARKET_DATA_READY")
        self.assertEqual(payload["session_mode"], "PREOPEN_MATCHING")
        self.assertEqual(payload["trigger_type"], "SCHEDULED")
        self.assertEqual(payload["evidence_mode"], "PREOPEN")
        self.assertEqual(payload["market_session_as_of"], "2026-10-01")
        self.assertEqual(payload["research_as_of"], "2026-10-05T03:41:00+00:00")
        self.assertEqual(payload["target_session"], "2026-10-05")
        self.assertEqual(payload["benchmark_role"], "SESSION_PREOPEN")
        self.assertFalse(payload["trading_enabled"])
        self.assertFalse(payload["forecast_release_enabled"])
        categories = {row["category"] for row in payload["observations"]}
        self.assertEqual(
            categories,
            {"PRICE_TECHNICALS", "DERIVATIVES_OI", "MARKET_TRUST", "EXECUTION_RISK"},
        )
        price = next(row for row in payload["observations"] if row["category"] == "PRICE_TECHNICALS")
        self.assertFalse(price["structured_data"]["normal_market_intraday_required"])
        self.assertAlmostEqual(price["structured_data"]["gap_pct_vs_prior_close"], 0.20202, places=5)

    def test_preopen_execution_risk_is_degraded_not_fabricated_live(self):
        payload = build_console_preopen_payload(
            "5drreq_test",
            bundle=fake_bundle(),
            sanitized_chain=fake_chain(),
            daily_context={"last_close": 24750.0},
            source_sha256="b" * 64,
        )
        execution = next(row for row in payload["observations"] if row["category"] == "EXECUTION_RISK")
        self.assertEqual(execution["verification"], "DEGRADED")
        self.assertEqual(execution["structured_data"]["execution_constraint"], "PREOPEN_CANONICAL_ANALYSIS_ONLY")
        self.assertFalse(execution["structured_data"]["normal_market_open"])

    def test_governance_side_effect_change_is_rejected(self):
        bundle = fake_bundle()
        bundle["side_effects"]["trading_enabled"] = True
        with self.assertRaises(ValueError):
            build_console_preopen_payload(
                "5drreq_test",
                bundle=bundle,
                sanitized_chain=fake_chain(),
                daily_context={},
                source_sha256="b" * 64,
            )

    def test_option_sample_is_required(self):
        chain = fake_chain()
        chain["sample_strikes"] = []
        with self.assertRaises(ValueError):
            build_console_preopen_payload(
                "5drreq_test",
                bundle=fake_bundle(),
                sanitized_chain=chain,
                daily_context={},
                source_sha256="b" * 64,
            )


if __name__ == "__main__":
    unittest.main()
