"""Reconcile 23-stock Bonanza PMS screenshot at 12-Oct-2026 close."""
import json, os, subprocess
from urllib.parse import quote
from datetime import datetime
from experiments.upstox_catalog import PublicInstrumentCatalog

SNAP={
"CGPOWER":{"symbol":"CGPOWER","cost":183713.32,"value":178705.00},
"VBL":{"symbol":"VBL","cost":238134.61,"value":244381.20},
"MEESHO":{"symbol":"MEESHO","cost":240933.94,"value":266920.40},
"SONACOMS":{"symbol":"SONACOMS","cost":169840.60,"value":165984.00},
"KANOHAR":{"symbol":"KANOHAR","cost":102666.11,"value":140312.50},
"TDPOWERSYS":{"symbol":"TDPOWERSYS","cost":181815.08,"value":185771.25},
"TEMPSENS":{"symbol":"TEMPSENS","cost":119568.42,"value":118901.55},
"NETWEB":{"symbol":"NETWEB","cost":115430.11,"value":115023.00},
"ONWARDTEC":{"symbol":"ONWARDTEC","cost":94751.75,"value":95080.69},
"OPTIEMUS":{"symbol":"OPTIEMUS","cost":123110.72,"value":159866.29},
"REDINGTON":{"symbol":"REDINGTON","cost":236387.13,"value":237241.60},
"ROLEXRINGS":{"symbol":"ROLEXRINGS","cost":182922.52,"value":161585.64},
"RPEL":{"symbol":"RPEL","cost":54536.50,"value":98917.50},
"STRTECH":{"symbol":"STLTECH","cost":292327.19,"value":455353.34},
"SWANDEF":{"symbol":"SWANDEF","cost":72726.61,"value":79139.69},
"SYNCOMF":{"symbol":"SYNCOMF","cost":173020.14,"value":157241.83},
"TATAELXSI":{"symbol":"TATAELXSI","cost":118226.77,"value":117252.00},
"EBGNG":{"symbol":"EBGNG","cost":425206.72,"value":466431.00},
"IOLCP":{"symbol":"IOLCP","cost":122214.46,"value":146015.10},
"JYOTICNC":{"symbol":"JYOTICNC","cost":120040.30,"value":120963.50},
"KISSHT":{"symbol":"KISSHT","cost":175074.26,"value":178978.35},
"KSB":{"symbol":"KSB","cost":155429.88,"value":140528.39},
"LLOYDSENGG":{"symbol":"LLOYDSENGG","cost":451287.08,"value":456999.65}
}
def main():
  token=os.environ["UPSTOX_ANALYTICS_TOKEN"].strip()
  rows=PublicInstrumentCatalog().nse_instruments()["records"]
  out=[]
  for app,h in SNAP.items():
    m=[r for r in rows if isinstance(r,dict) and r.get("exchange")=="NSE" and r.get("segment")=="NSE_EQ" and str(r.get("trading_symbol","")).upper()==h["symbol"]]
    if len(m)!=1: raise RuntimeError(f"{app} resolution {len(m)}")
    key=quote(m[0]["instrument_key"],safe="")
    url=f"https://api.upstox.com/v3/historical-candle/{key}/days/1/2026-10-12/2026-10-12"
    p=subprocess.run(["curl","--fail-with-body","--silent","--show-error","-H","Accept: application/json","-H",f"Authorization: Bearer {token}",url],text=True,capture_output=True,timeout=25)
    if p.returncode: raise RuntimeError(f"{app} hist fail {p.stderr[:200]}")
    cs=((json.loads(p.stdout).get("data") or {}).get("candles") or [])
    if not cs: raise RuntimeError(f"{app} no candle")
    close=float(cs[0][4]); qty=round(h["value"]/close)
    recon=qty*close
    out.append({"app":app,"symbol":h["symbol"],"close_12oct":close,"qty":qty,"screenshot_value":h["value"],"recon_value":recon,"diff":recon-h["value"],"cost":h["cost"]})
  total=sum(x["screenshot_value"] for x in out)
  print("PMS23_RECON="+json.dumps({"rows":out,"equity_value":total,"pms_total":5987724.23,"residual":5987724.23-total},separators=(",",":"),sort_keys=True))
if __name__=="__main__": main()
