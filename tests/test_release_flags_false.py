import unittest
from datetime import datetime, timezone
from src.autonomous_acquisition import build_evidence_envelope


class ReleaseFlagTests(unittest.TestCase):
    def test_even_blocked_empty_envelope_disables_release(self):
        envelope = build_evidence_envelope("5drreq_flags", [], now=datetime.now(timezone.utc))
        self.assertIs(envelope["trading_enabled"], False)
        self.assertIs(envelope["forecast_release_enabled"], False)


if __name__ == "__main__":
    unittest.main()
