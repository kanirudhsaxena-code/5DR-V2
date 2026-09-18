import unittest

from experiments.run_upstox_quant_probe import _prove_global_live
from phase1.upstox import PipelineError


class FakeClient:
    def __init__(self):
        self.calls = []
    def full_quotes(self, keys):
        self.calls.append(("quote", tuple(keys)))
        return {"validated_instrument_tokens": list(keys), "source_path":"/v3/market-quote/quotes", "sha256":"a"*64, "received_at":"2026-09-16T05:30:00+00:00"}
    def intraday(self, key, unit, interval):
        self.calls.append(("intraday", key, unit, interval))
        return {"validated_candles": 10, "source_path":"/v3/historical-candle/intraday/x/minutes/1", "sha256":"b"*64, "received_at":"2026-09-16T05:30:00+00:00"}


class GlobalStrategyTests(unittest.TestCase):
    def test_global_index_uses_full_quote(self):
        client = FakeClient()
        proof = _prove_global_live(client, "sp500", {"instrument_key":"GLOBAL_INDEX|SPX", "segment":"GLOBAL_INDEX"})
        self.assertEqual(proof["surface"], "FULL_QUOTE_V3")
        self.assertEqual(client.calls, [("quote", ("GLOBAL_INDEX|SPX",))])

    def test_global_indicator_uses_intraday_not_full_quote(self):
        client = FakeClient()
        proof = _prove_global_live(client, "brent", {"instrument_key":"GLOBAL_INDICATOR|BZUSD", "segment":"GLOBAL_INDICATOR"})
        self.assertEqual(proof["surface"], "INTRADAY_CANDLE_V3")
        self.assertEqual(client.calls, [("intraday", "GLOBAL_INDICATOR|BZUSD", "minutes", 1)])

    def test_unknown_global_segment_fails_closed(self):
        with self.assertRaises(PipelineError):
            _prove_global_live(FakeClient(), "x", {"instrument_key":"X|Y", "segment":"UNKNOWN"})


if __name__ == "__main__":
    unittest.main()
