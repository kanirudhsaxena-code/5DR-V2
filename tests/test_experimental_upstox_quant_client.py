import json
import unittest
from urllib.parse import parse_qs, urlparse

from experiments.upstox_quant_client import INDIA_VIX, QuantReadOnlyClient
from phase1.upstox import NIFTY, PipelineError


class Response:
    def __init__(self, body):
        self.body = body
    def read(self, size=-1):
        return self.body if size < 0 else self.body[:size]
    def __enter__(self):
        return self
    def __exit__(self, exc_type, exc, tb):
        return False


class QueueOpener:
    def __init__(self, payloads):
        self.payloads = list(payloads)
        self.requests = []
    def open(self, request, timeout=20):
        self.requests.append(request)
        payload = self.payloads.pop(0)
        return Response(json.dumps(payload).encode())


class QuantClientTests(unittest.TestCase):
    def test_full_quote_requires_exact_approved_identity_set(self):
        payload = {"status": "success", "data": {
            "NSE_INDEX:Nifty 50": {"instrument_token": NIFTY, "last_price": 25000, "volume": 0, "oi": 0, "timestamp": "2026-09-15T15:30:00+05:30"},
            "NSE_INDEX:India VIX": {"instrument_token": INDIA_VIX, "last_price": 12.5, "volume": 0, "oi": 0, "timestamp": "2026-09-15T15:30:00+05:30"},
        }}
        opener = QueueOpener([payload])
        client = QuantReadOnlyClient("secret-token", {NIFTY, INDIA_VIX}, opener=opener, sleep=lambda _: None)
        envelope = client.full_quotes([NIFTY, INDIA_VIX])
        self.assertEqual(set(envelope["validated_instrument_tokens"]), {NIFTY, INDIA_VIX})
        query = parse_qs(urlparse(opener.requests[0].full_url).query)
        self.assertEqual(query["instrument_key"], [f"{NIFTY},{INDIA_VIX}"])
        self.assertNotIn("secret-token", opener.requests[0].full_url)

    def test_unapproved_instrument_is_rejected_before_network(self):
        opener = QueueOpener([])
        client = QuantReadOnlyClient("secret-token", {NIFTY}, opener=opener, sleep=lambda _: None)
        with self.assertRaises(PipelineError):
            client.full_quotes(["NSE_EQ|INE002A01018"])
        self.assertEqual(opener.requests, [])

    def test_fii_serializes_repeated_data_type_and_validates_identity(self):
        types = ["NSE_EQ|CASH", "NSE_FO|INDEX_OPTIONS"]
        row = {"time_stamp": 1, "buy_amount": 1, "sell_amount": 2, "buy_contracts": 0, "sell_contracts": 0, "oi_contracts": 0}
        payload = {"status": "success", "data": {types[0]: [row], types[1]: [row]}}
        opener = QueueOpener([payload])
        client = QuantReadOnlyClient("secret-token", {NIFTY}, opener=opener, sleep=lambda _: None)
        result = client.institutional("fii", types)
        query = parse_qs(urlparse(opener.requests[0].full_url).query)
        self.assertEqual(query["data_type"], types)
        self.assertEqual(result["validated_data_types"], sorted(types))

    def test_intraday_ohlc_validation_fails_closed(self):
        bad = {"status": "success", "data": {"candles": [["2026-09-15T09:15:00+05:30", 100, 99, 90, 95, 1, 0]]}}
        client = QuantReadOnlyClient("secret-token", {NIFTY}, opener=QueueOpener([bad]), sleep=lambda _: None)
        with self.assertRaises(PipelineError) as caught:
            client.intraday(NIFTY, "minutes", 15)
        self.assertIn("index 0", str(caught.exception))
        self.assertIn("Invalid OHLC geometry", str(caught.exception))

    def test_oi_identity_and_nonnegative_fields(self):
        payload = {"status": "success", "data": {"total_puts": 10, "total_calls": 20, "spot_closing_price": 25000, "expiry": "2026-09-22", "call_put_oi_data_list": [{"strike_price": 25000, "call_oi": 10, "put_oi": 20}]}}
        client = QuantReadOnlyClient("secret-token", {NIFTY}, opener=QueueOpener([payload]), sleep=lambda _: None)
        result = client.option_analytics("oi", expiry="2026-09-22", date_value="2026-09-15")
        self.assertEqual(result["payload"]["data"]["expiry"], "2026-09-22")


if __name__ == "__main__":
    unittest.main()
