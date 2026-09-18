"""Live proof that Upstox historical candles can replace routine chart screenshots.

The probe fetches only NIFTY 5m/15m/30m/1h/1d candles, derives deterministic
multi-timeframe structure evidence, emits a sanitized summary, and performs no storage,
forecast, recommendation, lifecycle, or trading action.
"""
import json
import os
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from experiments.chart_structure import derive_multi_timeframe_evidence
from experiments.upstox_quant_client import QuantReadOnlyClient
from experiments.upstox_safe_diagnostics import diagnostic_code
from phase1.upstox import NIFTY, PipelineError

IST = ZoneInfo("Asia/Kolkata")
EXPECTED_REQUESTS = 5


def _rows(envelope):
    data = envelope.get("payload", {}).get("data", {})
    rows = data.get("candles") if isinstance(data, dict) else None
    if not isinstance(rows, list) or not rows:
        raise PipelineError("Chart probe candle array missing")
    return rows


def run(token):
    if not isinstance(token, str) or not token.strip():
        raise PipelineError("UPSTOX_ANALYTICS_TOKEN is missing")

    end = datetime.now(IST).date() - timedelta(days=1)
    intraday_start = end - timedelta(days=13)
    daily_start = end - timedelta(days=89)
    client = QuantReadOnlyClient(token, {NIFTY})

    requests = [
        ("5m", "minutes", 5, intraday_start, end),
        ("15m", "minutes", 15, intraday_start, end),
        ("30m", "minutes", 30, intraday_start, end),
        ("1h", "hours", 1, intraday_start, end),
        ("1d", "days", 1, daily_start, end),
    ]
    if len(requests) != EXPECTED_REQUESTS:
        raise PipelineError("Chart probe request budget mismatch")

    series = {}
    provenance = {}
    for timeframe, unit, interval, start, request_end in requests:
        envelope = client.historical(NIFTY, unit, interval, start, request_end)
        series[timeframe] = _rows(envelope)
        provenance[timeframe] = {
            "source_path": envelope["source_path"],
            "sha256": envelope["sha256"],
            "received_at": envelope["received_at"],
        }

    evidence = derive_multi_timeframe_evidence(
        series,
        swing_radius=2,
        breakout_lookback=20,
        min_gap_pct=0.0,
    )
    summaries = {}
    for timeframe, item in evidence["timeframes"].items():
        summaries[timeframe] = {
            "bar_count": item["bar_count"],
            "first_timestamp": item["first_timestamp"],
            "latest_timestamp": item["latest_timestamp"],
            "trend_structure": item["trend_structure"],
            "range_event": item["range_event"],
            "failed_breakout": item["failed_breakout"],
            "gap_count": len(item["recent_gaps"]),
            "volume_status": item["volume_confirmation"]["status"],
            "vwap_status": item["anchored_vwap_from_first_bar"]["status"],
            "execution_only": item["execution_only"],
            "source_sha256": provenance[timeframe]["sha256"],
        }

    required = {"1d", "1h", "30m", "15m", "5m"}
    if set(summaries) != required:
        raise PipelineError("Chart probe timeframe coverage mismatch")
    if not all(item["bar_count"] >= 5 for item in summaries.values()):
        raise PipelineError("Chart probe insufficient candle history")
    if evidence.get("directional_score_assigned") is not False:
        raise PipelineError("Chart probe crossed scoring boundary")

    return {
        "status": "5DR_LIVE_CHART_DERIVATION_PASSED",
        "source_semantic": "UPSTOX_AUTHENTICATED",
        "consumer_scope": "5DR_EXPERIMENT_ONLY",
        "requests_made": len(requests),
        "request_budget": EXPECTED_REQUESTS,
        "timeframes": summaries,
        "directional_alignment_excluding_5m": evidence["directional_alignment_excluding_5m"],
        "five_minute_execution_only": evidence["five_minute_execution_only"],
        "screenshot_required": False,
        "directional_score_assigned": False,
        "forecast_released": False,
        "cache_storage_write_enabled": False,
        "production_5dr_write_enabled": False,
        "canonical_integration_enabled": False,
        "trading_enabled": False,
        "read_only": True,
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
            "cache_storage_write_enabled": False,
            "forecast_released": False,
        }, sort_keys=True, separators=(",", ":")))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
