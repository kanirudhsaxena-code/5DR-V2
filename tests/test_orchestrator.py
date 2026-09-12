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
        "forecast_assessment": "assessment present",
        "recommendation_assessment": "assessment present",
        "assessment_snapshot_complete": True,
        "horizon_slots": {f"D+{i}": {} for i in range(1, 6)},
        "recommendation_ledger_complete": True,
    }


def test_execute_accepts_complete_contract():
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


def test_execute_rejects_missing_forecast_assessment():
    result = _valid_result()
    result["forecast_assessment"] = ""
    with pytest.raises(ValueError):
        execute(_request(), lambda request: result)


def test_execute_rejects_missing_recommendation_assessment():
    result = _valid_result()
    result["recommendation_assessment"] = ""
    with pytest.raises(ValueError):
        execute(_request(), lambda request: result)


def test_execute_rejects_incomplete_snapshot():
    result = _valid_result()
    result["assessment_snapshot_complete"] = False
    with pytest.raises(ValueError):
        execute(_request(), lambda request: result)


def test_execute_rejects_missing_horizon():
    result = _valid_result()
    del result["horizon_slots"]["D+5"]
    with pytest.raises(ValueError):
        execute(_request(), lambda request: result)


def test_execute_rejects_incomplete_recommendation_ledger():
    result = _valid_result()
    result["recommendation_ledger_complete"] = False
    with pytest.raises(ValueError):
        execute(_request(), lambda request: result)


def test_execute_rejects_invalid_provenance():
    with pytest.raises(ValueError, match="invalid provenance mode"):
        execute(_request(provenance_mode="UNKNOWN"), lambda request: _valid_result())


def test_execute_rejects_empty_evidence():
    with pytest.raises(ValueError, match="evidence is mandatory"):
        execute(_request(evidence=[]), lambda request: _valid_result())


def test_execute_rejects_invalid_executor_result():
    with pytest.raises(ValueError):
        execute(_request(), lambda request: None)
