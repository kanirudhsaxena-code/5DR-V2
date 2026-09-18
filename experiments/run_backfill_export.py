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
from experiments.upstox_quality import validate_ohlc
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
        KNOWN_QUARANTINES = (
            {
                "instrument_key": "GLOBAL_INDEX|SGX NIFTY",
                "timeframe": "1d",
                "timestamp": "2026-07-19T00:00:00+05:30",
                "open": 24373.5,
                "high": 24371.5,
                "low": 24092.0,
                "close": 24125.0,
                "volume": 0,
                "open_interest": 0,
                "reason": "PROVIDER_INVALID_OHLC_OPEN_ABOVE_HIGH",
            },
            {
                "instrument_key": "GLOBAL_INDICATOR|CLUSD",
                "timeframe": "1d",
                "timestamp": "2026-06-18T00:00:00+05:30",
                "open": 74.88,
                "high": 76.06,
                "low": 72.83,
                "close": 76.58,
                "volume": 0,
                "open_interest": 0,
                "reason": "PROVIDER_INVALID_OHLC_CLOSE_ABOVE_HIGH",
            },
        )

        def __init__(self):
            self.quarantines = []

        @classmethod
        def _known_quarantine(cls, instrument_key, timeframe, row):
            if not isinstance(row, list) or len(row) != 7:
                return None
            for expected in cls.KNOWN_QUARANTINES:
                if (
                    instrument_key == expected["instrument_key"]
                    and timeframe == expected["timeframe"]
                    and row[0] == expected["timestamp"]
                    and row[1] == expected["open"]
                    and row[2] == expected["high"]
                    and row[3] == expected["low"]
                    and row[4] == expected["close"]
                    and row[5] == expected["volume"]
                    and row[6] == expected["open_interest"]
                ):
                    return expected
            return None

        def get_historical_candles(self, instrument_key, timeframe, start, end):
            marker = {
                "event": "BACKFILL_CHUNK_START",
                "instrument_key": instrument_key,
                "timeframe": timeframe,
                "start": start.isoformat(),
                "end": end.isoformat(),
            }
            print(json.dumps(marker, sort_keys=True, separators=(",", ":")), flush=True)

            expected_for_series = [
                row for row in self.KNOWN_QUARANTINES
                if row["instrument_key"] == instrument_key and row["timeframe"] == timeframe
            ]
            if expected_for_series:
                unit, interval = UpstoxAdapter._HISTORICAL_TIMEFRAMES[timeframe]
                path = historical_path(
                    instrument_key, unit, interval, start=start, end=end, intraday=False
                )
                envelope = raw_client._get(path)
                raw_rows = envelope.get("payload", {}).get("data", {}).get("candles", [])
                if not isinstance(raw_rows, list) or not raw_rows:
                    raise DataArchitectureError("quarantine-series raw candle array missing")
                valid_rows = []
                quarantined_this_call = []
                for row in raw_rows:
                    try:
                        if not isinstance(row, list) or len(row) != 7:
                            raise DataArchitectureError("daily candle shape invalid")
                        stamp = datetime.fromisoformat(row[0])
                        if stamp.tzinfo is None:
                            raise DataArchitectureError("daily candle timestamp naive")
                        validate_ohlc(
                            row[1], row[2], row[3], row[4],
                            volume=row[5], open_interest=row[6],
                        )
                        valid_rows.append(row)
                    except Exception:
                        expected = self._known_quarantine(instrument_key, timeframe, row)
                        if expected is None:
                            raise
                        quarantine = {
                            **expected,
                            "source_sha256": envelope.get("sha256"),
                            "action": "QUARANTINED_NOT_CACHED",
                        }
                        quarantined_this_call.append(quarantine)
                        self.quarantines.append(quarantine)
                        print(json.dumps({
                            **marker,
                            "event": "BACKFILL_ROW_QUARANTINED",
                            "quarantine": quarantine,
                        }, sort_keys=True, separators=(",", ":")), flush=True)
                expected_in_range = [
                    row for row in expected_for_series
                    if start.isoformat() <= row["timestamp"][:10] <= end.isoformat()
                ]
                if len(quarantined_this_call) != len(expected_in_range):
                    raise DataArchitectureError("exact provider quarantine count mismatch")
                envelope["payload"]["data"]["candles"] = valid_rows
                envelope["validated_candles"] = len(valid_rows)
            else:
                envelope = base_provider.get_historical_candles(
                    instrument_key, timeframe, start, end
                )

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
    manifest["quarantined_provider_rows"] = provider.quarantines
    manifest["quarantined_provider_row_count"] = len(provider.quarantines)
    manifest["status"] = (
        "BACKFILL_EXPORT_COMPLETE_WITH_EXACT_QUARANTINE"
        if provider.quarantines else "BACKFILL_EXPORT_COMPLETE"
    )
    MANIFEST_FILE.write_text(
        json.dumps(manifest, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(manifest, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
