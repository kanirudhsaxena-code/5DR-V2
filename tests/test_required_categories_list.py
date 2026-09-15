import unittest
from datetime import datetime, timezone
from src.autonomous_acquisition import build_evidence_envelope

class RequiredCategoriesTests(unittest.TestCase):
    def test_required_categories_exact(self):
        envelope = build_evidence_envelope("5drreq_req", [], now=datetime.now(timezone.utc))
        self.assertEqual(envelope["required_categories"], ["MARKET_TRUST", "EVENT_SHOCK", "EXECUTION_RISK"])

if __name__ == "__main__":
    unittest.main()
