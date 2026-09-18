"""Validation-only representative EDGE_STOCK provider-core run."""
import json, os
from datetime import datetime, timezone
from pathlib import Path

from experiments.data_contract import DataArchitectureError
from experiments.edge_stock_identity import resolve_nse_equity, resolve_stock_fo_identity
from experiments.edge_stock_market_acquire import acquire_upstox_stock_core
from experiments.upstox_catalog import PublicInstrumentCatalog

OUT=Path(".edge_stock/core_validation/result.json")
NON_FO_CANDIDATES=("TATVA","AETHER","SENCO","DOMS","HAPPYFORGE","SHARDACROP","VSTIND")


def _norm(value):
    return " ".join(str(value or "").upper().replace("_"," ").split())


def resolve_index(rows, aliases):
    aliases={_norm(x) for x in aliases}
    matches=[]
    for row in rows:
        if not isinstance(row,dict) or row.get("exchange")!="NSE" or row.get("segment")!="NSE_INDEX":
            continue
        if _norm(row.get("name")) in aliases or _norm(row.get("trading_symbol")) in aliases:
            matches.append(row)
    if len(matches)!=1:
        raise DataArchitectureError(f"benchmark index ambiguous/missing: {sorted(aliases)}")
    row=matches[0]
    return {
        "kind":"MARKET_INSTRUMENT",
        "id":row["instrument_key"],
        "name":row.get("name") or row.get("trading_symbol"),
        "exchange":"NSE",
        "segment":"NSE_INDEX",
        "instrument_key":row["instrument_key"],
        "symbol":row.get("trading_symbol"),
    }


def choose_non_fo(rows, today):
    for symbol in NON_FO_CANDIDATES:
        try:
            stock=resolve_nse_equity(rows,symbol=symbol)
            fo=resolve_stock_fo_identity(rows,stock,as_of=today)
            if not fo["fo_eligible"]:
                return symbol
        except Exception:
            continue
    raise DataArchitectureError("no configured non-F&O representative resolved")


def run():
    token=os.environ.get("UPSTOX_ANALYTICS_TOKEN","").strip()
    if not token:
        raise ValueError("UPSTOX_ANALYTICS_TOKEN missing")
    now=datetime.now(timezone.utc)
    master=PublicInstrumentCatalog().nse_instruments()["records"]
    nifty50=resolve_index(master,("NIFTY 50","Nifty 50"))
    fin=resolve_index(master,("NIFTY FIN SERVICE","NIFTY FINANCIAL SERVICES","Nifty Fin Service"))
    nifty500=resolve_index(master,("NIFTY 500","Nifty 500"))
    non_fo=choose_non_fo(master,now.date())
    cases={
        "LTF":("LTF",fin),
        "LARGE_LIQUID_FO":("RELIANCE",nifty50),
        "NON_FO":(non_fo,nifty500),
    }
    out={"schema":"edge-stock-core-live-validation-v1","captured_at":now.isoformat(),"cases":{}}
    for label,(symbol,benchmark) in cases.items():
        core=acquire_upstox_stock_core(token,symbol=symbol,benchmark_identity=benchmark,as_of=now)
        variables=sorted(r["variable_id"] for r in core["records"])
        out["cases"][label]={
            "symbol":symbol,
            "subject_id":core["stock_identity"]["id"],
            "fo_eligible":core["fo_identity"]["fo_eligible"],
            "nearest_expiry":core["fo_identity"]["nearest_expiry"],
            "benchmark":benchmark,
            "variables":variables,
            "read_only":core["read_only"],
            "methodology_applied":core["methodology_applied"],
            "trading_enabled":core["trading_enabled"],
        }
    if not out["cases"]["LTF"]["fo_eligible"] or not out["cases"]["LARGE_LIQUID_FO"]["fo_eligible"]:
        raise DataArchitectureError("F&O representative classification failed")
    if out["cases"]["NON_FO"]["fo_eligible"]:
        raise DataArchitectureError("non-F&O representative classification failed")
    out["status"]="PASS"
    out["production_activation_allowed"]=False
    OUT.parent.mkdir(parents=True,exist_ok=True)
    OUT.write_text(json.dumps(out,sort_keys=True,separators=(",",":"),default=str)+"\n",encoding="utf-8")
    print(json.dumps(out,sort_keys=True,separators=(",",":"),default=str))
    return out

if __name__=="__main__":
    run()
