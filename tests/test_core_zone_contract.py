import pytest

from src.core_zone_contract import (
    CORE_ZONE_HORIZONS,
    CoreZoneContractError,
    validate_core_zone_horizons,
    validate_core_zone_report,
)


def rows(*horizons):
    return [{"horizon": h} for h in horizons]


def test_exact_authoritative_horizons_pass():
    validate_core_zone_horizons(rows(*CORE_ZONE_HORIZONS))


@pytest.mark.parametrize(
    "bad",
    [
        ("D+1", "D+2", "D+3", "D+4", "D+5"),
        ("D", "D+1", "D+2", "D+3"),
        ("D", "D+2", "D+1", "D+3", "D+4"),
        ("D", "D+1", "D+2", "D+3", "D+4", "D+5"),
        ("D", "D+1", "D+2", "D+3", "D+3"),
    ],
)
def test_horizon_deviation_fails_closed(bad):
    with pytest.raises(CoreZoneContractError):
        validate_core_zone_horizons(rows(*bad))


def test_report_requires_shadow_and_exact_lineage():
    report = {
        "mode": "SHADOW",
        "run_id": "run-1",
        "view_model_version": "core-zone-v1",
        "report_hash": "abc123",
        "horizons": rows(*CORE_ZONE_HORIZONS),
    }
    validate_core_zone_report(report)

    for field in ("run_id", "view_model_version", "report_hash"):
        broken = dict(report)
        broken[field] = None
        with pytest.raises(CoreZoneContractError):
            validate_core_zone_report(broken)

    production = dict(report, mode="PRODUCTION")
    with pytest.raises(CoreZoneContractError):
        validate_core_zone_report(production)
