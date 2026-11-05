import json, os, subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from urllib.parse import urlencode, quote
from experiments.upstox_catalog import PublicInstrumentCatalog

SNAP={
"BSE":{"value":302526.00,"cost":286876.23},
"HCLTECH":{"value":292240.00,"cost":289991.95},
"ICICIBANK":{"value":178012.50,"cost":173865.10},
"PNB":{"value":170775.89,"cost":172245.89},
"VBL":{"value":237133.79,"cost":238134.61},
"AUROPHARMA":{"value":180730.00,"cost":170579.36},
"BOSCHLTD":{"value":101850.00,"cost":91909.36},
"HINDCOPPER":{"value":34706.50,"cost":34562.05},
"INDHOTEL":{"value":236022.00,"cost":223121.73},
"IPCALAB":{"value":177480.00,"cost":174550.39},
"LTTS":{"value":111604.50,"cost":109074.94},
"MEESHO":{"value":259579.79,"cost":240933.94},
"SONACOMS":{"value":185889.60,"cost":169840.60},
"JAYNECOIND":{"value":163852.32,"cost":178604.29},
"JSWCEMENT":{"value":169897.04,"cost":165437.85},
"KROSS":{"value":168785.39,"cost":173257.67},
"LLOYDSENGG":{"value":411017.25,"cost":451287.08},
"NEWGEN":{"value":164735.45,"cost":178796.04},
"OMNI":{"value":93046.60,"cost":99754.64},
"PINELABS":{"value":173547.00,"cost":176947.35},
"SOUTHBANK":{"value":186427.29,"cost":175532.23},
"STLTECH":{"value":410764.00,"cost":356332.54},
"TATAELXSI":{"value":285380.00,"cost":262765.03},
"ACUTAAS":{"value":181310.39,"cost":166839.60},
"CAPILLARY":{"value":150989.69,"cost":169709.14},
"EBGNG":{"value":521163.50,"cost":481334.26}
}
PMS_BASE=5641167.15
NET_INVESTED=5050384.22
BASE_EQ=sum(v["value"] for v in SNAP.values())
RESIDUAL=PMS_BASE-BASE_EQ

def curl_json(url, token):
    p=subprocess.run(["curl","--fail-with-body","--silent","--show-error","-H","Accept: application/json","-H",f"Authorization: Bearer {token}",url],text=True,capture_output=True,timeout=30)
    if p.returncode: raise RuntimeError(p.stderr[:300])
    return json.loads(p.stdout)

def resolve(rows,s):
    exact=[r for r in rows if isinstance(r,dict) and str(r.get("trading_symbol","")).upper()==s]
    if exact:
        eq=[r for r in exact if r.get("exchange")=="NSE" and r.get("segment")=="NSE_EQ"]
        return (eq[0] if eq else exact[0])
    raise RuntimeError(f"resolve {s}:0")

def hist_close(key,token):
    k=quote(key,safe="")
    url=f"https://api.upstox.com/v3/historical-candle/{k}/days/1/2026-11-04/2026-11-04"
    data=curl_json(url,token)
    cs=((data.get("data") or {}).get("candles") or [])
    if not cs: raise RuntimeError("no 4-Nov candle")
    return float(cs[0][4])

def main():
    token=os.environ["UPSTOX_ANALYTICS_TOKEN"].strip()
    rows=PublicInstrumentCatalog().nse_instruments()["records"]
    resolved={s:resolve(rows,s)["instrument_key"] for s in SNAP}
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
        qd=bytoken.get(resolved[s])
        if not qd: raise RuntimeError(f"quote missing {s}")
        ltp=float(qd["last_price"]); b=base[s]
        cur=b["qty"]*ltp; pnl=cur-h["value"]; cur_eq+=cur
        out.append({"symbol":s,"qty":b["qty"],"base_close":b["close"],"base_recon":b["recon"],"base_diff":b["diff"],"ltp":ltp,"base_value":h["value"],"current_value":cur,"pnl":pnl,"move_pct":(cur/h["value"]-1)*100,"cost":h["cost"],"total_pl":cur-h["cost"],"total_return_pct":(cur/h["cost"]-1)*100})
    total=cur_eq+RESIDUAL
    result={"source":"UPSTOX_AUTHENTICATED_RECONCILED_04NOV_26","quote_timestamp":max(x.get("timestamp") for x in bytoken.values() if x.get("timestamp")),"holdings":26,"base_pms_value":PMS_BASE,"base_equity_value":BASE_EQ,"residual_assumed_unchanged":RESIDUAL,"current_equity_value":cur_eq,"current_pms_value":total,"pms_change":total-PMS_BASE,"pms_change_pct":(total/PMS_BASE-1)*100,"breadth":{"up":sum(r["pnl"]>0 for r in out),"down":sum(r["pnl"]<0 for r in out),"flat":sum(r["pnl"]==0 for r in out)},"simple_gain_vs_net_invested":total-NET_INVESTED,"simple_return_vs_net_invested_pct":(total/NET_INVESTED-1)*100,"rows":sorted(out,key=lambda x:x["pnl"],reverse=True)}
    print("PMS_LIVE_05NOV_RESULT="+json.dumps(result,separators=(",",":"),sort_keys=True))
if __name__=="__main__": main()
