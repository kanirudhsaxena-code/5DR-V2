import hashlib
import json
import unittest
from copy import deepcopy

from experiments.g11_live_capture import CAPTURE_SCHEMA
from experiments.g11_rollover import rollover_run_key, validate_next_session_rollover
from experiments.data_contract import DataArchitectureError


PRIOR_BUNDLE = "a" * 64
CURRENT_BUNDLE = "b" * 64


def prior_series():
    return {
        "schema": "5dr-v2-2-3-gate-record-v1",
        "gate": "G11_MANUAL_SAME_SESSION_SERIES",
        "status": "MANUAL_SERIES_PASS_ROLLOVER_PENDING",
        "session_date": "2026-09-17",
        "runs": [
            {"sequence": 1, "status": "PASS", "bundle_sha256": PRIOR_BUNDLE},
            {"sequence": 2, "status": "PASS", "bundle_sha256": "c" * 64},
            {"sequence": 3, "status": "PASS", "bundle_sha256": "d" * 64},
        ],
        "g11_final_gate_status": "PENDING_NEXT_SESSION_ROLLOVER",
    }


def capture(session_date="2026-09-18", bundle_sha=CURRENT_BUNDLE):
    row = {
        "schema": CAPTURE_SCHEMA,
        "status": "EVIDENCE_FROZEN_PENDING_GOVERNED_JUDGMENT",
        "source_mode": "UPSTOX_STRUCTURED",
        "request_id": "G11-ROLLOVER-20260918",
        "manual_run_id": "G11-ROLLOVER-20260918",
        "comparison_window_id": "G11-ROLLOVER-20260918",
        "evidence_cutoff_ist": f"{session_date}T09:30:00+05:30",
        "session_date_ist": session_date,
        "capture_started_at_ist": f"{session_date}T09:30:03+05:30",
        "bundle_frozen_at_ist": f"{session_date}T09:30:20+05:30",
        "capture_start_lag_seconds": 3.0,
        "bundle_freeze_lag_seconds": 20.0,
        "evidence_fingerprint": bundle_sha,
        "bundle_sha256": bundle_sha,
        "acceptance_decision_made": False,
        "production_activation_decision_made": False,
        "forecast_released": False,
        "production_5dr_write_enabled": False,
        "lifecycle_write_enabled": False,
        "trading_execution_enabled": False,
        "methodology_changed": False,
    }
    canonical = json.dumps(row, sort_keys=True, separators=(",", ":"))
    row["capture_sha256"] = hashlib.sha256(canonical.encode()).hexdigest()
    return row


def market_status(session_date="2026-09-18"):
    return {
        "exchange": "NFO",
        "status": "NORMAL_OPEN",
        "last_updated": f"{session_date}T09:15:00+05:30",
        "received_at": f"{session_date}T09:30:02+05:30",
    }


class G11RolloverTests(unittest.TestCase):
    def test_valid_next_session_rollover_passes(self):
        result = validate_next_session_rollover(
            previous_series=prior_series(),
            current_capture=capture(),
            market_status=market_status(),
            active_expiries=["2026-09-22", "2026-09-29"],
            replay_bundle_sha256=CURRENT_BUNDLE,
        )
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(result["session_date"], "2026-09-18")
        self.assertEqual(result["evidence"]["selected_expiry"], "2026-09-22")
        self.assertFalse(result["governance"]["production_activation_allowed"])
        self.assertFalse(result["governance"]["pr30_merge_allowed"])
        self.assertEqual(len(result["gate_sha256"]), 64)

    def test_same_session_evidence_fails_closed(self):
        with self.assertRaisesRegex(DataArchitectureError, "did not advance"):
            validate_next_session_rollover(
                previous_series=prior_series(),
                current_capture=capture("2026-09-17"),
                market_status=market_status("2026-09-17"),
                active_expiries=["2026-09-22"],
                replay_bundle_sha256=CURRENT_BUNDLE,
            )

    def test_prior_bundle_reuse_fails_closed(self):
        with self.assertRaisesRegex(DataArchitectureError, "prior-session bundle reused"):
            validate_next_session_rollover(
                previous_series=prior_series(),
                current_capture=capture(bundle_sha=PRIOR_BUNDLE),
                market_status=market_status(),
                active_expiries=["2026-09-22"],
                replay_bundle_sha256=PRIOR_BUNDLE,
            )

    def test_stale_market_status_fails_closed(self):
        with self.assertRaisesRegex(DataArchitectureError, "market status is not from"):
            validate_next_session_rollover(
                previous_series=prior_series(),
                current_capture=capture(),
                market_status=market_status("2026-09-17"),
                active_expiries=["2026-09-22"],
                replay_bundle_sha256=CURRENT_BUNDLE,
            )

    def test_stale_expiry_set_fails_closed(self):
        with self.assertRaises(DataArchitectureError):
            validate_next_session_rollover(
                previous_series=prior_series(),
                current_capture=capture(),
                market_status=market_status(),
                active_expiries=["2026-09-17"],
                replay_bundle_sha256=CURRENT_BUNDLE,
            )

    def test_mutated_capture_hash_fails_closed(self):
        row = capture()
        row["bundle_freeze_lag_seconds"] = 21.0
        with self.assertRaisesRegex(DataArchitectureError, "capture fingerprint mismatch"):
            validate_next_session_rollover(
                previous_series=prior_series(),
                current_capture=row,
                market_status=market_status(),
                active_expiries=["2026-09-22"],
                replay_bundle_sha256=CURRENT_BUNDLE,
            )

    def test_replay_hash_mismatch_fails_closed(self):
        with self.assertRaisesRegex(DataArchitectureError, "deterministic replay mismatch"):
            validate_next_session_rollover(
                previous_series=prior_series(),
                current_capture=capture(),
                market_status=market_status(),
                active_expiries=["2026-09-22"],
                replay_bundle_sha256="e" * 64,
            )

    def test_duplicate_run_key_fails_closed(self):
        key = rollover_run_key("2026-09-18")
        with self.assertRaisesRegex(DataArchitectureError, "duplicate run blocked"):
            validate_next_session_rollover(
                previous_series=prior_series(),
                current_capture=capture(),
                market_status=market_status(),
                active_expiries=["2026-09-22"],
                replay_bundle_sha256=CURRENT_BUNDLE,
                completed_run_keys=[key],
            )

    def test_safety_flag_crossing_fails_closed(self):
        row = capture()
        row["production_5dr_write_enabled"] = True
        unsigned = dict(row)
        unsigned.pop("capture_sha256")
        row["capture_sha256"] = hashlib.sha256(
            json.dumps(unsigned, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        with self.assertRaisesRegex(DataArchitectureError, "safety boundary crossed"):
            validate_next_session_rollover(
                previous_series=prior_series(),
                current_capture=row,
                market_status=market_status(),
                active_expiries=["2026-09-22"],
                replay_bundle_sha256=CURRENT_BUNDLE,
            )


if __name__ == "__main__":
    unittest.main()
