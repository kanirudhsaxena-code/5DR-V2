from src.learning_governance import hypothesis_gate, promotion_gate
from src.learning_lab import PromotionEvidence


def obs(n, outcome="DIRECTION_MISS"):
    return [{"dimension": "PROBABILITY_CALIBRATION", "outcome_classification": outcome} for _ in range(n)]


def passing_evidence():
    return PromotionEvidence(
        backtest_target_dates=40,
        shadow_target_dates=15,
        scoped=False,
        directional_improvement_pp=6.0,
        brier_relative_improvement=0.09,
        primary_horizon_deltas_pp={"D+1": 6.0, "D+3": 5.0, "D+5": 5.5},
        data_quality_passed=True,
        anti_leakage_passed=True,
        concentrated_on_single_day_or_event=False,
    )


def test_hypothesis_requires_minimum_support_and_ratio():
    result = hypothesis_gate(obs(12) + obs(6, "DIRECTION_AND_ZONE_HIT"), dimension="PROBABILITY_CALIBRATION", outcome_classification="DIRECTION_MISS")
    assert result["supporting_observations"] == 12
    assert result["support_ratio"] >= 0.65
    assert result["ready_for_challenger_testing"] is True
    assert result["production_change_allowed"] is False


def test_hypothesis_with_too_few_observations_fails_closed():
    result = hypothesis_gate(obs(11), dimension="PROBABILITY_CALIBRATION", outcome_classification="DIRECTION_MISS")
    assert result["status"] == "INSUFFICIENT_SUPPORT"


def test_passing_challenger_can_only_be_pending_user_approval():
    result = promotion_gate(passing_evidence(), challenger_code="C1", proposed_model_version="candidate-1")
    assert result["eligible"] is True
    assert result["status"] == "PENDING_USER_APPROVAL"
    assert result["explicit_user_approval_required"] is True
    assert result["production_change_allowed"] is False


def test_failed_challenger_never_creates_approval_candidate():
    evidence = PromotionEvidence(
        backtest_target_dates=5, shadow_target_dates=2, scoped=False,
        directional_improvement_pp=1.0, brier_relative_improvement=0.01,
        primary_horizon_deltas_pp={"D+1": 1.0, "D+3": 0.0, "D+5": -5.0},
    )
    result = promotion_gate(evidence, challenger_code="C2", proposed_model_version="candidate-2")
    assert result["eligible"] is False
    assert result["production_change_allowed"] is False
    assert result["status"] == "REJECTED_OR_INSUFFICIENT"


def test_execution_challenger_without_trade_metrics_fails_closed():
    base = passing_evidence()
    evidence = PromotionEvidence(**{**base.__dict__, "changes_execution_logic": True})
    result = promotion_gate(evidence, challenger_code="C3", proposed_model_version="candidate-3")
    assert result["eligible"] is False
    assert any("hit-rate" in reason for reason in result["reasons"])
