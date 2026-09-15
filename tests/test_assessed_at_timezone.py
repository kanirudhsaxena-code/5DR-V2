import unittest
from datetime import datetime, timezone
from src.autonomous_acquisition import build_evidence_envelope


class AssessedAtTests(unittest.TestCase):
    def test_assessed_at_is_timezone_aware(self):
        envelope = build_evidence_envelope("5drreq_time", [], now=datetime.now(timezone.utc))
        parsed = datetime.fromisoformat(envelope["assessed_at"])
        self.assertIsNotNone(parsed.tzinfo)


if __name__ == "__main__":
    unittest.main()
