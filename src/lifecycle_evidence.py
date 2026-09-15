"""Strict evidence adapter for 5DR V2.2.2 lifecycle accounting."""
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timezone

@dataclass(frozen=True)
class OptionEvidence:
    instrument: str
    strike: float
    expiry: str
    premium: float
    observed_at: datetime
    source_ref: str
    continuous_path: bool = False

    def validate_for(self, *, instrument: str, strike: float, expiry: str) -> None:
        if self.instrument != instrument:
            raise ValueError("instrument mismatch")
        if float(self.strike) != float(strike):
            raise ValueError("strike mismatch")
        if self.expiry != expiry:
            raise ValueError("expiry mismatch")
        if self.premium <= 0:
            raise ValueError("premium must be positive")
        if not self.source_ref.strip():
            raise ValueError("source_ref required")
        if self.observed_at.tzinfo is None:
            raise ValueError("observed_at must be timezone-aware")
        if self.observed_at > datetime.now(timezone.utc):
            raise ValueError("future evidence rejected")


def path_can_close(evidence: OptionEvidence) -> bool:
    """Terminal ordering requires continuous/ordered evidence, not a lone snapshot."""
    return evidence.continuous_path
