"""EDGE_STOCK wrapper around the shared consumer-neutral evidence backbone.

This module adds stock-specific coverage rules only. It contains no EDGE scoring,
weights, probability logic, recommendation semantics, persistence, or trading.
"""
from copy import deepcopy

from experiments.data_contract import DataArchitectureError
from experiments.shared_evidence_bundle import (
    build_shared_evidence_bundle,
    verify_shared_evidence_bundle,
)

BASE_REQUIRED_VARIABLES = frozenset({
    "STOCK_PRICE_CANDLES",
    "STOCK_RELATIVE_STRENGTH",
    "STOCK_FUNDAMENTALS",
    "STOCK_SHAREHOLDING",
    "STOCK_PEERS",
    "STOCK_CORPORATE_ACTIONS",
    "STOCK_NEWS_RECENT",
    "STOCK_FORWARD_CATALYSTS",
    "STOCK_GOVERNANCE_RISK",
    "STOCK_INSTITUTIONAL_EVENTS",
    "STOCK_RELEVANT_MACRO",
})


def edge_stock_required_variables(*, fo_eligible):
    if not isinstance(fo_eligible, bool):
        raise DataArchitectureError("EDGE_STOCK F&O eligibility invalid")
    required = set(BASE_REQUIRED_VARIABLES)
    if fo_eligible:
        required.add("STOCK_OPTIONS")
    return frozenset(required)


def build_edge_stock_bundle(*, stock_identity, fo_identity, run_id, frozen_at,
                            quantitative_records, external_evidence=(),
                            required_external_categories=()):
    if not isinstance(stock_identity, dict) or stock_identity.get("kind") != "STOCK":
        raise DataArchitectureError("EDGE_STOCK identity invalid")
    subject_id = stock_identity.get("id")
    if not isinstance(subject_id, str) or not subject_id:
        raise DataArchitectureError("EDGE_STOCK stable identity missing")
    if not isinstance(fo_identity, dict) or not isinstance(fo_identity.get("fo_eligible"), bool):
        raise DataArchitectureError("EDGE_STOCK F&O identity invalid")
    if fo_identity.get("underlying_key") != stock_identity.get("instrument_key"):
        raise DataArchitectureError("EDGE_STOCK F&O underlying mismatch")

    derived = {
        "schema": "edge-stock-evidence-context-v1",
        "stock_identity": deepcopy(stock_identity),
        "fo_identity": deepcopy(fo_identity),
        "methodology_applied": False,
        "scoring_applied": False,
        "recommendation_generated": False,
    }
    bundle = build_shared_evidence_bundle(
        consumer="EDGE_STOCK",
        subject=stock_identity,
        run_id=run_id,
        frozen_at=frozen_at,
        quantitative_records=quantitative_records,
        external_evidence=external_evidence,
        derived_evidence=derived,
        required_variables=edge_stock_required_variables(
            fo_eligible=fo_identity["fo_eligible"]
        ),
        required_external_categories=required_external_categories,
        require_screenshot_free=True,
    )
    return bundle


def verify_edge_stock_bundle(bundle):
    summary = verify_shared_evidence_bundle(bundle)
    if summary["consumer"] != "EDGE_STOCK":
        raise DataArchitectureError("EDGE_STOCK bundle consumer mismatch")
    context = bundle.get("derived_evidence")
    if not isinstance(context, dict) or context.get("schema") != "edge-stock-evidence-context-v1":
        raise DataArchitectureError("EDGE_STOCK context missing")
    for flag in ("methodology_applied", "scoring_applied", "recommendation_generated"):
        if context.get(flag) is not False:
            raise DataArchitectureError("EDGE_STOCK backbone crossed intelligence boundary")
    return summary
