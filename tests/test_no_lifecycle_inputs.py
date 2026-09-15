import unittest
from pathlib import Path


class NoLifecycleInputTests(unittest.TestCase):
    def test_acquisition_code_does_not_require_lifecycle_output_fields(self):
        text = "\n".join(Path(p).read_text() for p in ("src/autonomous_acquisition.py", "src/upstox_evidence.py", "src/event_evidence.py", "src/market_trust_evidence.py", "src/execution_risk_evidence.py"))
        for forbidden in ("forecast_assessment", "recommendation_assessment", "horizon_slots", "recommendation_ledger_complete", "assessment_snapshot_complete"):
            self.assertNotIn(forbidden, text)


if __name__ == "__main__":
    unittest.main()
