"""Fail-closed historical backfill/cache executor for the experimental data core.

Planning and dry-run are pure/offline. Network and storage writes are impossible unless
both are separately enabled and a concrete read-only provider/cache adapter is supplied.
No canonical 5DR lifecycle or trading surface is referenced here.
"""
import hashlib
import json
from datetime import date, datetime

from experiments.backfill_inventory import SERIES, series_id, validate_inventory
from experiments.data_contract import DataArchitectureError
from experiments.upstox_history_policy import TIMEFRAME_MAP, plan_history_chunks
from experiments.usage_ledger import UsageBudget, UsageLedger

MAX_BARS_PER_CALENDAR_DAY = {
    "NSE_INDEX": {"5m": 75, "15m": 25, "30m": 13, "1h": 7, "1d": 1},
    "GLOBAL": {"1h": 24, "1d": 1},
}


def _date(value, field):
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        try:
            return date.fromisoformat(value[:10])
        except ValueError:
            raise DataArchitectureError(f"{field} invalid") from None
    raise DataArchitectureError(f"{field} invalid")


def _family(instrument_key):
    if instrument_key.startswith("NSE_INDEX|"):
        return "NSE_INDEX"
    if instrument_key.startswith("GLOBAL_INDEX|") or instrument_key.startswith("GLOBAL_INDICATOR|"):
        return "GLOBAL"
    raise DataArchitectureError("backfill instrument family unsupported")


def _estimated_rows(row):
    family = _family(row["instrument_key"])
    per_day = MAX_BARS_PER_CALENDAR_DAY.get(family, {}).get(row["timeframe"])
    if per_day is None:
        raise DataArchitectureError("row estimate unavailable")
    return row["lookback_days"] * per_day


def build_initial_backfill_plan(as_of, *, latest_cached=None,
                                budget=None, rows=SERIES):
    """Return a deterministic bounded plan without making network/storage calls."""
    validate_inventory(rows)
    end = _date(as_of, "as_of")
    latest_cached = dict(latest_cached or {})
    budget = budget or UsageBudget()
    if not isinstance(budget, UsageBudget):
        raise DataArchitectureError("backfill budget invalid")

    series_plans = []
    planned_calls = 0
    estimated_rows = 0
    for row in rows:
        sid = series_id(row)
        required_start = end.fromordinal(end.toordinal() - row["lookback_days"] + 1)
        cached_value = latest_cached.get(sid)
        cache_complete = False
        missing_start = required_start
        if cached_value is not None:
            cached_date = _date(cached_value, "latest_cached")
            if cached_date >= end:
                cache_complete = True
            elif cached_date >= required_start:
                # Re-fetch the last cached calendar day intentionally. The future cache
                # adapter deduplicates by timestamp, protecting incomplete final bars.
                missing_start = cached_date
        unit, interval = TIMEFRAME_MAP[row["timeframe"]]
        chunks = [] if cache_complete else plan_history_chunks(missing_start, end, unit, interval)
        serialized_chunks = [
            {"start": chunk["start"].isoformat(), "end": chunk["end"].isoformat(),
             "unit": chunk["unit"], "interval": chunk["interval"]}
            for chunk in chunks
        ]
        planned_calls += len(serialized_chunks)
        conservative_rows = 0 if cache_complete else _estimated_rows({**row, "lookback_days": (end - missing_start).days + 1})
        estimated_rows += conservative_rows
        series_plans.append({
            "series_id": sid,
            "variable_id": row["variable_id"],
            "subject_id": row["subject_id"],
            "instrument_key": row["instrument_key"],
            "timeframe": row["timeframe"],
            "required_start": required_start.isoformat(),
            "required_end": end.isoformat(),
            "retention_days": row["retention_days"],
            "cache_complete": cache_complete,
            "estimated_rows_upper_bound": conservative_rows,
            "chunks": serialized_chunks,
        })

    if planned_calls > budget.max_calls:
        raise DataArchitectureError("planned backfill exceeds call budget")
    if estimated_rows > budget.max_rows_retained:
        raise DataArchitectureError("planned backfill exceeds retention-row budget")
    canonical = json.dumps(series_plans, sort_keys=True, separators=(",", ":"))
    return {
        "schema": "experimental-5dr-backfill-plan-v1",
        "consumer": "5DR",
        "as_of": end.isoformat(),
        "series_count": len(series_plans),
        "planned_calls": planned_calls,
        "estimated_rows_upper_bound": estimated_rows,
        "call_budget": budget.max_calls,
        "row_budget": budget.max_rows_retained,
        "billable_unit_budget": budget.max_billable_units,
        "plan_sha256": hashlib.sha256(canonical.encode()).hexdigest(),
        "series": series_plans,
    }


