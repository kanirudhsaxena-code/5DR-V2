"""Offline budget proof for the experimental 5DR initial candle backfill."""
import json
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from experiments.backfill_executor import BackfillExecutor, build_initial_backfill_plan
from experiments.usage_ledger import UsageBudget

IST = ZoneInfo("Asia/Kolkata")


def main():
    as_of = datetime.now(IST).date() - timedelta(days=1)
    budget = UsageBudget(max_calls=250, max_bytes=25_000_000,
                         max_rows_retained=250_000, max_billable_units=0)
    plan = build_initial_backfill_plan(as_of, budget=budget)
    result = BackfillExecutor(budget=budget).execute(plan, dry_run=True)
    by_variable = {}
    by_timeframe = {}
    for series in plan["series"]:
        by_variable[series["variable_id"]] = by_variable.get(series["variable_id"], 0) + len(series["chunks"])
        by_timeframe[series["timeframe"]] = by_timeframe.get(series["timeframe"], 0) + len(series["chunks"])
    result.update({
        "as_of": plan["as_of"],
        "call_budget": plan["call_budget"],
        "row_budget": plan["row_budget"],
        "billable_unit_budget": plan["billable_unit_budget"],
        "planned_calls_by_variable": dict(sorted(by_variable.items())),
        "planned_calls_by_timeframe": dict(sorted(by_timeframe.items())),
        "cache_storage_adapter_connected": False,
        "provider_adapter_invoked": False,
    })
    print(json.dumps(result, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
