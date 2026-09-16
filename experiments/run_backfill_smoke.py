"""One-call live execution proof for the backfill executor using ephemeral memory only."""
import json
import os
from copy import deepcopy
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from experiments.backfill_executor import BackfillExecutor, build_initial_backfill_plan
from experiments.backfill_inventory import SERIES
from experiments.upstox_adapter import UpstoxAdapter
from experiments.upstox_quant_client import QuantReadOnlyClient
from experiments.usage_ledger import UsageBudget
from phase1.upstox import NIFTY, PipelineError

IST = ZoneInfo("Asia/Kolkata")


class EphemeralProbeCache:
    def __init__(self):
        self.write_count = 0
        self.row_count = 0
        self.provenance = None

    def write_candles(self, series_id, candles, envelope):
        if not isinstance(series_id, str) or not isinstance(candles, list) or not isinstance(envelope, dict):
            raise PipelineError("Ephemeral cache input invalid")
        self.write_count += 1
        self.row_count += len(candles)
        self.provenance = {
            "source_path": envelope.get("source_path"),
            "sha256": envelope.get("sha256"),
            "received_at": envelope.get("received_at"),
        }


def main():
    token = os.environ.get("UPSTOX_ANALYTICS_TOKEN", "")
    if not token.strip():
        raise SystemExit("UPSTOX_ANALYTICS_TOKEN missing")
    as_of = datetime.now(IST).date() - timedelta(days=1)
    smoke_series = deepcopy(SERIES[0])
    if smoke_series["instrument_key"] != NIFTY or smoke_series["timeframe"] != "5m":
        raise PipelineError("Backfill smoke inventory identity changed")
    smoke_series["lookback_days"] = 7
    budget = UsageBudget(max_calls=1, max_bytes=2_000_000,
                         max_rows_retained=1_000, max_billable_units=0)
    plan = build_initial_backfill_plan(as_of, rows=(smoke_series,), budget=budget)
    if plan["planned_calls"] != 1:
        raise PipelineError("Backfill smoke must remain exactly one provider call")

    client = QuantReadOnlyClient(token, {NIFTY})
    provider = UpstoxAdapter(client)
    cache = EphemeralProbeCache()
    result = BackfillExecutor(
        provider=provider, cache=cache, budget=budget,
        allow_network=True, allow_storage_writes=True,
    ).execute(plan, dry_run=False)
    if result.get("usage", {}).get("calls") != 1 or cache.write_count != 1:
        raise PipelineError("Backfill smoke execution count mismatch")

    output = {
        "status": "BACKFILL_SINGLE_CHUNK_SMOKE_PASSED",
        "consumer_scope": "5DR_EXPERIMENT_ONLY",
        "series_id": plan["series"][0]["series_id"],
        "timeframe": "5m",
        "requested_start": plan["series"][0]["chunks"][0]["start"],
        "requested_end": plan["series"][0]["chunks"][0]["end"],
        "plan_sha256": plan["plan_sha256"],
        "network_calls_executed": result["usage"]["calls"],
        "rows_received": result["usage"]["rows_received"],
        "ephemeral_cache_writes": cache.write_count,
        "persistent_cache_writes": 0,
        "ephemeral_rows_held": cache.row_count,
        "provenance": cache.provenance,
        "full_backfill_started": False,
        "production_5dr_write_enabled": False,
        "canonical_integration_enabled": False,
        "trading_enabled": False,
        "read_only": True,
        "billable_units": result["usage"]["billable_units"],
    }
    print(json.dumps(output, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
