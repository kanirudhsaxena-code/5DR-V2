import unittest
from datetime import datetime, timezone
from src.autonomous_acquisition import SourceObservation, build_evidence_envelope


class UnavailableEvidenceTests(unittest.TestCase):
    def test_unavailable_item_without_ref_is_valid_but_blocks(self):
        now = datetime.now(timezone.utc)
        items = [
            SourceObservation("MARKET_TRUST", "source:market", now.isoformat()),
            SourceObservation("EVENT_SHOCK", "", now.isoformat(), status="UNAVAILABLE"),
            SourceObservation("EXECUTION_RISK", "source:exec", now.isoformat()),
        ]
        envelope = build_evidence_envelope("5drreq_unavailable", items, now=now)
        self.assertEqual(envelope["status"], "AUTONOMOUS_EVIDENCE_BLOCKED")
        self.assertIn("EVENT_SHOCK", envelope["blockers"]["unavailable"])


if __name__ == "__main__":
    unittest.main()
