import unittest
from datetime import datetime, timezone

from src.autonomous_acquisition import SourceObservation, build_evidence_envelope


class ShadowReleaseGateTests(unittest.TestCase):
    def test_ready_evidence_still_cannot_publish_in_shadow(self):
        now = datetime.now(timezone.utc)
        items = [SourceObservation(category, f"source:{category}", now.isoformat()) for category in ("MARKET_TRUST", "EVENT_SHOCK", "EXECUTION_RISK")]
        envelope = build_evidence_envelope("5drreq_ready_shadow", items, now=now)
        self.assertEqual(envelope["status"], "AUTONOMOUS_EVIDENCE_READY")
        self.assertFalse(envelope["forecast_release_enabled"])
        self.assertFalse(envelope["trading_enabled"])


if __name__ == "__main__":
    unittest.main()
