import tempfile
import unittest
from datetime import date

from experiments.backfill_executor import BackfillExecutor, build_initial_backfill_plan
from experiments.backfill_inventory import SERIES
from experiments.cache_reconcile import reconcile_candles
from experiments.cache_store import MarketCacheStore, build_cache_document
from experiments.data_contract import DataArchitectureError
from experiments.filesystem_reference_cache import JsonFileReferenceCacheStore
from experiments.store_candle_adapter import StoreBackedCandleCache

PROV_A = {"source_path": "/v3/history", "sha256": "a" * 64, "received_at": "2026-09-16T06:00:00+00:00"}
PROV_B = {"source_path": "/v3/history", "sha256": "b" * 64, "received_at": "2026-09-16T07:00:00+00:00"}
ROW_1 = ["2026-09-15T09:15:00+05:30", 100, 110, 90, 105, 10, 0]
SERIES_ID = "5DR:NIFTY_PRICE_CANDLES:NIFTY_50:5m"


class UnsafeCanonicalStore(MarketCacheStore):
    def describe(self):
        return {
            "backend_id": "UNSAFE",
            "provider_neutral": True,
            "production_approved": True,
            "canonical_5dr_storage": True,
        }


class FakeProvider:
    def __init__(self):
        self.calls = 0

    def get_historical_candles(self, instrument_key, timeframe, start, end):
        self.calls += 1
        row = [f"{start.isoformat()}T09:15:00+05:30", 100, 110, 90, 105, 10, 0]
        return {
            "source_path": "/v3/history",
            "sha256": (f"{self.calls:064x}")[-64:],
            "received_at": "2026-09-16T06:00:00+00:00",
            "payload": {"status": "success", "data": {"candles": [row]}},
        }


class StoreBackedCandleCacheTests(unittest.TestCase):
    def test_reference_store_roundtrip_deduplicates_with_cas(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = JsonFileReferenceCacheStore(tmp, test_mode=True)
            cache = StoreBackedCandleCache(store)
            first = cache.write_candles(SERIES_ID, [ROW_1], PROV_A)
            second = cache.write_candles(SERIES_ID, [ROW_1], PROV_B)
            self.assertEqual(first["record_count"], 1)
            self.assertEqual(second["record_count"], 1)
            self.assertEqual(second["duplicate_count"], 1)
            self.assertEqual(second["correction_count"], 0)
            self.assertEqual(cache.latest_timestamp(SERIES_ID), "2026-09-15T03:45:00+00:00")

    def test_provider_correction_is_preserved_in_store_audit(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = JsonFileReferenceCacheStore(tmp, test_mode=True)
            cache = StoreBackedCandleCache(store)
            cache.write_candles(SERIES_ID, [ROW_1], PROV_A)
            corrected = list(ROW_1)
            corrected[4] = 106
            result = cache.write_candles(SERIES_ID, [corrected], PROV_B)
            self.assertEqual(result["correction_count"], 1)
            self.assertEqual(result["audit_event_count"], 1)
            document = store.read_document(SERIES_ID)
            self.assertEqual(document["audit_events"][0]["event"], "PROVIDER_CORRECTION")

    def test_adapter_rejects_canonical_lifecycle_storage(self):
        with self.assertRaises(DataArchitectureError):
            StoreBackedCandleCache(UnsafeCanonicalStore())

    def test_production_gate_rejects_test_reference_backend(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = JsonFileReferenceCacheStore(tmp, test_mode=True)
            with self.assertRaises(DataArchitectureError):
                StoreBackedCandleCache(store, require_production_approved=True)

    def test_existing_document_provider_identity_cannot_be_relabelled(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = JsonFileReferenceCacheStore(tmp, test_mode=True)
            reconciled = reconcile_candles([], [ROW_1], PROV_A)
            foreign = build_cache_document(
                SERIES_ID, reconciled, provider_id="OTHER",
                source_semantic="OTHER_AUTHENTICATED",
            )
            store.write_document(foreign)
            cache = StoreBackedCandleCache(store)
            with self.assertRaises(DataArchitectureError):
                cache.write_candles(SERIES_ID, [ROW_1], PROV_B)

    def test_backfill_executor_can_only_reach_document_store_through_adapter(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = JsonFileReferenceCacheStore(tmp, test_mode=True)
            cache = StoreBackedCandleCache(store)
            provider = FakeProvider()
            plan = build_initial_backfill_plan(date(2026, 9, 15), rows=SERIES[:1])
            result = BackfillExecutor(
                provider=provider,
                cache=cache,
                allow_network=True,
                allow_storage_writes=True,
            ).execute(plan, dry_run=False)
            self.assertEqual(result["status"], "BACKFILL_EXECUTION_PASSED")
            self.assertEqual(provider.calls, plan["planned_calls"])
            self.assertEqual(result["storage_writes_executed"], plan["planned_calls"])
            stored = store.read_document(plan["series"][0]["series_id"])
            self.assertIsNotNone(stored)
            self.assertGreater(stored["record_count"], 0)


if __name__ == "__main__":
    unittest.main()
