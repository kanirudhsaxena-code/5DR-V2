"""Explicit Participation-engine acquisition universe for V2.2.3.

The canonical specification requires an approved NIFTY heavyweight and sector-index
set. This module binds the user-approved 16 Sep 2026 universe to exact Upstox
instrument identities. It does not change DES5 weights, screening, forecasting,
tradeability, Learning Lab rules or any other methodology semantics.
"""
from dataclasses import dataclass

from experiments.data_contract import DataArchitectureError

APPROVAL_REF = "user-explicit-2026-09-16-participation-v1"

APPROVED_HEAVYWEIGHT_KEYS = (
    "NSE_EQ|INE040A01034",  # HDFCBANK
    "NSE_EQ|INE090A01021",  # ICICIBANK
    "NSE_EQ|INE002A01018",  # RELIANCE
    "NSE_EQ|INE397D01024",  # BHARTIARTL
    "NSE_EQ|INE018A01030",  # LT
    "NSE_EQ|INE062A01020",  # SBIN
    "NSE_EQ|INE009A01021",  # INFY
    "NSE_EQ|INE238A01034",  # AXISBANK
)

APPROVED_SECTOR_INDEX_KEYS = (
    "NSE_INDEX|Nifty Fin Service",
    "NSE_INDEX|NIFTY OIL AND GAS",
    "NSE_INDEX|Nifty IT",
    "NSE_INDEX|Nifty Auto",
)


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


def approved_participation_universe():
    universe = build_participation_universe(
        heavyweight_keys=APPROVED_HEAVYWEIGHT_KEYS,
        sector_index_keys=APPROVED_SECTOR_INDEX_KEYS,
        approval_ref=APPROVAL_REF,
    )
    if len(universe.heavyweight_keys) != 8 or len(universe.sector_index_keys) != 4:
        raise DataArchitectureError("approved participation universe cardinality mismatch")
    return universe


def approved_participation_gate():
    universe = approved_participation_universe()
    return {
        "status": "READY",
        "approval_ref": universe.approval_ref,
        "heavyweight_keys": list(universe.heavyweight_keys),
        "sector_index_keys": list(universe.sector_index_keys),
        "missing_variables": [],
        "screening_enabled": False,
        "methodology_changed": False,
    }


def unresolved_participation_gate():
    """Legacy fail-closed state retained for tests/backward audit only."""
    return {
        "status": "BLOCKED",
        "blocker": "PARTICIPATION_UNIVERSE_NOT_EXPLICITLY_APPROVED",
        "missing_variables": ["NIFTY_HEAVYWEIGHTS", "NIFTY_SECTOR_INDICES"],
        "screening_enabled": False,
        "methodology_changed": False,
    }
