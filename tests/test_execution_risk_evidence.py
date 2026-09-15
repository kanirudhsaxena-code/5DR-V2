import unittest
from datetime import datetime, timezone

from src.autonomous_acquisition import AcquisitionBlocked, SourceObservation
from src.execution_risk_evidence import derive_execution_risk


class ExecutionRiskEvidenceTests(unittest.TestCase):
    def test_derived_item_has_system_provenance(self):
        item = SourceObservation("EXECUTION_RISK", "upstox:/v2/option/chain#sha256=" + "a" * 64, datetime.now(timezone.utc).isoformat(), status="DEGRADED", authority="UPSTOX_AUTHENTICATED")
        derived = derive_execution_risk([item])
        self.assertEqual(derived.authority, "SYSTEM_DERIVED")
        self.assertTrue(derived.source_ref.startswith("derived:execution-input-provenance#sha256="))
        self.assertEqual(derived.status, "DEGRADED")

    def test_missing_market_provenance_blocks(self):
        with self.assertRaisesRegex(AcquisitionBlocked, "EXECUTION_INPUT_PROVENANCE_MISSING"):
            derive_execution_risk([])


if __name__ == "__main__":
    unittest.main()
