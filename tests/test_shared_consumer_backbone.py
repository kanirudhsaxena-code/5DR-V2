import unittest
from datetime import datetime, timezone

from experiments.consumer_namespace import (
    ConsumerRunLedger,
    build_run_ledger_entry,
    consumer_cache_key,
    consumer_namespace,
)
from experiments.data_contract import DataArchitectureError, build_record
from experiments.shared_evidence_bundle import (
    build_shared_evidence_bundle,
    verify_shared_evidence_bundle,
)

NOW = datetime(2026, 9, 18, 5, 30, tzinfo=timezone.utc)
DIGEST = "a" * 64


def subject(kind="STOCK", sid="LTF", name="L&T Finance"):
    return {
        "kind": kind,
        "id": sid,
        "name": name,
        "exchange": "NSE",
        "symbol": sid,
    }


def stock_record(variable_id="STOCK_PRICE_CANDLES", consumer="EDGE_STOCK", sid="LTF"):
    return build_record(
        provider_id="UPSTOX",
        source_semantic="UPSTOX_AUTHENTICATED",
        variable_id=variable_id,
        consumer=consumer,
        subject=subject(sid=sid),
        metric="TEST",
        values={"value": 1},
        timeframe="15m",
        provider_timestamp=NOW,
        acquisition_timestamp=NOW,
        freshness_status="LIVE",
        source_reference="/v3/test",
        source_sha256=DIGEST,
    )


class SharedConsumerBackboneTests(unittest.TestCase):
    def test_shared_bundle_binds_consumer_subject_run_and_provenance(self):
        bundle = build_shared_evidence_bundle(
            consumer="EDGE_STOCK",
            subject=subject(),
            run_id="edge-stock-ltf-1",
            frozen_at=NOW,
            quantitative_records=[stock_record()],
            required_variables={"STOCK_PRICE_CANDLES"},
        )
        self.assertEqual(bundle["status"], "READY")
        self.assertEqual(bundle["consumer"], "EDGE_STOCK")
        self.assertEqual(bundle["subject"]["id"], "LTF")
        self.assertEqual(bundle["namespace"], "EDGE_STOCK:LTF")
        self.assertEqual(bundle["provenance"][0]["variable_id"], "STOCK_PRICE_CANDLES")
        self.assertEqual(len(bundle["bundle_sha256"]), 64)
        verified = verify_shared_evidence_bundle(bundle)
        self.assertEqual(verified["bundle_sha256"], bundle["bundle_sha256"])

    def test_cross_consumer_record_fails_closed(self):
        bad = stock_record(consumer="5DR")
        with self.assertRaises(DataArchitectureError):
            build_shared_evidence_bundle(
                consumer="EDGE_STOCK",
                subject=subject(),
                run_id="edge-stock-ltf-2",
                frozen_at=NOW,
                quantitative_records=[bad],
                required_variables={"STOCK_PRICE_CANDLES"},
            )

    def test_cross_subject_record_fails_closed(self):
        bad = stock_record(sid="OTHER")
        with self.assertRaises(DataArchitectureError):
            build_shared_evidence_bundle(
                consumer="EDGE_STOCK",
                subject=subject(),
                run_id="edge-stock-ltf-3",
                frozen_at=NOW,
                quantitative_records=[bad],
                required_variables={"STOCK_PRICE_CANDLES"},
            )

    def test_required_variable_must_belong_to_consumer_registry(self):
        with self.assertRaises(DataArchitectureError):
            build_shared_evidence_bundle(
                consumer="EDGE_STOCK",
                subject=subject(),
                run_id="edge-stock-ltf-4",
                frozen_at=NOW,
                required_variables={"NIFTY_PRICE_CANDLES"},
            )

    def test_missing_consumer_required_variable_blocks_bundle(self):
        bundle = build_shared_evidence_bundle(
            consumer="EDGE_STOCK",
            subject=subject(),
            run_id="edge-stock-ltf-5",
            frozen_at=NOW,
            quantitative_records=[],
            required_variables={"STOCK_PRICE_CANDLES"},
        )
        self.assertEqual(bundle["status"], "BLOCKED")
        self.assertEqual(bundle["coverage"]["missing_variables"], ["STOCK_PRICE_CANDLES"])

    def test_cache_namespace_prevents_cross_consumer_collision(self):
        a = consumer_cache_key(
            consumer="5DR", provider_id="UPSTOX", variable_id="X",
            subject_id="ABC", timeframe="15m",
        )
        b = consumer_cache_key(
            consumer="EDGE_STOCK", provider_id="UPSTOX", variable_id="X",
            subject_id="ABC", timeframe="15m",
        )
        self.assertNotEqual(a, b)
        self.assertEqual(consumer_namespace("EDGE_IPO", "IPO123"), "EDGE_IPO:IPO123")

    def test_run_ledger_is_consumer_and_subject_namespaced_and_idempotent(self):
        ledger = ConsumerRunLedger()
        entry = build_run_ledger_entry(
            consumer="EDGE_STOCK", subject_id="LTF", run_id="run-1",
            status="READY", bundle_sha256="b" * 64,
        )
        self.assertEqual(ledger.append(entry), ledger.append(entry))
        other = build_run_ledger_entry(
            consumer="EDGE_IPO", subject_id="LTF", run_id="run-1",
            status="READY", bundle_sha256="c" * 64,
        )
        ledger.append(other)
        self.assertEqual(len(ledger.entries()), 2)
        self.assertEqual(len(ledger.entries(consumer="EDGE_STOCK")), 1)

    def test_run_ledger_conflicting_duplicate_fails_closed(self):
        ledger = ConsumerRunLedger()
        first = build_run_ledger_entry(
            consumer="EDGE_STOCK", subject_id="LTF", run_id="run-2",
            status="READY", bundle_sha256="d" * 64,
        )
        second = build_run_ledger_entry(
            consumer="EDGE_STOCK", subject_id="LTF", run_id="run-2",
            status="BLOCKED", bundle_sha256="e" * 64,
        )
        ledger.append(first)
        with self.assertRaises(DataArchitectureError):
            ledger.append(second)


if __name__ == "__main__":
    unittest.main()
