"""After-hours production cache-first historical smoke.

Uses the exact production _historical_window CACHE_FIRST helper and canonical Neon.
The provider boundary raises on any historical call: success proves all five currently
required historical windows are satisfied by validated cache documents.
"""
from __future__ import annotations

import json, os
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from experiments.live_shadow_bundle import _historical_window
from experiments.production_cache_read import build_reader_from_database_url

IST=ZoneInfo("Asia/Kolkata")
OUT=Path(".production/cache_first_smoke/audit.json")

class NoHistoricalProvider:
    def __init__(self): self.calls=0
    def historical(self,*args,**kwargs):
        self.calls += 1
        raise RuntimeError("historical provider call not permitted in cache-first hit smoke")

def run():
    today=datetime.now(IST).date()
    end=today-timedelta(days=1)
    cfg={"5m":("minutes",5,4),"15m":("minutes",15,8),"30m":("minutes",30,15),"1h":("hours",1,30),"1d":("days",1,120)}
    reader=build_reader_from_database_url(os.environ["DATABASE_URL"].strip())
    provider=NoHistoricalProvider()
    series=[]
    for tf,(unit,interval,days) in cfg.items():
        start=today-timedelta(days=days)
        rows,_,audit=_historical_window(provider,reader,"CACHE_FIRST",tf,unit,interval,start,end)
        ok=audit["source"]=="CACHE" and audit["provider_calls_avoided"]==1 and audit["tail_calls_made"]==0 and bool(rows)
        series.append({"timeframe":tf,"status":"PASS" if ok else "FAIL","bar_count":len(rows),**audit})
    passed=all(x["status"]=="PASS" for x in series) and provider.calls==0
    result={
      "status":"PRODUCTION_CACHE_FIRST_SMOKE_PASS" if passed else "PRODUCTION_CACHE_FIRST_SMOKE_FAIL",
      "session_date_ist":today.isoformat(),"series":series,
      "provider_historical_calls_executed":provider.calls,
      "provider_historical_calls_avoided":sum(x["provider_calls_avoided"] for x in series),
      "tail_calls_made":sum(x["tail_calls_made"] for x in series),
      "forecast_released":False,"canonical_forecast_write_enabled":False,
      "trading_execution_enabled":False,"methodology_changed":False
    }
    OUT.parent.mkdir(parents=True,exist_ok=True)
    OUT.write_text(json.dumps(result,sort_keys=True,separators=(",",":"))+"\n")
    print(json.dumps(result,sort_keys=True,separators=(",",":")))
    if not passed: raise SystemExit(2)

if __name__=="__main__": run()
