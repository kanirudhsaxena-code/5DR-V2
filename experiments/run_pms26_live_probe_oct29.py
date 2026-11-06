import json, os, subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urlencode, quote
from experiments.upstox_catalog import PublicInstrumentCatalog

H={
"BSE":{"qty":84,"cost":286876.23},
"HCLTECH":{"qty":208,"cost":289991.95},
"ICICIBANK":{"qty":125,"cost":173865.10},
"PNB":{"qty":1395,"cost":172245.89},
"VBL":{"qty":564,"cost":238134.61},
"AUROPHARMA":{"qty":106,"cost":170579.36},
"BOSCHLTD":{"qty":2,"cost":91909.36},
"HINDCOPPER":{"qty":82,"cost":34562.05},
"INDHOTEL":{"qty":278,"cost":223121.73},
"IPCALAB":{"qty":90,"cost":174550.39},
"LTTS":{"qty":27,"cost":109074.94},
"MEESHO":{"qty":1156,"cost":240933.94},
"SONACOMS":{"qty":208,"cost":169840.60},
"JAYNECOIND":{"qty":1788,"cost":178604.29},
"JSWCEMENT":{"qty":1395,"cost":165437.85},
"KROSS":{"qty":588,"cost":173257.67},
"LLOYDSENGG":{"qty":4955,"cost":451287.08},
"NEWGEN":{"qty":373,"cost":178796.04},
"OMNI":{"qty":139,"cost":99754.64},
"PINELABS":{"qty":1100,"cost":176947.35},
"SOUTHBANK":{"qty":3338,"cost":175532.23},
"STLTECH":{"qty":515,"cost":356332.54},
"TATAELXSI":{"qty":76,"cost":262765.03},
"ACUTAAS":{"qty":48,"cost":166839.60},
"CAPILLARY":{"qty":296,"cost":169709.14},
"EBGNG":{"qty":715,"cost":481334.26}
}
PMS_BASE=5730820.16
NET_INVESTED=5050384.22

def curl_json(url,token):
    p=subprocess.run(["curl","--fail-with-body","--silent","--show-error","-H","Accept: application/json","-H",f"Authorization: Bearer {token}",url],capture_output=True,text=True,timeout=30)
    if p.returncode: raise RuntimeError(p.stderr[:300])
    return json.loads(p.stdout)

def resolve(rows,s):
    m=[r for r in rows if isinstance(r,dict) and str(r.get("trading_symbol","")).upper()==s]
    if not m: raise RuntimeError(f"resolve {s}:0")
    eq=[r for r in m if r.get("exchange")=="NSE" and r.get("segment")=="NSE_EQ"]
    return (eq[0] if eq else m[0])["instrument_key"]

def prev_close(key,token):
    k=quote(key,safe="")
    u=f"https://api.upstox.com/v3/historical-candle/{k}/days/1/2026-11-05/2026-11-05"
    d=curl_json(u,token)
    cs=((d.get("data") or {}).get("candles") or [])
    if not cs: raise RuntimeError("no 5-Nov candle")
    return float(cs[0][4])

def main():
    token=os.environ["UPSTOX_ANALYTICS_TOKEN"].strip()
    rows=PublicInstrumentCatalog().nse_instruments()["records"]
    resolved={s:resolve(rows,s) for s in H}
    closes={}
    with ThreadPoolExecutor(max_workers=8) as ex:
        futs={ex.submit(prev_close,k,token):s for s,k in resolved.items()}
        for fut in as_completed(futs): closes[futs[fut]]=fut.result()
    base_eq=sum(H[s]["qty"]*closes[s] for s in H)
    residual=PMS_BASE-base_eq
    q=urlencode({"instrument_key":",".join(resolved.values())})
    data=(curl_json("https://api.upstox.com/v3/market-quote/quotes?"+q,token).get("data") or {})
    bytoken={x.get("instrument_token"):x for x in data.values() if isinstance(x,dict)}
    out=[]; cur_eq=0.0
    for s,h in H.items():
        qd=bytoken.get(resolved[s])
        if not qd: raise RuntimeError(f"quote missing {s}")
        ltp=float(qd["last_price"]); pv=h["qty"]*closes[s]; cv=h["qty"]*ltp
        cur_eq+=cv
        out.append({"symbol":s,"qty":h["qty"],"prev_close":closes[s],"ltp":ltp,"day_pnl":cv-pv,"day_move_pct":(ltp/closes[s]-1)*100,"current_value":cv,"cost":h["cost"],"total_pl":cv-h["cost"],"total_return_pct":(cv/h["cost"]-1)*100})
    total=cur_eq+residual
    result={"source":"UPSTOX_AUTHENTICATED_05NOV_BASE_26","quote_timestamp":max(x.get("timestamp") for x in bytoken.values() if x.get("timestamp")),"holdings":26,"base_pms_value":PMS_BASE,"base_equity_value":base_eq,"residual_assumed_unchanged":residual,"current_equity_value":cur_eq,"current_pms_value":total,"day_pnl":total-PMS_BASE,"day_return_pct":(total/PMS_BASE-1)*100,"breadth":{"up":sum(r["day_pnl"]>0 for r in out),"down":sum(r["day_pnl"]<0 for r in out),"flat":sum(r["day_pnl"]==0 for r in out)},"simple_gain_vs_net_invested":total-NET_INVESTED,"simple_return_vs_net_invested_pct":(total/NET_INVESTED-1)*100,"rows":sorted(out,key=lambda x:x["day_pnl"],reverse=True)}
    print("PMS_LIVE_06NOV_RESULT="+json.dumps(result,separators=(",",":"),sort_keys=True))
if __name__=="__main__": main()
