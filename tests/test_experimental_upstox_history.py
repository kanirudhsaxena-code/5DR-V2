import json
import unittest
from datetime import date

from experiments.data_contract import DataArchitectureError
from experiments.data_requirements import requirements
from experiments.upstox_adapter import UpstoxAdapter
from experiments.upstox_endpoints import historical_path
from experiments.upstox_history_policy import plan_history_chunks, plan_requirement_history, safe_chunk_days
from experiments.upstox_quant_client import QuantReadOnlyClient
from phase1.upstox import NIFTY, PipelineError


class Response:
    def __init__(self, payload): self.body = json.dumps(payload).encode()
    def read(self, size=-1): return self.body if size < 0 else self.body[:size]
    def __enter__(self): return self
    def __exit__(self, exc_type, exc, tb): return False


class Opener:
    def __init__(self, payload): self.payload = payload; self.requests = []
    def open(self, request, timeout=20): self.requests.append(request); return Response(self.payload)


class HistoryClient:
    def __init__(self): self.calls = []
    def full_quotes(self, keys): return None
    def intraday(self, key, unit, interval): return None
    def institutional(self, kind, data_types, interval): return None
    def option_analytics(self, kind, **kwargs): return None
    def historical(self, key, unit, interval, start, end): self.calls.append((key, unit, interval, start, end)); return {"ok": True}


class HistoryTests(unittest.TestCase):
    def test_provider_interval_limits_fail_closed(self):
        with self.assertRaises(PipelineError): historical_path(NIFTY, "minutes", 301, start=date(2026,1,1), end=date(2026,1,2))
        with self.assertRaises(PipelineError): historical_path(NIFTY, "hours", 6, start=date(2026,1,1), end=date(2026,1,2))
        with self.assertRaises(PipelineError): historical_path(NIFTY, "days", 2, start=date(2026,1,1), end=date(2026,1,2))

    def test_historical_client_validates_candles_and_exact_path_dates(self):
        payload = {"status":"success","data":{"candles":[["2026-09-15T09:15:00+05:30",100,105,99,104,1000,0]]}}
        opener = Opener(payload)
        client = QuantReadOnlyClient("secret", {NIFTY}, opener=opener, sleep=lambda _: None)
        out = client.historical(NIFTY, "minutes", 15, date(2026,9,1), date(2026,9,15))
        self.assertEqual(out["validated_candles"], 1)
        self.assertIn("/minutes/15/2026-09-15/2026-09-01", opener.requests[0].full_url)
        self.assertNotIn("secret", opener.requests[0].full_url)

    def test_unapproved_historical_instrument_rejected_before_network(self):
        opener = Opener({"status":"success","data":{"candles":[]}})
        client = QuantReadOnlyClient("secret", {NIFTY}, opener=opener, sleep=lambda _: None)
        with self.assertRaises(PipelineError):
            client.historical("NSE_EQ|OTHER", "days", 1, date(2026,1,1), date(2026,1,2))
        self.assertEqual(opener.requests, [])

    def test_adapter_exposes_historical_without_trading_surface(self):
        fake = HistoryClient(); adapter = UpstoxAdapter(fake)
        adapter.get_historical_candles(NIFTY, "1d", date(2026,1,1), date(2026,9,1))
        self.assertEqual(fake.calls[0][1:3], ("days", 1))
        self.assertFalse(hasattr(adapter, "place_order"))

    def test_chunk_policy_is_conservative_and_nonoverlapping(self):
        self.assertEqual(safe_chunk_days("minutes", 15), 28)
        self.assertEqual(safe_chunk_days("minutes", 30), 89)
        self.assertEqual(safe_chunk_days("hours", 1), 89)
        self.assertEqual(safe_chunk_days("days", 1), 3650)
        chunks = plan_history_chunks(date(2026,1,1), date(2026,6,30), "minutes", 15)
        self.assertGreaterEqual(len(chunks), 7)
        for left, right in zip(chunks, chunks[1:]):
            self.assertEqual(left["end"].toordinal() + 1, right["start"].toordinal())

    def test_5dr_nifty_requirement_generates_bounded_default_plan(self):
        row = next(r for r in requirements("5DR") if r["variable_id"] == "NIFTY_PRICE_CANDLES")
        plan = plan_requirement_history(row, date(2026,9,16))
        timeframes = {item["timeframe"] for item in plan}
        self.assertEqual(timeframes, {"5m","15m","30m","1h","1d"})
        self.assertLess(len(plan), 30)

    def test_unsupported_history_requirement_fails(self):
        with self.assertRaises(DataArchitectureError):
            plan_history_chunks(date(2026,1,1), date(2026,1,2), "minutes", 301)


if __name__ == "__main__": unittest.main()
