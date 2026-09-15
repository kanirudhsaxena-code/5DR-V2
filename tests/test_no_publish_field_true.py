import unittest
from datetime import datetime, timezone
from src.autonomous_acquisition import build_evidence_envelope

class NoPublishTests(unittest.TestCase):
    def test_empty_blocked_envelope_nonpublishing(self):
        e = build_evidence_envelope("5drreq_np", [], now=datetime.now(timezone.utc))
        self.assertFalse(e["forecast_release_enabled"])

if __name__ == "__main__":
    unittest.main()
