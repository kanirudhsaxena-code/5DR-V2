"""Market Trust acquisition corroboration boundary.

NIFTY-only Upstox observations are insufficient to declare Market Trust
complete. This module requires independent governed cross-market provenance.
It does not compute or alter the framework's Market Trust score.
"""
import hashlib
import json
from datetime import datetime, timezone

from src.autonomous_acquisition import AcquisitionBlocked, SourceObservation


def corroborate_market_trust(primary: SourceObservation, cross_market_refs: list[str], *, degraded: bool = False) -> SourceObservation:
    if primary.category != "MARKET_TRUST" or primary.status not in {"VERIFIED", "DEGRADED"} or not primary.source_ref:
        raise AcquisitionBlocked("PRIMARY_MARKET_TRUST_INVALID")
    refs = sorted({ref.strip() for ref in cross_market_refs if isinstance(ref, str) and ref.strip()})
    if not refs:
        raise AcquisitionBlocked("CROSS_MARKET_PROVENANCE_MISSING")
    digest = hashlib.sha256(json.dumps([primary.source_ref, *refs], separators=(",", ":")).encode()).hexdigest()
    return SourceObservation(
        category="MARKET_TRUST",
        status="DEGRADED" if degraded else "VERIFIED",
        source_ref=f"derived:market-trust-corroboration#sha256={digest}",
        retrieved_at=datetime.now(timezone.utc).isoformat(),
        authority="SYSTEM_CORROBORATED",
        fallback_used=degraded,
        detail=f"Market Trust provenance corroborated across authenticated NIFTY observation plus {len(refs)} governed cross-market source(s)",
    )
