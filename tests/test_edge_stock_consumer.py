import unittest
from datetime import date, datetime, timezone

from experiments.data_contract import DataArchitectureError, build_record
from experiments.edge_stock_bundle import (
    build_edge_stock_bundle,
    edge_stock_required_variables,
    verify_edge_stock_bundle,
)
from experiments.edge_stock_identity import (
    resolve_nse_equity,
    resolve_stock_fo_identity,
)

NOW = datetime(2026, 9, 18, 6, 30, tzinfo=timezone.utc)
ISIN = "INE498L01015"
STOCK = {
    "kind": "STOCK",
    "id": ISIN,
    "name": "L&T Finance Ltd",
    "exchange": "NSE",
    "segment": "NSE_EQ",
    "instrument_key": "NSE_EQ|" + ISIN,
    "symbol": "LTF",
    "isin": ISIN,
}


def nse_rows():
    return [
        {
            "exchange": "NSE", "segment": "NSE_EQ", "instrument_type": "EQ",
            "instrument_key": "NSE_EQ|" + ISIN, "trading_symbol": "LTF",
            "name": "L&T Finance Ltd", "isin": ISIN,
        },
        {
            "exchange": "NSE", "segment": "NSE_FO", "instrument_type": "FUT",
            "underlying_key": "NSE_EQ|" + ISIN, "instrument_key": "NSE_FO|LTF-FUT",
            "trading_symbol": "LTF26SEPFUT", "expiry": "2026-09-29",
        },
        {
            "exchange": "NSE", "segment": "NSE_FO", "instrument_type": "CE",
            "underlying_key": "NSE_EQ|" + ISIN, "instrument_key": "NSE_FO|LTF-300-CE",
            "trading_symbol": "LTF26SEP300CE", "expiry": "2026-09-29",
        },
        {
            "exchange": "NSE", "segment": "NSE_FO", "instrument_type": "PE",
            "underlying_key": "NSE_EQ|" + ISIN, "instrument_key": "NSE_FO|LTF-300-PE",
            "trading_symbol": "LTF26SEP300PE", "expiry": "2026-09-29",
        },
    ]


def record(variable_id, suffix):
    return build_record(
        provider_id="TEST_PROVIDER",
        source_semantic="OFFICIAL_WEB",
        variable_id=variable_id,
        consumer="EDGE_STOCK",
        subject=STOCK,
        metric="TEST",
        values={"value": 1},
        timeframe="1d",
        provider_timestamp=NOW,
        acquisition_timestamp=NOW,
        freshness_status="LIVE",
        source_reference="https://example.invalid/" + variable_id.lower(),
        source_sha256=suffix * 64,
    )


class EdgeStockConsumerTests(unittest.TestCase):
    def test_exact_equity_identity_by_symbol_and_isin(self):
        by_symbol = resolve_nse_equity(nse_rows(), symbol="ltf")
        by_isin = resolve_nse_equity(nse_rows(), isin=ISIN)
        self.assertEqual(by_symbol, by_isin)
        self.assertEqual(by_symbol["id"], ISIN)

    def test_ambiguous_or_missing_identity_fails_closed(self):
        rows = nse_rows()
        rows.append(dict(rows[0]))
        with self.assertRaises(DataArchitectureError):
            resolve_nse_equity(rows, symbol="LTF")
        with self.assertRaises(DataArchitectureError):
            resolve_nse_equity(nse_rows(), symbol="NOPE")

    def test_fo_identity_requires_complete_nearest_chain(self):
        resolved = resolve_stock_fo_identity(nse_rows(), STOCK, as_of=date(2026, 9, 18))
        self.assertTrue(resolved["fo_eligible"])
        self.assertEqual(resolved["nearest_expiry"], "2026-09-29")
        self.assertTrue(resolved["has_calls"])
        self.assertTrue(resolved["has_puts"])

    def test_non_fo_stock_is_explicit_not_inferred(self):
        resolved = resolve_stock_fo_identity(
            [nse_rows()[0]], STOCK, as_of=date(2026, 9, 18)
        )
        self.assertFalse(resolved["fo_eligible"])
        self.assertEqual(resolved["active_expiries"], [])

    def test_fo_bundle_requires_stock_options(self):
        required = edge_stock_required_variables(fo_eligible=True)
        self.assertIn("STOCK_OPTIONS", required)
        self.assertNotIn("STOCK_OPTIONS", edge_stock_required_variables(fo_eligible=False))

    def test_complete_fo_bundle_is_ready_without_methodology(self):
        fo = resolve_stock_fo_identity(nse_rows(), STOCK, as_of=date(2026, 9, 18))
        required = sorted(edge_stock_required_variables(fo_eligible=True))
        records = [record(variable, chr(97 + i)) for i, variable in enumerate(required)]
        bundle = build_edge_stock_bundle(
            stock_identity=STOCK,
            fo_identity=fo,
            run_id="EDGE-STOCK-LTF-1",
            frozen_at=NOW,
            quantitative_records=records,
        )
        self.assertEqual(bundle["status"], "READY")
        self.assertFalse(bundle["derived_evidence"]["methodology_applied"])
        self.assertFalse(bundle["derived_evidence"]["recommendation_generated"])
        self.assertEqual(verify_edge_stock_bundle(bundle)["consumer"], "EDGE_STOCK")

    def test_missing_required_stock_evidence_blocks_bundle(self):
        fo = resolve_stock_fo_identity(nse_rows(), STOCK, as_of=date(2026, 9, 18))
        records = [record("STOCK_PRICE_CANDLES", "a")]
        bundle = build_edge_stock_bundle(
            stock_identity=STOCK,
            fo_identity=fo,
            run_id="EDGE-STOCK-LTF-2",
            frozen_at=NOW,
            quantitative_records=records,
        )
        self.assertEqual(bundle["status"], "BLOCKED")
        self.assertIn("STOCK_OPTIONS", bundle["coverage"]["missing_variables"])


if __name__ == "__main__":
    unittest.main()
