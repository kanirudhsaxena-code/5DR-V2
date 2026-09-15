import unittest

from src.upstox_evidence import acquire_market_observations


class FakeClient:
    def intraday(self):
        return {"received_at": "2026-09-15T10:30:00+00:00", "source_path": "/v3/historical-candle/intraday/NSE_INDEX%7CNifty%2050/minutes/1", "sha256": "a" * 64}

    def chain(self, expiry):
        return {"received_at": "2026-09-15T10:30:01+00:00", "source_path": "/v2/option/chain", "sha256": "b" * 64}


class UpstoxEvidenceTests(unittest.TestCase):
    def test_adapter_preserves_bounded_provenance(self):
        items = acquire_market_observations(FakeClient(), "2026-09-17")
        self.assertEqual([i.category for i in items], ["MARKET_TRUST", "EXECUTION_RISK"])
        self.assertTrue(all(i.status == "DEGRADED" for i in items))
        self.assertTrue(all(i.source_ref.startswith("upstox:") for i in items))
        self.assertNotIn("payload", repr(items))


if __name__ == "__main__":
    unittest.main()
