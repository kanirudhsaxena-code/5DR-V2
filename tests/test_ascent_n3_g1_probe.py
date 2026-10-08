"""Pure offline tests; never contact Upstox or GitHub secrets."""
import io
import json
import unittest
from datetime import date
from experiments.ascent_n3_g1_probe import (
    NIFTY, ProbeError, ReadOnlyBroker, expired_dates, summarize_candles, validate_contracts)

class NoNetwork:
    def __init__(self, data):
        self.data = data
    def open(self, request, timeout):
        assert request.method == "GET"
        return io.BytesIO(json.dumps(self.data).encode())

class SourceContractTests(unittest.TestCase):
    def contracts(self):
        return [{"underlying_key": NIFTY, "instrument_type": kind,
                 "strike_price": 25000.0, "lot_size": 65,
                 "instrument_key": f"NSE_FO|123|01-10-2026-{kind}",
                 "expiry": "2026-10-01"} for kind in ("CE", "PE")]

    def test_ce_pe_valid(self):
        self.assertEqual(len(validate_contracts(self.contracts())), 2)

    def test_missing_pe_rejected(self):
        with self.assertRaisesRegex(ProbeError, "CE_PE_COVERAGE_MISSING"):
            validate_contracts(self.contracts()[:1])

    def test_zero_lot_rejected(self):
        rows = self.contracts()
        rows[1]["lot_size"] = 0
        with self.assertRaisesRegex(ProbeError, "CE_PE_COVERAGE_MISSING"):
            validate_contracts(rows)

    def test_expiry_is_historical(self):
        d = expired_dates(["2026-10-09", "2026-10-01", "2026-09-25"], date(2026, 10, 8))
        self.assertEqual(d[-1], date(2026, 10, 1))

    def test_empty_expiry_rejected(self):
        with self.assertRaisesRegex(ProbeError, "NO_EXPIRED_EXPIRY"):
            expired_dates([], date(2026, 10, 8))

    def test_candle_timestamp_and_ohlc(self):
        rows = [["2026-10-01T09:15:00+05:30",5,6,4,5,10,2],
                ["2026-10-01T09:16:00+05:30",4,5,3,4,12,2]]
        x = summarize_candles(rows, date(2026,10,1), date(2026,10,1),True)
        self.assertEqual(x["count"],2)
        self.assertIn("high_low order unknown",x["precision"])

    def test_duplicate_candle_rejected(self):
        row = ["2026-10-01T09:15:00+05:30",5,6,4,5,10]
        with self.assertRaisesRegex(ProbeError, "DUPLICATE_CANDLE"):
            summarize_candles([row,row],date(2026,10,1),date(2026,10,1))

    def test_naive_timestamp_rejected(self):
        with self.assertRaisesRegex(ProbeError,"CANDLE_TIMEZONE_MISSING"):
            summarize_candles([["2026-10-01T09:15:00",5,6,4,5,10]],
                              date(2026,10,1),date(2026,10,1))

    def test_invalid_ohlc_rejected(self):
        with self.assertRaisesRegex(ProbeError,"CANDLE_OHLC_INCONSISTENT"):
            summarize_candles([["2026-10-01T09:15:00+05:30",5,4,3,5,10]],
                              date(2026,10,1),date(2026,10,1))

    def test_fake_get_is_readonly_and_hashes(self):
        b = ReadOnlyBroker("UNITTEST_SECRET",NoNetwork({"status":"success","data":[1]}))
        result = b.get("test","/v2/expired-instruments/expiries",{"instrument_key":NIFTY})
        self.assertEqual(result,[1])
        self.assertEqual(b.receipts[0]["method"],"GET")
        self.assertNotIn("UNITTEST_SECRET",str(b.receipts))

    def test_token_absent_fail_closed(self):
        with self.assertRaisesRegex(ProbeError,"EXISTING_SECRET_NOT_AVAILABLE"):
            ReadOnlyBroker("")

if __name__ == "__main__":
    unittest.main()
