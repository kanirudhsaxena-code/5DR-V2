"""Governed web/event research evidence producer for 5DR V2.2.2.

This module accepts observations from an approved external research executor.
It does not claim that HTTP reachability proves market facts. Research facts
must arrive with provenance, authority and timestamps and are emitted only as
WEB_RESEARCH EvidencePackets after strict validation.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
from typing import Iterable

from .evidence_bridge import EvidencePacket


class WebResearchBlocked(ValueError):
    pass


@dataclass(frozen=True)
class ResearchObservation:
    source_name: str
    source_ref: str
    authority: str
    observed_at: datetime
    captured_at: datetime
    fact: str
    verified: bool

    def validate(self, *, now: datetime, max_age_seconds: int = 900) -> None:
        if not all((self.source_name.strip(), self.source_ref.strip(), self.authority.strip(), self.fact.strip())):
            raise WebResearchBlocked('RESEARCH_PROVENANCE_INCOMPLETE')
        if not self.verified:
            raise WebResearchBlocked('RESEARCH_NOT_VERIFIED')
        for stamp in (self.observed_at, self.captured_at):
            if stamp.tzinfo is None or stamp.utcoffset() is None:
                raise WebResearchBlocked('RESEARCH_TIMESTAMP_NAIVE')
        if self.observed_at > self.captured_at:
            raise WebResearchBlocked('RESEARCH_OBSERVATION_AFTER_CAPTURE')
        age = (now.astimezone(timezone.utc) - self.captured_at.astimezone(timezone.utc)).total_seconds()
        if age < -60 or age > max_age_seconds:
            raise WebResearchBlocked('RESEARCH_STALE')


def build_web_research_packet(
    forecast_id: str,
    instrument: str,
    observations: Iterable[ResearchObservation],
    *,
    now: datetime | None = None,
) -> EvidencePacket:
    """Create one canonical non-price WEB_RESEARCH packet.

    This packet proves research provenance/readiness only. It deliberately does
    not invent option premium, strike, expiry, contract match or continuous path.
    Therefore it cannot close or mark an option lifecycle event by itself.
    """
    if not forecast_id.strip() or not instrument.strip():
        raise WebResearchBlocked('RESEARCH_BINDING_INCOMPLETE')
    now = now or datetime.now(timezone.utc)
    items = list(observations)
    if not items:
        raise WebResearchBlocked('RESEARCH_EMPTY')
    for item in items:
        item.validate(now=now)
    authorities = {item.authority for item in items}
    if not authorities:
        raise WebResearchBlocked('RESEARCH_AUTHORITY_MISSING')
    canonical = '\n'.join(sorted(f'{i.source_name}|{i.source_ref}|{i.authority}|{i.fact}' for i in items))
    digest = sha256(canonical.encode()).hexdigest()
    observed_at = max(i.observed_at for i in items)
    captured_at = max(i.captured_at for i in items)
    packet = EvidencePacket(
        forecast_id=forecast_id,
        source_type='WEB_RESEARCH',
        source_ref=f'5dr:web-research#sha256={digest}',
        observed_at=observed_at,
        captured_at=captured_at,
        instrument=instrument,
        verified=True,
        fresh=True,
        contract_matched=False,
        continuous_path=False,
        notes=f'Governed research bundle; sources={len(items)}; authorities={len(authorities)}',
    )
    packet.validate()
    return packet
