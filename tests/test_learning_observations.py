from src.learning_observations import build_learning_observations, efficacy_observation, recommendation_observation


def test_scorable_forecast_result_becomes_learning_observation():
    row = efficacy_observation({
        "forecast_id": "F1", "evaluation_id": 9, "evaluation_status": "SCORABLE",
        "checkpoint_type": "D+1", "directional_hit": True, "zone_hit": False,
        "directional_margin_points": 100.0, "zone_error_points": 25.0, "source_ref": "close-source",
    })
    assert row["dimension"] == "PROBABILITY_CALIBRATION"
    assert row["observation_type"] == "SUCCESS"
    assert row["outcome_classification"] == "DIRECTION_HIT_ZONE_MISS"


def test_unscorable_forecast_is_not_learning_signal():
    assert efficacy_observation({"evaluation_status": "NOT_SCORABLE", "checkpoint_type": "D+1"}) is None


def test_resolved_win_becomes_execution_observation():
    row = recommendation_observation({
        "forecast_id": "F1", "recommendation": "BUY_PE", "primary_outcome": "WIN",
        "terminal_event_id": 10, "final_pnl_pct": 40.0, "r_multiple": 2.0,
    })
    assert row["horizon"] == "TRADE"
    assert row["observation_type"] == "SUCCESS"


def test_open_trade_is_not_treated_as_learning_outcome():
    assert recommendation_observation({"recommendation": "BUY_PE", "primary_outcome": None}) is None


def test_no_trade_is_not_treated_as_execution_win_or_loss():
    assert recommendation_observation({"recommendation": "NO_TRADE", "primary_outcome": "WIN"}) is None


def test_combined_builder_keeps_only_immutable_scorable_results():
    rows = build_learning_observations(
        [{"forecast_id": "F1", "evaluation_status": "SCORABLE", "checkpoint_type": "D+3", "directional_hit": False, "zone_hit": False}],
        [{"forecast_id": "F2", "recommendation": "BUY_CE", "primary_outcome": "LOSS"}, {"forecast_id": "F3", "recommendation": "BUY_PE", "primary_outcome": None}],
    )
    assert len(rows) == 2
    assert rows[0]["observation_type"] == "ERROR"
    assert rows[1]["outcome_classification"] == "LOSS"
