"""V2.2.2 evidence bridge for screenshot and deep-web research packets.

The module normalizes evidence already produced/verified by the 5DR intelligence
layer. It does not scrape the web, inspect images, call brokers, or place orders.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Literal

from .lifecycle_evidence import OptionEvidence

SourceType = Literal['SCREENSHOT', 'WEB_RESEARCH']


class EvidenceBridgeError(ValueError):
    """Evidence is insufficient for lifecycle persistence."""


@dataclass(frozen=True)
class EvidencePacket:
    forecast_id: str
    source_type: SourceType
    source_ref: str
    observed_at: datetime
    captured_at: datetime
    instrument: str
    strike: float | None = None
    expiry: str | None = None
    premium: float | None = None
    verified: bool = False
    fresh: bool = False
    contract_matched: bool = False
    continuous_path: bool = False
    notes: str | None = None

    def validate(self) -> None:
        if self.source_type not in {'SCREENSHOT', 'WEB_RESEARCH'}:
            raise EvidenceBridgeError('SOURCE_NOT_ALLOWED')
        if not self.forecast_id or not self.source_ref or not self.instrument:
            raise EvidenceBridgeError('PROVENANCE_INCOMPLETE')
        for stamp in (self.observed_at, self.captured_at):
            if stamp.tzinfo is None or stamp.utcoffset() is None:
                raise EvidenceBridgeError('TIMESTAMP_NOT_TIMEZONE_AWARE')
        if self.observed_at > self.captured_at:
            raise EvidenceBridgeError('OBSERVATION_AFTER_CAPTURE')
        if not self.verified:
            raise EvidenceBridgeError('EVIDENCE_NOT_VERIFIED')
        if not self.fresh:
            raise EvidenceBridgeError('EVIDENCE_STALE')
        if self.premium is not None:
            if self.premium < 0:
                raise EvidenceBridgeError('PREMIUM_INVALID')
            if self.strike is None or not self.expiry or not self.contract_matched:
                raise EvidenceBridgeError('OPTION_CONTRACT_NOT_MATCHED')

    def to_option_evidence(self) -> OptionEvidence:
        self.validate()
        if self.premium is None or self.strike is None or not self.expiry:
            raise EvidenceBridgeError('OPTION_PREMIUM_MISSING')
        return OptionEvidence(
            instrument=self.instrument,
            strike=self.strike,
            expiry=self.expiry,
            premium=self.premium,
            observed_at=self.observed_at,
            source_ref=self.source_ref,
            continuous_path=self.continuous_path,
        )


def no_write_reason(packet: EvidencePacket) -> str | None:
    """Return a stable fail-closed reason instead of raising for orchestration."""
    try:
        packet.validate()
    except EvidenceBridgeError as exc:
        return str(exc)
    return None
