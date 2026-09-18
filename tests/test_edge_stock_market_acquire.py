import unittest
from datetime import datetime, timezone

from experiments.data_contract import DataArchitectureError
from experiments.edge_stock_market_acquire import derive_relative_strength, normalize_option_chain


class EdgeStockMarketAcquireTests(unittest.TestCase):
    def test_relative_strength_is_deterministic(self):
        stock = [
            ["2026-09-01T00:00:00+05:30", 100, 101, 99, 100, 10, 0],
            ["2026-09-02T00:00:00+05:30", 100, 111, 99, 110, 10, 0],
        ]
        benchmark = [
            ["2026-09-01T00:00:00+05:30", 200, 201, 199, 200, 10, 0],
            ["2026-09-02T00:00:00+05:30", 200, 211, 199, 210, 10, 0],
        ]
        out = derive_relative_strength(stock, benchmark)
        self.assertEqual(out["stock_return_pct"], 10.0)
        self.assertEqual(out["benchmark_return_pct"], 5.0)
        self.assertEqual(out["relative_strength_pct_points"], 5.0)

    def test_option_normalization_preserves_liquidity_and_greeks(self):
        envelope = {
            "payload": {
                "data": [{
                    "expiry": "2026-09-29",
                    "strike_price": 300,
                    "pcr": 1.1,
                    "call_options": {
                        "instrument_key": "CE",
                        "market_data": {
                            "ltp": 5, "volume": 100, "oi": 1000, "prev_oi": 900,
                            "bid_price": 4.9, "bid_qty": 10, "ask_price": 5.1, "ask_qty": 12,
                        },
                        "option_greeks": {"iv": 20, "delta": 0.5, "gamma": 0.1, "theta": -0.2, "vega": 0.3},
                    },
                    "put_options": {
                        "instrument_key": "PE",
                        "market_data": {
                            "ltp": 4, "volume": 90, "oi": 800, "prev_oi": 850,
                            "bid_price": 3.9, "bid_qty": 8, "ask_price": 4.1, "ask_qty": 9,
                        },
                        "option_greeks": {"iv": 21, "delta": -0.5, "gamma": 0.1, "theta": -0.2, "vega": 0.3},
                    },
                }],
            },
        }
        out = normalize_option_chain(envelope, spot_price=300)
        row = out["strikes"][0]
        self.assertEqual(row["CE"]["change_oi"], 100)
        self.assertEqual(row["PE"]["change_oi"], -50)
        self.assertEqual(row["CE"]["bid_ask_spread"], 0.2)
        self.assertEqual(row["CE"]["iv"], 20)

    def test_relative_strength_requires_overlap(self):
        stock = [["2026-09-01T00:00:00+05:30", 1, 1, 1, 1, 1, 0]]
        bench = [["2026-09-02T00:00:00+05:30", 1, 1, 1, 1, 1, 0]]
        with self.assertRaises(DataArchitectureError):
            derive_relative_strength(stock, bench)


if __name__ == "__main__":
    unittest.main()
