"""Adapter from the hardened read-only Upstox client to governed 5DR evidence.

No scoring or forecast semantics live here. Provider payloads remain inside the
acquisition process; the Console receives only bounded provenance observations.
"""
from datetime import datetime, timezone

from phase1.upstox import NIFTY, ReadOnlyClient, PipelineError
from src.autonomous_acquisition import SourceObservation


def _source_ref(envelope: dict) -> str:
    path = envelope.get("source_path")
    digest = envelope.get("sha256")
    if not isinstance(path, str) or not path or not isinstance(digest, str) or len(digest) != 64:
        raise PipelineError("Unexpected Upstox response schema")
    return f"upstox:{path}#sha256={digest}"


def acquire_market_observations(client: ReadOnlyClient, expiry: str) -> list[SourceObservation]:
    """Acquire bounded NIFTY market/derivatives provenance for downstream research.

    MARKET_TRUST is marked DEGRADED here because NIFTY + derivatives alone are
    not the full cross-market/breadth Market Trust layer. A later registry stage
    must corroborate it before forecast release.
    """
    intraday = client.intraday()
    chain = client.chain(expiry)
    now = datetime.now(timezone.utc).isoformat()
    return [
        SourceObservation(
            category="MARKET_TRUST",
            status="DEGRADED",
            source_ref=_source_ref(intraday),
            retrieved_at=intraday.get("received_at", now),
            authority="UPSTOX_AUTHENTICATED",
            detail=f"Authenticated read-only market observation for {NIFTY}; cross-market corroboration still required",
        ),
        SourceObservation(
            category="EXECUTION_RISK",
            status="DEGRADED",
            source_ref=_source_ref(chain),
            retrieved_at=chain.get("received_at", now),
            authority="UPSTOX_AUTHENTICATED",
            detail=f"Authenticated NIFTY option-chain observation for expiry {expiry}; execution risk remains system-derived",
        ),
    ]
