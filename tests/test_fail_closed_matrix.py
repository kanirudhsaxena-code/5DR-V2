import unittest
from datetime import datetime, timezone

from src.autonomous_acquisition import SourceObservation, build_evidence_envelope


class FailClosedMatrixTests(unittest.TestCase):
    def test_degraded_fallback_is_preserved_not_silently_promoted(self):
        now = datetime.now(timezone.utc)
        items = [
            SourceObservation("MARKET_TRUST", "source:market", now.isoformat()),
            SourceObservation("EVENT_SHOCK", "source:event-fallback", now.isoformat(), status="DEGRADED", fallback_used=True),
            SourceObservation("EXECUTION_RISK", "source:execution", now.isoformat()),
        ]
        envelope = build_evidence_envelope("5drreq_degraded", items, now=now)
        self.assertEqual(envelope["status"], "AUTONOMOUS_EVIDENCE_READY")
        event = next(i for i in envelope["items"] if i["category"] == "EVENT_SHOCK")
        self.assertEqual(event["status"], "DEGRADED")
        self.assertTrue(event["fallback_used"])
        self.assertFalse(envelope["forecast_release_enabled"])


if __name__ == "__main__":
    unittest.main()
