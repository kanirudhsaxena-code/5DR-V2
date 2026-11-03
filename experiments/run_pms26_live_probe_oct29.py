import json, os, subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from urllib.parse import urlencode, quote
from experiments.upstox_catalog import PublicInstrumentCatalog

SNAP={
"NIFTY":{"value":14108.25,"cost":38225.28},
"BSE":{"value":293160.00,"cost":286876.23},
"HCLTECH":{"value":298272.00,"cost":289991.95},
"ICICIBANK":{"value":173425.00,"cost":173865.10},
"PNB":{"value":171668.70,"cost":172245.89},
"VBL":{"value":223992.60,"cost":238134.61},
"AUROPHARMA":{"value":178482.79,"cost":170579.36},
"BOSCHLTD":{"value":96200.00,"cost":91909.36},
"INDHOTEL":{"value":228655.00,"cost":223121.73},
"IPCALAB":{"value":175491.00,"cost":174550.39},
"LTTS":{"value":114093.89,"cost":109074.94},
"MEESHO":{"value":256874.76,"cost":240933.94},
"SONACOMS":{"value":188437.60,"cost":169840.60},
"JAYNECOIND":{"value":160669.67,"cost":178604.29},
"JSWCEMENT":{"value":167344.20,"cost":165437.85},
"KROSS":{"value":157378.20,"cost":173257.67},
"LLOYDSENGG":{"value":420134.45,"cost":451287.08},
"NEWGEN":{"value":166469.89,"cost":178796.04},
"OMNI":{"value":96083.75,"cost":99754.64},
"PINELABS":{"value":173393.00,"cost":176947.35},
"SOUTHBANK":{"value":181954.38,"cost":175532.23},
"STLTECH":{"value":403399.50,"cost":356332.54},
"TATAELXSI":{"value":287568.79,"cost":262765.03},
"ACUTAAS":{"value":186844.79,"cost":166839.60},
"CAPILLARY":{"value":148680.79,"cost":169709.14},
"EBGNG":{"value":471614.00,"cost":481334.26}
}
PMS_BASE=5557654.29
NET_INVESTED=5050384.22
BASE_EQ=sum(v["value"] for v in SNAP.values())
RESIDUAL=PMS_BASE-BASE_EQ

def curl_json(url, token):
    p=subprocess.run(["curl","--fail-with-body","--silent","--show-error","-H","Accept: application/json","-H",f"Authorization: Bearer {token}",url],text=True,capture_output=True,timeout=30)
    if p.returncode: raise RuntimeError(p.stderr[:300])
    return json.loads(p.stdout)

def resolve(rows,s):
    aliases={"STLTECH":"STLTECH"}
    target=aliases.get(s,s)
    exact=[r for r in rows if isinstance(r,dict) and str(r.get("trading_symbol","")).upper()==target]
    if exact:
        eq=[r for r in exact if r.get("exchange")=="NSE" and r.get("segment")=="NSE_EQ"]
        return (eq[0] if eq else exact[0]), None
    fuzzy=[]
    for r in rows:
        if not isinstance(r,dict): continue
        ts=str(r.get("trading_symbol","")).upper()
        nm=str(r.get("name","")).upper()
        if target in ts or target in nm:
            fuzzy.append({"trading_symbol":ts,"name":nm,"segment":r.get("segment"),"exchange":r.get("exchange"),"instrument_key":r.get("instrument_key")})
    return None, fuzzy[:20]

def hist_close(key,token):
    k=quote(key,safe="")
    url=f"https://api.upstox.com/v3/historical-candle/{k}/days/1/2026-11-02/2026-11-02"
    data=curl_json(url,token)
    cs=((data.get("data") or {}).get("candles") or [])
    if not cs: raise RuntimeError("no 2-Nov candle")
    return float(cs[0][4])

def main():
    token=os.environ["UPSTOX_ANALYTICS_TOKEN"].strip()
    rows=PublicInstrumentCatalog().nse_instruments()["records"]
    resolved={}; unresolved={}
    for s in SNAP:
        r,f=resolve(rows,s)
        if r: resolved[s]=r["instrument_key"]
        else: unresolved[s]=f

    base={}
    with ThreadPoolExecutor(max_workers=8) as ex:
        futs={ex.submit(hist_close,key,token):s for s,key in resolved.items()}
        for fut in as_completed(futs):
            s=futs[fut]; close=fut.result(); qty=round(SNAP[s]["value"]/close)
            base[s]={"close":close,"qty":qty,"recon":qty*close,"diff":qty*close-SNAP[s]["value"]}

    q=urlencode({"instrument_key":",".join(resolved.values())})
    data=(curl_json("https://api.upstox.com/v3/market-quote/quotes?"+q,token).get("data") or {})
    bytoken={x.get("instrument_token"):x for x in data.values() if isinstance(x,dict)}
    out=[]; cur_eq=0.0
    for s,h in SNAP.items():
        if s in unresolved:
            out.append({"symbol":s,"status":"unresolved_held_at_base","base_value":h["value"],"current_value":h["value"],"pnl":0.0,"cost":h["cost"],"candidates":unresolved[s]})
            cur_eq+=h["value"]; continue
        qd=bytoken.get(resolved[s])
        if not qd: raise RuntimeError(f"quote missing {s}")
        ltp=float(qd["last_price"]); b=base[s]
        cur=b["qty"]*ltp; pnl=cur-h["value"]; cur_eq+=cur
        out.append({"symbol":s,"status":"live","qty":b["qty"],"base_close":b["close"],"base_recon":b["recon"],"base_diff":b["diff"],"ltp":ltp,"base_value":h["value"],"current_value":cur,"pnl":pnl,"move_pct":(cur/h["value"]-1)*100,"cost":h["cost"],"total_pl":cur-h["cost"],"total_return_pct":(cur/h["cost"]-1)*100})

    total=cur_eq+RESIDUAL
    live=[r for r in out if r["status"]=="live"]
    result={
      "source":"UPSTOX_AUTHENTICATED_RECONCILED_02NOV_26",
      "quote_timestamp":max(x.get("timestamp") for x in bytoken.values() if x.get("timestamp")),
      "holdings":26,
      "base_pms_value":PMS_BASE,
      "base_equity_value":BASE_EQ,
      "residual_assumed_unchanged":RESIDUAL,
      "current_equity_value":cur_eq,
      "current_pms_value":total,
      "pms_change":total-PMS_BASE,
      "pms_change_pct":(total/PMS_BASE-1)*100,
      "breadth":{"up":sum(r["pnl"]>0 for r in live),"down":sum(r["pnl"]<0 for r in live),"flat":sum(r["pnl"]==0 for r in live),"unresolved":len(unresolved)},
      "simple_gain_vs_net_invested":total-NET_INVESTED,
      "simple_return_vs_net_invested_pct":(total/NET_INVESTED-1)*100,
      "rows":sorted(out,key=lambda x:x["pnl"],reverse=True)
    }
    print("PMS_LIVE_03NOV_RESULT="+json.dumps(result,separators=(",",":"),sort_keys=True))
if __name__=="__main__": main()
