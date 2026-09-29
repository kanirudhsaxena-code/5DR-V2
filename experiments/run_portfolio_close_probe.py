"""Authenticated portfolio close/current-day reconciliation using Upstox quotes + prior trading-day historical closes."""
import json, os, subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta
from urllib.parse import urlencode, quote
from experiments.upstox_catalog import PublicInstrumentCatalog
from experiments.run_live_full_portfolio import HOLDINGS, PMS_NET_INVESTED, PMS_RESIDUAL


def resolve():
    rows=PublicInstrumentCatalog().nse_instruments()["records"]
    out={}
    for app,h in HOLDINGS.items():
        m=[r for r in rows if isinstance(r,dict) and r.get("exchange")=="NSE" and r.get("segment")=="NSE_EQ" and str(r.get("trading_symbol","")).upper()==h["symbol"]]
        if len(m)!=1: raise RuntimeError(f"resolution {app}->{h['symbol']}: {len(m)}")
        out[app]={"symbol":h["symbol"],"instrument_key":m[0]["instrument_key"]}
    return out


def hist_latest_before(app, meta, token, to_date, from_date):
    key=quote(meta["instrument_key"],safe="")
    url=f"https://api.upstox.com/v3/historical-candle/{key}/days/1/{to_date}/{from_date}"
    p=subprocess.run(["curl","--fail-with-body","--silent","--show-error","-H","Accept: application/json","-H",f"Authorization: Bearer {token}",url],text=True,capture_output=True,timeout=25)
    if p.returncode: raise RuntimeError(f"{app}: historical request failed: {p.stderr[:200]}")
    candles=((json.loads(p.stdout).get("data") or {}).get("candles") or [])
    candidates=[]
    for c in candles:
        if not isinstance(c,list) or len(c)<5: continue
        ts=str(c[0]); d=datetime.fromisoformat(ts.replace("Z","+00:00")).date()
        if d.isoformat()<=to_date: candidates.append((d,float(c[4])))
    if not candidates: raise RuntimeError(f"{app}: no prior candle")
    d,close=max(candidates,key=lambda x:x[0])
    return app,d.isoformat(),close


def main():
    instruments=resolve(); token=os.environ["UPSTOX_ANALYTICS_TOKEN"].strip()
    query=urlencode({"instrument_key":",".join(m["instrument_key"] for m in instruments.values())})
    url="https://api.upstox.com/v3/market-quote/quotes?"+query
    p=subprocess.run(["curl","--fail-with-body","--silent","--show-error","-H","Accept: application/json","-H",f"Authorization: Bearer {token}",url],text=True,capture_output=True,timeout=25)
    if p.returncode: raise RuntimeError("batch quote failed")
    data=(json.loads(p.stdout).get("data") or {})
    bytoken={q.get("instrument_token"):q for q in data.values() if isinstance(q,dict) and isinstance(q.get("instrument_token"),str)}
    timestamps=[q.get("timestamp") for q in bytoken.values() if q.get("timestamp")]
    if not timestamps: raise RuntimeError("quote timestamps missing")
    quote_ts=max(timestamps)
    quote_date=datetime.fromisoformat(quote_ts.replace("Z","+00:00")).date()
    to_date=(quote_date-timedelta(days=1)).isoformat(); from_date=(quote_date-timedelta(days=10)).isoformat()
    prev={}
    with ThreadPoolExecutor(max_workers=8) as ex:
        futs=[ex.submit(hist_latest_before,a,m,token,to_date,from_date) for a,m in instruments.items()]
        for fut in as_completed(futs):
            a,d,c=fut.result(); prev[a]=(d,c)
    rows=[]; eq=0.0; prev_eq=0.0; cost=0.0
    for app,h in HOLDINGS.items():
        q=bytoken.get(instruments[app]["instrument_key"])
        if not q: raise RuntimeError(f"quote missing {app}")
        ltp=float(q["last_price"]); pd,pc=prev[app]; qty=h["qty"]
        value=qty*ltp; day=qty*(ltp-pc); tpnl=value-h["cost"]
        eq+=value; prev_eq+=qty*pc; cost+=h["cost"]
        ohlc=q.get("ohlc") if isinstance(q.get("ohlc"),dict) else {}
        rows.append({"app_symbol":app,"nse_symbol":h["symbol"],"qty":qty,"ltp":ltp,"prev_close_date":pd,"prev_close":pc,"day_change_pct":(ltp/pc-1)*100,"day_pnl":day,"position_value":value,"total_pnl":tpnl,"total_return_pct":tpnl/h["cost"]*100,"open":ohlc.get("open"),"high":ohlc.get("high"),"low":ohlc.get("low"),"volume":q.get("volume") or ohlc.get("volume")})
    day_pnl=eq-prev_eq; est=eq+PMS_RESIDUAL
    result={"source":"UPSTOX_AUTHENTICATED_V3_BATCH_QUOTE_PLUS_V3_HISTORICAL_PREV_TRADING_DAY","quote_timestamp":quote_ts,"quote_date":quote_date.isoformat(),"previous_close_dates":sorted(set(d for d,_ in prev.values())),"holdings":len(rows),"visible_equity_value":eq,"previous_visible_equity_value":prev_eq,"actual_day_pnl":day_pnl,"actual_day_return_pct":day_pnl/prev_eq*100,"breadth":{"up":sum(r["day_pnl"]>0 for r in rows),"down":sum(r["day_pnl"]<0 for r in rows),"flat":sum(r["day_pnl"]==0 for r in rows)},"visible_equity_cost":cost,"visible_equity_total_pnl":eq-cost,"estimated_pms_total_value_if_residual_unchanged":est,"simple_gain_vs_net_invested":est-PMS_NET_INVESTED,"simple_return_vs_net_invested_pct":(est/PMS_NET_INVESTED-1)*100,"rows":sorted(rows,key=lambda x:x["day_pnl"],reverse=True)}
    print("PORTFOLIO_CLOSE_RESULT="+json.dumps(result,separators=(",",":"),sort_keys=True))

if __name__=="__main__": main()
