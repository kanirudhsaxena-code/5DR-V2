import unittest
from datetime import datetime, timezone
from src.autonomous_acquisition import SourceObservation, build_evidence_envelope


class AcquisitionContractFieldTests(unittest.TestCase):
    def test_required_handoff_fields_present(self):
        now = datetime.now(timezone.utc)
        items = [SourceObservation(c, f"source:{c}", now.isoformat()) for c in ("MARKET_TRUST", "EVENT_SHOCK", "EXECUTION_RISK")]
        envelope = build_evidence_envelope("5drreq_fields", items, now=now)
        for field in ("request_id", "status", "assessed_at", "required_categories", "items", "blockers", "trading_enabled", "forecast_release_enabled"):
            self.assertIn(field, envelope)


if __name__ == "__main__":
    unittest.main()
