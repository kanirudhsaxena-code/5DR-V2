"""ASCENT N3 G1 option-chain/depth and historical expired reach probe.
Only read-only GET with existing analytics token; no orders or production writes.
"""
import json
import os
from datetime import datetime, date
from pathlib import Path
from urllib.parse import quote
from zoneinfo import ZoneInfo
from experiments.ascent_n3_g1_probe import (
    ReadOnlyBroker, NIFTY, ProbeError, finite, summarize_candles, validate_contracts, expired_dates)
from experiments.ascent_n3_g1_freshness import parsed_quote, choose_nearest_ce_pe

IST=ZoneInfo("Asia/Kolkata")

def chain_fields(data, strike):
    if not isinstance(data,list) or not data:
        raise ProbeError("CHAIN_EMPTY")
    ranked=[x for x in data if isinstance(x,dict) and finite(x.get("strike_price"))]
    if not ranked:
        raise ProbeError("CHAIN_STRIKES_MISSING")
    item=min(ranked,key=lambda x:abs(x["strike_price"]-strike))
    out={"strike":item["strike_price"]}
    for key in ("call_options","put_options"):
        opt=item.get(key)
        if not isinstance(opt,dict):
            raise ProbeError("CHAIN_OPTION_MISSING")
        md=opt.get("market_data")
        gr=opt.get("option_greeks")
        if not isinstance(md,dict) or not isinstance(gr,dict):
            raise ProbeError("CHAIN_DETAILS_MISSING")
        needed_market=("ltp","oi","bid_price","ask_price","volume")
        needed_greeks=("iv","delta","gamma","theta","vega")
        missing=[v for v in needed_market if not finite(md.get(v))]
        missing+=["greeks."+v for v in needed_greeks if not finite(gr.get(v))]
        if missing:
            raise ProbeError("CHAIN_NUMERIC_MISSING")
        if md["ask_price"]<md["bid_price"] or md["bid_price"]<0:
            raise ProbeError("CHAIN_NEGATIVE_SPREAD")
        out[key]={"instrument_key":opt.get("instrument_key"),"bid":md["bid_price"],
                  "ask":md["ask_price"],"spread":md["ask_price"]-md["bid_price"],
                  "oi":md["oi"],"iv":gr["iv"],"delta":gr["delta"],
                  "gamma":gr["gamma"],"theta":gr["theta"],"vega":gr["vega"]}
    return out

