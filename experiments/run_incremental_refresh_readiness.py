"""Offline proof that a populated 29-series cache refreshes only the missing tail."""
import json
from datetime import date
from experiments.backfill_executor import build_initial_backfill_plan
from experiments.backfill_inventory import SERIES, series_id
from experiments.usage_ledger import UsageBudget

def main():
    latest={series_id(row): date(2026,9,17) for row in SERIES}
    budget=UsageBudget(max_calls=250,max_bytes=25_000_000,max_rows_retained=250_000,max_billable_units=0)
    complete=build_initial_backfill_plan(date(2026,9,17),latest_cached=latest,budget=budget)
    next_day=build_initial_backfill_plan(date(2026,9,18),latest_cached=latest,budget=budget)
    if complete["planned_calls"]!=0:
        raise SystemExit("complete cache unexpectedly schedules calls")
    if next_day["planned_calls"]!=29:
        raise SystemExit("next-day incremental plan must be one bounded chunk per series")
    if any(len(row["chunks"])!=1 for row in next_day["series"]):
        raise SystemExit("incremental series chunk count invalid")
    out={
      "status":"INCREMENTAL_REFRESH_READINESS_PASS",
      "cache_complete_as_of":"2026-09-17",
      "complete_cache_planned_calls":complete["planned_calls"],
      "next_completed_date_simulation":"2026-09-18",
      "incremental_series_count":next_day["series_count"],
      "incremental_planned_calls":next_day["planned_calls"],
      "incremental_estimated_rows_upper_bound":next_day["estimated_rows_upper_bound"],
      "call_budget":next_day["call_budget"],
      "row_budget":next_day["row_budget"],
      "billable_unit_budget":next_day["billable_unit_budget"],
      "overlap_policy":"REFETCH_LAST_CACHED_TRADING_DAY_FOR_DEDUP_AND_PROVIDER_CORRECTION",
      "network_calls_executed":0,
      "storage_writes_executed":0,
      "production_activation":False,
    }
    print(json.dumps(out,sort_keys=True,separators=(",",":")))
if __name__=="__main__": main()
