import copy
import unittest
from datetime import date

from experiments.backfill_executor import BackfillExecutor, build_initial_backfill_plan
from experiments.backfill_inventory import SERIES
from experiments.data_contract import DataArchitectureError
from experiments.usage_ledger import UsageBudget


class FakeProvider:
    def __init__(self):
        self.calls = 0
    def get_historical_candles(self, instrument_key, timeframe, start, end):
        self.calls += 1
        return {"payload": {"data": {"candles": [["2026-09-15T09:15:00+05:30", 1, 1, 1, 1, 0, 0]]}},
                "source_path": "/history", "sha256": "a" * 64, "received_at": "2026-09-16T00:00:00+00:00"}


class FakeCache:
    def __init__(self):
        self.writes = 0
    def write_candles(self, series_id, candles, envelope):
        self.writes += 1


class BackfillIntegrityTests(unittest.TestCase):
    def _single_plan(self):
        row = copy.deepcopy(SERIES[0])
        row["lookback_days"] = 7
        return build_initial_backfill_plan(date(2026, 9, 15), rows=(row,),
                                           budget=UsageBudget(max_calls=1, max_rows_retained=1000))

    def test_tampered_plan_fingerprint_fails_before_provider(self):
        plan = self._single_plan()
        plan["series"][0]["chunks"][0]["start"] = "2026-09-08"
        provider, cache = FakeProvider(), FakeCache()
        with self.assertRaises(DataArchitectureError):
            BackfillExecutor(provider=provider, cache=cache,
                             budget=UsageBudget(max_calls=1, max_rows_retained=1000),
                             allow_network=True, allow_storage_writes=True).execute(plan, dry_run=False)
        self.assertEqual(provider.calls, 0)
        self.assertEqual(cache.writes, 0)

    def test_single_chunk_execution_uses_exactly_one_provider_and_cache_call(self):
        plan = self._single_plan()
        provider, cache = FakeProvider(), FakeCache()
        result = BackfillExecutor(provider=provider, cache=cache,
                                  budget=UsageBudget(max_calls=1, max_rows_retained=1000),
                                  allow_network=True, allow_storage_writes=True).execute(plan, dry_run=False)
        self.assertEqual(result["status"], "BACKFILL_EXECUTION_PASSED")
        self.assertEqual(result["usage"]["calls"], 1)
        self.assertEqual(provider.calls, 1)
        self.assertEqual(cache.writes, 1)
        self.assertFalse(result["production_5dr_write_enabled"])


if __name__ == "__main__":
    unittest.main()
