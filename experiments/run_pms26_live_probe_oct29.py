import json, os, subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urlencode, quote
from experiments.upstox_catalog import PublicInstrumentCatalog

SNAP={
"BSE":{"value":328364.40,"cost":286876.23},
"HCLTECH":{"value":287206.40,"cost":289991.95},
"ICICIBANK":{"value":198750.00,"cost":173865.10},
"PNB":{"value":197797.04,"cost":172245.89},
"VBL":{"value":245340.00,"cost":238134.61},
"AUROPHARMA":{"value":191563.20,"cost":170579.36},
"BOSCHLTD":{"value":101000.00,"cost":91909.36},
"HINDCOPPER":{"value":114214.39,"cost":113906.08},
"INDHOTEL":{"value":245196.00,"cost":223121.73},
"IPCALAB":{"value":170973.00,"cost":174550.39},
"LTTS":{"value":115206.30,"cost":109074.94},
"MEESHO":{"value":293751.15,"cost":240933.94},
"SONACOMS":{"value":192608.00,"cost":169840.60},
"ACUTAAS":{"value":191812.79,"cost":166839.60},
"EBGNG":{"value":408872.75,"cost":481334.26},
"JAYNECOIND":{"value":165443.64,"cost":178604.29},
"JSWCEMENT":{"value":175253.85,"cost":165437.85},
"KROSS":{"value":178663.79,"cost":173257.67},
"LLOYDSENGG":{"value":432472.40,"cost":451287.08},
"NELCO":{"value":67800.60,"cost":68410.33},
"NEWGEN":{"value":164977.89,"cost":178796.04},
"OMNI":{"value":79271.69,"cost":99754.64},
"PINELABS":{"value":193490.00,"cost":176947.35},
"SOUTHBANK":{"value":204686.16,"cost":175532.23},
"STLTECH":{"value":366371.00,"cost":356332.54},
"TATAELXSI":{"value":293512.00,"cost":262765.03}
}
PMS_BASE=5696402.66
NET_INVESTED=5050384.22
BASE_EQ=sum(v["value"] for v in SNAP.values())
RESIDUAL=PMS_BASE-BASE_EQ

def curl_json(url,token):
    p=subprocess.run(["curl","--fail-with-body","--silent","--show-error","-H","Accept: application/json","-H",f"Authorization: Bearer {token}",url],capture_output=True,text=True,timeout=30)
    if p.returncode: raise RuntimeError(p.stderr[:300])
    return json.loads(p.stdout)

def resolve(rows,s):
    m=[r for r in rows if isinstance(r,dict) and str(r.get("trading_symbol","")).upper()==s]
    if not m: raise RuntimeError(f"resolve {s}:0")
    eq=[r for r in m if r.get("exchange")=="NSE" and r.get("segment")=="NSE_EQ"]
    return (eq[0] if eq else m[0])["instrument_key"]

def hist_close(key,token):
    k=quote(key,safe="")
    u=f"https://api.upstox.com/v3/historical-candle/{k}/days/1/2026-11-12/2026-11-12"
    d=curl_json(u,token)
    cs=((d.get("data") or {}).get("candles") or [])
    if not cs: raise RuntimeError("no 12-Nov candle")
    return float(cs[0][4])

def main():
    token=os.environ["UPSTOX_ANALYTICS_TOKEN"].strip()
    rows=PublicInstrumentCatalog().nse_instruments()["records"]
    resolved={s:resolve(rows,s) for s in SNAP}
    closes={}
    with ThreadPoolExecutor(max_workers=8) as ex:
        futs={ex.submit(hist_close,k,token):s for s,k in resolved.items()}
        for fut in as_completed(futs): closes[futs[fut]]=fut.result()

    base={}
    for s,h in SNAP.items():
        qty=round(h["value"]/closes[s])
        base[s]={"qty":qty,"close":closes[s],"recon":qty*closes[s],"diff":qty*closes[s]-h["value"]}

    q=urlencode({"instrument_key":",".join(resolved.values())})
    data=(curl_json("https://api.upstox.com/v3/market-quote/quotes?"+q,token).get("data") or {})
    bytoken={x.get("instrument_token"):x for x in data.values() if isinstance(x,dict)}

    out=[]; cur_eq=0.0
    for s,h in SNAP.items():
        qd=bytoken.get(resolved[s])
        if not qd: raise RuntimeError(f"quote missing {s}")
        ltp=float(qd["last_price"]); b=base[s]
        cv=b["qty"]*ltp; pnl=cv-h["value"]; cur_eq+=cv
        out.append({
            "symbol":s,"qty":b["qty"],"prev_close":b["close"],"base_recon":b["recon"],"base_diff":b["diff"],
            "ltp":ltp,"day_pnl":pnl,"day_move_pct":(cv/h["value"]-1)*100,"current_value":cv,
            "cost":h["cost"],"total_pl":cv-h["cost"],"total_return_pct":(cv/h["cost"]-1)*100
        })

    total=cur_eq+RESIDUAL
    result={
      "source":"UPSTOX_AUTHENTICATED_12NOV_PMS_BASE_26",
      "quote_timestamp":max(x.get("timestamp") for x in bytoken.values() if x.get("timestamp")),
      "holdings":26,
      "base_pms_value":PMS_BASE,
      "base_equity_value":BASE_EQ,
      "residual_assumed_unchanged":RESIDUAL,
      "current_equity_value":cur_eq,
      "current_pms_value":total,
      "day_pnl":total-PMS_BASE,
      "day_return_pct":(total/PMS_BASE-1)*100,
      "breadth":{"up":sum(r["day_pnl"]>0 for r in out),"down":sum(r["day_pnl"]<0 for r in out),"flat":sum(r["day_pnl"]==0 for r in out)},
      "simple_gain_vs_net_invested":total-NET_INVESTED,
      "simple_return_vs_net_invested_pct":(total/NET_INVESTED-1)*100,
      "rows":sorted(out,key=lambda x:x["day_pnl"],reverse=True)
    }
    print("PMS_LIVE_13NOV_RESULT="+json.dumps(result,separators=(",",":"),sort_keys=True))
if __name__=="__main__": main()
