import json, os, subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta
from urllib.parse import urlencode, quote
from experiments.upstox_catalog import PublicInstrumentCatalog

SNAP = {
"MIDCPNIFTY":40668.00,"TDPOWERSYS":165825.00,"TEMPSENS":213345.29,"BOSCHLTD":90390.00,
"MEESHO":265406.03,"SONACOMS":165152.00,"BSE":173472.00,"HCLTECH":179387.00,"VBL":237190.20,
"NETWEB":159796.60,"NEWGEN":178704.29,"ONWARDTEC":129658.10,"REDINGTON":225598.39,"ROLEXRINGS":158249.92,
"SOUTHBANK":181119.88,"STLTECH":456933.75,"SWANDEF":79126.19,"SYNCOMF":144860.05,"TATAELXSI":261510.00,
"EBGNG":593069.40,"INOXGREEN":113053.58,"JAYNECOIND":175188.23,"JINDALSAW":83359.19,"KISSHT":164153.29,
"KSB":136636.89,"LLOYDSENGG":467306.04
}
PMS_TOTAL_BASE=5813799.58
NET_INVESTED=5050384.22
RESIDUAL=PMS_TOTAL_BASE-sum(SNAP.values())

def curl_json(url, token):
    p=subprocess.run(["curl","--fail-with-body","--silent","--show-error","-H","Accept: application/json","-H",f"Authorization: Bearer {token}",url],text=True,capture_output=True,timeout=30)
    if p.returncode: raise RuntimeError(p.stderr[:300])
    return json.loads(p.stdout)

def hist_close(app,key,token):
    k=quote(key,safe="")
    url=f"https://api.upstox.com/v3/historical-candle/{k}/days/1/2026-10-20/2026-10-10"
    data=curl_json(url,token)
    candles=((data.get("data") or {}).get("candles") or [])
    cand=[]
    for c in candles:
        if isinstance(c,list) and len(c)>=5:
            d=datetime.fromisoformat(str(c[0]).replace("Z","+00:00")).date()
            if d.isoformat()<="2026-10-20":
                cand.append((d,float(c[4])))
    if not cand: raise RuntimeError(f"no hist {app}")
    return app,max(cand,key=lambda x:x[0])

def main():
    token=os.environ["UPSTOX_ANALYTICS_TOKEN"].strip()
    rows=PublicInstrumentCatalog().nse_instruments()["records"]
    resolved={}
    for s in SNAP:
        m=[r for r in rows if isinstance(r,dict) and r.get("exchange")=="NSE" and r.get("segment")=="NSE_EQ" and str(r.get("trading_symbol","")).upper()==s]
        if len(m)!=1: raise RuntimeError(f"resolve {s}: {len(m)}")
        resolved[s]=m[0]["instrument_key"]

    base={}
    with ThreadPoolExecutor(max_workers=8) as ex:
        futs=[ex.submit(hist_close,s,k,token) for s,k in resolved.items()]
        for fut in as_completed(futs):
            s,(d,c)=fut.result()
            qty=round(SNAP[s]/c)
            base[s]={"date":d.isoformat(),"close":c,"qty":qty,"base_value":SNAP[s]}

    q=urlencode({"instrument_key":",".join(resolved.values())})
    data=(curl_json("https://api.upstox.com/v3/market-quote/quotes?"+q,token).get("data") or {})
    bytoken={x.get("instrument_token"):x for x in data.values() if isinstance(x,dict)}
    rows_out=[]; cur_eq=0.0; base_eq=sum(SNAP.values())
    for s in SNAP:
        qd=bytoken.get(resolved[s])
        if not qd: raise RuntimeError(f"quote missing {s}")
        ltp=float(qd["last_price"]); b=base[s]
        move=ltp/b["close"]-1.0
        cur_value=b["base_value"]*(1.0+move)
        pnl=cur_value-b["base_value"]
        cur_eq+=cur_value
        rows_out.append({"symbol":s,"qty":b["qty"],"base_close_date":b["date"],"base_close":b["close"],"ltp":ltp,"move_pct":move*100,"base_value":b["base_value"],"current_value":cur_value,"pnl":pnl})
    total=cur_eq+RESIDUAL
    result={"source":"UPSTOX_AUTHENTICATED_RECONCILED_26","quote_timestamp":max(x.get("timestamp") for x in bytoken.values() if x.get("timestamp")),"holdings":26,"base_pms_value":PMS_TOTAL_BASE,"base_equity_value":base_eq,"residual_assumed_unchanged":RESIDUAL,"current_equity_value":cur_eq,"current_pms_value":total,"pms_change":total-PMS_TOTAL_BASE,"pms_change_pct":(total/PMS_TOTAL_BASE-1)*100,"breadth":{"up":sum(r["pnl"]>0 for r in rows_out),"down":sum(r["pnl"]<0 for r in rows_out),"flat":sum(r["pnl"]==0 for r in rows_out)},"simple_gain_vs_net_invested":total-NET_INVESTED,"simple_return_vs_net_invested_pct":(total/NET_INVESTED-1)*100,"rows":sorted(rows_out,key=lambda x:x["pnl"],reverse=True)}
    print("PMS26_LIVE_RESULT="+json.dumps(result,separators=(",",":"),sort_keys=True))
if __name__=="__main__": main()
