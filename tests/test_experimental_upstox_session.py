import json
import unittest
from datetime import date, datetime, timedelta, timezone

from experiments.upstox_session import get_market_timings, get_nfo_market_status, select_session_valid_expiry
from phase1.upstox import PipelineError


class FakeResponse:
    def __init__(self, body):
        self.body = body
        self.status = 200

    def read(self, size=-1):
        return self.body if size < 0 else self.body[:size]

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class FakeOpener:
    def __init__(self, payload):
        self.payload = payload
        self.request = None

    def open(self, request, timeout=20):
        self.request = request
        return FakeResponse(json.dumps(self.payload).encode())


class SessionTests(unittest.TestCase):

    def test_market_timings_identifies_open_nse_and_nfo_date(self):
        opener = FakeOpener({
            "status": "success",
            "data": [
                {"exchange": "NSE", "start_time": 1791162900000, "end_time": 1791187200000},
                {"exchange": "NFO", "start_time": 1791162900000, "end_time": 1791187800000},
                {"exchange": "MCX", "start_time": 1791162000000, "end_time": 1791210600000},
            ],
        })
        result = get_market_timings("secret", date(2026, 10, 5), opener=opener)
        self.assertIn("NSE", result["exchanges"])
        self.assertIn("NFO", result["exchanges"])
        self.assertEqual(opener.request.get_method(), "GET")
        self.assertEqual(opener.request.full_url, "https://api.upstox.com/v2/market/timings/2026-10-05")

    def test_market_timings_preserves_closed_holiday_as_missing_exchange_rows(self):
        opener = FakeOpener({"status": "success", "data": [{"exchange": "MCX", "start_time": 1790902800000, "end_time": 1790951400000}]})
        result = get_market_timings("secret", date(2026, 10, 2), opener=opener)
        self.assertNotIn("NSE", result["exchanges"])
        self.assertNotIn("NFO", result["exchanges"])

    def test_market_timings_malformed_row_fails_closed(self):
        opener = FakeOpener({"status": "success", "data": [{"exchange": "NFO", "start_time": 10, "end_time": 5}]})
        with self.assertRaises(PipelineError):
            get_market_timings("secret", date(2026, 10, 5), opener=opener)

    def test_closed_expiry_day_rolls_to_next_expiry(self):
        self.assertEqual(
            select_session_valid_expiry(["2026-09-15", "2026-09-22"], date(2026, 9, 15), "NORMAL_CLOSE"),
            "2026-09-22",
        )

    def test_open_expiry_day_keeps_same_day_expiry(self):
        self.assertEqual(
            select_session_valid_expiry(["2026-09-15", "2026-09-22"], date(2026, 9, 15), "NORMAL_OPEN"),
            "2026-09-15",
        )

    def test_unknown_market_status_fails_closed(self):
        with self.assertRaises(PipelineError):
            select_session_valid_expiry(["2026-09-22"], date(2026, 9, 15), "UNKNOWN")

    def test_market_status_schema_and_get_only(self):
        stamp = int(datetime.now(timezone.utc).timestamp() * 1000)
        opener = FakeOpener({"status": "success", "data": {"exchange": "NFO", "status": "NORMAL_CLOSE", "last_updated": stamp}})
        result = get_nfo_market_status("secret", opener=opener)
        self.assertEqual(result["exchange"], "NFO")
        self.assertEqual(result["status"], "NORMAL_CLOSE")
        self.assertEqual(opener.request.get_method(), "GET")
        self.assertEqual(opener.request.full_url, "https://api.upstox.com/v2/market/status/NFO")

    def test_stale_market_status_fails_closed(self):
        stale = datetime.now(timezone.utc) - timedelta(days=8)
        opener = FakeOpener({"status": "success", "data": {"exchange": "NFO", "status": "NORMAL_CLOSE", "last_updated": int(stale.timestamp() * 1000)}})
        with self.assertRaises(PipelineError):
            get_nfo_market_status("secret", opener=opener)


if __name__ == "__main__":
    unittest.main()
