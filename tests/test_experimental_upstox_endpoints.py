import unittest
from datetime import date

from experiments.upstox_endpoints import assert_no_trading_surface, historical_path, validate_request
from phase1.upstox import PipelineError


class EndpointTests(unittest.TestCase):
    def test_registry_contains_no_trading_surface(self):
        self.assertTrue(assert_no_trading_surface())

    def test_nifty_derivative_analytics_are_locked_to_nifty(self):
        result = validate_request("pcr", {"instrument_key": "NSE_INDEX|Nifty 50", "expiry": "2026-09-22", "date": "2026-09-15", "bucket_interval": 60})
        self.assertEqual(result["path"], "/v2/market/pcr")
        with self.assertRaises(PipelineError):
            validate_request("pcr", {"instrument_key": "NSE_INDEX|Nifty Bank", "expiry": "2026-09-22", "date": "2026-09-15", "bucket_interval": 60})

    def test_institutional_types_are_allowlisted(self):
        result = validate_request("fii", {"data_type": ["NSE_EQ|CASH", "NSE_FO|INDEX_OPTIONS"], "interval": "1D"})
        self.assertEqual(result["method"], "GET")
        with self.assertRaises(PipelineError):
            validate_request("dii", {"data_type": "NSE_FO|INDEX_OPTIONS", "interval": "1D"})

    def test_historical_paths_are_read_only_and_bounded_by_inputs(self):
        path = historical_path("NSE_INDEX|Nifty 50", "minutes", 15, intraday=True)
        self.assertIn("/v3/historical-candle/intraday/", path)
        daily = historical_path("NSE_INDEX|Nifty 50", "days", 1, start=date(2026, 9, 1), end=date(2026, 9, 15))
        self.assertTrue(daily.startswith("/v3/historical-candle/"))
        with self.assertRaises(PipelineError):
            historical_path("NSE_INDEX|Nifty 50", "days", 1, intraday=True, start=date.today())


if __name__ == "__main__":
    unittest.main()
