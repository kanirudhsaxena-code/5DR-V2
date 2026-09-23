"""One-shot authenticated Upstox live snapshot for the user's 33-stock PMS holdings."""
import json, os, subprocess
from urllib.parse import urlencode
from experiments.upstox_catalog import PublicInstrumentCatalog

HOLDINGS={
"ANANDRATHI":{"symbol":"ANANDRATHI","qty":62,"close22":2179.0,"cost":131362.89},
"APOLLO":{"symbol":"APOLLO","qty":281,"close22":406.75,"cost":117583.78},
"BEPL":{"symbol":"BEPL","qty":1806,"close22":130.23,"cost":237102.11},
"CEIGALL":{"symbol":"CEIGALL","qty":763,"close22":380.0,"cost":289543.09},
"EBGNG":{"symbol":"EBGNG","qty":464,"close22":692.3,"cost":282539.98},
"GLS":{"symbol":"ALIVUS","qty":80,"close22":1374.2,"cost":115930.57},
"INDGN":{"symbol":"INDGN","qty":420,"close22":592.1,"cost":240814.38},
"IOLCP":{"symbol":"IOLCP","qty":853,"close22":200.39,"cost":141916.00},
"JYOTICNC":{"symbol":"JYOTICNC","qty":279,"close22":1084.3,"cost":270242.46},
"KISSHT":{"symbol":"KISSHT","qty":479,"close22":352.55,"cost":175074.26},
"KSHINTL":{"symbol":"KSHINTL","qty":142,"close22":1040.95,"cost":144001.64},
"LLOYDSENGG":{"symbol":"LLOYDSENGG","qty":820,"close22":85.73,"cost":69630.30},
"LTFOODS":{"symbol":"LTFOODS","qty":278,"close22":421.35,"cost":114974.17},
"OPTIEMUS":{"symbol":"OPTIEMUS","qty":206,"close22":708.9,"cost":123110.72},
"PINELABS":{"symbol":"PINELABS","qty":2304,"close22":197.58,"cost":380258.25},
"RAYMOND":{"symbol":"RAYMOND","qty":171,"close22":1116.95,"cost":115279.75},
"REDINGTON":{"symbol":"REDINGTON","qty":382,"close22":410.35,"cost":144202.23},
"RPEL":{"symbol":"RPEL","qty":108,"close22":1735.0,"cost":106562.96},
"RUBICON":{"symbol":"RUBICON","qty":56,"close22":1671.2,"cost":96046.66},
"SANSERA":{"symbol":"SANSERA","qty":24,"close22":4586.5,"cost":75260.35},
"SMLMAH":{"symbol":"SMLMAH","qty":23,"close22":6719.5,"cost":150484.80},
"STAR":{"symbol":"STAR","qty":97,"close22":1219.0,"cost":118022.38},
"STLNETWORK":{"symbol":"STLNETWORK","qty":4098,"close22":47.34,"cost":151113.69},
"STRTECH":{"symbol":"STLTECH","qty":358,"close22":839.55,"cost":199138.79},
"SWANDEF":{"symbol":"SWANDEF","qty":27,"close22":2727.0,"cost":72726.61},
"WINDLAS":{"symbol":"WINDLAS","qty":157,"close22":1102.3,"cost":172800.69},
"WOCKPHARMA":{"symbol":"WOCKPHARMA","qty":86,"close22":2185.4,"cost":173915.52},
"MEESHO":{"symbol":"MEESHO","qty":1243,"close22":240.19,"cost":230424.17},
"SONACOMS":{"symbol":"SONACOMS","qty":208,"close22":809.0,"cost":169840.60},
"KANOHAR":{"symbol":"KANOHAR","qty":178,"close22":870.5,"cost":146196.54},
"TDPOWERSYS":{"symbol":"TDPOWERSYS","qty":225,"close22":756.4,"cost":181815.08},
"TVSMOTOR":{"symbol":"TVSMOTOR","qty":9,"close22":4140.0,"cost":35951.43},
"VBL":{"symbol":"VBL","qty":292,"close22":430.0,"cost":120217.91}
}
PMS_NET_INVESTED=5050384.22
PMS_RESIDUAL=220842.89


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
