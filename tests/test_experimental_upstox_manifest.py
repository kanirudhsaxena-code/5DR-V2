import copy
import unittest

from experiments.upstox_manifest import build_failure_manifest, build_success_manifest
from phase1.upstox import PipelineError


BASE = {
    "status": "LIVE_SAMPLE_PASSED",
    "read_only": True,
    "trading_enabled": False,
    "production_5dr_write_enabled": False,
    "transport": "curl",
    "underlying": "NSE_INDEX|Nifty 50",
    "selected_expiry": "2026-09-22",
    "market_session": {"exchange": "NFO", "status": "NORMAL_CLOSE", "last_updated": "2026-09-15T10:10:00+00:00"},
    "latest_intraday_candle": {"timestamp": "2026-09-15T15:29:00+05:30"},
    "reliability": {"status": "FRESHNESS_PASS", "mode": "CLOSED_SESSION_FINAL", "forecast_freshness_ready": False},
    "audit": {
        "snapshot_fingerprint": "1" * 64,
        "context": {"github_run_id": "123", "github_sha": "abc", "github_event_name": "push"},
    },
    "provenance": {
        "contracts": {"source_path": "/v2/option/contract", "sha256": "2" * 64, "received_at": "2026-09-15T17:51:46+00:00"},
        "market_status": {"source_path": "/v2/market/status/NFO", "sha256": "3" * 64, "received_at": "2026-09-15T17:51:47+00:00"},
        "intraday": {"source_path": "/v3/historical-candle/intraday/NSE_INDEX%7CNifty%2050/minutes/1", "sha256": "4" * 64, "received_at": "2026-09-15T17:51:48+00:00"},
        "option_chain": {"source_path": "/v2/option/chain", "sha256": "5" * 64, "received_at": "2026-09-15T17:51:49+00:00"},
    },
    "sample_strikes": [
        {"strike": 23100, "CE": {"instrument_key": "NSE_FO|1"}, "PE": {"instrument_key": "NSE_FO|2"}},
        {"strike": 23150, "CE": {"instrument_key": "NSE_FO|3"}, "PE": {"instrument_key": "NSE_FO|4"}},
    ],
}


class ManifestTests(unittest.TestCase):
    def test_success_manifest_is_sanitized_and_hashed(self):
        manifest = build_success_manifest(copy.deepcopy(BASE))
        self.assertEqual(manifest["status"], "PASS")
        self.assertTrue(manifest["read_only"])
        self.assertFalse(manifest["trading_enabled"])
        self.assertFalse(manifest["production_5dr_write_enabled"])
        self.assertEqual(manifest["coverage"]["source_count"], 4)
        self.assertEqual(manifest["coverage"]["option_leg_count"], 4)
        self.assertEqual(len(manifest["manifest_sha256"]), 64)
        text = str(manifest).lower()
        self.assertNotIn("authorization", text)
        self.assertNotIn("bearer", text)
        self.assertNotIn("token", text)

    def test_manifest_hash_is_deterministic(self):
        first = build_success_manifest(copy.deepcopy(BASE))
        second = build_success_manifest(copy.deepcopy(BASE))
        self.assertEqual(first["manifest_sha256"], second["manifest_sha256"])

    def test_bad_source_digest_fails_closed(self):
        sample = copy.deepcopy(BASE)
        sample["provenance"]["option_chain"]["sha256"] = "bad"
        with self.assertRaises(PipelineError):
            build_success_manifest(sample)

    def test_duplicate_instrument_identity_fails_closed(self):
        sample = copy.deepcopy(BASE)
        sample["sample_strikes"][1]["CE"]["instrument_key"] = "NSE_FO|1"
        with self.assertRaises(PipelineError):
            build_success_manifest(sample)

    def test_failure_manifest_is_fixed_and_sanitized(self):
        manifest = build_failure_manifest("OPTION_CHAIN", "AUTH_REJECTED", {"github_run_id": "77"})
        self.assertEqual(manifest["status"], "BLOCKED")
        self.assertEqual(manifest["diagnostic_code"], "AUTH_REJECTED")
        self.assertFalse(manifest["trading_enabled"])
        self.assertEqual(len(manifest["manifest_sha256"]), 64)


if __name__ == "__main__":
    unittest.main()
