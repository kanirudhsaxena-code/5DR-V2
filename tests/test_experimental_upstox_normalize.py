import copy
import unittest

from experiments.upstox_normalize import build_observation
from phase1.upstox import PipelineError

BASE = {
    "run_id": "run-1",
    "instrument": {"name": "GIFT NIFTY", "exchange": "GLOBAL", "segment": "GLOBAL_INDEX", "instrument_key": "GLOBAL_INDEX|SGX NIFTY", "trading_symbol": "GIFT NIFTY"},
    "observation_type": "QUOTE",
    "values": {"ltp": 23100.0},
    "provider_timestamp": "2026-09-15T11:58:30+00:00",
    "acquisition_timestamp": "2026-09-15T12:00:00+00:00",
    "market_session": "GLOBAL_ACTIVE",
    "source_endpoint": "/v3/market-quote/quotes",
    "raw_response_sha256": "a" * 64,
    "latency": {"classification": "DELAYED_120S", "seconds": 120, "declared": "120 Seconds"},
    "freshness_classification": "DELAYED_120S",
}


class NormalizeTests(unittest.TestCase):
    def test_authenticated_machine_semantic_and_deterministic_market_fingerprint(self):
        first = build_observation(**copy.deepcopy(BASE))
        second_args = copy.deepcopy(BASE)
        second_args["acquisition_timestamp"] = "2026-09-15T12:00:10+00:00"
        second = build_observation(**second_args)
        self.assertEqual(first["source_semantic"], "UPSTOX_AUTHENTICATED")
        self.assertTrue(first["eligible_for_5dr_quantitative_evidence"])
        self.assertEqual(first["observation_fingerprint"], second["observation_fingerprint"])

    def test_missing_field_cannot_be_valid(self):
        args = copy.deepcopy(BASE)
        args["missing_fields"] = ["ltp"]
        with self.assertRaises(PipelineError):
            build_observation(**args)

    def test_stale_cannot_be_valid(self):
        args = copy.deepcopy(BASE)
        args["freshness_classification"] = "STALE"
        with self.assertRaises(PipelineError):
            build_observation(**args)

    def test_current_valid_observation_requires_provider_timestamp(self):
        args = copy.deepcopy(BASE)
        args["provider_timestamp"] = None
        with self.assertRaises(PipelineError):
            build_observation(**args)


if __name__ == "__main__":
    unittest.main()
