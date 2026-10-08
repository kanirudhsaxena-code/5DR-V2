"""ASCENT N3 G1 follow-through: prove SAME-DAY NIFTY/option candles and quote time.
Uses the existing verified read-only broker object; does not alter production.
"""
import json
import math
import os
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import quote
from zoneinfo import ZoneInfo
from experiments.ascent_n3_g1_probe import (
    NIFTY, ProbeError, ReadOnlyBroker, finite, summarize_candles, validate_contracts)

IST=ZoneInfo("Asia/Kolkata")

def parsed_quote(data):
    if not isinstance(data,dict) or not data:
        raise ProbeError("FULL_QUOTE_EMPTY")
    matches=[x for x in data.values() if isinstance(x,dict) and (
        x.get("instrument_token")==NIFTY or x.get("instrument_key")==NIFTY)]
    if len(matches)!=1:
        raise ProbeError("FULL_QUOTE_NIFTY_IDENTITY")
    q=matches[0]
    if not finite(q.get("last_price")) or q["last_price"]<=0:
        raise ProbeError("FULL_QUOTE_PRICE_INVALID")
    if not isinstance(q.get("timestamp"),str):
        raise ProbeError("FULL_QUOTE_NO_PROVIDER_TIME")
    try:
        ts=datetime.fromisoformat(q["timestamp"])
    except ValueError as exc:
        raise ProbeError("FULL_QUOTE_TIME_INVALID") from exc
    if ts.tzinfo is None:
        raise ProbeError("FULL_QUOTE_TZ_ABSENT")
    return {"last_price":q["last_price"],"provider_timestamp":ts.isoformat(),
            "ohlc_ts": q.get("ohlc",{}).get("ts") if isinstance(q.get("ohlc"),dict) else None}

def choose_nearest_ce_pe(items,price,today):
    contracts=validate_contracts(items)
    valid=sorted({c["expiry"] for c in contracts if c["expiry"]>=str(today)})
    if not valid:
        raise ProbeError("NO_CURRENT_EXPIRY")
    exp=valid[0]
    pairs={}
    for side in ("CE","PE"):
        available=[c for c in contracts if c["expiry"]==exp and c["instrument_type"]==side]
        if not available:
            raise ProbeError("NO_"+side+"_FOR_CURRENT_EXPIRY")
        pairs[side]=min(available,key=lambda x:(abs(x["strike_price"]-price),x["instrument_key"]))
    return pairs

def run():
    today=datetime.now(IST).date()
    result={"schema":"ascent-n3-g1-current-day-proof-v1",
            "run_id":os.getenv("GITHUB_RUN_ID","LOCAL"),
            "as_of_ist":str(today),"read_only":True,"trading_enabled":False,
            "stages":{},"receipts":[],"source_probe_pass":False,
            "consumer_ack":"UNTESTED",
            "note":"Full provider timestamp is NOT equivalent to current live execution eligibility."}
    broker=None
    def stage(key,action):
        try:
            value=action()
            result["stages"][key]={"status":"PASS",**value}
            return value
        except ProbeError as exc:
            result["stages"][key]={"status":"FAIL","code":str(exc)}
        except Exception:
            result["stages"][key]={"status":"FAIL","code":"UNEXPECTED_SCHEMA"}
        return None
    try:
        broker=ReadOnlyBroker(os.getenv("UPSTOX_ANALYTICS_TOKEN",""))
        full=stage("full_nifty_quote",lambda:parsed_quote(broker.get(
            "full_nifty_quote","/v3/market-quote/quotes",{"instrument_key":NIFTY})))
        path=f"/v3/historical-candle/intraday/{quote(NIFTY,safe='')}/minutes/1"
        def current_index():
            d=broker.get("nifty_today_1m",path)
            if not isinstance(d,dict):raise ProbeError("TODAY_INDEX_SCHEMA")
            return summarize_candles(d.get("candles"),today,today)
        stage("nifty_today_1m",current_index)
        start=today-timedelta(days=10)
        def daily_index():
            path=f"/v3/historical-candle/{quote(NIFTY,safe='')}/days/1/{today}/{start}"
            d=broker.get("nifty_daily",path)
            if not isinstance(d,dict):raise ProbeError("DAILY_SCHEMA")
            return summarize_candles(d.get("candles"),start,today)
        stage("nifty_daily",daily_index)
        if full:
            def current_options():
                cs=broker.get("current_option_contracts","/v2/option/contract",{"instrument_key":NIFTY})
                pair=choose_nearest_ce_pe(cs,full["last_price"],today)
                values={}
                for side,contract in pair.items():
                    path=f"/v3/historical-candle/intraday/{quote(contract['instrument_key'],safe='')}/minutes/1"
                    data=broker.get(side+"_today_1m",path)
                    if not isinstance(data,dict):raise ProbeError("TODAY_OPTION_SCHEMA")
                    values[side]=summarize_candles(data.get("candles"),today,today,require_volume=True)
                    values[side]["expiry"]=contract["expiry"]
                    values[side]["strike"]=contract["strike_price"]
                    values[side]["lot"]=contract["lot_size"]
                return values
            stage("current_ce_pe_today_1m",current_options)
        else:
            result["stages"]["current_ce_pe_today_1m"]={"status":"NOT_RUN","code":"QUOTE_UNVERIFIED"}
    except ProbeError as exc:
        result["stages"]["authentication"]={"status":"FAIL","code":str(exc)}
    result["receipts"]=broker.receipts if broker else []
    result["source_probe_pass"]=all(result["stages"].get(k,{}).get("status")=="PASS" for k in
        ("full_nifty_quote","nifty_today_1m","nifty_daily","current_ce_pe_today_1m"))
    path=Path(".g1/freshness.json")
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(result,sort_keys=True,indent=2),encoding="utf-8")
    print("G1_FRESHNESS_PROBE="+("PASS" if result["source_probe_pass"] else "BLOCKED"))
    for key,value in result["stages"].items():
        print("G1_FRESHNESS="+key+":"+value["status"]+":"+value.get("code",""))
    return 0 if result["source_probe_pass"] else 1

if __name__=="__main__":
    raise SystemExit(run())
