import json
import unittest
from datetime import date

from experiments.data_contract import DataArchitectureError
from experiments.edge_stock_upstox import (
    EdgeStockReadOnlyClient,
    assert_edge_stock_read_only_surface,
)
from phase1.upstox import PipelineError


class Response:
    def __init__(self, payload):
        self.body = json.dumps(payload).encode()
    def read(self, size=-1):
        return self.body if size < 0 else self.body[:size]
    def __enter__(self):
        return self
    def __exit__(self, exc_type, exc, tb):
        return False


class Opener:
    def __init__(self, payload):
        self.payload = payload
        self.requests = []
    def open(self, request, timeout=20):
        self.requests.append(request)
        return Response(self.payload)


class EdgeStockUpstoxTests(unittest.TestCase):
    def test_surface_is_read_only(self):
        self.assertTrue(assert_edge_stock_read_only_surface())
        client = EdgeStockReadOnlyClient(
            "secret",
            approved_instruments={"NSE_EQ|INE002A01018"},
            opener=Opener({"status": "success", "data": {}}),
            sleep=lambda _: None,
        )
        for forbidden in ("place_order", "cancel_order", "funds", "holdings", "positions"):
            self.assertFalse(hasattr(client, forbidden))

    def test_fundamental_path_uses_exact_isin_and_get(self):
        opener = Opener({"status": "success", "data": {"x": 1}})
        client = EdgeStockReadOnlyClient(
            "secret",
            approved_instruments={"NSE_EQ|INE002A01018"},
            opener=opener,
            sleep=lambda _: None,
        )
        out = client.fundamental("key_ratios", "INE002A01018")
        self.assertEqual(out["source_path"], "/v2/fundamentals/INE002A01018/key-ratios")
        self.assertEqual(opener.requests[0].get_method(), "GET")
        self.assertNotIn("secret", opener.requests[0].full_url)

    def test_income_statement_params_are_bounded(self):
        opener = Opener({"status": "success", "data": {}})
        client = EdgeStockReadOnlyClient(
            "secret",
            approved_instruments={"NSE_EQ|INE002A01018"},
            opener=opener,
            sleep=lambda _: None,
        )
        client.fundamental(
            "income_statement",
            "INE002A01018",
            type="consolidated",
            time_period="quarterly",
            fs=True,
        )
        url = opener.requests[0].full_url
        self.assertIn("time_period=quarterly", url)
        self.assertIn("fs=true", url)
        with self.assertRaises(DataArchitectureError):
            client.fundamental("income_statement", "INE002A01018", type="bad")

    def test_unapproved_quote_fails_before_network(self):
        opener = Opener({"status": "success", "data": {}})
        client = EdgeStockReadOnlyClient(
            "secret",
            approved_instruments={"NSE_EQ|INE002A01018"},
            opener=opener,
            sleep=lambda _: None,
        )
        with self.assertRaises(DataArchitectureError):
            client.full_quotes(["NSE_EQ|OTHER"])
        self.assertEqual(opener.requests, [])

    def test_option_chain_can_use_equity_underlying(self):
        payload = {
            "status": "success",
            "data": [{
                "underlying_key": "NSE_EQ|INE002A01018",
                "expiry": "2026-09-29",
                "strike_price": 300,
            }],
        }
        opener = Opener(payload)
        client = EdgeStockReadOnlyClient(
            "secret",
            approved_instruments={"NSE_EQ|INE002A01018"},
            opener=opener,
            sleep=lambda _: None,
        )
        out = client.option_chain("NSE_EQ|INE002A01018", date(2026, 9, 29))
        self.assertEqual(out["payload"]["data"][0]["expiry"], "2026-09-29")

    def test_forbidden_path_is_not_exposed(self):
        client = EdgeStockReadOnlyClient(
            "secret",
            approved_instruments={"NSE_EQ|INE002A01018"},
            opener=Opener({"status": "success", "data": {}}),
            sleep=lambda _: None,
        )
        with self.assertRaises(PipelineError):
            client._get("/v2/order/place")


if __name__ == "__main__":
    unittest.main()
