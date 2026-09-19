import json
import unittest

from experiments.console_automated_evidence import (
    SCHEMA,
    blocked_payload,
    build_console_payload,
)


def fake_bundle():
    return {
        "status": "READY",
        "bundle_sha256": "a" * 64,
        "frozen_at": "2026-09-19T05:00:00+00:00",
        "screenshot_policy": {"screenshot_dependency": False},
        "forecast_released": False,
        "production_5dr_write_enabled": False,
        "trading_enabled": False,
        "runtime_context": {
            "forecast_release_enabled": False,
            "production_5dr_write_enabled": False,
            "lifecycle_write_enabled": False,
            "trading_enabled": False,
            "canonical_integration_enabled": False,
            "methodology_changed": False,
        },
    }


def fake_summary():
    return {
        "nifty": {"spot": {"last_price": 25123.4}},
        "chart": {"directional_alignment_excluding_5m": "MIXED", "timeframes": {}},
        "india_vix": {"last_price": 12.4},
        "nifty_futures": {"basis_points": 22.0},
        "option_chain": {"selected_expiry": "2026-09-24", "underlying_spot_price": 25123.4, "sample_strikes": []},
        "derivative_analytics": {"pcr": {"value": 1.0}},
        "heavyweights": {},
        "sectors": {},
        "fii_dii_cash": {},
        "fii_index_derivatives": {},
        "global_risk": {},
        "crude_usdinr": {},
    }


class ConsoleAutomatedEvidenceTests(unittest.TestCase):
    def test_ready_payload_has_required_market_families_and_no_side_effects(self):
        payload = build_console_payload("5drreq_test", fake_bundle(), fake_summary())
        self.assertEqual(payload["schema"], SCHEMA)
        self.assertEqual(payload["status"], "AUTOMATED_MARKET_DATA_READY")
        categories = {row["category"] for row in payload["observations"]}
        self.assertTrue({"PRICE_TECHNICALS", "DERIVATIVES_OI", "MARKET_TRUST", "EXECUTION_RISK"} <= categories)
        self.assertFalse(payload["trading_enabled"])
        self.assertFalse(payload["forecast_release_enabled"])
        text = json.dumps(payload).lower()
        for forbidden in ("authorization", "client_secret", "access_token", "raw_payload"):
            self.assertNotIn(forbidden, text)

    def test_blocked_payload_is_safe_and_resumable_by_console_fallback(self):
        payload = blocked_payload("5drreq_test", "UPSTOX_UNAVAILABLE")
        self.assertEqual(payload["status"], "AUTOMATED_MARKET_DATA_BLOCKED")
        self.assertEqual(payload["blockers"], ["UPSTOX_UNAVAILABLE"])
        self.assertEqual(payload["observations"], [])

    def test_screenshot_dependent_bundle_is_rejected(self):
        bundle = fake_bundle()
        bundle["screenshot_policy"]["screenshot_dependency"] = True
        with self.assertRaises(ValueError):
            build_console_payload("5drreq_test", bundle, fake_summary())


if __name__ == "__main__":
    unittest.main()
