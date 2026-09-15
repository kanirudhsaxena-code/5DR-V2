import unittest
from datetime import datetime, timezone
from src.autonomous_acquisition import SourceObservation, build_evidence_envelope


class StateVocabularyTests(unittest.TestCase):
    def test_acquisition_emits_only_ready_or_blocked(self):
        now = datetime.now(timezone.utc)
        blocked = build_evidence_envelope("5drreq_b", [], now=now)
        ready = build_evidence_envelope("5drreq_r", [SourceObservation(c, f"source:{c}", now.isoformat()) for c in ("MARKET_TRUST", "EVENT_SHOCK", "EXECUTION_RISK")], now=now)
        self.assertEqual({blocked["status"], ready["status"]}, {"AUTONOMOUS_EVIDENCE_BLOCKED", "AUTONOMOUS_EVIDENCE_READY"})


if __name__ == "__main__":
    unittest.main()
