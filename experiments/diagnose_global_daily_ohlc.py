"""One-time raw diagnostic for global daily historical OHLC geometry.

Read-only only. It does not write cache/database state and does not relax validators.
"""
import json
import os
from datetime import date

from experiments.backfill_inventory import GLOBAL_RISK, GLOBAL_MACRO
from experiments.data_contract import DataArchitectureError
from experiments.upstox_endpoints import historical_path
from experiments.upstox_quant_client import QuantReadOnlyClient
from experiments.upstox_quality import validate_ohlc

START = date(2025, 9, 18)
END = date(2026, 9, 17)


def main():
    token=os.environ.get("UPSTOX_ANALYTICS_TOKEN","").strip()
    if not token:
        raise DataArchitectureError("UPSTOX_ANALYTICS_TOKEN missing")
    keys=list(GLOBAL_RISK.values())+list(GLOBAL_MACRO.values())
    client=QuantReadOnlyClient(token,set(keys))
    findings=[]
    for key in keys:
        path=historical_path(key,"days",1,start=START,end=END,intraday=False)
        env=client._get(path)
        rows=env.get("payload",{}).get("data",{}).get("candles",[])
        if not isinstance(rows,list) or not rows:
            raise DataArchitectureError("global daily diagnostic candles missing")
        bad=[]
        for row in rows:
            try:
                if not isinstance(row,list) or len(row)!=7:
                    raise DataArchitectureError("candle shape invalid")
                validate_ohlc(row[1],row[2],row[3],row[4],volume=row[5],open_interest=row[6])
            except Exception as exc:
                bad.append({
                    "row":row,
                    "reason":str(exc),
                })
        result={
            "instrument_key":key,
            "row_count":len(rows),
            "invalid_row_count":len(bad),
            "invalid_rows":bad,
            "source_sha256":env.get("sha256"),
        }
        findings.append(result)
        print(json.dumps({"event":"GLOBAL_DAILY_OHLC_SCAN",**result},sort_keys=True,separators=(",",":")),flush=True)
    print(json.dumps({
        "status":"GLOBAL_DAILY_OHLC_SCAN_COMPLETE",
        "series_scanned":len(findings),
        "invalid_series_count":sum(1 for x in findings if x["invalid_row_count"]),
        "invalid_row_count":sum(x["invalid_row_count"] for x in findings),
        "findings":findings,
        "persistent_writes":0,
        "production_writes":0,
    },sort_keys=True,separators=(",",":")))
    return 0

if __name__=="__main__":
    raise SystemExit(main())
