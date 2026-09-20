import unittest

from datetime import date

from experiments.run_upstox_quant_probe import _prove_global_live
from experiments.live_shadow_bundle import _global_indicator_snapshot
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


class IndicatorClient:
    def __init__(self, *, intraday_error=None):
        self.intraday_error=intraday_error
        self.calls=[]

    def intraday(self, key, unit, interval):
        self.calls.append(("intraday",key,unit,interval))
        if self.intraday_error:
            raise PipelineError(self.intraday_error)
        return {
            "payload":{"data":{"candles":[
                ["2026-09-18T10:00:00+00:00",100,102,99,101,50,0]
            ]}},
            "sha256":"a"*64,
        }

    def historical(self, key, unit, interval, start, end):
        self.calls.append(("historical",key,unit,interval,start,end))
        return {
            "payload":{"data":{"candles":[
                ["2026-09-18T00:00:00+00:00",98,103,97,100,70,0]
            ]}},
            "sha256":"b"*64,
        }


def test_closed_global_indicator_uses_authenticated_daily_carry_forward():
    client=IndicatorClient(intraday_error="Candle array missing")
    snap, env=_global_indicator_snapshot(
        client,"GLOBAL_INDICATOR|BZUSD",date(2026,9,20),"NORMAL_CLOSE"
    )
    assert snap["last_price"]==100
    assert snap["snapshot_basis"]=="UPSTOX_DAILY_MARKET_CLOSED_CARRY_FORWARD"
    assert client.calls[0][0]=="intraday"
    assert client.calls[1][0]=="historical"
    assert env["sha256"]=="b"*64


def test_open_global_indicator_empty_intraday_still_fails_closed():
    client=IndicatorClient(intraday_error="Candle array missing")
    with unittest.TestCase().assertRaises(PipelineError):
        _global_indicator_snapshot(
            client,"GLOBAL_INDICATOR|BZUSD",date(2026,9,20),"NORMAL_OPEN"
        )
    assert [call[0] for call in client.calls]==["intraday"]


def test_available_global_intraday_remains_primary():
    client=IndicatorClient()
    snap, env=_global_indicator_snapshot(
        client,"GLOBAL_INDICATOR|BZUSD",date(2026,9,20),"NORMAL_CLOSE"
    )
    assert snap["last_price"]==101
    assert snap["snapshot_basis"]=="UPSTOX_INTRADAY_1M"
    assert [call[0] for call in client.calls]==["intraday"]
    assert env["sha256"]=="a"*64
