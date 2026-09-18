import json
import unittest

from experiments.upstox_quant_client import QuantReadOnlyClient, _canonical_expiry
from phase1.upstox import NIFTY, PipelineError


class Response:
    def __init__(self, payload): self.body = json.dumps(payload).encode()
    def read(self, size=-1): return self.body if size < 0 else self.body[:size]
    def __enter__(self): return self
    def __exit__(self, exc_type, exc, tb): return False


class Opener:
    def __init__(self, payload): self.payload = payload
    def open(self, request, timeout=20): return Response(self.payload)


def client_for(payload):
    return QuantReadOnlyClient("secret", {NIFTY}, opener=Opener(payload), sleep=lambda _: None)


class ExpiryNormalizationTests(unittest.TestCase):
    def test_iso_expiry_remains_canonical(self):
        self.assertEqual(_canonical_expiry("2026-09-22"), "2026-09-22")

    def test_live_provider_ddmmyyyy_normalizes_strictly(self):
        self.assertEqual(_canonical_expiry("22-09-2026"), "2026-09-22")

    def test_malformed_or_ambiguous_expiry_fails_closed(self):
        for value in ("22/09/2026", "09-22-2026", "2026/09/22", "22-9-26", ""):
            with self.subTest(value=value):
                with self.assertRaises(PipelineError):
                    _canonical_expiry(value)

    def test_oi_accepts_equivalent_live_provider_format(self):
        payload = {"status":"success","data":{"total_puts":10,"total_calls":20,"spot_closing_price":25000,"expiry":"22-09-2026","call_put_oi_data_list":[{"strike_price":25000,"call_oi":10,"put_oi":20}]}}
        result = client_for(payload).option_analytics("oi", expiry="2026-09-22", date_value="2026-09-16")
        self.assertEqual(result["validated_expiry"], "2026-09-22")

    def test_oi_different_semantic_date_still_fails(self):
        payload = {"status":"success","data":{"total_puts":10,"total_calls":20,"spot_closing_price":25000,"expiry":"23-09-2026","call_put_oi_data_list":[{"strike_price":25000,"call_oi":10,"put_oi":20}]}}
        with self.assertRaisesRegex(PipelineError, "OI expiry mismatch"):
            client_for(payload).option_analytics("oi", expiry="2026-09-22", date_value="2026-09-16")

    def test_change_oi_accepts_equivalent_live_provider_format(self):
        payload = {"status":"success","data":{"expiry":"22-09-2026","spot_closing_price":25000,"total_call_change_oi":1,"total_put_change_oi":2,"call_put_oi_data_list":[{"strike_price":25000,"call_change_oi":1,"put_change_oi":2}]}}
        result = client_for(payload).option_analytics("change_oi", expiry="2026-09-22", date_value="2026-09-16", interval=1)
        self.assertEqual(result["validated_expiry"], "2026-09-22")


if __name__ == "__main__": unittest.main()
