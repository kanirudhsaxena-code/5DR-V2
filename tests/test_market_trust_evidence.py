import unittest
from datetime import datetime, timezone

from src.autonomous_acquisition import AcquisitionBlocked, SourceObservation
from src.market_trust_evidence import corroborate_market_trust


PRIMARY = SourceObservation("MARKET_TRUST", "upstox:nifty#sha256=" + "a" * 64, datetime.now(timezone.utc).isoformat(), status="DEGRADED", authority="UPSTOX_AUTHENTICATED")


class MarketTrustEvidenceTests(unittest.TestCase):
    def test_cross_market_provenance_can_corroborate(self):
        item = corroborate_market_trust(PRIMARY, ["provider:vix#sha256=" + "b" * 64, "provider:global#sha256=" + "c" * 64])
        self.assertEqual(item.status, "VERIFIED")
        self.assertEqual(item.authority, "SYSTEM_CORROBORATED")

    def test_missing_cross_market_provenance_blocks(self):
        with self.assertRaisesRegex(AcquisitionBlocked, "CROSS_MARKET_PROVENANCE_MISSING"):
            corroborate_market_trust(PRIMARY, [])


if __name__ == "__main__":
    unittest.main()
