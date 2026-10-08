"""ASCENT G1 source check: Upstox institutional flows, global macro proxies and market news.
Diagnostic only. Uses pre-existing Analytics Token, GET-only, no trading/portfolio/order
queries, no production writes. Never logs raw responses or access credentials.
"""
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo
from experiments.ascent_n3_g1_probe import ReadOnlyBroker, ProbeError, NIFTY
from experiments.upstox_catalog import PublicInstrumentCatalog
from experiments.upstox_instruments import resolve_global_instruments
from experiments.upstox_quant_client import QuantReadOnlyClient

IST=ZoneInfo("Asia/Kolkata")
TARGETS=("gift_nifty","sp500","dow_jones","nikkei_225","brent","wti","usd_inr")
EQUITY="NSE_EQ|INE002A01018"  # Reliance Industries (public equity instrument)

def latest_timestamp(rows):
    if not isinstance(rows,list) or not rows:
        raise ProbeError("NO_DATED_RECORDS")
    stamps=[v.get("time_stamp") for v in rows if isinstance(v,dict) and isinstance(v.get("time_stamp"),int)]
    if not stamps: raise ProbeError("NO_PUBLISHER_TIMESTAMPS")
    return datetime.fromtimestamp(max(stamps)/1000,tz=timezone.utc).astimezone(IST).isoformat()

def main():
    proof={"schema":"ascent-g1-upstox-macro-news-check-v1",
           "run_id":os.getenv("GITHUB_RUN_ID","LOCAL"),
           "read_only":True,"trading_enabled":False,"stages":{},
           "run_at_utc":datetime.now(timezone.utc).isoformat(),
           "disclosure":"Market proxy quotes are not GDP, CPI, RBI releases or unrestricted geopolitical news"}
    broker=None
    def stage(label,fn):
        try:
            proof["stages"][label]={"status":"PASS",**fn()}
        except ProbeError as e:
            proof["stages"][label]={"status":"CONSTRAINED","reason":str(e)}
        except Exception:
            proof["stages"][label]={"status":"CONSTRAINED","reason":"SOURCE_OR_VALIDATION_ERROR"}
    try:
        token=os.getenv("UPSTOX_ANALYTICS_TOKEN","")
        broker=ReadOnlyBroker(token)
        stage("fii_and_dii",lambda:institutional(token))
        stage("global_quotes_and_indicators",lambda:global_sources(token))
        stage("news_reliance_equity",lambda:news(broker,EQUITY))
        stage("news_nifty_index",lambda:news(broker,NIFTY))
        stage("fundamentals_company_profile",lambda:company(broker))
    except ProbeError as e:
        proof["stages"]["authentication"]={"status":"BLOCKED","reason":str(e)}
    proof["source_receipts"]=broker.receipts if broker else []
    dest=Path(".g1/upstox-macro-news.json")
    dest.parent.mkdir(parents=True,exist_ok=True)
    dest.write_text(json.dumps(proof,indent=2,sort_keys=True),encoding="utf-8")
    for lane,x in proof["stages"].items():
        print("G1_MACRO_NEWS="+lane+":"+x["status"]+":"+x.get("reason",""))
    return 0

def institutional(token):
    c=QuantReadOnlyClient(token,{NIFTY})
    f=c.institutional("fii",["NSE_EQ|CASH","NSE_FO|INDEX_FUTURES","NSE_FO|INDEX_OPTIONS"])
    d=c.institutional("dii","NSE_EQ|CASH")
    values={}
    for group,envelope in (("FII",f),("DII",d)):
        for segment,rows in envelope["payload"]["data"].items():
            values[group+":"+segment]={"rows":len(rows),
                                        "latest_record_ist":latest_timestamp(rows),
                                        "payload_sha256":envelope["sha256"]}
    return {"groups":values,"note":"Dates are exchange reporting dates, not live order-flow ticks"}

def global_sources(token):
    cat=PublicInstrumentCatalog().global_instruments()
    resolved=resolve_global_instruments(cat["records"],list(TARGETS))
    universe={x["instrument_key"] for x in resolved.values()}
    client=QuantReadOnlyClient(token,universe)
    outputs={}
    for name,row in resolved.items():
        key=row["instrument_key"]
        try:
            if row["segment"]=="GLOBAL_INDEX":
                data=client.full_quotes([key])
                sample=data["payload"]["data"]
                quote=next(iter(sample.values()))
                outputs[name]={"status":"PASS","source":"full_quotes","key":key,
                               "provider_time":quote.get("timestamp"),
                               "declared_latency_seconds":row["provider_latency"]["seconds"],
                               "payload_sha256":data["sha256"]}
            else:
                data=client.intraday(key,"minutes",1)
                rows=data["payload"]["data"]["candles"]
                outputs[name]={"status":"PASS","source":"intraday_1min","key":key,
                               "rows":len(rows),
                               "first_bar":rows[-1][0],"last_bar":rows[0][0],
                               "declared_latency_seconds":row["provider_latency"]["seconds"],
                               "payload_sha256":data["sha256"]}
        except Exception:
            outputs[name]={"status":"CONSTRAINED","reason":"SOURCE_RETRIEVAL_FAILED_OR_UNSUPPORTED","key":key}
    return {"catalog_sha256":cat["sha256"],"indicators":outputs,
            "note":"Provider-latency classification should be checked against observed timestamps"}

def news(broker,key):
    data=broker.get("news_public_instrument_"+key.split("|")[0],
       "/v2/news",{"category":"instrument_keys","instrument_keys":key,"page_size":20})
    if not isinstance(data,dict):raise ProbeError("NEWS_DATA_SCHEMA_INVALID")
    items=data.get(key,[])
    if not isinstance(items,list):raise ProbeError("NEWS_LIST_SCHEMA_INVALID")
    published=[p.get("published_time") for p in items
         if isinstance(p,dict) and isinstance(p.get("published_time"),int)]
    newest=datetime.fromtimestamp(max(published)/1000,tz=timezone.utc).astimezone(IST).isoformat() if published else None
    return {"instrument_key":key,"article_count":len(items),
            "newest_published_time_ist":newest,
            "scope":"instrument-specific, last 7 days",
            "note":"Successful zero articles does not imply global news availability"}

def company(broker):
    data=broker.get("reliance_company_public_profile","/v2/fundamentals/INE002A01018/profile")
    if not isinstance(data,dict) or not data:raise ProbeError("PROFILE_EMPTY")
    return {"public_company":"Reliance Industries","received":True,
            "available_fields":sorted(k for k in data.keys() if isinstance(k,str))}

if __name__=="__main__":
    raise SystemExit(main())
