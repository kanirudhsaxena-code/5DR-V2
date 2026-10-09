"""One-shot authenticated Upstox live snapshot for the user's 29-stock PMS holdings."""
import json, os, subprocess
from urllib.parse import urlencode
from experiments.upstox_catalog import PublicInstrumentCatalog

HOLDINGS={
"APOLLO":{"symbol":"APOLLO","qty":281,"close22":394.0,"cost":117583.78},
"BEPL":{"symbol":"BEPL","qty":1806,"close22":123.76,"cost":237102.11},
"CEIGALL":{"symbol":"CEIGALL","qty":763,"close22":380.1,"cost":289543.09},
"EBGNG":{"symbol":"EBGNG","qty":668,"close22":704.7,"cost":425206.72},
"GLS":{"symbol":"ALIVUS","qty":80,"close22":1374.2,"cost":115930.57},
"INDGN":{"symbol":"INDGN","qty":420,"close22":593.5,"cost":240814.38},
"IOLCP":{"symbol":"IOLCP","qty":853,"close22":209.39,"cost":141916.00},
"JYOTICNC":{"symbol":"JYOTICNC","qty":279,"close22":1032.1,"cost":270242.46},
"KISSHT":{"symbol":"KISSHT","qty":479,"close22":371.15,"cost":175074.26},
"KSB":{"symbol":"KSB","qty":181,"close22":806.45,"cost":155429.88},
"LLOYDSENGG":{"symbol":"LLOYDSENGG","qty":4955,"close22":98.31,"cost":451287.08},
"OPTIEMUS":{"symbol":"OPTIEMUS","qty":206,"close22":803.7,"cost":123110.72},
"PINELABS":{"symbol":"PINELABS","qty":1180,"close22":167.59,"cost":199187.88},
"REDINGTON":{"symbol":"REDINGTON","qty":608,"close22":397.95,"cost":236387.13},
"ROLEXRINGS":{"symbol":"ROLEXRINGS","qty":937,"close22":196.36,"cost":182922.52},
"RPEL":{"symbol":"RPEL","qty":55,"close22":1818.9,"cost":54536.50},
"SMLMAH":{"symbol":"SMLMAH","qty":23,"close22":6251.0,"cost":150484.80},
"STAR":{"symbol":"STAR","qty":97,"close22":1084.8,"cost":118022.38},
"STLNETWORK":{"symbol":"STLNETWORK","qty":1229,"close22":49.43,"cost":46806.19},
"STRTECH":{"symbol":"STLTECH","qty":449,"close22":1016.8,"cost":292327.19},
"SWANDEF":{"symbol":"SWANDEF","qty":27,"close22":2718.2,"cost":72726.61},
"SYNCOMF":{"symbol":"SYNCOMF","qty":6766,"close22":23.96,"cost":173020.14},
"WOCKPHARMA":{"symbol":"WOCKPHARMA","qty":86,"close22":2083.9,"cost":173915.52},
"MEESHO":{"symbol":"MEESHO","qty":1020,"close22":232.6,"cost":209836.76},
"SONACOMS":{"symbol":"SONACOMS","qty":208,"close22":805.0,"cost":169840.60},
"KANOHAR":{"symbol":"KANOHAR","qty":125,"close22":1091.05,"cost":102666.11},
"TDPOWERSYS":{"symbol":"TDPOWERSYS","qty":225,"close22":792.15,"cost":181815.08},
"CGPOWER":{"symbol":"CGPOWER","qty":206,"close22":894.5,"cost":183713.32},
"VBL":{"symbol":"VBL","qty":564,"close22":425.3,"cost":238134.61}
}
PMS_NET_INVESTED=5050384.22
PMS_RESIDUAL=186373.77


def main():
    rows=PublicInstrumentCatalog().nse_instruments()["records"]
    resolved={}
    for app,h in HOLDINGS.items():
        m=[r for r in rows if isinstance(r,dict) and r.get("exchange")=="NSE" and r.get("segment")=="NSE_EQ" and str(r.get("trading_symbol","")).upper()==h["symbol"]]
        if len(m)!=1: raise RuntimeError(f"resolution {app}->{h['symbol']}: {len(m)}")
        resolved[app]=m[0]["instrument_key"]
    token=os.environ["UPSTOX_ANALYTICS_TOKEN"].strip()
    query=urlencode({"instrument_key":",".join(resolved.values())})
    url="https://api.upstox.com/v3/market-quote/quotes?"+query
    p=subprocess.run(["curl","--fail-with-body","--silent","--show-error","-H","Accept: application/json","-H",f"Authorization: Bearer {token}",url],text=True,capture_output=True,timeout=25)
    if p.returncode: raise RuntimeError("Upstox batch quote failed")
    payload=json.loads(p.stdout)
    data=payload.get("data") or {}
    bytoken={q.get("instrument_token"):q for q in data.values() if isinstance(q,dict) and isinstance(q.get("instrument_token"),str)}
    out=[]; eq_value=0.0; day_pnl=0.0; cost_total=0.0
    quote_ts=[]
    for app,h in HOLDINGS.items():
        q=bytoken.get(resolved[app])
        if not q: raise RuntimeError(f"quote missing: {app}")
        ltp=q.get("last_price")
        if not isinstance(ltp,(int,float)): raise RuntimeError(f"ltp missing: {app}")
        value=h["qty"]*float(ltp); dpnl=h["qty"]*(float(ltp)-h["close22"]); tpnl=value-h["cost"]
        eq_value+=value; day_pnl+=dpnl; cost_total+=h["cost"]
        if q.get("timestamp"): quote_ts.append(q["timestamp"])
        ohlc=q.get("ohlc") if isinstance(q.get("ohlc"),dict) else {}
        out.append({"app_symbol":app,"nse_symbol":h["symbol"],"qty":h["qty"],"ltp":float(ltp),"prev_close":h["close22"],"day_change_pct":(float(ltp)/h["close22"]-1)*100,"day_pnl":dpnl,"position_value":value,"cost":h["cost"],"total_pnl":tpnl,"total_return_pct":tpnl/h["cost"]*100,"open":ohlc.get("open"),"high":ohlc.get("high"),"low":ohlc.get("low"),"volume":q.get("volume") or ohlc.get("volume")})
    est_total=eq_value+PMS_RESIDUAL
    result={"source":"UPSTOX_AUTHENTICATED_V3_BATCH_FULL_QUOTE","quote_timestamp":max(quote_ts) if quote_ts else None,"holdings":len(out),"visible_equity_value":eq_value,"visible_equity_day_pnl":day_pnl,"visible_equity_day_return_pct":day_pnl/sum(h["qty"]*h["close22"] for h in HOLDINGS.values())*100,"visible_equity_cost":cost_total,"visible_equity_total_pnl":eq_value-cost_total,"estimated_pms_total_value_if_residual_unchanged":est_total,"estimated_pms_day_pnl":day_pnl,"simple_gain_vs_net_invested":est_total-PMS_NET_INVESTED,"simple_return_vs_net_invested_pct":(est_total/PMS_NET_INVESTED-1)*100,"rows":sorted(out,key=lambda x:x["day_pnl"],reverse=True)}
    print("LIVE_FULL_PORTFOLIO="+json.dumps(result,separators=(",",":"),sort_keys=True))

if __name__=="__main__": main()
