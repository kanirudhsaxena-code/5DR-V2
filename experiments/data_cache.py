"""Storage-neutral incremental/backfill planning primitives.

No database is created here. These functions let a future cache/storage adapter fetch
only missing intervals and apply bounded retention.
"""
import hashlib
from datetime import datetime, timedelta, timezone

from experiments.data_contract import DataArchitectureError


def _utc(value, field):
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value)
        except ValueError:
            raise DataArchitectureError(f"{field} invalid") from None
    else:
        raise DataArchitectureError(f"{field} missing")
    if parsed.tzinfo is None:
        raise DataArchitectureError(f"{field} naive")
    return parsed.astimezone(timezone.utc)


def cache_key(provider_id, variable_id, subject_id, timeframe="none"):
    parts = [provider_id, variable_id, subject_id, timeframe]
    if any(not isinstance(v, str) or not v.strip() for v in parts):
        raise DataArchitectureError("cache key field invalid")
    canonical = "|".join(v.strip().upper() for v in parts)
    return hashlib.sha256(canonical.encode()).hexdigest()


def plan_incremental_range(required_from, required_to, latest_cached=None, *, overlap_seconds=0):
    start = _utc(required_from, "required_from")
    end = _utc(required_to, "required_to")
    if end < start:
        raise DataArchitectureError("incremental range reversed")
    if isinstance(overlap_seconds, bool) or not isinstance(overlap_seconds, (int, float)) or overlap_seconds < 0:
        raise DataArchitectureError("overlap invalid")
    if latest_cached is None:
        return {"from": start.isoformat(), "to": end.isoformat(), "cache_hit": False}
    latest = _utc(latest_cached, "latest_cached")
    if latest >= end:
        return None
    missing_start = max(start, latest - timedelta(seconds=overlap_seconds))
    return {"from": missing_start.isoformat(), "to": end.isoformat(), "cache_hit": latest >= start}


def retention_cutoff(as_of, retention_days):
    current = _utc(as_of, "as_of")
    if isinstance(retention_days, bool) or not isinstance(retention_days, int) or retention_days <= 0:
        raise DataArchitectureError("retention invalid")
    return (current - timedelta(days=retention_days)).isoformat()


def backfill_chunks(required_from, required_to, max_chunk_days):
    start = _utc(required_from, "required_from")
    end = _utc(required_to, "required_to")
    if end < start:
        raise DataArchitectureError("backfill range reversed")
    if isinstance(max_chunk_days, bool) or not isinstance(max_chunk_days, int) or max_chunk_days <= 0:
        raise DataArchitectureError("chunk size invalid")
    chunks = []
    cursor = start
    delta = timedelta(days=max_chunk_days)
    while cursor < end:
        chunk_end = min(end, cursor + delta)
        chunks.append({"from": cursor.isoformat(), "to": chunk_end.isoformat()})
        cursor = chunk_end
    if not chunks:
        chunks.append({"from": start.isoformat(), "to": end.isoformat()})
    return chunks
