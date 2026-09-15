import unittest
from datetime import datetime, timezone
from src.autonomous_acquisition import build_evidence_envelope

class BlockerShapeTests(unittest.TestCase):
    def test_blockers_have_expected_keys(self):
        envelope = build_evidence_envelope("5drreq_blockers", [], now=datetime.now(timezone.utc))
        self.assertEqual(set(envelope["blockers"]), {"missing", "unavailable", "conflicts"})

if __name__ == "__main__":
    unittest.main()
