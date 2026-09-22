"""Fast one-shot read-only portfolio quote probe using one Upstox batch request."""
import json, os, subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urlencode, quote
from experiments.upstox_catalog import PublicInstrumentCatalog

VALUES_21={
"ANANDRATHI":137094.39,"APOLLO":108311.44,"BEPL":231348.60,"CEIGALL":289901.84,"EBGNG":320368.79,
"GLS":112032.00,"INDGN":250299.00,"IOLCP":173082.23,"JYOTICNC":310764.15,"KISSHT":173637.50,
"KSHINTL":146565.29,"LLOYDSENGG":69708.19,"LTFOODS":119762.39,"OPTIEMUS":121694.50,"PINELABS":446284.79,
"RAYMOND":185526.45,"REDINGTON":149763.10,"RPEL":182757.60,"RUBICON":97025.60,"SANSERA":103128.00,
"SMLMAH":148672.00,"STAR":119804.69,"STLNETWORK":184778.82,"STRTECH":291286.70,"SWANDEF":73261.80,
"WINDLAS":177315.79,"WOCKPHARMA":188107.79,"MEESHO":272403.45,"SONACOMS":165412.00,"KANOHAR":154317.10,
"TDPOWERSYS":168142.50,"TVSMOTOR":37395.00,"VBL":124100.00}
ALIASES={"GLS":"ALIVUS","STRTECH":"STLTECH"}

def resolve():
    rows=PublicInstrumentCatalog().nse_instruments()["records"]
    out={}
    for app_symbol in VALUES_21:
        symbol=ALIASES.get(app_symbol,app_symbol)
        m=[r for r in rows if isinstance(r,dict) and r.get("exchange")=="NSE" and r.get("segment")=="NSE_EQ"
           and str(r.get("trading_symbol","")).upper()==symbol]
        if len(m)!=1: raise RuntimeError(f"instrument resolution {app_symbol}->{symbol}: {len(m)}")
        out[app_symbol]={"symbol":symbol,"instrument_key":m[0]["instrument_key"],"name":m[0].get("name")}
    return out

def historical_21(app_symbol, meta, token):
    key=quote(meta["instrument_key"],safe="")
    url=f"https://api.upstox.com/v3/historical-candle/{key}/days/1/2026-09-21/2026-09-21"
    p=subprocess.run(["curl","--fail-with-body","--silent","--show-error",
                      "-H","Accept: application/json","-H",f"Authorization: Bearer {token}",url],
                      text=True,capture_output=True,timeout=25)
    if p.returncode: raise RuntimeError(f"{app_symbol}: historical close request failed")
    d=json.loads(p.stdout)
    rows=((d.get("data") or {}).get("candles") or [])
    if not rows or not isinstance(rows[0],list) or len(rows[0])<5:
        raise RuntimeError(f"{app_symbol}: 21-Sep candle missing")
    return app_symbol,float(rows[0][4])

def main():
    instruments=resolve()
    keys=[m["instrument_key"] for m in instruments.values()]
    token=os.environ["UPSTOX_ANALYTICS_TOKEN"].strip()

    query=urlencode({"instrument_key":",".join(keys)})
    url="https://api.upstox.com/v3/market-quote/quotes?"+query
    p=subprocess.run(["curl","--fail-with-body","--silent","--show-error","-H","Accept: application/json",
                      "-H",f"Authorization: Bearer {token}",url],text=True,capture_output=True,timeout=25)
    if p.returncode: raise RuntimeError("batch quote failed")
    payload=json.loads(p.stdout)
    data=payload.get("data") or {}
    bytoken={}
    for row in data.values():
        if isinstance(row,dict) and isinstance(row.get("instrument_token"),str):
            bytoken[row["instrument_token"]]=row

    close21={}
    with ThreadPoolExecutor(max_workers=8) as ex:
        futs=[ex.submit(historical_21,a,m,token) for a,m in instruments.items()]
        for fut in as_completed(futs):
            a,x=fut.result(); close21[a]=x

    rows=[]; totalpnl=0.0; maxres=0.0
    for app,v21 in VALUES_21.items():
        meta=instruments[app]; qrow=bytoken.get(meta["instrument_key"])
        if not qrow: raise RuntimeError(f"{app}: quote missing")
        ltp=qrow.get("last_price")
        if not isinstance(ltp,(int,float)): raise RuntimeError(f"{app}: last_price missing")
        c21=close21[app]
        qty=round(v21/c21)
        residual=v21-qty*c21
        maxres=max(maxres,abs(residual))
        pnl=qty*(float(ltp)-c21)
        totalpnl+=pnl
        rows.append({"app_symbol":app,"nse_symbol":meta["symbol"],"qty":qty,"close_21":c21,
                     "close_22":float(ltp),"change_pct":(float(ltp)/c21-1)*100,
                     "day_pnl":pnl,"reconstruction_residual":residual,
                     "quote_timestamp":qrow.get("timestamp"),"trade_timestamp":qrow.get("trade_timestamp")})
    result={"source":"UPSTOX_AUTHENTICATED: V3_BATCH_QUOTE_22SEP + V3_HISTORICAL_21SEP",
            "as_of":"2026-09-22","visible_equity_value_21":sum(VALUES_21.values()),
            "day_pnl":totalpnl,"day_return_pct":totalpnl/sum(VALUES_21.values())*100,
            "pms_value_21":6054896.38,
            "pms_value_22_if_non_equity_residual_unchanged":6054896.38+totalpnl,
            "max_quantity_reconstruction_residual":maxres,
            "rows":sorted(rows,key=lambda x:x["app_symbol"])}
    print("PORTFOLIO_CLOSE_RESULT="+json.dumps(result,separators=(",",":"),sort_keys=True))

if __name__=="__main__": main()
