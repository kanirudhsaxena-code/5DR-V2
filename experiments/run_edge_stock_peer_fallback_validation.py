"""Validation-only live proof for EDGE_STOCK peer fallback."""
import json
from datetime import datetime, timezone
from pathlib import Path

from experiments.edge_stock_peer_fallback import acquire_peer_fallback

OUT=Path(".edge_stock/peer_fallback/result.json")
CASES={
    "LTF":{
        "kind":"STOCK","id":"INE498L01015","name":"L&T Finance Ltd",
        "exchange":"NSE","segment":"NSE_EQ","instrument_key":"NSE_EQ|INE498L01015",
        "symbol":"LTF","isin":"INE498L01015",
    },
    "RELIANCE":{
        "kind":"STOCK","id":"INE002A01018","name":"Reliance Industries Ltd",
        "exchange":"NSE","segment":"NSE_EQ","instrument_key":"NSE_EQ|INE002A01018",
        "symbol":"RELIANCE","isin":"INE002A01018",
    },
    "TATVA":{
        "kind":"STOCK","id":"INE0GK401011","name":"Tatva Chintan Pharma Chem Ltd",
        "exchange":"NSE","segment":"NSE_EQ","instrument_key":"NSE_EQ|INE0GK401011",
        "symbol":"TATVA","isin":"INE0GK401011",
    },
}

def run():
    now=datetime.now(timezone.utc)
    result={
        "schema":"edge-stock-peer-fallback-live-validation-v1",
        "captured_at":now.isoformat(),
        "cases":{},
        "production_activation_allowed":False,
    }
    for symbol,identity in CASES.items():
        record=acquire_peer_fallback(identity,acquisition_timestamp=now)
        values=record["values"]
        result["cases"][symbol]={
            "status":values["reconciliation_status"],
            "industry":values["industry"],
            "peer_count":values["peer_count"],
            "peer_cohort":values["peer_cohort"],
            "source_reference":record["source_reference"],
            "source_sha256":record["source_sha256"],
            "eligible_for_consumer":record["eligible_for_consumer"],
        }
    if any(row["status"]!="RECOVERED_VIA_FALLBACK" or row["peer_count"]<3
           for row in result["cases"].values()):
        raise RuntimeError("peer fallback validation failed")
    result["status"]="PASS"
    OUT.parent.mkdir(parents=True,exist_ok=True)
    OUT.write_text(json.dumps(result,sort_keys=True,separators=(",",":"))+"\n",encoding="utf-8")
    print(json.dumps(result,sort_keys=True,separators=(",",":")))
    return result

if __name__=="__main__":
    run()
