"""G6/Core SHADOW shared contract. Additive only; production methodology is untouched."""

from __future__ import annotations

CORE_ZONE_HORIZONS = ("D", "D+1", "D+2", "D+3", "D+4")
CORE_ZONE_CONTRACT_VERSION = "G6-A-2026-09-26"


class CoreZoneContractError(ValueError):
    """Raised when a SHADOW Core Zone payload violates the governed contract."""


def validate_core_zone_horizons(rows: list[dict] | tuple[dict, ...]) -> None:
    """Fail closed unless rows are exactly D,D+1,D+2,D+3,D+4 in order."""
    if len(rows) != len(CORE_ZONE_HORIZONS):
        raise CoreZoneContractError("Core Zone requires exactly five ordered horizon rows")
    horizons = tuple(row.get("horizon") for row in rows)
    if horizons != CORE_ZONE_HORIZONS:
        raise CoreZoneContractError(
            f"invalid Core Zone horizons {horizons!r}; expected {CORE_ZONE_HORIZONS!r}"
        )
    if "D+5" in horizons:
        raise CoreZoneContractError("D+5 is forbidden by the G6/Core SHADOW contract")


def validate_core_zone_report(report: dict) -> None:
    """Validate minimum cross-surface/read-model invariants for a SHADOW report."""
    if report.get("mode") != "SHADOW":
        raise CoreZoneContractError("Core Zone report must remain SHADOW")
    if not report.get("run_id") or not report.get("view_model_version") or not report.get("report_hash"):
        raise CoreZoneContractError("run/version/hash lineage is required")
    validate_core_zone_horizons(report.get("horizons") or [])
