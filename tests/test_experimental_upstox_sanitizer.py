import unittest
from datetime import date

from experiments.upstox_sanitizer import sanitize_live_envelopes
from phase1.upstox import NIFTY, PipelineError


def envelope(path, data, digest):
    return {
        "received_at": "2026-09-15T10:00:00+00:00",
        "source_path": path,
        "sha256": digest * 64,
        "payload": {"status": "success", "data": data},
    }


def fixtures():
    expiry = "2026-09-22"
    contracts = []
    chain = []
    for strike in (25000, 25050, 25100, 25150, 25200):
        call_key = f"NSE_FO|C{strike}"
        put_key = f"NSE_FO|P{strike}"
        contracts.extend([
            {"underlying_key": NIFTY, "expiry": expiry, "instrument_key": call_key,
             "instrument_type": "CE", "strike_price": strike, "trading_symbol": f"NIFTY {strike} CE"},
            {"underlying_key": NIFTY, "expiry": expiry, "instrument_key": put_key,
             "instrument_type": "PE", "strike_price": strike, "trading_symbol": f"NIFTY {strike} PE"},
        ])
        chain.append({
            "underlying_key": NIFTY, "expiry": expiry, "strike_price": strike,
            "underlying_spot_price": 25110,
            "call_options": {"instrument_key": call_key, "market_data": {"ltp": 100, "oi": 1000, "volume": 200}},
            "put_options": {"instrument_key": put_key, "market_data": {"ltp": 90, "oi": 1100, "volume": 220}},
        })
    intraday = {"candles": [
        ["2026-09-15T09:15:00+05:30", 25050, 25080, 25040, 25070, 0, 0],
        ["2026-09-15T15:29:00+05:30", 25100, 25120, 25095, 25110, 0, 0],
    ]}
    return (
        envelope("/v2/option/contract", contracts, "a"),
        envelope("/v3/historical-candle/intraday/...", intraday, "b"),
        envelope("/v2/option/chain", chain, "c"),
    )


class ExperimentalSanitizerTests(unittest.TestCase):
    def test_sanitized_sample_has_exact_contract_identity_and_no_credentials(self):
        contracts, intraday, chain = fixtures()
        result = sanitize_live_envelopes(contracts, intraday, chain, date(2026, 9, 15))
        self.assertTrue(result["read_only"])
        self.assertFalse(result["trading_enabled"])
        self.assertFalse(result["production_5dr_write_enabled"])
        self.assertEqual(result["selected_expiry"], "2026-09-22")
        self.assertEqual(result["underlying_spot_price"], 25110)
        self.assertEqual(result["latest_intraday_candle"]["timestamp"], "2026-09-15T15:29:00+05:30")
        self.assertEqual(result["intraday_availability"], "AVAILABLE")
        self.assertEqual(len(result["sample_strikes"]), 5)
        serialized = repr(result).lower()
        self.assertNotIn("authorization", serialized)
        self.assertNotIn("bearer", serialized)
        self.assertNotIn("token", serialized)
        for row in result["sample_strikes"]:
            self.assertTrue(row["CE"]["instrument_key"].startswith("NSE_FO|C"))
            self.assertTrue(row["PE"]["instrument_key"].startswith("NSE_FO|P"))

    def test_empty_intraday_still_fails_closed_by_default(self):
        contracts, intraday, chain = fixtures()
        intraday["payload"]["data"]["candles"] = []
        with self.assertRaises(PipelineError):
            sanitize_live_envelopes(contracts, intraday, chain, date(2026, 9, 15))

    def test_verified_closed_session_can_mark_intraday_unavailable(self):
        contracts, intraday, chain = fixtures()
        intraday["payload"]["data"]["candles"] = []
        result = sanitize_live_envelopes(
            contracts,
            intraday,
            chain,
            date(2026, 9, 15),
            allow_empty_intraday=True,
        )
        self.assertIsNone(result["latest_intraday_candle"])
        self.assertEqual(result["intraday_availability"], "UNAVAILABLE_MARKET_CLOSED")
        self.assertEqual(result["underlying_spot_price"], 25110)
        self.assertEqual(len(result["sample_strikes"]), 5)

    def test_contract_side_mismatch_fails_closed(self):
        contracts, intraday, chain = fixtures()
        contracts["payload"]["data"][0]["instrument_type"] = "PE"
        with self.assertRaises(PipelineError):
            sanitize_live_envelopes(contracts, intraday, chain, date(2026, 9, 15))

    def test_chain_contract_key_mismatch_fails_closed(self):
        contracts, intraday, chain = fixtures()
        chain["payload"]["data"][2]["call_options"]["instrument_key"] = "NSE_FO|UNKNOWN"
        with self.assertRaises(PipelineError):
            sanitize_live_envelopes(contracts, intraday, chain, date(2026, 9, 15))


if __name__ == "__main__":
    unittest.main()
