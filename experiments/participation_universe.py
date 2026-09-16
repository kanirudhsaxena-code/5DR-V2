"""Explicit Participation-engine acquisition universe for V2.2.3.

The canonical specification requires an *approved* NIFTY heavyweight and sector-index
set but does not enumerate exact instrument identities. This module deliberately has
no implicit defaults: choosing constituents or sector indices changes what the
Participation engine sees and therefore must not be invented by the acquisition layer.
"""
from dataclasses import dataclass

from experiments.data_contract import DataArchitectureError


@dataclass(frozen=True)
class ParticipationUniverse:
    heavyweight_keys: tuple[str, ...]
    sector_index_keys: tuple[str, ...]
    approval_ref: str

    def describe(self):
        return {
            "heavyweight_count": len(self.heavyweight_keys),
            "sector_index_count": len(self.sector_index_keys),
            "approval_ref": self.approval_ref,
            "methodology_changed": False,
            "screening_enabled": False,
        }


def _exact_unique(values, prefix, field):
    if not isinstance(values, (list, tuple)) or not values:
        raise DataArchitectureError(f"{field} approval missing")
    cleaned = []
    for value in values:
        if not isinstance(value, str) or not value.strip():
            raise DataArchitectureError(f"{field} identity invalid")
        value = value.strip()
        if not value.startswith(prefix):
            raise DataArchitectureError(f"{field} identity outside allowed segment")
        cleaned.append(value)
    if len(cleaned) != len(set(cleaned)):
        raise DataArchitectureError(f"{field} duplicate identity")
    return tuple(cleaned)


def build_participation_universe(*, heavyweight_keys, sector_index_keys, approval_ref):
    if not isinstance(approval_ref, str) or not approval_ref.strip():
        raise DataArchitectureError("participation universe approval reference missing")
    heavyweights = _exact_unique(heavyweight_keys, "NSE_EQ|", "heavyweight")
    sectors = _exact_unique(sector_index_keys, "NSE_INDEX|", "sector index")
    return ParticipationUniverse(heavyweights, sectors, approval_ref.strip())


def unresolved_participation_gate():
    """Machine-readable fail-closed state until exact identities are explicitly approved."""
    return {
        "status": "BLOCKED",
        "blocker": "PARTICIPATION_UNIVERSE_NOT_EXPLICITLY_APPROVED",
        "missing_variables": ["NIFTY_HEAVYWEIGHTS", "NIFTY_SECTOR_INDICES"],
        "screening_enabled": False,
        "methodology_changed": False,
    }
