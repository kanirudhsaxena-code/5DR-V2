import unittest
from datetime import datetime, timezone
from src.autonomous_acquisition import SourceObservation, build_evidence_envelope


class AuthorityFieldTests(unittest.TestCase):
    def test_authority_survives_handoff(self):
        now = datetime.now(timezone.utc)
        items = [SourceObservation(c, f"source:{c}", now.isoformat(), authority="TEST_AUTHORITY") for c in ("MARKET_TRUST", "EVENT_SHOCK", "EXECUTION_RISK")]
        envelope = build_evidence_envelope("5drreq_authority", items, now=now)
        self.assertTrue(all(i["authority"] == "TEST_AUTHORITY" for i in envelope["items"]))


if __name__ == "__main__":
    unittest.main()
