"""Historical-only production cache shadow validation.

Runs outside the live evidence window without weakening any live freshness rule.
It compares the five production NIFTY historical windows from canonical Neon against
authenticated Upstox historical candles using the same normalization as production.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from experiments.live_shadow_bundle import _merge_candles, _series_digest
from experiments.production_cache_read import build_reader_from_database_url
from experiments.upstox_quant_client import QuantReadOnlyClient
from experiments.upstox_transport import CurlOpener
from phase1.upstox import NIFTY

IST = ZoneInfo("Asia/Kolkata")
OUT = Path(".production/cache_shadow/audit.json")


def run():
    token=os.environ["UPSTOX_ANALYTICS_TOKEN"].strip()
    database_url=os.environ["DATABASE_URL"].strip()
    today=datetime.now(IST).date()
    end=today-timedelta(days=1)
    history_cfg={
        "5m":("minutes",5,4),
        "15m":("minutes",15,8),
        "30m":("minutes",30,15),
        "1h":("hours",1,30),
        "1d":("days",1,120),
    }
    reader=build_reader_from_database_url(database_url)
    client=QuantReadOnlyClient(token,{NIFTY},opener=CurlOpener())
    rows=[]
    for timeframe,(unit,interval,lookback_days) in history_cfg.items():
        start=today-timedelta(days=lookback_days)
        cached=reader.read_nifty_window(timeframe,start,end)
        direct=client.historical(NIFTY,unit,interval,start,end)
        direct_rows=_merge_candles(direct["payload"]["data"]["candles"])
        cache_rows=_merge_candles(cached["rows"])
        direct_fp=_series_digest(direct_rows)
        cache_fp=_series_digest(cache_rows)
        exact=bool(cached["covers_required_window"] and direct_fp==cache_fp)
        rows.append({
            "timeframe":timeframe,
            "status":"PASS" if exact else "FAIL",
            "exact_match":exact,
            "direct_bar_count":len(direct_rows),
            "cache_bar_count":len(cache_rows),
            "direct_series_sha256":direct_fp,
            "cache_series_sha256":cache_fp,
            "cache_document_sha256":cached["document_sha256"],
            "dataset_sha256":cached["dataset_sha256"],
            "latest_cached_timestamp":cached["latest_cached_timestamp"],
        })
    passed=all(row["exact_match"] for row in rows)
    audit={
        "status":"PRODUCTION_CACHE_HISTORICAL_SHADOW_PASS" if passed else "PRODUCTION_CACHE_HISTORICAL_SHADOW_FAIL",
        "session_date_ist":today.isoformat(),
        "series":rows,
        "series_count":len(rows),
        "exact_match_count":sum(1 for row in rows if row["exact_match"]),
        "forecast_released":False,
        "canonical_forecast_write_enabled":False,
        "trading_execution_enabled":False,
        "methodology_changed":False,
    }
    OUT.parent.mkdir(parents=True,exist_ok=True)
    OUT.write_text(json.dumps(audit,sort_keys=True,separators=(",",":"))+"\n",encoding="utf-8")
    print(json.dumps(audit,sort_keys=True,separators=(",",":")))
    if not passed:
        raise SystemExit(2)
    return audit


if __name__=="__main__":
    run()
