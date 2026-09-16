import json
import unittest

from experiments.cache_reconcile import reconcile_candles
from experiments.cache_store import build_cache_document
from experiments.data_contract import DataArchitectureError
from experiments.postgres_cache_store import PostgresMarketCacheStore

PROV_A = {"source_path": "/v3/history", "sha256": "a" * 64, "received_at": "2026-09-16T06:00:00+00:00"}
PROV_B = {"source_path": "/v3/history", "sha256": "b" * 64, "received_at": "2026-09-16T07:00:00+00:00"}
ROW = ["2026-09-15T09:15:00+05:30", 100, 110, 90, 105, 10, 0]
SERIES_ID = "5DR:NIFTY_PRICE_CANDLES:NIFTY_50:5m"


def document(close=105, provenance=PROV_A):
    row = list(ROW)
    row[4] = close
    reconciled = reconcile_candles([], [row], provenance)
    return build_cache_document(
        SERIES_ID, reconciled,
        provider_id="UPSTOX",
        source_semantic="UPSTOX_AUTHENTICATED",
    )


class FakeDatabase:
    def __init__(self):
        self.documents = {}
        self.last_sql = None

    def fetch_one(self, sql, params):
        self.last_sql = sql
        if sql == "SELECT 1":
            return (1,)
        if sql.startswith("SELECT document"):
            value = self.documents.get(params[0])
            return None if value is None else (value,)
        if sql.startswith("INSERT INTO"):
            series_id = params[0]
            if series_id in self.documents:
                return None
            self.documents[series_id] = json.loads(params[7])
            return (params[3],)
        if sql.startswith("UPDATE"):
            series_id = params[7]
            expected = params[8]
            current = self.documents.get(series_id)
            if current is None or current["document_sha256"] != expected:
                return None
            self.documents[series_id] = json.loads(params[6])
            return (params[2],)
        raise AssertionError(f"unexpected SQL: {sql}")

    def fetch_all(self, sql, params):
        self.last_sql = sql
        return [(series_id,) for series_id in sorted(self.documents)]

    def execute(self, sql, params=()):
        self.last_sql = sql
        return None


class PostgresCacheStoreTests(unittest.TestCase):
    def test_descriptor_proves_isolation_and_defaults_unapproved(self):
        store = PostgresMarketCacheStore(FakeDatabase())
        descriptor = store.describe()
        self.assertTrue(descriptor["provider_neutral"])
        self.assertTrue(descriptor["durable"])
        self.assertTrue(descriptor["transactional"])
        self.assertFalse(descriptor["canonical_5dr_storage"])
        self.assertFalse(descriptor["production_approved"])
        self.assertFalse(descriptor["credential_embedded"])

    def test_migration_is_isolated_jsonb_schema(self):
        sql = PostgresMarketCacheStore.migration_sql()
        self.assertIn("CREATE SCHEMA IF NOT EXISTS market_data_cache", sql)
        self.assertIn("market_data_cache.market_cache_documents", sql)
        self.assertIn("document jsonb NOT NULL", sql)
        self.assertNotIn("forecast", sql.lower())
        self.assertNotIn("recommendation", sql.lower())

    def test_create_roundtrip_and_list(self):
        db = FakeDatabase()
        store = PostgresMarketCacheStore(db)
        first = document()
        summary = store.write_document(first)
        self.assertEqual(summary["series_id"], SERIES_ID)
        self.assertEqual(store.read_document(SERIES_ID), first)
        self.assertEqual(store.list_series(), [SERIES_ID])
        self.assertEqual(store.recover()["status"], "POSTGRES_CACHE_HEALTHY")

    def test_existing_series_requires_compare_and_swap(self):
        db = FakeDatabase()
        store = PostgresMarketCacheStore(db)
        first = document()
        store.write_document(first)
        with self.assertRaises(DataArchitectureError):
            store.write_document(first)

    def test_cas_update_rejects_wrong_prior_hash(self):
        db = FakeDatabase()
        store = PostgresMarketCacheStore(db)
        first = document()
        store.write_document(first)
        corrected = document(close=106, provenance=PROV_B)
        with self.assertRaises(DataArchitectureError):
            store.write_document(corrected, expected_document_sha256="0" * 64)

    def test_cas_update_verifies_durable_readback(self):
        db = FakeDatabase()
        store = PostgresMarketCacheStore(db)
        first = document()
        store.write_document(first)
        corrected = document(close=106, provenance=PROV_B)
        summary = store.write_document(corrected, expected_document_sha256=first["document_sha256"])
        self.assertEqual(summary["document_sha256"], corrected["document_sha256"])
        self.assertEqual(store.read_document(SERIES_ID)["records"][0]["candle"][4], 106)

    def test_schema_identifier_injection_is_rejected(self):
        with self.assertRaises(DataArchitectureError):
            PostgresMarketCacheStore(FakeDatabase(), schema="market_data_cache;drop")
        with self.assertRaises(DataArchitectureError):
            PostgresMarketCacheStore.migration_sql("Bad-Schema")


if __name__ == "__main__":
    unittest.main()
