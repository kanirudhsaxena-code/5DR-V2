import pytest

from src.engine_contract import EngineRequest, EvidenceItem
from src.orchestrator import execute


def _request(**overrides):
    values = {
        "request_id": "req_test",
        "provenance_mode": "HYBRID",
        "evidence": [EvidenceItem(evidence_type="NORMALIZED", source_ref="test", normalized={"x": 1})],
    }
    values.update(overrides)
    return EngineRequest(**values)


def _valid_result():
    return {
        "model_version": "5DR_V2_1",
        "output_contract_version": "5DR_V2_1_2",
        "horizon_slots": {
            f"D+{i}": {
                "direction": "RANGE",
                "probabilities": {"BULL": 25.0, "RANGE": 50.0, "BEAR": 25.0},
                "zone_low": 23000 + i * 10,
                "zone_high": 23500 + i * 10,
                "basis": f"governed test horizon {i}",
            }
            for i in range(1, 6)
        },
    }


def test_execute_accepts_complete_calculation_contract():
    assert execute(_request(), lambda request: _valid_result())["model_version"] == "5DR_V2_1"


def test_execute_rejects_wrong_model_version():
    result = _valid_result()
    result["model_version"] = "OTHER_MODEL"
    with pytest.raises(ValueError, match="invalid model version"):
        execute(_request(), lambda request: result)


def test_execute_rejects_wrong_output_contract_version():
    result = _valid_result()
    result["output_contract_version"] = "5DR_V2_1_1"
    with pytest.raises(ValueError, match="invalid output contract version"):
        execute(_request(), lambda request: result)


def test_execute_does_not_require_post_forecast_lifecycle_fields():
    result = _valid_result()
    calculated = execute(_request(), lambda request: result)
    assert "forecast_assessment" not in calculated
    assert "recommendation_assessment" not in calculated
    assert "assessment_snapshot_complete" not in calculated
    assert "recommendation_ledger_complete" not in calculated


def test_execute_rejects_missing_horizon():
    result = _valid_result()
    del result["horizon_slots"]["D+5"]
    with pytest.raises(ValueError, match="horizon_slots must contain exactly"):
        execute(_request(), lambda request: result)


def test_execute_rejects_non_object_horizons():
    result = _valid_result()
    result["horizon_slots"] = []
    with pytest.raises(ValueError, match="horizon_slots must contain exactly"):
        execute(_request(), lambda request: result)


def test_execute_rejects_invalid_provenance():
    with pytest.raises(ValueError, match="invalid provenance mode"):
        execute(_request(provenance_mode="UNKNOWN"), lambda request: _valid_result())


def test_execute_rejects_empty_evidence():
    with pytest.raises(ValueError, match="evidence is mandatory"):
        execute(_request(evidence=[]), lambda request: _valid_result())


def test_execute_rejects_invalid_executor_result():
    with pytest.raises(ValueError, match="invalid result"):
        execute(_request(), lambda request: None)
