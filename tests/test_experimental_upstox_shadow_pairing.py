import unittest

from experiments.data_contract import DataArchitectureError
from experiments.shadow_pairing import assess_pair_comparability


class ShadowPairingTests(unittest.TestCase):
    def test_exact_same_declared_window_and_cutoff_is_comparable(self):
        reference = {
            "comparison_window_id": "G11-20260916-1500",
            "evidence_cutoff_ist": "2026-09-16T15:00:00+05:30",
        }
        structured = dict(reference)
        result = assess_pair_comparability(reference, structured)
        self.assertEqual(result["status"], "COMPARABLE")
        self.assertTrue(result["acceptance_eligible"])
        self.assertEqual(result["reasons"], [])

    def test_different_cutoff_is_observational_only(self):
        reference = {
            "comparison_window_id": "G11-20260916-1500",
            "evidence_cutoff_ist": "2026-09-16T15:00:00+05:30",
        }
        structured = {
            "comparison_window_id": "G11-20260916-1500",
            "evidence_cutoff_ist": "2026-09-16T15:01:00+05:30",
        }
        result = assess_pair_comparability(reference, structured)
        self.assertEqual(result["status"], "NOT_COMPARABLE")
        self.assertFalse(result["acceptance_eligible"])
        self.assertIn("EVIDENCE_CUTOFF_MISMATCH", result["reasons"])

    def test_different_pair_id_is_not_comparable(self):
        reference = {
            "comparison_window_id": "A",
            "evidence_cutoff_ist": "2026-09-16T15:00:00+05:30",
        }
        structured = {
            "comparison_window_id": "B",
            "evidence_cutoff_ist": "2026-09-16T15:00:00+05:30",
        }
        result = assess_pair_comparability(reference, structured)
        self.assertFalse(result["acceptance_eligible"])
        self.assertIn("COMPARISON_WINDOW_ID_MISMATCH", result["reasons"])

    def test_missing_pair_metadata_fails_closed(self):
        with self.assertRaises(DataArchitectureError):
            assess_pair_comparability({}, {})


if __name__ == "__main__":
    unittest.main()
