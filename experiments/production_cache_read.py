"""Guarded production historical-cache read adapter for 5DR V2.2.3.

Read-only execution layer only. It validates immutable cache documents via the existing
PostgresMarketCacheStore and never writes canonical/cache/lifecycle/trading state.
"""
from __future__ import annotations

from contextlib import closing
from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo

from experiments.data_contract import DataArchitectureError
from experiments.postgres_cache_store import PostgresMarketCacheStore

IST = ZoneInfo("Asia/Kolkata")

NIFTY_SERIES = {
    "5m": "5DR:NIFTY_PRICE_CANDLES:NIFTY_50:5m",
    "15m": "5DR:NIFTY_PRICE_CANDLES:NIFTY_50:15m",
    "30m": "5DR:NIFTY_PRICE_CANDLES:NIFTY_50:30m",
    "1h": "5DR:NIFTY_PRICE_CANDLES:NIFTY_50:1h",
    "1d": "5DR:NIFTY_PRICE_CANDLES:NIFTY_50:1d",
}


def _stamp(value):
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str):
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    else:
        raise DataArchitectureError("cache historical timestamp invalid")
    if parsed.tzinfo is None:
        raise DataArchitectureError("cache historical timestamp naive")
    return parsed.astimezone(timezone.utc)


def _session_date(value):
    return _stamp(value).astimezone(IST).date()


class PsycopgReadOnlyBoundary:
    """Small DB-API boundary satisfying PostgresMarketCacheStore reads only."""

    def __init__(self, dsn, connect):
        if not isinstance(dsn, str) or not dsn.strip():
            raise DataArchitectureError("DATABASE_URL missing for production cache")
        if not callable(connect):
            raise DataArchitectureError("postgres connect factory missing")
        self._dsn = dsn.strip()
        self._connect = connect

    def fetch_one(self, sql, params=()):
        with closing(self._connect(self._dsn)) as conn:
            with conn.cursor() as cur:
                cur.execute(sql, params)
                return cur.fetchone()

    def fetch_all(self, sql, params=()):
        with closing(self._connect(self._dsn)) as conn:
            with conn.cursor() as cur:
                cur.execute(sql, params)
                return list(cur.fetchall())

    def execute(self, sql, params=()):
        raise DataArchitectureError("production cache boundary is read-only")


class ProductionHistoricalCacheReader:
    def __init__(self, store):
        if not isinstance(store, PostgresMarketCacheStore):
            raise DataArchitectureError("production cache store invalid")
        if not store.production_approved:
            raise DataArchitectureError("production cache store not approved")
        self.store = store

    def read_nifty_window(self, timeframe, start, end):
        if timeframe not in NIFTY_SERIES:
            raise DataArchitectureError("production cache timeframe unsupported")
        if not isinstance(start, date) or not isinstance(end, date) or start > end:
            raise DataArchitectureError("production cache window invalid")
        sid = NIFTY_SERIES[timeframe]
        document = self.store.read_document(sid)
        if document is None:
            return {
                "series_id": sid, "status": "MISS", "rows": [],
                "document_sha256": None, "dataset_sha256": None,
                "latest_cached_timestamp": None, "earliest_session_date": None,
                "latest_session_date": None, "covers_required_window": False,
            }
        records = document["records"]
        if not records:
            raise DataArchitectureError("production cache document empty")
        earliest = min(_session_date(row["timestamp"]) for row in records)
        latest = max(_session_date(row["timestamp"]) for row in records)
        rows = [
            list(row["candle"])
            for row in records
            if start <= _session_date(row["timestamp"]) <= end
        ]
        return {
            "series_id": sid,
            "status": "HIT" if earliest <= start and latest >= end else "PARTIAL",
            "rows": rows,
            "document_sha256": document["document_sha256"],
            "dataset_sha256": document["dataset_sha256"],
            "latest_cached_timestamp": document["latest_timestamp"],
            "earliest_session_date": earliest.isoformat(),
            "latest_session_date": latest.isoformat(),
            "covers_required_window": earliest <= start and latest >= end,
            "audit_event_count": len(document["audit_events"]),
        }


def build_reader_from_database_url(database_url):
    try:
        import psycopg
    except ImportError as error:
        raise DataArchitectureError("psycopg unavailable for production cache") from error
    boundary = PsycopgReadOnlyBoundary(database_url, psycopg.connect)
    store = PostgresMarketCacheStore(boundary, production_approved=True)
    return ProductionHistoricalCacheReader(store)
