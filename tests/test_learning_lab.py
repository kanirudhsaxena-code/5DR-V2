from src.learning_lab import (
    PromotionEvidence,
    day_normalized_mean,
    evaluate_promotion,
    hypothesis_ready,
)


def good_evidence(**overrides):
    base = dict(
        backtest_target_dates=45,
        shadow_target_dates=18,
        scoped=False,
        directional_improvement_pp=6.0,
        brier_relative_improvement=0.09,
        primary_horizon_deltas_pp={"D+1": 5.5, "D+3": 6.0, "D+5": 5.0},
        recommendation_hit_rate_delta_pp=1.0,
        average_r_delta=0.05,
        drawdown_relative_delta=-0.02,
        changes_execution_logic=True,
        data_quality_passed=True,
        anti_leakage_passed=True,
        concentrated_on_single_day_or_event=False,
    )
    base.update(overrides)
    return PromotionEvidence(**base)


def test_hypothesis_testing_gate():
    assert hypothesis_ready(12, 0.65)
    assert not hypothesis_ready(11, 0.90)
    assert not hypothesis_ready(30, 0.64)


def test_full_promotion_gate_passes_but_does_not_auto_approve():
    decision = evaluate_promotion(good_evidence())
    assert decision.eligible is True
    assert any("PENDING_USER_APPROVAL" in reason for reason in decision.reasons)


def test_backtest_sample_gate_blocks():
    decision = evaluate_promotion(good_evidence(backtest_target_dates=39))
    assert decision.eligible is False
    assert any("backtest target dates" in reason for reason in decision.reasons)


def test_shadow_gate_blocks():
    decision = evaluate_promotion(good_evidence(shadow_target_dates=14))
    assert decision.eligible is False
    assert any("shadow target dates" in reason for reason in decision.reasons)


def test_scoped_thresholds_are_lower_but_still_strict():
    decision = evaluate_promotion(good_evidence(scoped=True, backtest_target_dates=30, shadow_target_dates=12))
    assert decision.eligible is True


def test_primary_horizon_deterioration_blocks():
    ev = good_evidence(primary_horizon_deltas_pp={"D+1": 6.0, "D+3": -3.1, "D+5": 5.0})
    decision = evaluate_promotion(ev)
    assert decision.eligible is False
    assert any("D+3 deteriorates" in reason for reason in decision.reasons)


def test_execution_regression_blocks():
    decision = evaluate_promotion(good_evidence(average_r_delta=-0.11))
    assert decision.eligible is False
    assert any("average R" in reason for reason in decision.reasons)


def test_anti_leakage_failure_blocks():
    decision = evaluate_promotion(good_evidence(anti_leakage_passed=False))
    assert decision.eligible is False
    assert any("anti-leakage" in reason for reason in decision.reasons)


def test_day_normalization_prevents_snapshot_inflation():
    value = day_normalized_mean({"2026-09-11": [1.0, 1.0, 1.0, 1.0], "2026-09-15": [0.0]})
    assert value == 0.5
