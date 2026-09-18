"""G11 manual shadow-pair comparability guard.

This validation boundary allows a bounded timestamp difference between the structured
snapshot and screenshot-assisted reference from the same explicitly approved manual run.
It never changes forecasting methodology or makes an acceptance decision.
"""
from datetime import datetime
from zoneinfo import ZoneInfo

from experiments.data_contract import DataArchitectureError

SCHEMA = "5dr-v2-2-3-shadow-pair-comparability-v2"
IST = ZoneInfo("Asia/Kolkata")
DEFAULT_PREFERRED_DELTA_SECONDS = 180
DEFAULT_MAX_DELTA_SECONDS = 300


def _text(record, key):
    value = record.get(key) if isinstance(record, dict) else None
    if not isinstance(value, str) or not value.strip():
        raise DataArchitectureError(f"shadow pair {key} missing")
    return value.strip()


def _aware(record, key):
    value = _text(record, key)
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise DataArchitectureError(f"shadow pair {key} invalid") from error
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise DataArchitectureError(f"shadow pair {key} timezone missing")
    return parsed.astimezone(IST)


def assess_pair_comparability(reference, structured, *,
                              preferred_delta_seconds=DEFAULT_PREFERRED_DELTA_SECONDS,
                              max_delta_seconds=DEFAULT_MAX_DELTA_SECONDS):
    if not isinstance(preferred_delta_seconds, int) or not isinstance(max_delta_seconds, int):
        raise DataArchitectureError("shadow pair timing tolerance invalid")
    if preferred_delta_seconds < 0 or max_delta_seconds < preferred_delta_seconds:
        raise DataArchitectureError("shadow pair timing tolerance invalid")
    reference_window = _text(reference, "comparison_window_id")
    structured_window = _text(structured, "comparison_window_id")
    reference_cutoff = _aware(reference, "evidence_cutoff_ist")
    structured_cutoff = _aware(structured, "evidence_cutoff_ist")

    reasons = []
    if reference_window != structured_window:
        reasons.append("COMPARISON_WINDOW_ID_MISMATCH")
    delta_seconds = abs((reference_cutoff - structured_cutoff).total_seconds())
    if delta_seconds > max_delta_seconds:
        reasons.append("EVIDENCE_TIME_DELTA_EXCEEDS_TOLERANCE")

    comparable = not reasons
    timing_quality = None
    if comparable:
        timing_quality = "PREFERRED" if delta_seconds <= preferred_delta_seconds else "WITHIN_TOLERANCE"
    return {
        "schema": SCHEMA,
        "status": "COMPARABLE" if comparable else "NOT_COMPARABLE",
        "acceptance_eligible": comparable,
        "comparison_window_id": reference_window if comparable else None,
        "reference_evidence_cutoff_ist": reference_cutoff.isoformat(),
        "structured_evidence_cutoff_ist": structured_cutoff.isoformat(),
        "pair_delta_seconds": round(delta_seconds, 3),
        "timing_quality": timing_quality,
        "preferred_delta_seconds": preferred_delta_seconds,
        "max_delta_seconds": max_delta_seconds,
        "reasons": reasons,
    }
