"""Derive execution-risk provenance from verified market observations.

This does not calculate the 5DR execution score or alter thresholds. It only
proves that the inputs needed by the downstream execution layer have governed
provenance.
"""
import hashlib
import json
from datetime import datetime, timezone

from src.autonomous_acquisition import AcquisitionBlocked, SourceObservation


def derive_execution_risk(market_items: list[SourceObservation]) -> SourceObservation:
    usable = [item for item in market_items if item.category == "EXECUTION_RISK" and item.status in {"VERIFIED", "DEGRADED"} and item.source_ref]
    if not usable:
        raise AcquisitionBlocked("EXECUTION_INPUT_PROVENANCE_MISSING")
    refs = sorted(item.source_ref for item in usable)
    digest = hashlib.sha256(json.dumps(refs, separators=(",", ":")).encode()).hexdigest()
    return SourceObservation(
        category="EXECUTION_RISK",
        status="DEGRADED" if any(item.status == "DEGRADED" for item in usable) else "VERIFIED",
        source_ref=f"derived:execution-input-provenance#sha256={digest}",
        retrieved_at=datetime.now(timezone.utc).isoformat(),
        authority="SYSTEM_DERIVED",
        fallback_used=any(item.fallback_used for item in usable),
        detail="Execution-risk input provenance derived from authenticated market observations; downstream 5DR execution logic remains authoritative",
    )
