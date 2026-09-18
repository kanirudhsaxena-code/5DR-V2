"""Export the approved 29-series historical cache as immutable documents.

This runner performs authenticated read-only Upstox historical GETs and writes only
ephemeral GitHub runner files. It has no database credentials and cannot touch Neon,
canonical 5DR lifecycle tables, forecast publication, or trading surfaces.
"""
from __future__ import annotations

import json
import os
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path

from experiments.backfill_executor import BackfillExecutor, build_initial_backfill_plan
from experiments.backfill_inventory import SERIES, series_id
from experiments.cache_reconcile import reconcile_candles
from experiments.cache_store import build_cache_document, validate_cache_document
from experiments.data_contract import DataArchitectureError
from experiments.upstox_adapter import UpstoxAdapter
from experiments.upstox_quant_client import QuantReadOnlyClient
from experiments.upstox_endpoints import historical_path
from experiments.usage_ledger import UsageBudget

OUTPUT_DIR = Path(".shadow/backfill_export")
DOC_DIR = OUTPUT_DIR / "documents"
MANIFEST_FILE = OUTPUT_DIR / "manifest.json"


class ArtifactDocumentCache:
    def __init__(self, *, as_of: date):
        self.as_of = as_of
        self.documents = {}
        self.meta = {series_id(row): row for row in SERIES}

    def write_candles(self, sid, candles, envelope):
        if sid not in self.meta:
            raise DataArchitectureError("backfill artifact series outside approved inventory")
        current = self.documents.get(sid)
        existing = [] if current is None else current["records"]
        prior_events = () if current is None else current["audit_events"]
        retention_days = self.meta[sid]["retention_days"]
        cutoff_day = self.as_of - timedelta(days=retention_days - 1)
        cutoff = datetime.combine(cutoff_day, time.min, tzinfo=timezone.utc).isoformat()
        reconciled = reconcile_candles(
            existing, candles, envelope, retention_cutoff=cutoff
        )
        document = build_cache_document(
            sid,
            reconciled,
            provider_id="UPSTOX",
            source_semantic="UPSTOX_AUTHENTICATED",
            prior_audit_events=prior_events,
        )
        validate_cache_document(document)
        self.documents[sid] = document

    def export(self, plan, result):
        expected = {row["series_id"] for row in plan["series"]}
        actual = set(self.documents)
        if actual != expected:
            raise DataArchitectureError("backfill export series set mismatch")
        DOC_DIR.mkdir(parents=True, exist_ok=True)
        index = []
        total_records = 0
        for sid in sorted(actual):
            document = self.documents[sid]
            checked = validate_cache_document(document)
            filename = document["document_sha256"] + ".json"
            (DOC_DIR / filename).write_text(
                json.dumps(document, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
            total_records += checked["record_count"]
            index.append({
                "series_id": sid,
                "filename": filename,
                "record_count": checked["record_count"],
                "latest_timestamp": checked["latest_timestamp"],
                "dataset_sha256": checked["dataset_sha256"],
                "document_sha256": checked["document_sha256"],
                "audit_event_count": checked["audit_event_count"],
            })
        manifest = {
            "schema": "experimental-5dr-backfill-export-v1",
            "status": "BACKFILL_EXPORT_COMPLETE",
            "consumer": "5DR",
            "as_of": plan["as_of"],
            "plan_sha256": plan["plan_sha256"],
            "series_count": len(index),
            "planned_calls": plan["planned_calls"],
            "actual_provider_calls": result["usage"]["calls"],
            "rows_received": result["usage"]["rows_received"],
            "rows_retained_event_sum": result["usage"]["rows_retained"],
            "final_unique_records": total_records,
            "billable_units": result["usage"]["billable_units"],
            "documents": index,
            "persistent_cache_writes": 0,
            "canonical_5dr_writes": 0,
            "production_5dr_write_enabled": False,
            "forecast_release_enabled": False,
            "lifecycle_write_enabled": False,
            "trading_execution_enabled": False,
            "pr30_merge_allowed": False,
        }
        MANIFEST_FILE.write_text(
            json.dumps(manifest, sort_keys=True, separators=(",", ":")) + "\n",
            encoding="utf-8",
        )
        return manifest


def main():
    token = os.environ.get("UPSTOX_ANALYTICS_TOKEN", "").strip()
    if not token:
        raise DataArchitectureError("UPSTOX_ANALYTICS_TOKEN missing")
    raw_as_of = os.environ.get("BACKFILL_AS_OF", "").strip()
    if not raw_as_of:
        raise DataArchitectureError("BACKFILL_AS_OF missing")
    as_of = date.fromisoformat(raw_as_of)

    budget = UsageBudget(
        max_calls=250,
        max_bytes=25_000_000,
        max_rows_retained=250_000,
        max_billable_units=0,
    )
    plan = build_initial_backfill_plan(as_of, budget=budget)
    approved = {row["instrument_key"] for row in SERIES}
    raw_client = QuantReadOnlyClient(token, approved)
    base_provider = UpstoxAdapter(raw_client)

    class TracingProvider:
        def get_historical_candles(self, instrument_key, timeframe, start, end):
            marker = {
                "event": "BACKFILL_CHUNK_START",
                "instrument_key": instrument_key,
                "timeframe": timeframe,
                "start": start.isoformat(),
                "end": end.isoformat(),
            }
            print(json.dumps(marker, sort_keys=True, separators=(",", ":")), flush=True)
            try:
                envelope = base_provider.get_historical_candles(
                    instrument_key, timeframe, start, end
                )
            except Exception as exc:
                if "Invalid OHLC geometry" in str(exc):
                    unit, interval = UpstoxAdapter._HISTORICAL_TIMEFRAMES[timeframe]
                    path = historical_path(
                        instrument_key, unit, interval, start=start, end=end, intraday=False
                    )
                    raw = raw_client._get(path)
                    rows = raw.get("payload", {}).get("data", {}).get("candles", [])
                    bad = []
                    for row in rows:
                        if not isinstance(row, list) or len(row) != 7:
                            bad.append({"row": row, "reason": "shape"})
                            continue
                        try:
                            o, h, l, close = map(float, row[1:5])
                            valid = l <= min(o, close) <= max(o, close) <= h and min(o, h, l, close) > 0
                        except (TypeError, ValueError):
                            valid = False
                        if not valid:
                            bad.append({
                                "timestamp": row[0],
                                "open": row[1],
                                "high": row[2],
                                "low": row[3],
                                "close": row[4],
                                "volume": row[5],
                                "open_interest": row[6],
                            })
                    print(json.dumps({
                        **marker,
                        "event": "BACKFILL_OHLC_DIAGNOSTIC",
                        "invalid_row_count": len(bad),
                        "invalid_rows": bad[:20],
                    }, sort_keys=True, separators=(",", ":")), flush=True)
                raise
            rows = envelope.get("payload", {}).get("data", {}).get("candles", [])
            print(json.dumps({
                **marker,
                "event": "BACKFILL_CHUNK_PASS",
                "rows": len(rows),
            }, sort_keys=True, separators=(",", ":")), flush=True)
            return envelope

    provider = TracingProvider()
    cache = ArtifactDocumentCache(as_of=as_of)
    result = BackfillExecutor(
        provider=provider,
        cache=cache,
        budget=budget,
        allow_network=True,
        allow_storage_writes=True,
    ).execute(plan, dry_run=False)
    manifest = cache.export(plan, result)
    print(json.dumps(manifest, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
