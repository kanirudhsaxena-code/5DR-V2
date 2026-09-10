from src.assessment import (
    aggregate_all_horizons,
    aggregate_forecast_horizon,
    aggregate_recommendations,
    evaluate_forecast_checkpoint,
)


def test_bearish_checkpoint_hit_and_zone_hit():
    result = evaluate_forecast_checkpoint(
        bias="BEARISH", reference_spot=23500, actual_close=23350,
        zone_low=23250, zone_high=23400,
    )
    assert result["directional_hit"] is True
    assert result["directional_margin_points"] == 150
    assert result["zone_hit"] is True
    assert result["zone_error_points"] == 0


def test_bullish_miss_has_negative_margin_and_zone_error():
    result = evaluate_forecast_checkpoint(
        bias="BULLISH", reference_spot=23500, actual_close=23400,
        zone_low=23550, zone_high=23700,
    )
    assert result["directional_hit"] is False
    assert result["directional_margin_points"] == -100
    assert result["zone_hit"] is False
    assert result["zone_error_points"] == 150


def test_range_margin_inside_and_outside():
    inside = evaluate_forecast_checkpoint(
        bias="RANGE", reference_spot=23500, actual_close=23550,
        zone_low=23500, zone_high=23600,
    )
    outside = evaluate_forecast_checkpoint(
        bias="RANGE", reference_spot=23500, actual_close=23700,
        zone_low=23500, zone_high=23600,
    )
    assert inside["directional_hit"] is True
    assert inside["directional_margin_points"] == 50
    assert outside["directional_hit"] is False
    assert outside["directional_margin_points"] == -100


def test_not_scorable_excluded_from_denominator():
    metrics = aggregate_forecast_horizon([
        {"evaluation_status": "SCORABLE", "directional_hit": True, "zone_hit": True,
         "directional_margin_points": 100, "zone_error_points": 0},
        {"evaluation_status": "NOT_SCORABLE", "directional_hit": False, "zone_hit": False,
         "directional_margin_points": -500, "zone_error_points": 500},
    ])
    assert metrics["scorable_count"] == 1
    assert metrics["directional_accuracy"] == "1/1 = 100.0%"


def test_all_five_horizon_slots_always_exist():
    result = aggregate_all_horizons([])
    assert set(result) == {"D+1", "D+2", "D+3", "D+4", "D+5"}
    assert result["D+5"]["scorable_count"] == 0


def test_recommendation_hit_rate_and_pnl():
    result = aggregate_recommendations([
        {"recommendation": "BUY_PE", "status": "T1_HIT", "primary_outcome": "WIN",
         "final_pnl_pct": 40, "r_multiple": 2.0},
        {"recommendation": "BUY_CE", "status": "SL_HIT", "primary_outcome": "LOSS",
         "final_pnl_pct": -20, "r_multiple": -1.0},
        {"recommendation": "BUY_PE", "status": "OPEN", "primary_outcome": None,
         "current_pnl_pct": 10},
        {"recommendation": "NO_TRADE", "status": "NO_TRADE", "primary_outcome": None},
    ])
    assert result["wins"] == 1
    assert result["losses"] == 1
    assert result["hit_rate"] == "1/2 = 50.0%"
    assert result["realized_standardized_model_pnl_pct"] == 20
    assert result["open_standardized_mtm_pct"] == 10
