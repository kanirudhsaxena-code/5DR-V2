import json, os, subprocess
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import quote, urlencode
from experiments.upstox_catalog import PublicInstrumentCatalog

BASE_TOTAL=5669411.87
NET_INVESTED=5050384.22
BASE={
"MIDCPNIFTY":[41544.00,51962.92],"BSE":[292740.00,286876.23],"HCLTECH":[291304.00,289991.95],"ICICIBANK":[172200.00,173865.10],"PNB":[167832.45,172245.89],"VBL":[228138.00,238134.61],
"AUROPHARMA":[174348.79,170579.36],"BOSCHLTD":[95250.00,91909.36],"INDHOTEL":[223845.60,223121.73],"IPCALAB":[173745.00,174550.39],"LTTS":[110378.69,109074.94],"MEESHO":[263383.03,240933.94],"SONACOMS":[182925.60,169840.60],
"JAYNECOIND":[159865.07,178604.29],"JSWCEMENT":[160676.10,165437.85],"KROSS":[173283.60,173257.67],"LLOYDSENGG":[415328.09,451287.08],"NEWGEN":[170834.00,178796.04],"OMNI":[99975.75,99754.64],"PINELABS":[178860.00,176947.35],"SOUTHBANK":[182388.32,175532.23],"STLTECH":[452891.00,356332.54],"TATAELXSI":[285380.00,262765.03],
"ACUTAAS":[178080.00,166839.60],"CAPILLARY":[156317.60,169709.14],"EBGNG":[517123.75,481334.26]
}
RESIDUAL=BASE_TOTAL-sum(v[0] for v in BASE.values())

def main():
    token=os.environ["UPSTOX_ANALYTICS_TOKEN"].strip()
    rows=PublicInstrumentCatalog().nse_instruments()["records"]
    resolved={}
    for s in BASE:
        m=[r for r in rows if isinstance(r,dict) and r.get("exchange")=="NSE" and str(r.get("trading_symbol","")).upper()==s and r.get("segment")=="NSE_EQ"]
        if not m:
            m=[r for r in rows if isinstance(r,dict) and r.get("exchange")=="NSE" and str(r.get("trading_symbol","")).upper()==s]
        if len(m)!=1: raise RuntimeError(f"resolution {s}: {len(m)}")
        resolved[s]=m[0]["instrument_key"]
    q=urlencode({"instrument_key":",".join(resolved.values())})
    p=subprocess.run(["curl","--fail-with-body","--silent","--show-error","-H","Accept: application/json","-H",f"Authorization: Bearer {token}","https://api.upstox.com/v3/market-quote/quotes?"+q],text=True,capture_output=True,timeout=30)
    if p.returncode: raise RuntimeError(p.stderr[:300])
    data=(json.loads(p.stdout).get("data") or {})
    bytoken={x.get("instrument_token"):x for x in data.values() if isinstance(x,dict)}
    def prev(item):
        s,key=item
        k=quote(key,safe="")
        url=f"https://api.upstox.com/v3/historical-candle/{k}/days/1/2026-10-28/2026-10-28"
        r=subprocess.run(["curl","--fail-with-body","--silent","--show-error","-H","Accept: application/json","-H",f"Authorization: Bearer {token}",url],text=True,capture_output=True,timeout=25)
        if r.returncode: raise RuntimeError(f"{s}: {r.stderr[:200]}")
        cs=((json.loads(r.stdout).get("data") or {}).get("candles") or [])
        if not cs: raise RuntimeError(f"{s}: no 28-Oct candle")
        return s,float(cs[0][4])
    with ThreadPoolExecutor(max_workers=8) as ex:
        prevs=dict(ex.map(prev,resolved.items()))
    out=[]; eq=0.0; dpnl=0.0; up=down=flat=0; timestamps=[]
    for s,(basev,cost) in BASE.items():
        qt=bytoken.get(resolved[s]); ltp=float(qt["last_price"]); pc=prevs[s]
        cur=basev*(ltp/pc); ch=cur-basev; eq+=cur; dpnl+=ch
        if ltp>pc: up+=1
        elif ltp<pc: down+=1
        else: flat+=1
        if qt.get("timestamp"): timestamps.append(qt["timestamp"])
        out.append({"symbol":s,"ltp":ltp,"prev_close":pc,"day_change_pct":(ltp/pc-1)*100,"day_pnl":ch,"position_value":cur,"cost":cost,"total_pnl":cur-cost,"total_return_pct":(cur/cost-1)*100})
    total=eq+RESIDUAL
    print("PMS26_LIVE="+json.dumps({"quote_timestamp":max(timestamps) if timestamps else None,"baseline_total":BASE_TOTAL,"residual":RESIDUAL,"equity_value":eq,"current_total":total,"day_pnl":total-BASE_TOTAL,"day_return_pct":(total/BASE_TOTAL-1)*100,"breadth":{"up":up,"down":down,"flat":flat},"gain_vs_net_invested":total-NET_INVESTED,"return_vs_net_invested_pct":(total/NET_INVESTED-1)*100,"rows":sorted(out,key=lambda x:x["day_pnl"],reverse=True)},separators=(",",":"),sort_keys=True))
if __name__=="__main__": main()
