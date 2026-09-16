"""Representative, bounded historical live proof for the experimental 5DR data backbone.

This intentionally performs only eight authenticated read-only GET requests. It does
not backfill the configured 6/12 month history, persist data, write to canonical 5DR,
or expose any trading/account surface.
"""
import json
import os
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from experiments.upstox_catalog import PublicInstrumentCatalog
from experiments.upstox_instruments import resolve_global_instruments
from experiments.upstox_quant_client import INDIA_VIX, QuantReadOnlyClient
from experiments.upstox_safe_diagnostics import diagnostic_code
from phase1.upstox import NIFTY, PipelineError

IST = ZoneInfo("Asia/Kolkata")
EXPECTED_REQUESTS = 8


def _history_proof(envelope, requested_start, requested_end):
    data = envelope.get("payload", {}).get("data", {})
    rows = data.get("candles") if isinstance(data, dict) else None
    if not isinstance(rows, list) or not rows:
        raise PipelineError("Historical probe candle array missing")
    stamps = []
    for row in rows:
        if not isinstance(row, list) or not row:
            raise PipelineError("Historical probe candle row invalid")
        stamp = datetime.fromisoformat(row[0])
        if stamp.tzinfo is None:
            raise PipelineError("Historical probe candle timestamp naive")
        if not (requested_start <= stamp.date() <= requested_end):
            raise PipelineError("Historical probe candle outside requested range")
        stamps.append(stamp)
    if len(stamps) != len(set(stamps)):
        raise PipelineError("Historical probe duplicate candle timestamp")
    return {
        "requested_start": requested_start.isoformat(),
        "requested_end": requested_end.isoformat(),
        "validated_candles": len(rows),
        "earliest_timestamp": min(stamps).isoformat(),
        "latest_timestamp": max(stamps).isoformat(),
        "source_path": envelope["source_path"],
        "sha256": envelope["sha256"],
        "received_at": envelope["received_at"],
    }


def run(token):
    if not isinstance(token, str) or not token.strip():
        raise PipelineError("UPSTOX_ANALYTICS_TOKEN is missing")

    # Use completed calendar days only. A seven-day intraday sample normally spans
    # several sessions; daily proof uses 45 calendar days. These are proof windows,
    # not the later production backfill horizon.
    end = datetime.now(IST).date() - timedelta(days=1)
    intraday_start = end - timedelta(days=6)
    daily_start = end - timedelta(days=44)

    catalog = PublicInstrumentCatalog()
    global_master = catalog.global_instruments()
    globals_by_id = resolve_global_instruments(global_master["records"], ("sp500", "brent"))

    approved = {
        NIFTY,
        INDIA_VIX,
        globals_by_id["sp500"]["instrument_key"],
        globals_by_id["brent"]["instrument_key"],
    }
    client = QuantReadOnlyClient(token, approved)

    requests = [
        ("nifty_5m", NIFTY, "minutes", 5, intraday_start, end),
        ("nifty_15m", NIFTY, "minutes", 15, intraday_start, end),
        ("nifty_30m", NIFTY, "minutes", 30, intraday_start, end),
        ("nifty_1h", NIFTY, "hours", 1, intraday_start, end),
        ("nifty_1d", NIFTY, "days", 1, daily_start, end),
        ("india_vix_1d", INDIA_VIX, "days", 1, daily_start, end),
        ("sp500_1d", globals_by_id["sp500"]["instrument_key"], "days", 1, daily_start, end),
        ("brent_1d", globals_by_id["brent"]["instrument_key"], "days", 1, daily_start, end),
    ]
    if len(requests) != EXPECTED_REQUESTS:
        raise PipelineError("Historical probe request budget mismatch")

    history = {}
    for label, instrument_key, unit, interval, start, request_end in requests:
        envelope = client.historical(instrument_key, unit, interval, start, request_end)
        history[label] = {
            "instrument_key": instrument_key,
            "unit": unit,
            "interval": interval,
            **_history_proof(envelope, start, request_end),
        }

    return {
        "status": "5DR_REPRESENTATIVE_HISTORY_PROBE_PASSED",
        "source_semantic": "UPSTOX_AUTHENTICATED",
        "consumer_scope": "5DR_EXPERIMENT_ONLY",
        "requests_made": len(requests),
        "request_budget": EXPECTED_REQUESTS,
        "full_backfill_started": False,
        "cache_storage_write_enabled": False,
        "production_5dr_write_enabled": False,
        "canonical_integration_enabled": False,
        "trading_enabled": False,
        "read_only": True,
        "catalog_provenance": {
            "global": {
                "sha256": global_master["sha256"],
                "received_at": global_master["received_at"],
            }
        },
        "history": history,
    }


def main():
    try:
        result = run(os.environ.get("UPSTOX_ANALYTICS_TOKEN", ""))
        print(json.dumps(result, sort_keys=True, separators=(",", ":")))
        return 0
    except Exception as error:
        print(json.dumps({
            "status": "BLOCKED",
            "diagnostic_code": diagnostic_code(error),
            "read_only": True,
            "trading_enabled": False,
            "production_5dr_write_enabled": False,
            "canonical_integration_enabled": False,
            "full_backfill_started": False,
        }, sort_keys=True, separators=(",", ":")))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
