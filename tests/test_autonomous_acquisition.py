import unittest
from datetime import datetime, timedelta, timezone

from src.autonomous_acquisition import AcquisitionBlocked, SourceObservation, build_evidence_envelope


NOW = datetime(2026, 9, 15, 10, 30, tzinfo=timezone.utc)


def obs(category, *, status="VERIFIED", source="provider://verified", detail=None, age=30):
    return SourceObservation(category, source, (NOW - timedelta(seconds=age)).isoformat(), status=status, detail=detail)


class AutonomousAcquisitionTests(unittest.TestCase):
    def test_all_system_categories_ready(self):
        envelope = build_evidence_envelope("5drreq_test", [obs("MARKET_TRUST"), obs("EVENT_SHOCK"), obs("EXECUTION_RISK")], now=NOW)
        self.assertEqual(envelope["status"], "AUTONOMOUS_EVIDENCE_READY")
        self.assertFalse(envelope["forecast_release_enabled"])

    def test_missing_category_blocks(self):
        envelope = build_evidence_envelope("5drreq_test", [obs("MARKET_TRUST"), obs("EVENT_SHOCK")], now=NOW)
        self.assertEqual(envelope["status"], "AUTONOMOUS_EVIDENCE_BLOCKED")
        self.assertIn("EXECUTION_RISK", envelope["blockers"]["missing"])

    def test_total_source_failure_blocks(self):
        envelope = build_evidence_envelope("5drreq_test", [obs("MARKET_TRUST", status="UNAVAILABLE", source=""), obs("EVENT_SHOCK", status="UNAVAILABLE", source=""), obs("EXECUTION_RISK", status="UNAVAILABLE", source="")], now=NOW)
        self.assertEqual(envelope["status"], "AUTONOMOUS_EVIDENCE_BLOCKED")
        self.assertEqual(set(envelope["blockers"]["unavailable"]), {"MARKET_TRUST", "EVENT_SHOCK", "EXECUTION_RISK"})

    def test_stale_verified_data_fails_closed(self):
        with self.assertRaisesRegex(AcquisitionBlocked, "STALE_EVIDENCE"):
            build_evidence_envelope("5drreq_test", [obs("MARKET_TRUST", age=3600), obs("EVENT_SHOCK"), obs("EXECUTION_RISK")], now=NOW)

    def test_verified_requires_provenance(self):
        with self.assertRaisesRegex(AcquisitionBlocked, "SOURCE_REF_REQUIRED"):
            build_evidence_envelope("5drreq_test", [obs("MARKET_TRUST", source=""), obs("EVENT_SHOCK"), obs("EXECUTION_RISK")], now=NOW)

    def test_conflicting_verified_observations_block(self):
        envelope = build_evidence_envelope("5drreq_test", [obs("MARKET_TRUST", source="provider://a", detail="risk_on"), obs("MARKET_TRUST", source="provider://b", detail="risk_off"), obs("EVENT_SHOCK"), obs("EXECUTION_RISK")], now=NOW)
        self.assertEqual(envelope["status"], "AUTONOMOUS_EVIDENCE_BLOCKED")
        self.assertIn("MARKET_TRUST", envelope["blockers"]["conflicts"])


if __name__ == "__main__":
    unittest.main()
