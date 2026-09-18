"""Diagnostic only: identify invalid raw OHLC rows for one approved historical chunk."""
import json, os
from datetime import date
from experiments.upstox_quant_client import QuantReadOnlyClient
from experiments.upstox_endpoints import historical_path
from experiments.backfill_inventory import GLOBAL_RISK
from experiments.upstox_quality import validate_ohlc

KEY = GLOBAL_RISK["GIFT_NIFTY"]

def main():
    token=os.environ["UPSTOX_ANALYTICS_TOKEN"]
    client=QuantReadOnlyClient(token,{KEY})
    path=historical_path(KEY,"days",1,start=date(2025,9,18),end=date(2026,9,17),intraday=False)
    env=client._get(path)
    rows=env["payload"]["data"]["candles"]
    bad=[]
    for i,row in enumerate(rows):
        try:
            validate_ohlc(row[1],row[2],row[3],row[4],volume=row[5],open_interest=row[6])
        except Exception as exc:
            bad.append({"index":i,"row":row,"error":str(exc)})
    print(json.dumps({"instrument_key":KEY,"row_count":len(rows),"bad_count":len(bad),"bad_rows":bad[:20],"source_sha256":env["sha256"]},sort_keys=True,separators=(",",":")))
if __name__=="__main__": main()