class BackfillExecutor:
    def __init__(self, *, provider=None, cache=None, budget=None,
                 allow_network=False, allow_storage_writes=False):
        self.provider = provider
        self.cache = cache
        self.budget = budget or UsageBudget()
        if not isinstance(allow_network, bool) or not isinstance(allow_storage_writes, bool):
            raise DataArchitectureError("backfill execution flags invalid")
        self.allow_network = allow_network
        self.allow_storage_writes = allow_storage_writes

    def execute(self, plan, *, dry_run=True):
        if not isinstance(dry_run, bool) or not isinstance(plan, dict):
            raise DataArchitectureError("backfill execution request invalid")
        calls = plan.get("planned_calls")
        rows = plan.get("estimated_rows_upper_bound")
        if isinstance(calls, bool) or not isinstance(calls, int) or calls < 0:
            raise DataArchitectureError("backfill plan calls invalid")
        if isinstance(rows, bool) or not isinstance(rows, int) or rows < 0:
            raise DataArchitectureError("backfill plan rows invalid")
        if calls > self.budget.max_calls or rows > self.budget.max_rows_retained:
            raise DataArchitectureError("backfill execution budget exceeded")
        if self.budget.max_billable_units != 0:
            raise DataArchitectureError("experimental backfill billable budget must remain zero")

        if dry_run:
            return {
                "status": "BACKFILL_DRY_RUN_PASSED",
                "plan_sha256": plan.get("plan_sha256"),
                "series_count": plan.get("series_count"),
                "planned_calls": calls,
                "estimated_rows_upper_bound": rows,
                "network_calls_executed": 0,
                "storage_writes_executed": 0,
                "full_backfill_started": False,
                "read_only": True,
                "production_5dr_write_enabled": False,
                "canonical_integration_enabled": False,
                "trading_enabled": False,
            }

        # Any future actual backfill must cross two independent explicit gates.
        if not self.allow_network or not self.allow_storage_writes:
            raise DataArchitectureError("backfill execution is not explicitly enabled")
        if self.provider is None or not callable(getattr(self.provider, "get_historical_candles", None)):
            raise DataArchitectureError("backfill provider unavailable")
        if self.cache is None or not callable(getattr(self.cache, "write_candles", None)):
            raise DataArchitectureError("backfill cache unavailable")

        ledger = UsageLedger(self.budget)
        writes = 0
        for series in plan.get("series", []):
            for chunk in series.get("chunks", []):
                envelope = self.provider.get_historical_candles(
                    series["instrument_key"], series["timeframe"],
                    date.fromisoformat(chunk["start"]), date.fromisoformat(chunk["end"]),
                )
                payload = envelope.get("payload", {}) if isinstance(envelope, dict) else {}
                data = payload.get("data", {}) if isinstance(payload, dict) else {}
                candles = data.get("candles") if isinstance(data, dict) else None
                if not isinstance(candles, list):
                    raise DataArchitectureError("backfill provider candle schema invalid")
                ledger.record(provider="UPSTOX", consumer="5DR", operation="HISTORICAL_CANDLES",
                              rows_received=len(candles), rows_retained=len(candles),
                              response_bytes=0, cache_hit=False, billable_units=0)
                self.cache.write_candles(series["series_id"], candles, envelope)
                writes += 1
        return {
            "status": "BACKFILL_EXECUTION_PASSED",
            "usage": ledger.summary(),
            "storage_writes_executed": writes,
            "read_only_provider": True,
            "production_5dr_write_enabled": False,
            "canonical_integration_enabled": False,
            "trading_enabled": False,
        }
