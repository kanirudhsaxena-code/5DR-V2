from src.learning_lab import PromotionEvidence, day_normalized_mean, evaluate_promotion, hypothesis_ready


def good_evidence(**overrides):
    values = dict(
        backtest_target_dates=40,
        shadow_target_dates=15,
        scoped=False,
        directional_improvement_pp=6.0,
        brier_relative_improvement=0.09,
        primary_horizon_deltas_pp={"D+1": 5.0, "D+3": 1.0, "D+5": 0.0},
        data_quality_passed=True,
        anti_leakage_passed=True,
    )
    values.update(overrides)
    return PromotionEvidence(**values)


def test_hypothesis_gate_requires_minimum_support():
    assert not hypothesis_ready(11, 0.90)
    assert not hypothesis_ready(20, 0.64)
    assert hypothesis_ready(12, 0.65)


def test_passing_challenger_only_requests_user_approval():
    decision = evaluate_promotion(good_evidence())
    assert decision.eligible is True
    assert any("PENDING_USER_APPROVAL" in reason for reason in decision.reasons)
    assert any("explicit user approval" in reason for reason in decision.reasons)


def test_bad_data_or_leakage_fails_closed():
    assert not evaluate_promotion(good_evidence(data_quality_passed=False)).eligible
    assert not evaluate_promotion(good_evidence(anti_leakage_passed=False)).eligible


def test_execution_challenger_requires_execution_metrics():
    decision = evaluate_promotion(good_evidence(changes_execution_logic=True))
    assert decision.eligible is False
    assert any("hit-rate" in reason for reason in decision.reasons)
    assert any("average-R" in reason for reason in decision.reasons)


def test_primary_horizon_deterioration_blocks_promotion():
    decision = evaluate_promotion(good_evidence(primary_horizon_deltas_pp={"D+1": 6.0, "D+3": -3.1, "D+5": 1.0}))
    assert decision.eligible is False


def test_single_event_concentration_blocks_promotion():
    assert not evaluate_promotion(good_evidence(concentrated_on_single_day_or_event=True)).eligible


def test_day_normalization_equal_weights_dates():
    assert day_normalized_mean({"d1": [1.0, 1.0, 1.0], "d2": [3.0]}) == 2.0
    assert day_normalized_mean({}) is None
