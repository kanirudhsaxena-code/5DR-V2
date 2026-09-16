import json
import tempfile
import unittest
from pathlib import Path

from experiments.cache_reconcile import reconcile_candles
from experiments.cache_store import build_cache_document, validate_cache_document
from experiments.data_contract import DataArchitectureError
from experiments.filesystem_reference_cache import JsonFileReferenceCacheStore

PROV_A = {"source_path": "/v3/history", "sha256": "a" * 64, "received_at": "2026-09-16T06:00:00+00:00"}
PROV_B = {"source_path": "/v3/history", "sha256": "b" * 64, "received_at": "2026-09-16T07:00:00+00:00"}
ROW_1 = ["2026-09-15T09:15:00+05:30", 100, 110, 90, 105, 10, 0]
ROW_2 = ["2026-09-15T09:20:00+05:30", 105, 112, 100, 108, 12, 0]
SERIES = "5DR:NIFTY_PRICE_CANDLES:NIFTY_50:5m"


def document(rows=(ROW_1,), provenance=PROV_A, prior=None):
    reconciled = reconcile_candles([], list(rows), provenance)
    return build_cache_document(
        SERIES, reconciled, provider_id="UPSTOX",
        source_semantic="UPSTOX_AUTHENTICATED",
        prior_audit_events=prior or (),
    )


class CacheStoreTests(unittest.TestCase):
    def test_reference_backend_requires_explicit_test_mode(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(DataArchitectureError):
                JsonFileReferenceCacheStore(tmp)

    def test_roundtrip_is_atomic_validated_and_listable(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = JsonFileReferenceCacheStore(tmp, test_mode=True)
            doc = document()
            written = store.write_document(doc)
            self.assertEqual(written["document_sha256"], doc["document_sha256"])
            self.assertEqual(store.read_document(SERIES), doc)
            self.assertEqual(store.list_series(), [SERIES])
            self.assertTrue(store.describe()["test_mode_only"])
            self.assertFalse(store.describe()["production_approved"])

    def test_overwrite_requires_compare_and_swap(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = JsonFileReferenceCacheStore(tmp, test_mode=True)
            first = document()
            store.write_document(first)
            second = document((ROW_1, ROW_2))
            with self.assertRaises(DataArchitectureError):
                store.write_document(second)
            with self.assertRaises(DataArchitectureError):
                store.write_document(second, expected_document_sha256="f" * 64)
            store.write_document(second, expected_document_sha256=first["document_sha256"])
            self.assertEqual(store.read_document(SERIES)["record_count"], 2)

    def test_corrupt_committed_file_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = JsonFileReferenceCacheStore(tmp, test_mode=True)
            doc = document()
            store.write_document(doc)
            path = next(Path(tmp).glob("*.json"))
            path.write_text("{not-json", encoding="utf-8")
            with self.assertRaises(DataArchitectureError):
                store.read_document(SERIES)

    def test_series_id_cannot_escape_root(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = JsonFileReferenceCacheStore(tmp, test_mode=True)
            hostile = "../../outside/series"
            reconciled = reconcile_candles([], [ROW_1], PROV_A)
            doc = build_cache_document(hostile, reconciled, provider_id="UPSTOX", source_semantic="UPSTOX_AUTHENTICATED")
            store.write_document(doc)
            files = list(Path(tmp).glob("*.json"))
            self.assertEqual(len(files), 1)
            self.assertEqual(files[0].parent.resolve(), Path(tmp).resolve())
            self.assertEqual(store.read_document(hostile)["series_id"], hostile)

    def test_recovery_removes_only_owned_temp_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = JsonFileReferenceCacheStore(tmp, test_mode=True)
            doc = document()
            store.write_document(doc)
            stale = Path(tmp) / ".market-cache-crash.tmp"
            stale.write_text("partial", encoding="utf-8")
            unrelated = Path(tmp) / "keep.tmp"
            unrelated.write_text("keep", encoding="utf-8")
            result = store.recover()
            self.assertEqual(result["stale_temp_files_removed"], 1)
            self.assertFalse(stale.exists())
            self.assertTrue(unrelated.exists())
            self.assertEqual(store.read_document(SERIES), doc)

    def test_document_fingerprint_and_dataset_fingerprint_are_independently_verified(self):
        doc = document()
        doc["dataset_sha256"] = "0" * 64
        with self.assertRaises(DataArchitectureError):
            validate_cache_document(doc)
        doc = document()
        doc["document_sha256"] = "0" * 64
        with self.assertRaises(DataArchitectureError):
            validate_cache_document(doc)

    def test_provider_correction_audit_survives_document_build(self):
        first = reconcile_candles([], [ROW_1], PROV_A)
        corrected = list(ROW_1)
        corrected[4] = 106
        second = reconcile_candles(first["records"], [corrected], PROV_B)
        doc = build_cache_document(SERIES, second, provider_id="UPSTOX", source_semantic="UPSTOX_AUTHENTICATED")
        checked = validate_cache_document(doc)
        self.assertEqual(checked["audit_event_count"], 1)
        self.assertEqual(doc["audit_events"][0]["event"], "PROVIDER_CORRECTION")


if __name__ == "__main__":
    unittest.main()
