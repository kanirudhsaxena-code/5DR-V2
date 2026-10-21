import json, os, subprocess
from urllib.parse import quote
from experiments.upstox_catalog import PublicInstrumentCatalog

SNAP={
"MIDCPNIFTY":{"symbol":"MIDCPNIFTY","value":40668.00,"cost":41791.76},
"TDPOWERSYS":{"symbol":"TDPOWERSYS","value":165825.00,"cost":181815.08},
"TEMPSENS":{"symbol":"TEMPSENS","value":213345.29,"cost":240606.97},
"BOSCHLTD":{"symbol":"BOSCHLTD","value":90390.00,"cost":91909.36},
"MEESHO":{"symbol":"MEESHO","value":265406.03,"cost":240933.94},
"SONACOMS":{"symbol":"SONACOMS","value":165152.00,"cost":169840.60},
"BSE":{"symbol":"BSE","value":173472.00,"cost":178828.35},
"HCLTECH":{"symbol":"HCLTECH","value":179387.00,"cost":178509.92},
"VBL":{"symbol":"VBL","value":237190.20,"cost":238134.61},
"NETWEB":{"symbol":"NETWEB","value":159796.60,"cost":171065.52},
"NEWGEN":{"symbol":"NEWGEN","value":178704.29,"cost":178796.04},
"ONWARDTEC":{"symbol":"ONWARDTEC","value":129658.10,"cost":94751.75},
"REDINGTON":{"symbol":"REDINGTON","value":225598.39,"cost":236387.13},
"ROLEXRINGS":{"symbol":"ROLEXRINGS","value":158249.92,"cost":182922.52},
"SOUTHBANK":{"symbol":"SOUTHBANK","value":181119.88,"cost":175532.23},
"STLTECH":{"symbol":"STLTECH","value":456933.75,"cost":356332.54},
"SWANDEF":{"symbol":"SWANDEF","value":79126.19,"cost":72726.61},
"SYNCOMF":{"symbol":"SYNCOMF","value":144860.05,"cost":173020.14},
"TATAELXSI":{"symbol":"TATAELXSI","value":261510.00,"cost":235729.17},
"EBGNG":{"symbol":"EBGNG","value":593069.40,"cost":557619.01},
"INOXGREEN":{"symbol":"INOXGREEN","value":113053.58,"cost":119484.92},
"JAYNECOIND":{"symbol":"JAYNECOIND","value":175188.23,"cost":178604.29},
"JINDALSAW":{"symbol":"JINDALSAW","value":83359.19,"cost":87621.46},
"KISSHT":{"symbol":"KISSHT","value":164153.29,"cost":175074.26},
"KSB":{"symbol":"KSB","value":136636.89,"cost":155429.88},
"LLOYDSENGG":{"symbol":"LLOYDSENGG","value":467306.04,"cost":451287.08}
}

def main():
    token=os.environ["UPSTOX_ANALYTICS_TOKEN"].strip()
    rows=PublicInstrumentCatalog().nse_instruments()["records"]
    out=[]
    for app,h in SNAP.items():
        m=[r for r in rows if isinstance(r,dict) and r.get("exchange")=="NSE" and r.get("segment")=="NSE_EQ" and str(r.get("trading_symbol","")).upper()==h["symbol"]]
        if len(m)!=1:
            raise RuntimeError(f"{app} resolution {len(m)}")
        key=quote(m[0]["instrument_key"],safe="")
        url=f"https://api.upstox.com/v3/historical-candle/{key}/days/1/2026-10-20/2026-10-20"
        p=subprocess.run(["curl","--fail-with-body","--silent","--show-error","-H","Accept: application/json","-H",f"Authorization: Bearer {token}",url],text=True,capture_output=True,timeout=25)
        if p.returncode: raise RuntimeError(f"{app} hist fail {p.stderr[:200]}")
        cs=((json.loads(p.stdout).get("data") or {}).get("candles") or [])
        if not cs: raise RuntimeError(f"{app} no candle")
        close=float(cs[0][4]); qty=round(h["value"]/close); recon=qty*close
        out.append({"app":app,"symbol":h["symbol"],"close":close,"qty":qty,"screenshot_value":h["value"],"recon_value":recon,"diff":recon-h["value"],"cost":h["cost"]})
    total=sum(x["screenshot_value"] for x in out)
    print("PMS26_RECON="+json.dumps({"rows":out,"equity_value":total,"pms_total":5813799.58,"residual":5813799.58-total},separators=(",",":"),sort_keys=True))
if __name__=="__main__": main()
