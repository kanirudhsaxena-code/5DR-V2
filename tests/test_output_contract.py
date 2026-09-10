import pytest

from src.output_contract import (
    LEGACY_OUTPUT_CONTRACT_VERSION,
    OUTPUT_CONTRACT_VERSION,
    validate_output_contract,
)


FULL_HORIZONS = {f"D+{i}": {} for i in range(1, 6)}


def test_complete_v212_output_is_accepted():
    assert validate_output_contract(
        "5DR_V2_1", "forecast assessment", "recommendation assessment",
        OUTPUT_CONTRACT_VERSION,
        assessment_snapshot_complete=True,
        horizon_slots=FULL_HORIZONS,
        recommendation_ledger_complete=True,
    ) is True


@pytest.mark.parametrize(
    "kwargs",
    [
        {"forecast_assessment": ""},
        {"recommendation_assessment": ""},
        {"output_contract_version": LEGACY_OUTPUT_CONTRACT_VERSION},
        {"assessment_snapshot_complete": False},
        {"horizon_slots": {"D+1": {}}},
        {"recommendation_ledger_complete": False},
    ],
)
def test_incomplete_v212_output_is_blocked(kwargs):
    params = dict(
        model_version="5DR_V2_1",
        forecast_assessment="forecast assessment",
        recommendation_assessment="recommendation assessment",
        output_contract_version=OUTPUT_CONTRACT_VERSION,
        assessment_snapshot_complete=True,
        horizon_slots=FULL_HORIZONS,
        recommendation_ledger_complete=True,
    )
    params.update(kwargs)
    with pytest.raises(ValueError):
        validate_output_contract(**params)


def test_historical_v211_can_still_be_validated():
    assert validate_output_contract(
        "5DR_V2_1", "forecast assessment", "recommendation assessment",
        LEGACY_OUTPUT_CONTRACT_VERSION, historical=True,
    ) is True


def test_legacy_model_is_not_blocked():
    assert validate_output_contract("5DR_V2", None, None, None) is True
