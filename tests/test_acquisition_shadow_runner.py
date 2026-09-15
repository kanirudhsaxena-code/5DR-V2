import unittest
from datetime import date

from src.acquisition_shadow_runner import run_shadow


class FakeClient:
    def contracts(self):
        return {"payload": {"data": [{"underlying_key": "NSE_INDEX|Nifty 50", "expiry": "2026-09-17"}]}}

    def intraday(self):
        return {"received_at": "2026-09-15T10:30:00+00:00", "source_path": "/v3/historical-candle/intraday/NSE_INDEX%7CNifty%2050/minutes/1", "sha256": "a" * 64}

    def chain(self, expiry):
        return {"received_at": "2026-09-15T10:30:01+00:00", "source_path": "/v2/option/chain", "sha256": "b" * 64}


class ShadowRunnerTests(unittest.TestCase):
    def test_missing_event_registry_keeps_shadow_blocked(self):
        result = run_shadow("5drreq_shadow", FakeClient(), date(2026, 9, 15))
        self.assertEqual(result["status"], "AUTONOMOUS_EVIDENCE_BLOCKED")
        self.assertIn("EVENT_SHOCK", result["blockers"]["missing"])
        self.assertFalse(result["forecast_release_enabled"])
        self.assertFalse(result["trading_enabled"])


if __name__ == "__main__":
    unittest.main()
