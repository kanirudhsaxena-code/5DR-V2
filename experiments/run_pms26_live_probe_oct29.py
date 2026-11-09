import json, os, subprocess
from urllib.parse import urlencode
from experiments.upstox_catalog import PublicInstrumentCatalog

H={
"BSE":{"qty":84,"base_value":319200.00,"cost":286876.23},
"HCLTECH":{"qty":208,"base_value":299936.00,"cost":289991.95},
"ICICIBANK":{"qty":125,"base_value":195625.00,"cost":173865.10},
"PNB":{"qty":1395,"base_value":175142.25,"cost":172245.89},
"VBL":{"qty":564,"base_value":245340.00,"cost":238134.61},
"AUROPHARMA":{"qty":106,"base_value":191224.00,"cost":170579.36},
"BOSCHLTD":{"qty":2,"base_value":101600.00,"cost":91909.36},
"HINDCOPPER":{"qty":82,"base_value":35419.90,"cost":34562.05},
"INDHOTEL":{"qty":278,"base_value":247142.00,"cost":223121.73},
"IPCALAB":{"qty":90,"base_value":174483.00,"cost":174550.39},
"LTTS":{"qty":27,"base_value":115125.30,"cost":109074.94},
"MEESHO":{"qty":1156,"base_value":270157.20,"cost":240933.94},
"SONACOMS":{"qty":208,"base_value":188968.00,"cost":169840.60},
"JAYNECOIND":{"qty":1788,"base_value":163637.76,"cost":178604.29},
"JSWCEMENT":{"qty":1395,"base_value":172868.39,"cost":165437.85},
"KROSS":{"qty":588,"base_value":174900.60,"cost":173257.67},
"LLOYDSENGG":{"qty":4955,"base_value":419093.90,"cost":451287.08},
"NEWGEN":{"qty":373,"base_value":167029.39,"cost":178796.04},
"OMNI":{"qty":139,"base_value":83094.19,"cost":99754.64},
"PINELABS":{"qty":1100,"base_value":180202.00,"cost":176947.35},
"SOUTHBANK":{"qty":3338,"base_value":193704.14,"cost":175532.23},
"STLTECH":{"qty":515,"base_value":363718.75,"cost":356332.54},
"TATAELXSI":{"qty":76,"base_value":294500.00,"cost":262765.03},
"ACUTAAS":{"qty":48,"base_value":188491.20,"cost":166839.60},
"CAPILLARY":{"qty":296,"base_value":149968.39,"cost":169709.14},
"EBGNG":{"qty":715,"base_value":433111.25,"cost":481334.26}
}
PMS_BASE=5635306.75
NET_INVESTED=5050384.22
BASE_EQ=sum(v["base_value"] for v in H.values())
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

def main():
    token=os.environ["UPSTOX_ANALYTICS_TOKEN"].strip()
    rows=PublicInstrumentCatalog().nse_instruments()["records"]
    resolved={s:resolve(rows,s) for s in H}
    q=urlencode({"instrument_key":",".join(resolved.values())})
    data=(curl_json("https://api.upstox.com/v3/market-quote/quotes?"+q,token).get("data") or {})
    bytoken={x.get("instrument_token"):x for x in data.values() if isinstance(x,dict)}
    out=[]; cur_eq=0.0
    for s,h in H.items():
        qd=bytoken.get(resolved[s])
        if not qd: raise RuntimeError(f"quote missing {s}")
        ltp=float(qd["last_price"]); cv=h["qty"]*ltp; pnl=cv-h["base_value"]; cur_eq+=cv
        out.append({"symbol":s,"qty":h["qty"],"base_close":h["base_value"]/h["qty"],"ltp":ltp,"day_pnl":pnl,"day_move_pct":(cv/h["base_value"]-1)*100,"current_value":cv,"cost":h["cost"],"total_pl":cv-h["cost"],"total_return_pct":(cv/h["cost"]-1)*100})
    total=cur_eq+RESIDUAL
    result={"source":"UPSTOX_AUTHENTICATED_08NOV_PMS_BASE_26","quote_timestamp":max(x.get("timestamp") for x in bytoken.values() if x.get("timestamp")),"holdings":26,"base_pms_value":PMS_BASE,"base_equity_value":BASE_EQ,"residual_assumed_unchanged":RESIDUAL,"current_equity_value":cur_eq,"current_pms_value":total,"day_pnl":total-PMS_BASE,"day_return_pct":(total/PMS_BASE-1)*100,"breadth":{"up":sum(r["day_pnl"]>0 for r in out),"down":sum(r["day_pnl"]<0 for r in out),"flat":sum(r["day_pnl"]==0 for r in out)},"simple_gain_vs_net_invested":total-NET_INVESTED,"simple_return_vs_net_invested_pct":(total/NET_INVESTED-1)*100,"rows":sorted(out,key=lambda x:x["day_pnl"],reverse=True)}
    print("PMS_LIVE_09NOV_RESULT="+json.dumps(result,separators=(",",":"),sort_keys=True))
if __name__=="__main__": main()
