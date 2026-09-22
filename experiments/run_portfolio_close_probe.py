"""Fast one-shot read-only portfolio quote probe using one Upstox batch request."""
import json, os, subprocess
from urllib.parse import urlencode
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

def nested(d,path):
    cur=d
    for k in path:
        if not isinstance(cur,dict): return None
        cur=cur.get(k)
    return cur if isinstance(cur,(int,float)) and not isinstance(cur,bool) else None

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
    rows=[]; totalpnl=0.0; maxres=0.0
    for app,v21 in VALUES_21.items():
        meta=instruments[app]; qrow=bytoken.get(meta["instrument_key"])
        if not qrow: raise RuntimeError(f"{app}: quote missing")
        ltp=qrow.get("last_price")
        if not isinstance(ltp,(int,float)): raise RuntimeError(f"{app}: last_price missing")
        candidates=[]
        for label,path in [
            ("prev_ohlc.close",("prev_ohlc","close")),
            ("ohlc.close",("ohlc","close")),
            ("previous_close",("previous_close",)),
            ("prev_close",("prev_close",)),
        ]:
            x=nested(qrow,path)
            if x and x>0:
                qty=round(v21/x); residual=abs(v21-qty*x)
                candidates.append((residual,label,float(x),int(qty)))
        if not candidates: raise RuntimeError(f"{app}: previous close unavailable; keys={sorted(qrow.keys())}")
        residual,label,c21,qty=min(candidates,key=lambda z:z[0])
        pnl=qty*(float(ltp)-c21)
        totalpnl+=pnl; maxres=max(maxres,residual)
        rows.append({"app_symbol":app,"nse_symbol":meta["symbol"],"qty":qty,"close_21":c21,
                     "price_22":float(ltp),"change_pct":(float(ltp)/c21-1)*100,
                     "day_pnl":pnl,"reconstruction_residual":v21-qty*c21,
                     "previous_close_field":label,"quote_timestamp":qrow.get("timestamp"),
                     "trade_timestamp":qrow.get("trade_timestamp")})
    result={"source":"UPSTOX_AUTHENTICATED_V3_BATCH_FULL_QUOTE","as_of":"2026-09-22",
            "visible_equity_value_21":sum(VALUES_21.values()),"day_pnl":totalpnl,
            "day_return_pct":totalpnl/sum(VALUES_21.values())*100,
            "pms_value_21":6054896.38,"estimated_pms_value_22_if_non_equity_residual_unchanged":6054896.38+totalpnl,
            "max_quantity_reconstruction_residual":maxres,"rows":sorted(rows,key=lambda x:x["app_symbol"])}
    print("PORTFOLIO_CLOSE_RESULT="+json.dumps(result,separators=(",",":"),sort_keys=True))

if __name__=="__main__": main()
