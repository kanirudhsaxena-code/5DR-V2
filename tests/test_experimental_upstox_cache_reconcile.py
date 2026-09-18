import copy
import unittest

from experiments.cache_reconcile import normalize_candle, reconcile_candles
from experiments.data_contract import DataArchitectureError

PROV_A = {"source_path": "/v3/history", "sha256": "a" * 64, "received_at": "2026-09-16T06:00:00+00:00"}
PROV_B = {"source_path": "/v3/history", "sha256": "b" * 64, "received_at": "2026-09-16T07:00:00+00:00"}
ROW_1 = ["2026-09-15T09:15:00+05:30", 100, 110, 90, 105, 10, 0]
ROW_2 = ["2026-09-15T09:20:00+05:30", 105, 112, 100, 108, 12, 0]


class CacheReconcileTests(unittest.TestCase):
    def test_exact_overlap_is_deduplicated_without_market_mutation(self):
        first = reconcile_candles([], [ROW_1], PROV_A)
        second = reconcile_candles(first["records"], [ROW_1], PROV_B)
        self.assertEqual(second["record_count"], 1)
        self.assertEqual(second["duplicate_count"], 1)
        self.assertEqual(second["correction_count"], 0)
        self.assertEqual(second["dataset_sha256"], first["dataset_sha256"])

    def test_provider_correction_is_replaced_with_explicit_audit_link(self):
        first = reconcile_candles([], [ROW_1], PROV_A)
        corrected = copy.deepcopy(ROW_1)
        corrected[4] = 106
        second = reconcile_candles(first["records"], [corrected], PROV_B)
        self.assertEqual(second["correction_count"], 1)
        self.assertEqual(second["record_count"], 1)
        self.assertEqual(second["records"][0]["candle"][4], 106)
        self.assertEqual(second["records"][0]["supersedes_market_sha256"], first["records"][0]["market_sha256"])
        self.assertEqual(second["audit_events"][0]["event"], "PROVIDER_CORRECTION")

    def test_duplicate_timestamp_inside_provider_batch_fails_closed(self):
        with self.assertRaises(DataArchitectureError):
            reconcile_candles([], [ROW_1, ROW_1], PROV_A)

    def test_retention_prunes_only_older_records(self):
        result = reconcile_candles([], [ROW_1, ROW_2], PROV_A,
                                   retention_cutoff="2026-09-15T03:48:00+00:00")
        self.assertEqual(result["record_count"], 1)
        self.assertEqual(result["pruned_count"], 1)
        self.assertEqual(result["records"][0]["timestamp"], "2026-09-15T03:50:00+00:00")

    def test_bad_ohlc_and_naive_timestamp_fail_closed(self):
        bad_ohlc = ["2026-09-15T09:15:00+05:30", 100, 99, 90, 95, 1, 0]
        with self.assertRaises(Exception):
            normalize_candle(bad_ohlc, PROV_A)
        naive = ["2026-09-15T09:15:00", 100, 110, 90, 105, 1, 0]
        with self.assertRaises(DataArchitectureError):
            normalize_candle(naive, PROV_A)

    def test_tampered_cached_market_hash_fails_closed(self):
        first = reconcile_candles([], [ROW_1], PROV_A)
        first["records"][0]["market_sha256"] = "0" * 64
        with self.assertRaises(DataArchitectureError):
            reconcile_candles(first["records"], [ROW_2], PROV_B)


if __name__ == "__main__":
    unittest.main()
