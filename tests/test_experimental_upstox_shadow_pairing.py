import unittest

from experiments.data_contract import DataArchitectureError
from experiments.shadow_pairing import assess_pair_comparability


class ShadowPairingTests(unittest.TestCase):
    def test_same_run_within_preferred_tolerance_is_comparable(self):
        reference = {"comparison_window_id":"G11-20260917-RUN1","evidence_cutoff_ist":"2026-09-17T10:02:00+05:30"}
        structured = {"comparison_window_id":"G11-20260917-RUN1","evidence_cutoff_ist":"2026-09-17T10:00:00+05:30"}
        result = assess_pair_comparability(reference, structured)
        self.assertEqual(result["status"], "COMPARABLE")
        self.assertEqual(result["timing_quality"], "PREFERRED")
        self.assertEqual(result["pair_delta_seconds"], 120.0)

    def test_same_run_within_five_minutes_is_comparable_with_tolerance(self):
        reference = {"comparison_window_id":"G11-20260917-RUN1","evidence_cutoff_ist":"2026-09-17T10:04:00+05:30"}
        structured = {"comparison_window_id":"G11-20260917-RUN1","evidence_cutoff_ist":"2026-09-17T10:00:00+05:30"}
        result = assess_pair_comparability(reference, structured)
        self.assertTrue(result["acceptance_eligible"])
        self.assertEqual(result["timing_quality"], "WITHIN_TOLERANCE")

    def test_over_five_minutes_is_not_comparable(self):
        reference = {"comparison_window_id":"G11-20260917-RUN1","evidence_cutoff_ist":"2026-09-17T10:06:00+05:30"}
        structured = {"comparison_window_id":"G11-20260917-RUN1","evidence_cutoff_ist":"2026-09-17T10:00:00+05:30"}
        result = assess_pair_comparability(reference, structured)
        self.assertFalse(result["acceptance_eligible"])
        self.assertIn("EVIDENCE_TIME_DELTA_EXCEEDS_TOLERANCE", result["reasons"])

    def test_different_pair_id_is_not_comparable(self):
        reference = {"comparison_window_id":"A","evidence_cutoff_ist":"2026-09-17T10:00:00+05:30"}
        structured = {"comparison_window_id":"B","evidence_cutoff_ist":"2026-09-17T10:00:00+05:30"}
        result = assess_pair_comparability(reference, structured)
        self.assertFalse(result["acceptance_eligible"])
        self.assertIn("COMPARISON_WINDOW_ID_MISMATCH", result["reasons"])

    def test_missing_pair_metadata_fails_closed(self):
        with self.assertRaises(DataArchitectureError):
            assess_pair_comparability({}, {})


if __name__ == "__main__":
    unittest.main()
