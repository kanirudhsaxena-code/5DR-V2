"""Storage-neutral candle cache reconciliation for the experimental data backbone.

This module performs no I/O. It defines how overlapping historical batches are merged,
how provider corrections are audited, how retention is applied, and how deterministic
market-content fingerprints are produced before any durable backend is introduced.
"""
import hashlib
import json
from datetime import datetime, timezone

from experiments.data_contract import DataArchitectureError
from experiments.upstox_quality import validate_ohlc


def _timestamp(value, field):
    if not isinstance(value, str):
        raise DataArchitectureError(f"{field} invalid")
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        raise DataArchitectureError(f"{field} invalid") from None
    if parsed.tzinfo is None:
        raise DataArchitectureError(f"{field} naive")
    return parsed.astimezone(timezone.utc)


def _provenance(envelope):
    if not isinstance(envelope, dict):
        raise DataArchitectureError("cache provenance missing")
    source_path = envelope.get("source_path")
    digest = envelope.get("sha256")
    received_at = envelope.get("received_at")
    if not isinstance(source_path, str) or not source_path.startswith("/"):
        raise DataArchitectureError("cache source path invalid")
    if not isinstance(digest, str) or len(digest) != 64 or any(c not in "0123456789abcdef" for c in digest.lower()):
        raise DataArchitectureError("cache source digest invalid")
    received = _timestamp(received_at, "received_at")
    return {"source_path": source_path, "sha256": digest.lower(), "received_at": received.isoformat()}


def _market_hash(candle):
    canonical = json.dumps(candle, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode()).hexdigest()


def normalize_candle(row, envelope):
    if not isinstance(row, list) or len(row) != 7:
        raise DataArchitectureError("cache candle schema invalid")
    stamp = _timestamp(row[0], "candle timestamp")
    validate_ohlc(row[1], row[2], row[3], row[4], volume=row[5], open_interest=row[6])
    candle = [stamp.isoformat(), row[1], row[2], row[3], row[4], row[5], row[6]]
    provenance = _provenance(envelope)
    return {
        "timestamp": stamp.isoformat(),
        "candle": candle,
        "market_sha256": _market_hash(candle),
        "provenance": provenance,
        "supersedes_market_sha256": None,
    }


def _validate_cached_record(record):
    if not isinstance(record, dict):
        raise DataArchitectureError("cached record invalid")
    required = {"timestamp", "candle", "market_sha256", "provenance", "supersedes_market_sha256"}
    if set(record) != required:
        raise DataArchitectureError("cached record schema invalid")
    stamp = _timestamp(record["timestamp"], "cached timestamp")
    candle = record["candle"]
    if not isinstance(candle, list) or len(candle) != 7 or _timestamp(candle[0], "cached candle timestamp") != stamp:
        raise DataArchitectureError("cached candle identity mismatch")
    validate_ohlc(candle[1], candle[2], candle[3], candle[4], volume=candle[5], open_interest=candle[6])
    if record["market_sha256"] != _market_hash(candle):
        raise DataArchitectureError("cached market fingerprint mismatch")
    _provenance(record["provenance"])
    prior = record["supersedes_market_sha256"]
    if prior is not None and (not isinstance(prior, str) or len(prior) != 64):
        raise DataArchitectureError("cached supersedes fingerprint invalid")
    return stamp


def _dataset_hash(records):
    compact = [[record["timestamp"], record["market_sha256"]] for record in records]
    canonical = json.dumps(compact, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()


def reconcile_candles(existing, incoming_rows, envelope, *, retention_cutoff=None):
    if not isinstance(existing, list) or not isinstance(incoming_rows, list):
        raise DataArchitectureError("cache reconciliation input invalid")
    by_timestamp = {}
    for record in existing:
        stamp = _validate_cached_record(record).isoformat()
        if stamp in by_timestamp:
            raise DataArchitectureError("duplicate cached timestamp")
        by_timestamp[stamp] = dict(record)

    normalized = [normalize_candle(row, envelope) for row in incoming_rows]
    incoming_stamps = [record["timestamp"] for record in normalized]
    if len(incoming_stamps) != len(set(incoming_stamps)):
        raise DataArchitectureError("duplicate incoming candle timestamp")

    duplicate_count = 0
    corrections = []
    for new_record in normalized:
        stamp = new_record["timestamp"]
        old = by_timestamp.get(stamp)
        if old is None:
            by_timestamp[stamp] = new_record
            continue
        if old["market_sha256"] == new_record["market_sha256"]:
            duplicate_count += 1
            continue
        new_record["supersedes_market_sha256"] = old["market_sha256"]
        corrections.append({
            "event": "PROVIDER_CORRECTION",
            "timestamp": stamp,
            "old_market_sha256": old["market_sha256"],
            "new_market_sha256": new_record["market_sha256"],
            "source_sha256": new_record["provenance"]["sha256"],
            "received_at": new_record["provenance"]["received_at"],
        })
        by_timestamp[stamp] = new_record

    cutoff = None
    if retention_cutoff is not None:
        if isinstance(retention_cutoff, datetime):
            if retention_cutoff.tzinfo is None:
                raise DataArchitectureError("retention cutoff naive")
            cutoff = retention_cutoff.astimezone(timezone.utc)
        else:
            cutoff = _timestamp(retention_cutoff, "retention cutoff")
    before = len(by_timestamp)
    if cutoff is not None:
        by_timestamp = {
            stamp: record for stamp, record in by_timestamp.items()
            if _timestamp(stamp, "cache timestamp") >= cutoff
        }
    pruned_count = before - len(by_timestamp)
    records = [by_timestamp[key] for key in sorted(by_timestamp)]
    latest = records[-1]["timestamp"] if records else None
    return {
        "status": "CACHE_RECONCILIATION_PASS",
        "records": records,
        "record_count": len(records),
        "latest_timestamp": latest,
        "duplicate_count": duplicate_count,
        "correction_count": len(corrections),
        "pruned_count": pruned_count,
        "audit_events": corrections,
        "dataset_sha256": _dataset_hash(records),
    }
