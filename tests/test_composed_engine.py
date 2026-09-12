import pytest

from src.composed_engine import domain_execute
from src.engine_contract import EngineRequest, EvidenceItem
from src.orchestrator import execute


def _normalized():
    return {
        "regime": "TREND",
        "component_scores": {
            "PRICE_STRUCTURE": 50,
            "PVPO": 40,
            "PARTICIPATION": 30,
            "MACRO_CATALYSTS": 20,
        },
        "market_trust_inputs": {
            "price_confirmation": 80,
            "pvpo_confirmation": 75,
            "participation_confirmation": 70,
            "cross_engine_consistency": 65,
            "closing_confirmation": 80,
            "evidence_freshness_completeness": 90,
        },
        "event_shock": "NORMAL",
        "execution_inputs": {
            "rr_score": 80,
            "premium_iv_theta_score": 70,
            "strike_expiry_fit_score": 80,
            "liquidity_spread_score": 80,
            "entry_invalidation_score": 75,
        },
        "data_adequate": True,
        "event_kill_switch": False,
        "expected_rr": 2.5,
        "forecast_assessment": "Forecast assessment present",
        "recommendation_assessment": "Recommendation assessment present",
        "horizon_slots": {f"D+{i}": {} for i in range(1, 6)},
        "recommendation_ledger_complete": True,
        "assessment_snapshot_complete": True,
    }


def _request(data=None):
    return EngineRequest(
        request_id="req_composed",
        provenance_mode="HYBRID",
        evidence=[EvidenceItem(evidence_type="NORMALIZED", source_ref="test", normalized=data or _normalized())],
    )


def test_composed_engine_produces_valid_release_shape():
    result = execute(_request(), domain_execute)
    assert result["model_version"] == "5DR_V2_1"
    assert result["output_contract_version"] == "5DR_V2_1_2"
    assert set(result["probabilities"]) == {"BULL", "RANGE", "BEAR"}
    assert isinstance(result["tradeability_blockers"], list)


def test_composed_engine_fails_on_missing_normalized_input():
    data = _normalized()
    del data["component_scores"]
    with pytest.raises(ValueError, match="missing normalized inputs"):
        execute(_request(data), domain_execute)


def test_composed_engine_fails_on_conflicting_evidence():
    request = EngineRequest(
        request_id="req_conflict",
        provenance_mode="HYBRID",
        evidence=[
            EvidenceItem(evidence_type="NORMALIZED", source_ref="a", normalized={"regime": "TREND"}),
            EvidenceItem(evidence_type="NORMALIZED", source_ref="b", normalized={"regime": "RANGE"}),
        ],
    )
    with pytest.raises(ValueError, match="conflicting normalized evidence"):
        execute(request, domain_execute)
