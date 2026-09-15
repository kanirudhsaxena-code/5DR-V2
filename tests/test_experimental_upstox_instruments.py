import unittest
from datetime import date

from experiments.upstox_instruments import parse_global_latency, resolve_global_instruments, resolve_nearest_nifty_future
from phase1.upstox import PipelineError


class InstrumentTests(unittest.TestCase):
    def test_provider_latency_mapping_is_exact(self):
        self.assertEqual(parse_global_latency("20 Seconds")["classification"], "DELAYED_20S")
        self.assertEqual(parse_global_latency("120 Seconds")["classification"], "DELAYED_120S")
        self.assertEqual(parse_global_latency("900 Seconds")["classification"], "DELAYED_15M")
        with self.assertRaises(PipelineError):
            parse_global_latency("Realtime")

    def test_global_resolution_requires_exact_unique_identity(self):
        rows = [
            {"name": "GIFT NIFTY", "exchange": "GLOBAL", "segment": "GLOBAL_INDEX", "instrument_key": "GLOBAL_INDEX|SGX NIFTY", "trading_symbol": "GIFT NIFTY", "country": "India", "latency": "120 Seconds"},
            {"name": "Oil (Brent)", "exchange": "GLOBAL", "segment": "GLOBAL_INDICATOR", "instrument_key": "GLOBAL_INDICATOR|BZUSD", "trading_symbol": "BZUSD", "latency": "20 Seconds"},
        ]
        result = resolve_global_instruments(rows, ["gift_nifty", "brent"])
        self.assertEqual(result["gift_nifty"]["provider_latency"]["seconds"], 120)
        self.assertEqual(result["brent"]["provider_latency"]["seconds"], 20)

    def test_missing_or_duplicate_global_identity_fails_closed(self):
        row = {"name": "GIFT NIFTY", "exchange": "GLOBAL", "segment": "GLOBAL_INDEX", "instrument_key": "GLOBAL_INDEX|SGX NIFTY", "trading_symbol": "GIFT NIFTY", "latency": "120 Seconds"}
        with self.assertRaises(PipelineError):
            resolve_global_instruments([], ["gift_nifty"])
        with self.assertRaises(PipelineError):
            resolve_global_instruments([row, dict(row)], ["gift_nifty"])

    def test_nifty_future_selects_nearest_exact_underlying(self):
        rows = [
            {"segment": "NSE_FO", "exchange": "NSE", "instrument_type": "FUT", "underlying_key": "NSE_INDEX|Nifty 50", "expiry": "2026-09-24", "instrument_key": "NSE_FO|100", "trading_symbol": "NIFTY FUT 24 SEP 26"},
            {"segment": "NSE_FO", "exchange": "NSE", "instrument_type": "FUT", "underlying_key": "NSE_INDEX|Nifty 50", "expiry": "2026-10-29", "instrument_key": "NSE_FO|101", "trading_symbol": "NIFTY FUT 29 OCT 26"},
            {"segment": "NSE_FO", "exchange": "NSE", "instrument_type": "FUT", "underlying_key": "NSE_INDEX|BANKNIFTY", "expiry": "2026-09-24", "instrument_key": "NSE_FO|999", "trading_symbol": "BANKNIFTY FUT 24 SEP 26"},
        ]
        result = resolve_nearest_nifty_future(rows, date(2026, 9, 15))
        self.assertEqual(result["instrument_key"], "NSE_FO|100")
        self.assertEqual(result["expiry"], "2026-09-24")


if __name__ == "__main__":
    unittest.main()
