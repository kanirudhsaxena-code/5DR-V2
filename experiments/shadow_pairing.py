"""G11 shadow-pair comparability guard.

This is a quality-control boundary, not forecasting methodology. A structured shadow
and screenshot-assisted reference may be compared for acceptance only when the
orchestrator has bound both to the same declared comparison window and evidence cutoff.
Otherwise the result is observational only.
"""
from experiments.data_contract import DataArchitectureError

SCHEMA = "5dr-v2-2-3-shadow-pair-comparability-v1"


def _text(record, key):
    value = record.get(key) if isinstance(record, dict) else None
    if not isinstance(value, str) or not value.strip():
        raise DataArchitectureError(f"shadow pair {key} missing")
    return value.strip()


def assess_pair_comparability(reference, structured):
    reference_window = _text(reference, "comparison_window_id")
    structured_window = _text(structured, "comparison_window_id")
    reference_cutoff = _text(reference, "evidence_cutoff_ist")
    structured_cutoff = _text(structured, "evidence_cutoff_ist")

    reasons = []
    if reference_window != structured_window:
        reasons.append("COMPARISON_WINDOW_ID_MISMATCH")
    if reference_cutoff != structured_cutoff:
        reasons.append("EVIDENCE_CUTOFF_MISMATCH")

    comparable = not reasons
    return {
        "schema": SCHEMA,
        "status": "COMPARABLE" if comparable else "NOT_COMPARABLE",
        "acceptance_eligible": comparable,
        "comparison_window_id": reference_window if comparable else None,
        "evidence_cutoff_ist": reference_cutoff if comparable else None,
        "reasons": reasons,
    }
