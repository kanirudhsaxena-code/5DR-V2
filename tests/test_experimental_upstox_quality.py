import unittest
from datetime import datetime, timezone

from experiments.upstox_quality import classify_timestamp_freshness, require_global_freshness, validate_change_oi, validate_ohlc, validate_price
from phase1.upstox import PipelineError


class QualityTests(unittest.TestCase):
    def test_ohlc_and_nonnegative_rules(self):
        self.assertTrue(validate_ohlc(100, 110, 90, 105, volume=10, open_interest=0))
        with self.assertRaises(PipelineError):
            validate_ohlc(100, 99, 90, 105)
        with self.assertRaises(PipelineError):
            validate_price(-1)
        self.assertTrue(validate_change_oi(-100))

    def test_global_latency_is_preserved(self):
        acquired = datetime(2026, 9, 15, 12, 0, tzinfo=timezone.utc)
        provider = datetime(2026, 9, 15, 11, 58, 30, tzinfo=timezone.utc)
        self.assertEqual(require_global_freshness(provider, acquired, 120, 30), "DELAYED_120S")
        stale = datetime(2026, 9, 15, 11, 50, tzinfo=timezone.utc)
        self.assertEqual(require_global_freshness(stale, acquired, 120, 30), "STALE")

    def test_future_timestamp_fails_closed(self):
        acquired = datetime(2026, 9, 15, 12, 0, tzinfo=timezone.utc)
        provider = datetime(2026, 9, 15, 12, 2, tzinfo=timezone.utc)
        with self.assertRaises(PipelineError):
            classify_timestamp_freshness(provider, acquired, "LIVE", 300)


if __name__ == "__main__":
    unittest.main()
