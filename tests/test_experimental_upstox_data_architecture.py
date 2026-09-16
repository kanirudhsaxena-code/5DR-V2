import unittest
from datetime import datetime, timezone

from experiments.data_cache import backfill_chunks, cache_key, plan_incremental_range, retention_cutoff
from experiments.data_contract import DataArchitectureError, build_record
from experiments.data_policy import build_request_plan, enabled_variable_ids, validate_cost_posture
from experiments.data_requirements import requirements, validate_registry
from experiments.upstox_adapter import UpstoxAdapter
from experiments.usage_ledger import UsageBudget, UsageLedger


DIGEST = "a" * 64
NOW = datetime(2026, 9, 16, 5, 0, tzinfo=timezone.utc)
SUBJECT = {"kind":"MARKET_INSTRUMENT","id":"NIFTY50","name":"NIFTY 50","exchange":"NSE","instrument_key":"NSE_INDEX|Nifty 50"}


class FakeQuantClient:
    def __init__(self):
        self.calls = []
    def full_quotes(self, keys):
        self.calls.append(("quotes", tuple(keys))); return {"ok": True}
    def intraday(self, key, unit, interval):
        self.calls.append(("candles", key, unit, interval)); return {"ok": True}
    def institutional(self, kind, data_types, interval):
        self.calls.append(("institutional", kind, tuple(data_types), interval)); return {"ok": True}
    def option_analytics(self, kind, **kwargs):
        self.calls.append(("option", kind, kwargs)); return {"ok": True}


class DataArchitectureTests(unittest.TestCase):
    def test_provider_neutral_contract_accepts_upstox_without_embedding_provider_schema(self):
        record = build_record(provider_id="UPSTOX", source_semantic="UPSTOX_AUTHENTICATED",
            variable_id="NIFTY_PRICE_CANDLES", consumer="5DR", subject=SUBJECT,
            metric="quote", values={"last_price": 23100}, timeframe="quote",
            provider_timestamp=NOW, acquisition_timestamp=NOW, freshness_status="LIVE",
            source_reference="/v3/market-quote/quotes", source_sha256=DIGEST)
        self.assertTrue(record["eligible_for_consumer"])
        self.assertEqual(record["provider_id"], "UPSTOX")
        self.assertEqual(len(record["record_fingerprint"]), 64)

    def test_stale_record_cannot_be_valid(self):
        with self.assertRaises(DataArchitectureError):
            build_record(provider_id="P", source_semantic="P_SOURCE", variable_id="X", consumer="5DR",
                subject=SUBJECT, metric="quote", values={}, timeframe=None, provider_timestamp=NOW,
                acquisition_timestamp=NOW, freshness_status="STALE", source_reference="/x", source_sha256=DIGEST)

    def test_fingerprint_ignores_receipt_time_but_not_market_content(self):
        base = dict(provider_id="UPSTOX", source_semantic="UPSTOX_AUTHENTICATED", variable_id="X",
            consumer="5DR", subject=SUBJECT, metric="quote", timeframe="quote", provider_timestamp=NOW,
            freshness_status="LIVE", source_reference="/x", source_sha256=DIGEST)
        a = build_record(**base, values={"p":1}, acquisition_timestamp=NOW)
        later = datetime(2026,9,16,5,1,tzinfo=timezone.utc)
        b = build_record(**base, values={"p":1}, acquisition_timestamp=later)
        c = build_record(**base, values={"p":2}, acquisition_timestamp=later)
        self.assertEqual(a["record_fingerprint"], b["record_fingerprint"])
        self.assertNotEqual(a["record_fingerprint"], c["record_fingerprint"])

    def test_registry_covers_all_three_consumers_and_has_unique_variables(self):
        self.assertGreater(validate_registry(), 30)
        self.assertEqual({r["consumer"] for r in requirements()}, {"5DR","EDGE_STOCK","EDGE_IPO"})

    def test_edge_profiles_are_provisioned_but_not_background_enabled(self):
        self.assertEqual(build_request_plan("EDGE_STOCK"), [])
        self.assertEqual(build_request_plan("EDGE_IPO"), [])
        self.assertGreater(len(build_request_plan("EDGE_STOCK", include_provisioned=True)), 5)
        self.assertGreater(len(build_request_plan("EDGE_IPO", include_provisioned=True)), 5)

    def test_5dr_experiment_plan_is_bounded(self):
        ids = set(enabled_variable_ids("5DR"))
        self.assertIn("NIFTY_PRICE_CANDLES", ids)
        self.assertIn("GLOBAL_RISK_INDICES", ids)
        self.assertNotIn("GOLD", ids)
        self.assertNotIn("DXY_RATES", ids)
        self.assertTrue(validate_cost_posture())

    def test_ipo_gmp_is_provisioned_as_non_upstox(self):
        row = next(r for r in requirements("EDGE_IPO") if r["variable_id"] == "IPO_GMP")
        self.assertEqual(row["upstox_availability"], "UNAVAILABLE")
        self.assertEqual(row["source_preference"], "SPECIALIST_SECONDARY")

    def test_incremental_cache_fetches_only_missing_tail(self):
        plan = plan_incremental_range("2026-09-01T00:00:00+00:00", "2026-09-16T00:00:00+00:00", "2026-09-15T00:00:00+00:00")
        self.assertTrue(plan["cache_hit"])
        self.assertTrue(plan["from"].startswith("2026-09-15"))
        self.assertIsNone(plan_incremental_range("2026-09-01T00:00:00+00:00", "2026-09-16T00:00:00+00:00", "2026-09-16T00:00:00+00:00"))

    def test_cache_key_is_deterministic(self):
        self.assertEqual(cache_key("UPSTOX","X","NIFTY","15m"), cache_key("upstox","x","nifty","15m"))
        self.assertEqual(len(cache_key("UPSTOX","X","NIFTY","15m")), 64)

    def test_backfill_is_bounded_and_retention_is_explicit(self):
        chunks = backfill_chunks("2026-01-01T00:00:00+00:00", "2026-04-01T00:00:00+00:00", 31)
        self.assertGreater(len(chunks), 2)
        self.assertTrue(retention_cutoff(NOW, 30).startswith("2026-08-17"))

    def test_usage_ledger_blocks_call_budget(self):
        ledger = UsageLedger(UsageBudget(max_calls=1, max_bytes=100, max_rows_retained=10, max_billable_units=0))
        ledger.record(provider="UPSTOX", consumer="5DR", operation="quote", rows_received=1, rows_retained=1)
        with self.assertRaises(DataArchitectureError):
            ledger.record(provider="UPSTOX", consumer="5DR", operation="quote", rows_received=1, rows_retained=1)

    def test_usage_ledger_blocks_unplanned_billable_units(self):
        ledger = UsageLedger()
        with self.assertRaises(DataArchitectureError):
            ledger.record(provider="UPSTOX", consumer="5DR", operation="x", billable_units=1)

    def test_upstox_adapter_exposes_read_only_provider_surface(self):
        fake = FakeQuantClient(); adapter = UpstoxAdapter(fake)
        self.assertTrue(adapter.describe()["read_only"])
        self.assertFalse(hasattr(adapter, "place_order"))
        adapter.get_quotes(["NSE_INDEX|Nifty 50"])
        adapter.get_candles("NSE_INDEX|Nifty 50", "15m")
        self.assertEqual(fake.calls[1][-2:], ("minutes", 15))

    def test_upstox_adapter_rejects_unwired_timeframe(self):
        with self.assertRaises(DataArchitectureError):
            UpstoxAdapter(FakeQuantClient()).get_candles("NIFTY", "1d")


if __name__ == "__main__":
    unittest.main()
