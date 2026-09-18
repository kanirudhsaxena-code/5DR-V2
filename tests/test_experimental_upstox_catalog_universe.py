import gzip
import json
import unittest

from experiments.upstox_catalog import GLOBAL_URL, PublicInstrumentCatalog
from experiments.upstox_instruments import GLOBAL_TARGET_NAMES
from experiments.upstox_quant_client import INDIA_VIX
from experiments.upstox_universe import build_core_5dr_universe
from phase1.upstox import NIFTY, PipelineError


class Response:
    def __init__(self, body): self.body = body
    def read(self, size=-1): return self.body if size < 0 else self.body[:size]
    def __enter__(self): return self
    def __exit__(self, exc_type, exc, tb): return False

class Opener:
    def __init__(self, body): self.body = body; self.requests = []
    def open(self, request, timeout=20): self.requests.append(request); return Response(self.body)


class CatalogUniverseTests(unittest.TestCase):
    def test_catalog_is_strict_public_allowlist_and_no_authorization_header(self):
        body = gzip.compress(json.dumps([{"name": "GIFT NIFTY"}]).encode())
        opener = Opener(body)
        catalog = PublicInstrumentCatalog(opener=opener)
        result = catalog.fetch(GLOBAL_URL)
        self.assertEqual(len(result["records"]), 1)
        headers = {name.lower(): value for name, value in opener.requests[0].header_items()}
        self.assertNotIn("authorization", headers)
        with self.assertRaises(PipelineError):
            catalog.fetch("https://example.com/data.json.gz")

    def test_core_universe_contains_only_expected_market_key_families(self):
        globals_ = {}
        for index, target in enumerate(GLOBAL_TARGET_NAMES):
            globals_[target] = {"exchange": "GLOBAL", "instrument_key": f"GLOBAL_INDEX|K{index}"}
        future = {"underlying_key": NIFTY, "instrument_type": "FUT", "instrument_key": "NSE_FO|123"}
        keys = build_core_5dr_universe(globals_, future)
        self.assertEqual(len(keys), 14)
        self.assertIn(NIFTY, keys)
        self.assertIn(INDIA_VIX, keys)
        self.assertFalse(any(key.startswith("NSE_EQ|") for key in keys))

    def test_incomplete_global_universe_fails_closed(self):
        future = {"underlying_key": NIFTY, "instrument_type": "FUT", "instrument_key": "NSE_FO|123"}
        with self.assertRaises(PipelineError):
            build_core_5dr_universe({}, future)


if __name__ == "__main__":
    unittest.main()
