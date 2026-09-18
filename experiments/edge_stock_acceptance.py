"""Representative acceptance gate for EDGE_STOCK evidence bundles.

This is a data-backbone gate only. It does not score stocks or issue recommendations.
"""
import hashlib
import json

from experiments.data_contract import DataArchitectureError
from experiments.edge_stock_bundle import verify_edge_stock_bundle

REQUIRED_CASES = {"LTF", "LARGE_LIQUID_FO", "NON_FO"}


def build_edge_stock_acceptance_gate(cases):
    if not isinstance(cases, dict) or set(cases) != REQUIRED_CASES:
        raise DataArchitectureError("EDGE_STOCK acceptance case set invalid")

    results = {}
    for label, bundle in cases.items():
        summary = verify_edge_stock_bundle(bundle)
        if summary["status"] != "READY":
            raise DataArchitectureError(f"EDGE_STOCK acceptance case not READY: {label}")
        context = bundle["derived_evidence"]
        fo = context["fo_identity"]
        if label in {"LTF", "LARGE_LIQUID_FO"} and fo.get("fo_eligible") is not True:
            raise DataArchitectureError(f"EDGE_STOCK F&O acceptance identity invalid: {label}")
        if label == "NON_FO" and fo.get("fo_eligible") is not False:
            raise DataArchitectureError("EDGE_STOCK non-F&O acceptance identity invalid")
        if bundle.get("screenshot_policy", {}).get("screenshot_dependency") is not False:
            raise DataArchitectureError("EDGE_STOCK acceptance still depends on screenshot")
        results[label] = {
            "consumer": summary["consumer"],
            "subject_id": summary["subject_id"],
            "bundle_sha256": summary["bundle_sha256"],
            "fo_eligible": fo["fo_eligible"],
            "status": "PASS",
        }

    gate = {
        "schema": "edge-stock-backbone-acceptance-gate-v1",
        "status": "PASS",
        "cases": results,
        "checks": {
            "consumer_isolation": "PASS",
            "subject_identity": "PASS",
            "required_variable_coverage": "PASS",
            "fo_conditionality": "PASS",
            "screenshot_free": "PASS",
            "provenance_integrity": "PASS",
            "methodology_applied": False,
            "recommendation_generated": False,
            "trading_enabled": False,
            "production_activation_allowed": False,
        },
    }
    encoded = json.dumps(gate, sort_keys=True, separators=(",", ":")).encode()
    gate["gate_sha256"] = hashlib.sha256(encoded).hexdigest()
    return gate
