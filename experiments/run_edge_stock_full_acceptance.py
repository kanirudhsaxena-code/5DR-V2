"""Validation-only full EDGE_STOCK representative acceptance run."""
import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path

from experiments.data_contract import DataArchitectureError
from experiments.edge_stock_acceptance import build_edge_stock_acceptance_gate
from experiments.edge_stock_full_acceptance_manifest import validation_manifest
from experiments.edge_stock_market_acquire import acquire_upstox_stock_core
from experiments.edge_stock_orchestrator import assemble_edge_stock_bundle, build_shared_macro_record
from experiments.edge_stock_research import build_research_record
from experiments.live_shadow_bundle import build_live_shadow_bundle
from experiments.run_edge_stock_core_validation import resolve_index, choose_non_fo
from experiments.upstox_catalog import PublicInstrumentCatalog

OUT=Path(".edge_stock/full_acceptance")


def _shared_macro_snapshot(bundle):
    by_var={r["variable_id"]:r for r in bundle["quantitative_records"]}
    needed=["GLOBAL_RISK_INDICES","CRUDE_USDINR"]
    if any(v not in by_var for v in needed):
        raise DataArchitectureError("shared market core macro evidence missing")
    web=[
        item for item in bundle["external_evidence"]
        if item.get("category") in {"DXY_RATES","MACRO_EVENTS_GEOPOLITICS"}
    ]
    payload={
        "global_risk":by_var["GLOBAL_RISK_INDICES"]["values"],
        "crude_usdinr":by_var["CRUDE_USDINR"]["values"],
        "external_context":[{
            "category":x["category"],
            "source_reference":x["source_reference"],
            "research_sha256":x["research_sha256"],
        } for x in web],
    }
    digest=hashlib.sha256(
        "|".join(sorted([
            by_var["GLOBAL_RISK_INDICES"]["record_fingerprint"],
            by_var["CRUDE_USDINR"]["record_fingerprint"],
            *(x["research_sha256"] for x in web),
        ])).encode()
    ).hexdigest()
    return {
        "source_sha256":digest,
        "source_reference":"SHARED_5DR_EVIDENCE:"+bundle["bundle_sha256"],
        "observed_at":bundle["frozen_at"],
        "values":payload,
        "transmission_channels":["UNFILTERED_SHARED_MARKET_CONTEXT"],
    }


def _research_records(stock, symbol, now):
    manifest=validation_manifest(symbol)
    rows=[]
    for variable_id in (
        "STOCK_PEERS",
        "STOCK_FORWARD_CATALYSTS",
        "STOCK_GOVERNANCE_RISK",
        "STOCK_INSTITUTIONAL_EVENTS",
    ):
        spec=manifest[variable_id]
        rows.append(build_research_record(
            stock_identity=stock,
            variable_id=variable_id,
            sources=spec["sources"],
            status=spec["status"],
            acquisition_timestamp=now,
        ))
    return rows


def run():
    token=os.environ.get("UPSTOX_ANALYTICS_TOKEN","").strip()
    if not token:
        raise ValueError("UPSTOX_ANALYTICS_TOKEN missing")
    now=datetime.now(timezone.utc)

    shared=build_live_shadow_bundle(token)
    if shared.get("status")!="READY":
        raise DataArchitectureError("shared 5DR market evidence not READY")
    macro_snapshot=_shared_macro_snapshot(shared)

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

    bundles={}
    details={}
    for label,(symbol,benchmark) in cases.items():
        core=acquire_upstox_stock_core(
            token,symbol=symbol,benchmark_identity=benchmark,as_of=now
        )
        research=_research_records(core["stock_identity"],symbol,datetime.now(timezone.utc))
        macro=build_shared_macro_record(
            stock_identity=core["stock_identity"],
            macro_evidence=macro_snapshot,
            acquisition_timestamp=datetime.now(timezone.utc),
        )
        assembled=assemble_edge_stock_bundle(
            core_acquisition=core,
            research_records=research,
            macro_record=macro,
            run_id=f"EDGE-STOCK-ACCEPT-{label}-{now.strftime('%Y%m%dT%H%M%SZ')}",
            frozen_at=datetime.now(timezone.utc),
        )
        if assembled["status"]!="READY":
            raise DataArchitectureError(f"EDGE_STOCK full bundle blocked: {label}")
        bundles[label]=assembled["bundle"]
        details[label]={
            "symbol":symbol,
            "subject_id":core["stock_identity"]["id"],
            "provider_gaps":core.get("provider_gaps",[]),
            "bundle_sha256":assembled["bundle"]["bundle_sha256"],
            "coverage":assembled["bundle"]["coverage"],
        }

    gate=build_edge_stock_acceptance_gate(bundles)
    result={
        "schema":"edge-stock-full-live-acceptance-v1",
        "status":"PASS",
        "captured_at":now.isoformat(),
        "shared_market_bundle_sha256":shared["bundle_sha256"],
        "cases":details,
        "acceptance_gate":gate,
        "production_activation_allowed":False,
        "methodology_applied":False,
        "recommendation_generated":False,
        "trading_enabled":False,
    }
    OUT.mkdir(parents=True,exist_ok=True)
    (OUT/"result.json").write_text(
        json.dumps(result,sort_keys=True,separators=(",",":"),default=str)+"\n",
        encoding="utf-8",
    )
    print(json.dumps(result,sort_keys=True,separators=(",",":"),default=str))
    return result

if __name__=="__main__":
    run()
