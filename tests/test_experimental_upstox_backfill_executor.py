import unittest
from datetime import date

from experiments.backfill_executor import BackfillExecutor, build_initial_backfill_plan
from experiments.backfill_inventory import SERIES, series_id, validate_inventory
from experiments.data_contract import DataArchitectureError
from experiments.usage_ledger import UsageBudget


class ExplodingProvider:
    def __init__(self):
        self.calls = 0
    def get_historical_candles(self, *args, **kwargs):
        self.calls += 1
        raise AssertionError("provider must not be called")


class ExplodingCache:
    def __init__(self):
        self.writes = 0
    def write_candles(self, *args, **kwargs):
        self.writes += 1
        raise AssertionError("cache must not be written")


class BackfillExecutorTests(unittest.TestCase):
    def test_inventory_is_5dr_only_and_exactly_bounded(self):
        self.assertEqual(validate_inventory(), 29)
        self.assertEqual(len(SERIES), 29)
        self.assertTrue(all(row["consumer"] == "5DR" for row in SERIES))

    def test_full_initial_plan_is_within_explicit_budgets(self):
        plan = build_initial_backfill_plan(date(2026, 9, 15))
        self.assertEqual(plan["series_count"], 29)
        self.assertEqual(plan["planned_calls"], 90)
        self.assertEqual(plan["estimated_rows_upper_bound"], 115305)
        self.assertLessEqual(plan["planned_calls"], 250)
        self.assertLessEqual(plan["estimated_rows_upper_bound"], 250000)
        self.assertEqual(plan["billable_unit_budget"], 0)

    def test_dry_run_never_touches_provider_or_cache(self):
        provider = ExplodingProvider()
        cache = ExplodingCache()
        plan = build_initial_backfill_plan(date(2026, 9, 15))
        result = BackfillExecutor(provider=provider, cache=cache).execute(plan)
        self.assertEqual(result["status"], "BACKFILL_DRY_RUN_PASSED")
        self.assertEqual(result["network_calls_executed"], 0)
        self.assertEqual(result["storage_writes_executed"], 0)
        self.assertFalse(result["full_backfill_started"])
        self.assertEqual(provider.calls, 0)
        self.assertEqual(cache.writes, 0)

    def test_execution_requires_independent_network_and_storage_gates(self):
        plan = build_initial_backfill_plan(date(2026, 9, 15))
        with self.assertRaises(DataArchitectureError):
            BackfillExecutor(provider=ExplodingProvider(), cache=ExplodingCache(),
                             allow_network=True, allow_storage_writes=False).execute(plan, dry_run=False)
        with self.assertRaises(DataArchitectureError):
            BackfillExecutor(provider=ExplodingProvider(), cache=ExplodingCache(),
                             allow_network=False, allow_storage_writes=True).execute(plan, dry_run=False)

    def test_budget_failure_occurs_before_execution(self):
        with self.assertRaises(DataArchitectureError):
            build_initial_backfill_plan(date(2026, 9, 15), budget=UsageBudget(max_calls=89))
        with self.assertRaises(DataArchitectureError):
            build_initial_backfill_plan(date(2026, 9, 15), budget=UsageBudget(max_rows_retained=115304))

    def test_completed_cache_eliminates_all_calls(self):
        latest = {series_id(row): "2026-09-15" for row in SERIES}
        plan = build_initial_backfill_plan(date(2026, 9, 15), latest_cached=latest)
        self.assertEqual(plan["planned_calls"], 0)
        self.assertEqual(plan["estimated_rows_upper_bound"], 0)
        self.assertTrue(all(row["cache_complete"] for row in plan["series"]))

    def test_partial_cache_only_plans_missing_tail_with_overlap_day(self):
        target = SERIES[0]
        latest = {series_id(target): "2026-09-10"}
        plan = build_initial_backfill_plan(date(2026, 9, 15), latest_cached=latest)
        row = next(item for item in plan["series"] if item["series_id"] == series_id(target))
        self.assertEqual(row["chunks"][0]["start"], "2026-09-10")
        self.assertEqual(row["chunks"][-1]["end"], "2026-09-15")


if __name__ == "__main__":
    unittest.main()
