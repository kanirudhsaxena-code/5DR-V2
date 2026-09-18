"""Prove incremental refresh against the actual 29-series cache baseline.

Reads the immutable baseline cache documents exported by the approved full backfill,
fetches only the planner's missing tail, reconciles overlap by timestamp, applies
retention, and emits refreshed immutable documents. No database credentials or
production surfaces are present.
"""
from __future__ import annotations

import json
import os
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path

from experiments.backfill_executor import build_initial_backfill_plan
from experiments.backfill_inventory import SERIES, series_id
from experiments.cache_reconcile import reconcile_candles
from experiments.cache_store import build_cache_document, validate_cache_document
from experiments.data_contract import DataArchitectureError
from experiments.upstox_adapter import UpstoxAdapter
from experiments.upstox_quant_client import QuantReadOnlyClient
from experiments.usage_ledger import UsageBudget, UsageLedger

BASELINE_DIR = Path(os.environ.get("BASELINE_CACHE_DIR", ".shadow/baseline/cache_transfer/documents"))
SNAPSHOT = Path("experiments/gate_records/CACHE_latest_snapshot_2026-09-18.json")
OUTPUT_DIR = Path(".shadow/incremental_refresh")
DOC_DIR = OUTPUT_DIR / "documents"
MANIFEST = OUTPUT_DIR / "manifest.json"


def _load_baseline():
    docs = {}
    for path in sorted(BASELINE_DIR.glob("*.json")):
        doc = json.loads(path.read_text(encoding="utf-8"))
        checked = validate_cache_document(doc)
        docs[checked["series_id"]] = doc
    if len(docs) != 29:
        raise DataArchitectureError("incremental baseline must contain exactly 29 series")
    return docs


def main():
    token = os.environ.get("UPSTOX_ANALYTICS_TOKEN", "").strip()
    if not token:
        raise DataArchitectureError("UPSTOX_ANALYTICS_TOKEN missing")
    snap = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
    if snap.get("series_count") != 29:
        raise DataArchitectureError("latest-cache snapshot incomplete")
    latest = snap.get("latest_cached")
    if not isinstance(latest, dict) or len(latest) != 29:
        raise DataArchitectureError("latest-cache map incomplete")

    budget = UsageBudget(max_calls=60, max_bytes=25_000_000,
                         max_rows_retained=10_000, max_billable_units=0)
    plan = build_initial_backfill_plan(date(2026, 9, 18), latest_cached=latest, budget=budget)
    if plan["planned_calls"] != 29:
        raise DataArchitectureError(f"incremental plan expected 29 calls, got {plan['planned_calls']}")
    if any(len(row["chunks"]) != 1 for row in plan["series"]):
        raise DataArchitectureError("incremental plan must have exactly one tail chunk per series")
    if any(row["chunks"][0]["start"] != "2026-09-17" or row["chunks"][0]["end"] != "2026-09-18"
           for row in plan["series"]):
        raise DataArchitectureError("incremental plan escaped bounded 17..18 Sep tail")

    baseline = _load_baseline()
    approved = {row["instrument_key"] for row in SERIES}
    provider = UpstoxAdapter(QuantReadOnlyClient(token, approved))
    ledger = UsageLedger(budget)
    meta = {series_id(row): row for row in SERIES}
    results = []
    DOC_DIR.mkdir(parents=True, exist_ok=True)

    for row in plan["series"]:
        sid = row["series_id"]
        chunk = row["chunks"][0]
        env = provider.get_historical_candles(
            row["instrument_key"], row["timeframe"],
            date.fromisoformat(chunk["start"]), date.fromisoformat(chunk["end"])
        )
        candles = env["payload"]["data"]["candles"]
        ledger.record(provider="UPSTOX", consumer="5DR", operation="INCREMENTAL_HISTORICAL_TAIL",
                      rows_received=len(candles), rows_retained=len(candles),
                      response_bytes=0, cache_hit=True, billable_units=0)

        old = baseline[sid]
        retention_days = meta[sid]["retention_days"]
        cutoff_day = date(2026, 9, 18) - timedelta(days=retention_days - 1)
        cutoff = datetime.combine(cutoff_day, time.min, tzinfo=timezone.utc).isoformat()
        reconciled = reconcile_candles(old["records"], candles, env, retention_cutoff=cutoff)
        refreshed = build_cache_document(
            sid, reconciled,
            provider_id=old["provider_id"],
            source_semantic=old["source_semantic"],
            prior_audit_events=old["audit_events"],
        )
        checked = validate_cache_document(refreshed)
        filename = checked["document_sha256"] + ".json"
        (DOC_DIR / filename).write_text(
            json.dumps(refreshed, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        results.append({
            "series_id": sid,
            "tail_start": chunk["start"],
            "tail_end": chunk["end"],
            "rows_received": len(candles),
            "duplicate_count": reconciled["duplicate_count"],
            "correction_count": reconciled["correction_count"],
            "pruned_count": reconciled["pruned_count"],
            "old_record_count": old["record_count"],
            "new_record_count": checked["record_count"],
            "old_document_sha256": old["document_sha256"],
            "new_document_sha256": checked["document_sha256"],
            "latest_timestamp": checked["latest_timestamp"],
            "filename": filename,
        })

    usage = ledger.summary()
    if usage.get("calls") != 29:
        raise DataArchitectureError("incremental provider call count mismatch")
    if len(results) != 29:
        raise DataArchitectureError("incremental result count mismatch")

    manifest = {
        "schema": "5dr-v2-2-3-incremental-cache-proof-v1",
        "status": "INCREMENTAL_REFRESH_PASS",
        "as_of": "2026-09-18",
        "series_count": 29,
        "initial_backfill_calls": 90,
        "incremental_planned_calls": plan["planned_calls"],
        "incremental_actual_calls": usage["calls"],
        "estimated_rows_upper_bound": plan["estimated_rows_upper_bound"],
        "rows_received": usage["rows_received"],
        "billable_units": usage["billable_units"],
        "all_tail_chunks_bounded_to_2026_09_17_18": True,
        "canonical_integration_enabled": False,
        "production_5dr_write_enabled": False,
        "lifecycle_write_enabled": False,
        "forecast_release_enabled": False,
        "trading_execution_enabled": False,
        "results": results,
    }
    MANIFEST.write_text(json.dumps(manifest, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")
    print(json.dumps({
        "status": manifest["status"],
        "series_count": 29,
        "initial_backfill_calls": 90,
        "incremental_actual_calls": usage["calls"],
        "rows_received": usage["rows_received"],
        "duplicates": sum(r["duplicate_count"] for r in results),
        "corrections": sum(r["correction_count"] for r in results),
        "pruned": sum(r["pruned_count"] for r in results),
        "billable_units": usage["billable_units"],
    }, sort_keys=True, separators=(",", ":")))


if __name__ == "__main__":
    main()