def older_expired_candles(b, expired, asof):
    dates=expired_dates(expired,asof)
    # Probe oldest and midpoint, not just the most recent expiry.
    candidates=[dates[0],dates[len(dates)//2]]
    out=[]
    for when in candidates:
        contracts=b.get("older_contract_"+str(when),
            "/v2/expired-instruments/option/contract",
            {"instrument_key":NIFTY,"expiry_date":str(when)})
        valid=validate_contracts(contracts,when)
        mid=sorted(c["strike_price"] for c in valid)[len(valid)//2]
        picked={}
        for side in ("CE","PE"):
            picked[side]=min((c for c in valid if c["instrument_type"]==side),
                key=lambda c:(abs(c["strike_price"]-mid),c["instrument_key"]))
        one={"expiry":str(when)}
        for side,c in picked.items():
            path=f"/v2/expired-instruments/historical-candle/{quote(c['instrument_key'],safe='')}/1minute/{when}/{when}"
            candles=b.get(f"older_{when}_{side}",path)
            if not isinstance(candles,dict):
                raise ProbeError("OLDER_CANDLE_BODY_INVALID")
            one[side]=summarize_candles(candles.get("candles"),when,when,True)
            one[side]["strike"]=c["strike_price"]
            one[side]["lot"]=c["lot_size"]
        out.append(one)
    return {"samples":out,"earliest_listed":str(dates[0]),
            "note":"2 expiry date samples only; no blanket full-history coverage guarantee"}

def probe_chain_and_quotes(b,asof):
    full=parsed_quote(b.get("full_spot_for_chain","/v3/market-quote/quotes",{"instrument_key":NIFTY}))
    cs=b.get("current_contracts_chain","/v2/option/contract",{"instrument_key":NIFTY})
    selected=choose_nearest_ce_pe(cs,full["last_price"],asof)
    expiry=selected["CE"]["expiry"]
    data=b.get("option_chain","/v2/option/chain",{"instrument_key":NIFTY,"expiry_date":expiry})
    result=chain_fields(data,selected["CE"]["strike_price"])
    result["expiry"]=expiry
    keys=",".join([selected[x]["instrument_key"] for x in ("CE","PE")])
    quotes=b.get("selected_option_full_quote","/v3/market-quote/quotes",{"instrument_key":keys})
    if not isinstance(quotes,dict) or len(quotes)<2:
        raise ProbeError("FULL_OPTION_QUOTE_MISSING")
    seen=[]
    for q in quotes.values():
        if isinstance(q,dict) and isinstance(q.get("timestamp"),str):
            ts=datetime.fromisoformat(q["timestamp"])
            if ts.tzinfo is not None:
                seen.append(ts)
    if len(seen)<2:
        raise ProbeError("FULL_OPTION_QUOTE_TIME_ABSENT")
    result["option_quote_times_ist"]=sorted(x.astimezone(IST).isoformat() for x in seen)
    greeks=b.get("option_greeks","/v3/market-quote/option-greek",{"instrument_key":keys})
    if not isinstance(greeks,dict) or len(greeks)<2:
        raise ProbeError("EXPLICIT_OPTION_GREEKS_MISSING")
    result["explicit_greeks_entries"]=len(greeks)
    result["chain_rows"]=len(data)
    result["warning"]="after-close quotes do not imply executable live spreads"
    return result

def main():
    now=datetime.now(IST).date()
    result={"schema":"ascent-n3-g1-depth-retention-v1",
            "run_id":os.getenv("GITHUB_RUN_ID","LOCAL"),"asof_ist":str(now),
            "read_only":True,"trading_enabled":False,
            "stages":{},"receipts":[],"all_tested_pass":False,
            "consumer_ack":"UNTESTED"}
    b=None
    def stage(name, fn):
        try:
            value=fn()
            result["stages"][name]={"status":"PASS",**value}
        except ProbeError as exc:
            result["stages"][name]={"status":"FAIL","code":str(exc)}
        except Exception:
            result["stages"][name]={"status":"FAIL","code":"VALIDATION_EXCEPTION"}
    try:
        b=ReadOnlyBroker(os.getenv("UPSTOX_ANALYTICS_TOKEN",""))
        stage("option_chain_bidask_greeks",lambda:probe_chain_and_quotes(b,now))
        def historic():
            values=b.get("expired_list_for_boundary","/v2/expired-instruments/expiries",{"instrument_key":NIFTY})
            return older_expired_candles(b,values,now)
        stage("older_expired_ce_pe_1m",historic)
    except ProbeError as exc:
        result["stages"]["authentication"]={"status":"FAIL","code":str(exc)}
    result["receipts"]=b.receipts if b else []
    result["all_tested_pass"]=all(result["stages"].get(k,{}).get("status")=="PASS" for k in
                              ("option_chain_bidask_greeks","older_expired_ce_pe_1m"))
    path=Path(".g1/depth-retention.json")
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(result,sort_keys=True,indent=2),encoding="utf-8")
    print("G1_DEPTH_RETENTION="+("PASS" if result["all_tested_pass"] else "CONSTRAINED"))
    for k,v in result["stages"].items():
        print("G1_DEPTH="+k+":"+v["status"]+":"+v.get("code",""))
    # This optional lane does not invalidate earlier source tests on coverage gaps.
    return 0

if __name__=="__main__":
    raise SystemExit(main())
