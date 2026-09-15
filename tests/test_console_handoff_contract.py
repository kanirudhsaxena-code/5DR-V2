import json
import unittest
from datetime import datetime, timezone

from src.autonomous_acquisition import SourceObservation, build_evidence_envelope


class ConsoleHandoffContractTests(unittest.TestCase):
    def test_envelope_is_bounded_and_contains_no_secret_fields(self):
        now = datetime.now(timezone.utc)
        items = [SourceObservation(c, f"source:{c}#sha256=" + "a" * 64, now.isoformat()) for c in ("MARKET_TRUST", "EVENT_SHOCK", "EXECUTION_RISK")]
        envelope = build_evidence_envelope("5drreq_contract", items, now=now)
        text = json.dumps(envelope).lower()
        self.assertEqual(envelope["status"], "AUTONOMOUS_EVIDENCE_READY")
        for forbidden in ("token", "authorization", "client_secret", "raw_payload", "screenshot_bytes"):
            self.assertNotIn(forbidden, text)


if __name__ == "__main__":
    unittest.main()
