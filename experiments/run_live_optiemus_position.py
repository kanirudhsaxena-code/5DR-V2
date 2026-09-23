"""Fast read-only live OPTIEMUS position from authenticated Upstox quote."""
import json, os, subprocess
from urllib.parse import urlencode
from experiments.upstox_catalog import PublicInstrumentCatalog

QTY=206
COST=123110.72
PREV_CLOSE=708.90


def main():
    rows=PublicInstrumentCatalog().nse_instruments()["records"]
    m=[r for r in rows if isinstance(r,dict) and r.get("exchange")=="NSE" and r.get("segment")=="NSE_EQ" and str(r.get("trading_symbol","")).upper()=="OPTIEMUS"]
    if len(m)!=1:
        raise RuntimeError(f"OPTIEMUS instrument resolution failed: {len(m)}")
    key=m[0]["instrument_key"]
    token=os.environ["UPSTOX_ANALYTICS_TOKEN"].strip()
    url="https://api.upstox.com/v3/market-quote/quotes?"+urlencode({"instrument_key":key})
    p=subprocess.run(["curl","--fail-with-body","--silent","--show-error","-H","Accept: application/json","-H",f"Authorization: Bearer {token}",url],text=True,capture_output=True,timeout=20)
    if p.returncode:
        raise RuntimeError("Upstox quote request failed")
    payload=json.loads(p.stdout)
    data=payload.get("data") or {}
    row=next(iter(data.values())) if data else None
    if not isinstance(row,dict):
        raise RuntimeError("Upstox quote missing")
    ltp=float(row["last_price"])
    value=QTY*ltp
    day_pnl=QTY*(ltp-PREV_CLOSE)
    total_pnl=value-COST
    result={
        "source":"UPSTOX_AUTHENTICATED_V3_FULL_QUOTE",
        "ticker":"OPTIEMUS",
        "instrument_key":key,
        "qty":QTY,
        "ltp":ltp,
        "prev_close":PREV_CLOSE,
        "day_change":ltp-PREV_CLOSE,
        "day_change_pct":(ltp/PREV_CLOSE-1)*100,
        "position_value":value,
        "day_pnl":day_pnl,
        "cost":COST,
        "total_pnl":total_pnl,
        "total_return_pct":total_pnl/COST*100,
        "quote_timestamp":row.get("timestamp"),
        "trade_timestamp":row.get("trade_timestamp"),
        "ohlc":row.get("ohlc"),
        "volume":row.get("volume")
    }
    print("LIVE_OPTIEMUS_POSITION="+json.dumps(result,separators=(",",":"),sort_keys=True))

if __name__=="__main__":
    main()
