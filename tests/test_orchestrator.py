import pytest

from src.engine_contract import EngineRequest, EvidenceItem
from src.orchestrator import execute


def _request():
    return EngineRequest(
        request_id="req_test",
        provenance_mode="HYBRID",
        evidence=[EvidenceItem(evidence_type="NORMALIZED", source_ref="test", normalized={"x": 1})],
    )


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


def test_execute_rejects_incomplete_contract():
    result = _valid_result()
    result["assessment_snapshot_complete"] = False
    with pytest.raises(ValueError):
        execute(_request(), lambda request: result)


def test_execute_rejects_invalid_executor_result():
    with pytest.raises(ValueError):
        execute(_request(), lambda request: None)
