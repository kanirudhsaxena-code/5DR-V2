"""Reconcile autonomous acquisition with the canonical V2.2.2 EvidencePacket boundary.

This gate deliberately does not translate provider observations into lifecycle
facts. Provider readiness and canonical EvidencePackets are separate proofs.
Only already-normalized packets may cross into the production lifecycle.
"""
from __future__ import annotations

from pathlib import Path

from .autonomous_acquisition import AcquisitionBlocked
from .evidence_handoff import load_packets


class AutonomousEvidenceGateBlocked(AcquisitionBlocked):
    pass


def release_normalized_evidence(envelope: dict, evidence_path: str | Path):
    """Return canonical packets only when autonomous readiness is independently proven.

    The canonical handoff validator remains authoritative for freshness,
    verification, contract matching and source type. No Upstox/provider payload
    is silently converted to SCREENSHOT or WEB_RESEARCH evidence.
    """
    if envelope.get("status") != "AUTONOMOUS_EVIDENCE_READY":
        raise AutonomousEvidenceGateBlocked("ACQUISITION_NOT_READY")
    if envelope.get("trading_enabled") is not False:
        raise AutonomousEvidenceGateBlocked("TRADING_MUST_REMAIN_DISABLED")
    if envelope.get("forecast_release_enabled") is not False:
        raise AutonomousEvidenceGateBlocked("ACQUISITION_CANNOT_SELF_AUTHORIZE_FORECAST")

    packets = load_packets(Path(evidence_path))
    if not packets:
        raise AutonomousEvidenceGateBlocked("NORMALIZED_EVIDENCE_REQUIRED")
    return packets
