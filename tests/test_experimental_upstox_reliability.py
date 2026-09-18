import copy
import unittest
from datetime import datetime, timezone

from experiments.upstox_reliability import annotate_sample, compare_snapshots, snapshot_fingerprint, validate_freshness
from phase1.upstox import PipelineError


NOW = datetime(2026, 9, 15, 17, 46, 5, tzinfo=timezone.utc)


def sample(status="NORMAL_CLOSE", candle="2026-09-15T15:29:00+05:30", session_updated="2026-09-15T10:10:00+00:00"):
    received = "2026-09-15T17:46:00+00:00"
    return {
        "underlying": "NSE_INDEX|Nifty 50",
        "selected_expiry": "2026-09-22",
        "market_session": {"exchange": "NFO", "status": status, "last_updated": session_updated},
        "latest_intraday_candle": {"timestamp": candle, "open": 1, "high": 2, "low": 1, "close": 2, "volume": 0, "open_interest": 0},
        "provenance": {
            "contracts": {"source_path": "/v2/option/contract", "sha256": "a" * 64, "received_at": received},
            "market_status": {"source_path": "/v2/market/status/NFO", "sha256": "b" * 64, "received_at": received},
            "intraday": {"source_path": "/v3/historical-candle/intraday/x/minutes/1", "sha256": "c" * 64, "received_at": received},
            "option_chain": {"source_path": "/v2/option/chain", "sha256": "d" * 64, "received_at": received},
        },
    }


class ReliabilityTests(unittest.TestCase):
    def test_fingerprint_stable_across_receipt_time_and_audit_metadata(self):
        first = sample()
        second = copy.deepcopy(first)
        for entry in second["provenance"].values():
            entry["received_at"] = "2026-09-15T17:46:04+00:00"
        second["audit"] = {"ignored": True}
        self.assertEqual(snapshot_fingerprint(first), snapshot_fingerprint(second))

    def test_bad_digest_fails_closed(self):
        data = sample()
        data["provenance"]["intraday"]["sha256"] = "bad"
        with self.assertRaises(PipelineError):
            snapshot_fingerprint(data)

    def test_closed_session_final_candle_passes_after_hours(self):
        report = validate_freshness(sample(), now=NOW)
        self.assertEqual(report["mode"], "CLOSED_SESSION_FINAL")
        self.assertFalse(report["forecast_freshness_ready"])

    def test_closed_session_wrong_day_fails_closed(self):
        data = sample(candle="2026-09-12T15:29:00+05:30")
        with self.assertRaises(PipelineError):
            validate_freshness(data, now=NOW)

    def test_open_market_recent_candle_passes(self):
        now = datetime(2026, 9, 16, 5, 1, 30, tzinfo=timezone.utc)  # 10:31 IST
        data = sample(
            status="NORMAL_OPEN",
            candle="2026-09-16T10:30:00+05:30",
            session_updated="2026-09-16T03:45:00+00:00",
        )
        for entry in data["provenance"].values():
            entry["received_at"] = "2026-09-16T05:01:25+00:00"
        report = validate_freshness(data, now=now)
        self.assertEqual(report["mode"], "LIVE_OPEN")
        self.assertTrue(report["forecast_freshness_ready"])

    def test_open_market_stale_candle_fails_closed(self):
        now = datetime(2026, 9, 16, 5, 10, 0, tzinfo=timezone.utc)
        data = sample(
            status="NORMAL_OPEN",
            candle="2026-09-16T10:00:00+05:30",
            session_updated="2026-09-16T03:45:00+00:00",
        )
        for entry in data["provenance"].values():
            entry["received_at"] = "2026-09-16T05:09:55+00:00"
        with self.assertRaises(PipelineError):
            validate_freshness(data, now=now)

    def test_stale_receipt_fails_closed(self):
        data = sample()
        data["provenance"]["contracts"]["received_at"] = "2026-09-15T17:30:00+00:00"
        with self.assertRaises(PipelineError):
            validate_freshness(data, now=NOW)

    def test_annotate_adds_audit_fingerprint_without_market_mutation(self):
        data = sample()
        result = annotate_sample(data, now=NOW, audit_context={"github_run_id": 123, "github_sha": "abc"})
        self.assertEqual(len(result["audit"]["snapshot_fingerprint"]), 64)
        self.assertEqual(result["audit"]["context"]["github_run_id"], "123")
        self.assertEqual(result["selected_expiry"], "2026-09-22")

    def test_closed_market_duplicate_is_expected(self):
        first = sample()
        second = copy.deepcopy(first)
        result = compare_snapshots(first, second, 75)
        self.assertTrue(result["duplicate"])
        self.assertEqual(result["classification"], "EXPECTED_STATIC_NONTRADING_SESSION")

    def test_open_market_nonadvancing_snapshot_after_one_minute_fails(self):
        first = sample(status="NORMAL_OPEN", candle="2026-09-16T10:30:00+05:30", session_updated="2026-09-16T03:45:00+00:00")
        second = copy.deepcopy(first)
        with self.assertRaises(PipelineError):
            compare_snapshots(first, second, 75)

    def test_open_market_advanced_snapshot_passes(self):
        first = sample(status="NORMAL_OPEN", candle="2026-09-16T10:30:00+05:30", session_updated="2026-09-16T03:45:00+00:00")
        second = copy.deepcopy(first)
        second["latest_intraday_candle"]["timestamp"] = "2026-09-16T10:31:00+05:30"
        second["provenance"]["intraday"]["sha256"] = "e" * 64
        result = compare_snapshots(first, second, 75)
        self.assertFalse(result["duplicate"])
        self.assertEqual(result["classification"], "ADVANCED")


if __name__ == "__main__":
    unittest.main()
