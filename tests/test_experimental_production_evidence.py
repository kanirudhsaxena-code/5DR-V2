import unittest
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from experiments.data_contract import DataArchitectureError
from experiments.production_evidence import (
    build_production_evidence_audit,
    classify_production_window,
)

IST = ZoneInfo("Asia/Kolkata")


def fake_bundle():
    return {
        "status": "READY",
        "run_id": "V223-PROD-TEST",
        "bundle_sha256": "a" * 64,
        "screenshot_policy": {"screenshot_dependency": False},
        "runtime_context": {
            "forecast_release_enabled": False,
            "production_5dr_write_enabled": False,
            "lifecycle_write_enabled": False,
            "trading_enabled": False,
            "canonical_integration_enabled": False,
            "methodology_changed": False,
        },
        "forecast_released": False,
        "production_5dr_write_enabled": False,
        "trading_enabled": False,
    }


class ProductionEvidenceTests(unittest.TestCase):
    def test_prior_close_window_is_canonical_candidate(self):
        now = datetime(2026, 9, 18, 15, 25, tzinfo=IST)
        row = classify_production_window(now)
        self.assertEqual(row["label"], "PRIOR_CLOSE_REFRESH")
        self.assertEqual(row["run_class"], "CANONICAL_CANDIDATE")

    def test_late_morning_window_is_intraday_snapshot(self):
        now = datetime(2026, 9, 18, 10, 30, tzinfo=IST)
        row = classify_production_window(now)
        self.assertEqual(row["label"], "LATE_MORNING_SNAPSHOT")
        self.assertEqual(row["run_class"], "INTRADAY_SNAPSHOT")

    def test_outside_window_fails_closed(self):
        with self.assertRaises(DataArchitectureError):
            classify_production_window(datetime(2026, 9, 18, 9, 0, tzinfo=IST))

    def test_weekend_fails_closed(self):
        with self.assertRaises(DataArchitectureError):
            classify_production_window(datetime(2026, 9, 19, 10, 30, tzinfo=IST))

    def test_naive_time_fails_closed(self):
        with self.assertRaises(DataArchitectureError):
            classify_production_window(datetime(2026, 9, 18, 10, 30))

    def test_ready_bundle_passes_without_release_or_write(self):
        audit = build_production_evidence_audit(
            fake_bundle(), datetime(2026, 9, 18, 10, 30, tzinfo=IST)
        )
        self.assertEqual(audit["status"], "PRODUCTION_EVIDENCE_READY")
        self.assertTrue(audit["structured_evidence_primary"])
        self.assertFalse(audit["routine_screenshot_required"])
        self.assertFalse(audit["forecast_release_enabled"])
        self.assertFalse(audit["production_5dr_write_enabled"])
        self.assertFalse(audit["trading_execution_enabled"])

    def test_screenshot_dependency_fails_closed(self):
        bundle = fake_bundle()
        bundle["screenshot_policy"]["screenshot_dependency"] = True
        with self.assertRaises(DataArchitectureError):
            build_production_evidence_audit(
                bundle, datetime(2026, 9, 18, 10, 30, tzinfo=IST)
            )

    def test_runtime_side_effect_flag_fails_closed(self):
        bundle = fake_bundle()
        bundle["runtime_context"]["canonical_integration_enabled"] = True
        with self.assertRaises(DataArchitectureError):
            build_production_evidence_audit(
                bundle, datetime(2026, 9, 18, 10, 30, tzinfo=IST)
            )


if __name__ == "__main__":
    unittest.main()
