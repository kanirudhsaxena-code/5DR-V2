"""Read-only shadow harness for the 5DR V2.2.2 evidence-to-lifecycle chain."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .autonomous_acquisition import SourceObservation, build_evidence_envelope
from .autonomous_evidence_gate import AutonomousEvidenceGateBlocked, release_normalized_evidence
from .production_activation import ActivationResult, activate


@dataclass(frozen=True)
class ShadowResult:
    acquisition_status: str
    gate_status: str
    activation: ActivationResult | None
    reason: str | None = None


def run_shadow(db, evidence_path: str | Path, observations: list[SourceObservation], *, request_id: str, now=None) -> ShadowResult:
    """Exercise acquisition -> canonical firewall -> lifecycle with writes forced off."""
    envelope = build_evidence_envelope(request_id, observations, now=now)
    if envelope['status'] != 'AUTONOMOUS_EVIDENCE_READY':
        return ShadowResult(envelope['status'], 'BLOCKED', None, 'ACQUISITION_NOT_READY')

    try:
        release_normalized_evidence(envelope, evidence_path)
    except AutonomousEvidenceGateBlocked as exc:
        return ShadowResult(envelope['status'], 'BLOCKED', None, str(exc))

    activation = activate(db, evidence_path, writes_enabled=False)
    if activation.writes_enabled or activation.mode != 'DRY_RUN':
        raise RuntimeError('SHADOW_WRITE_FIREWALL_BREACH')
    return ShadowResult(envelope['status'], 'CANONICAL_EVIDENCE_READY', activation)
