"""On-demand EDGE_STOCK evidence orchestrator.

Acquisition is delegated to provider/research adapters. This layer assembles only facts
into the shared frozen bundle and remains independent of EDGE intelligence semantics.
"""
from copy import deepcopy
from datetime import datetime

from experiments.data_contract import DataArchitectureError, build_record
from experiments.edge_stock_bundle import build_edge_stock_bundle, verify_edge_stock_bundle

REQUIRED_RESEARCH_VARIABLES = {
    "STOCK_FORWARD_CATALYSTS",
    "STOCK_GOVERNANCE_RISK",
    "STOCK_INSTITUTIONAL_EVENTS",
}
FALLBACK_RESEARCH_VARIABLES = {"STOCK_PEERS"}
ALLOWED_RESEARCH_VARIABLES = REQUIRED_RESEARCH_VARIABLES | FALLBACK_RESEARCH_VARIABLES


def build_shared_macro_record(*, stock_identity, macro_evidence, acquisition_timestamp):
    if not isinstance(stock_identity, dict) or stock_identity.get("kind") != "STOCK":
        raise DataArchitectureError("EDGE_STOCK macro stock identity invalid")
    if not isinstance(macro_evidence, dict):
        raise DataArchitectureError("EDGE_STOCK shared macro evidence missing")
    source_sha256 = macro_evidence.get("source_sha256")
    source_reference = macro_evidence.get("source_reference")
    observed_at = macro_evidence.get("observed_at")
    values = macro_evidence.get("values")
    if not isinstance(source_sha256, str) or len(source_sha256) != 64:
        raise DataArchitectureError("EDGE_STOCK shared macro digest invalid")
    if not isinstance(source_reference, str) or not source_reference:
        raise DataArchitectureError("EDGE_STOCK shared macro source invalid")
    if not isinstance(observed_at, (str, datetime)):
        raise DataArchitectureError("EDGE_STOCK shared macro timestamp invalid")
    if not isinstance(values, dict):
        raise DataArchitectureError("EDGE_STOCK shared macro values invalid")
    return build_record(
        provider_id="SHARED_MARKET_CORE",
        source_semantic="SHARED_MARKET_CORE",
        variable_id="STOCK_RELEVANT_MACRO",
        consumer="EDGE_STOCK",
        subject=stock_identity,
        metric="stock_relevant_macro_fact_set",
        values={
            "values": deepcopy(values),
            "transmission_channels": deepcopy(macro_evidence.get("transmission_channels", [])),
            "judgment_applied": False,
        },
        timeframe="snapshot",
        provider_timestamp=observed_at,
        acquisition_timestamp=acquisition_timestamp,
        freshness_status="LIVE",
        source_reference=source_reference,
        source_sha256=source_sha256,
    )


def assemble_edge_stock_bundle(*, core_acquisition, research_records,
                               macro_record, run_id, frozen_at):
    if not isinstance(core_acquisition, dict):
        raise DataArchitectureError("EDGE_STOCK core acquisition missing")
    stock = core_acquisition.get("stock_identity")
    fo = core_acquisition.get("fo_identity")
    records = core_acquisition.get("records")
    if not isinstance(records, list):
        raise DataArchitectureError("EDGE_STOCK core records missing")
    if core_acquisition.get("read_only") is not True:
        raise DataArchitectureError("EDGE_STOCK core acquisition not read-only")
    if core_acquisition.get("methodology_applied") is not False:
        raise DataArchitectureError("EDGE_STOCK methodology leaked into acquisition")

    if not isinstance(research_records, (list, tuple)):
        raise DataArchitectureError("EDGE_STOCK research records invalid")
    research_by_variable = {}
    for record in research_records:
        if not isinstance(record, dict):
            raise DataArchitectureError("EDGE_STOCK research record invalid")
        variable_id = record.get("variable_id")
        if variable_id not in ALLOWED_RESEARCH_VARIABLES:
            raise DataArchitectureError("unexpected EDGE_STOCK research variable")
        if variable_id in research_by_variable:
            raise DataArchitectureError("duplicate EDGE_STOCK research variable")
        if record.get("consumer") != "EDGE_STOCK":
            raise DataArchitectureError("cross-consumer research contamination")
        if record.get("subject", {}).get("id") != stock.get("id"):
            raise DataArchitectureError("cross-stock research contamination")
        research_by_variable[variable_id] = record
    missing_research = sorted(REQUIRED_RESEARCH_VARIABLES - set(research_by_variable))
    if missing_research:
        raise DataArchitectureError(f"EDGE_STOCK research variables missing: {missing_research}")

    if not isinstance(macro_record, dict) or macro_record.get("variable_id") != "STOCK_RELEVANT_MACRO":
        raise DataArchitectureError("EDGE_STOCK macro record invalid")
    if macro_record.get("consumer") != "EDGE_STOCK":
        raise DataArchitectureError("EDGE_STOCK macro consumer invalid")
    if macro_record.get("subject", {}).get("id") != stock.get("id"):
        raise DataArchitectureError("EDGE_STOCK macro subject invalid")

    core_variables = {record.get("variable_id") for record in records if isinstance(record, dict)}
    provider_gaps = {
        row.get("variable_id")
        for row in core_acquisition.get("provider_gaps", [])
        if isinstance(row, dict) and row.get("fallback_required") is True
    }
    fallback_records = []
    for variable_id in FALLBACK_RESEARCH_VARIABLES:
        fallback = research_by_variable.get(variable_id)
        if variable_id in core_variables:
            if fallback is not None:
                raise DataArchitectureError("unnecessary EDGE_STOCK fallback duplicates provider evidence")
            continue
        if variable_id not in provider_gaps:
            raise DataArchitectureError("EDGE_STOCK missing variable lacks explicit provider gap")
        if fallback is None:
            raise DataArchitectureError(f"EDGE_STOCK fallback evidence missing: {variable_id}")
        if fallback.get("values", {}).get("reconciliation_status") != "RECOVERED_VIA_FALLBACK":
            raise DataArchitectureError("EDGE_STOCK fallback status invalid")
        fallback_records.append(fallback)

    required_research_records = [
        research_by_variable[variable_id]
        for variable_id in sorted(REQUIRED_RESEARCH_VARIABLES)
    ]
    all_records = list(records) + required_research_records + fallback_records + [macro_record]
    bundle = build_edge_stock_bundle(
        stock_identity=stock,
        fo_identity=fo,
        run_id=run_id,
        frozen_at=frozen_at,
        quantitative_records=all_records,
    )
    summary = verify_edge_stock_bundle(bundle) if bundle["status"] == "READY" else None
    return {
        "bundle": bundle,
        "verification": summary,
        "status": bundle["status"],
        "stock_identity": deepcopy(stock),
        "fo_identity": deepcopy(fo),
        "methodology_applied": False,
        "recommendation_generated": False,
        "trading_enabled": False,
    }
