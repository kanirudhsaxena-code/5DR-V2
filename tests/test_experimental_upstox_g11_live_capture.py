import unittest
from datetime import datetime
from zoneinfo import ZoneInfo

from experiments.data_contract import DataArchitectureError
from experiments.g11_live_capture import build_structured_capture, schedule_capture

IST = ZoneInfo("Asia/Kolkata")


def _bundle(frozen="2026-09-17T09:45:20+05:30"):
    return {
        "status": "READY",
        "run_id": "G11-STRUCTURED-TEST",
        "frozen_at": frozen,
        "bundle_sha256": "a" * 64,
        "runtime_context": {
            "forecast_release_enabled": False,
            "production_5dr_write_enabled": False,
            "lifecycle_write_enabled": False,
            "trading_enabled": False,
            "canonical_integration_enabled": False,
            "methodology_changed": False,
        },
    }


class G11LiveCaptureTests(unittest.TestCase):
    def test_target_session_builds_deterministic_pair_and_wait(self):
        scheduled = schedule_capture(datetime(2026, 9, 17, 9, 44, 0, tzinfo=IST))
        self.assertEqual(scheduled["pair_id"], "G11-20260917-0945")
        self.assertEqual(scheduled["evidence_cutoff_ist"], "2026-09-17T09:45:00+05:30")
        self.assertEqual(scheduled["wait_seconds"], 60.0)

    def test_non_target_or_late_capture_fails_closed(self):
        with self.assertRaises(DataArchitectureError):
            schedule_capture(datetime(2026, 9, 16, 9, 45, tzinfo=IST))
        with self.assertRaises(DataArchitectureError):
            schedule_capture(datetime(2026, 9, 17, 9, 47, 1, tzinfo=IST))

    def test_ready_bundle_is_bound_to_exact_window_and_digest(self):
        scheduled = schedule_capture(datetime(2026, 9, 17, 9, 45, 10, tzinfo=IST))
        capture = build_structured_capture(
            _bundle(), scheduled, datetime(2026, 9, 17, 9, 45, 10, tzinfo=IST)
        )
        self.assertEqual(capture["source_mode"], "UPSTOX_STRUCTURED")
        self.assertEqual(capture["comparison_window_id"], "G11-20260917-0945")
        self.assertEqual(capture["evidence_cutoff_ist"], "2026-09-17T09:45:00+05:30")
        self.assertEqual(capture["evidence_fingerprint"], "a" * 64)
        self.assertEqual(len(capture["capture_sha256"]), 64)
        self.assertFalse(capture["acceptance_decision_made"])

    def test_tampered_or_side_effect_bundle_fails_closed(self):
        scheduled = schedule_capture(datetime(2026, 9, 17, 9, 45, 10, tzinfo=IST))
        bad = _bundle()
        bad["bundle_sha256"] = "bad"
        with self.assertRaises(DataArchitectureError):
            build_structured_capture(bad, scheduled, datetime(2026, 9, 17, 9, 45, 10, tzinfo=IST))
        unsafe = _bundle()
        unsafe["runtime_context"]["trading_enabled"] = True
        with self.assertRaises(DataArchitectureError):
            build_structured_capture(unsafe, scheduled, datetime(2026, 9, 17, 9, 45, 10, tzinfo=IST))

    def test_freeze_lag_outside_tolerance_fails(self):
        scheduled = schedule_capture(datetime(2026, 9, 17, 9, 45, 10, tzinfo=IST))
        late = _bundle("2026-09-17T09:48:01+05:30")
        with self.assertRaises(DataArchitectureError):
            build_structured_capture(late, scheduled, datetime(2026, 9, 17, 9, 45, 10, tzinfo=IST))


if __name__ == "__main__":
    unittest.main()
