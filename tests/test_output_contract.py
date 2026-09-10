import pytest

from src.output_contract import validate_output_contract, OUTPUT_CONTRACT_VERSION

def test_complete_output_is_accepted():
    assert validate_output_contract(
        "5DR_V2_1", "Bearish conviction is moderate-high.", 
        "BUY_PE permitted by gate.", OUTPUT_CONTRACT_VERSION
    ) is True

@pytest.mark.parametrize(
    "forecast_assessment,recommendation_assessment,version",
    [
        ("", "trade assessment", OUTPUT_CONTRACT_VERSION),
        ("forecast assessment", "", OUTPUT_CONTRACT_VERSION),
        ("forecast assessment", "trade assessment", "5DR_V2_1"),
    ],
)
def test_incomplete_output_is_blocked(forecast_assessment, recommendation_assessment, version):
    with pytest.raises(ValueError):
        validate_output_contract(
            "5DR_V2_1", forecast_assessment,
            recommendation_assessment, version
        )

def test_legacy_model_is_not_blocked_by_new_contract():
    assert validate_output_contract("5DR_V2", None, None, None) is True
