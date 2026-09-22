"""One-shot read-only portfolio close probe using Upstox authenticated market data."""
import json, os, subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date
from urllib.parse import quote

from experiments.upstox_catalog import PublicInstrumentCatalog

VALUES_21 = {
"ANANDRATHI":137094.39,"APOLLO":108311.44,"BEPL":231348.60,"CEIGALL":289901.84,"EBGNG":320368.79,
"GLS":112032.00,"INDGN":250299.00,"IOLCP":173082.23,"JYOTICNC":310764.15,"KISSHT":173637.50,
"KSHINTL":146565.29,"LLOYDSENGG":69708.19,"LTFOODS":119762.39,"OPTIEMUS":121694.50,"PINELABS":446284.79,
"RAYMOND":185526.45,"REDINGTON":149763.10,"RPEL":182757.60,"RUBICON":97025.60,"SANSERA":103128.00,
"SMLMAH":148672.00,"STAR":119804.69,"STLNETWORK":184778.82,"STRTECH":291286.70,"SWANDEF":73261.80,
"WINDLAS":177315.79,"WOCKPHARMA":188107.79,"MEESHO":272403.45,"SONACOMS":165412.00,"KANOHAR":154317.10,
"TDPOWERSYS":168142.50,"TVSMOTOR":37395.00,"VBL":124100.00
}
ALIASES={"GLS":"ALIVUS","STRTECH":"STLTECH"}

def resolve():
    rows=PublicInstrumentCatalog().nse_instruments()["records"]
    out={}
    for app_symbol in VALUES_21:
        symbol=ALIASES.get(app_symbol,app_symbol)
        matches=[r for r in rows if isinstance(r,dict) and r.get("exchange")=="NSE" and r.get("segment")=="NSE_EQ"
                 and str(r.get("trading_symbol","")).upper()==symbol]
        if len(matches)!=1:
            raise RuntimeError(f"instrument resolution {app_symbol}->{symbol}: {len(matches)} matches")
        out[app_symbol]={"symbol":symbol,"instrument_key":matches[0]["instrument_key"],"name":matches[0].get("name")}
    return out

def candles(item):
    app_symbol,meta=item
    token=os.environ["UPSTOX_ANALYTICS_TOKEN"].strip()
    key=quote(meta["instrument_key"],safe="")
    url=f"https://api.upstox.com/v3/historical-candle/{key}/days/1/2026-09-22/2026-09-21"
    p=subprocess.run(["curl","--fail-with-body","--silent","--show-error",
        "-H","Accept: application/json","-H",f"Authorization: Bearer {token}",url],
        text=True,capture_output=True,timeout=25)
    if p.returncode:
        raise RuntimeError(f"{app_symbol}: curl failed")
    d=json.loads(p.stdout)
    rows=((d.get("data") or {}).get("candles") or [])
    bydate={str(r[0])[:10]:r for r in rows if isinstance(r,list) and len(r)>=5}
    if "2026-09-21" not in bydate or "2026-09-22" not in bydate:
        raise RuntimeError(f"{app_symbol}: required candles missing")
    return app_symbol,float(bydate["2026-09-21"][4]),float(bydate["2026-09-22"][4])

def main():
    instruments=resolve()
    prices={}
    with ThreadPoolExecutor(max_workers=6) as ex:
        futs=[ex.submit(candles,x) for x in instruments.items()]
        for f in as_completed(futs):
            s,c21,c22=f.result()
            prices[s]=(c21,c22)
    rows=[]
    total21=sum(VALUES_21.values())
    total22=0.0
    daypnl=0.0
    max_residual=0.0
    for s,v21 in VALUES_21.items():
        c21,c22=prices[s]
        qty=round(v21/c21)
        recon=qty*c21
        residual=v21-recon
        max_residual=max(max_residual,abs(residual))
        pnl=qty*(c22-c21)
        v22=qty*c22
        total22+=v22
        daypnl+=pnl
        rows.append({"app_symbol":s,"nse_symbol":instruments[s]["symbol"],"qty":qty,
                     "close_21":c21,"close_22":c22,"change_pct":(c22/c21-1)*100,
                     "value_21_screenshot":v21,"reconstructed_21":recon,"residual":residual,
                     "day_pnl":pnl,"value_22":v22})
    rows.sort(key=lambda x:x["app_symbol"])
    result={"source":"UPSTOX_AUTHENTICATED_HISTORICAL_DAILY","as_of":"2026-09-22",
            "visible_equity_value_21":total21,"visible_equity_value_22":total22,
            "visible_equity_day_pnl":daypnl,"visible_equity_day_return_pct":daypnl/total21*100,
            "max_quantity_reconstruction_residual":max_residual,"rows":rows}
    print("PORTFOLIO_CLOSE_RESULT="+json.dumps(result,separators=(",",":"),sort_keys=True))

if __name__=="__main__":
    main()
