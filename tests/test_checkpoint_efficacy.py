from src.assessment import aggregate_all_horizons
from src.checkpoint_efficacy import build_efficacy_records, checkpoint_to_efficacy


def forecast(**overrides):
    row = {"forecast_id": "F1", "bias": "BEARISH", "reference_spot": 23400.0, "zone_low": 23000.0, "zone_high": 23200.0}
    row.update(overrides)
    return row


def checkpoint(**overrides):
    row = {"checkpoint_id": 1, "forecast_id": "F1", "checkpoint_type": "D+1", "status": "CAPTURED", "actual_nifty": 23118.60, "source_ref": "verified-close"}
    row.update(overrides)
    return row


def test_captured_checkpoint_becomes_scorable_efficacy_record():
    row = checkpoint_to_efficacy(forecast(), checkpoint())
    assert row["evaluation_status"] == "SCORABLE"
    assert row["day_number"] == 1
    assert row["directional_hit"] is True
    assert row["zone_hit"] is True


def test_uncaptured_checkpoint_fails_closed():
    row = checkpoint_to_efficacy(forecast(), checkpoint(status="DUE", actual_nifty=None))
    assert row["evaluation_status"] == "NOT_SCORABLE"


def test_forecast_identity_mismatch_fails_closed():
    row = checkpoint_to_efficacy(forecast(), checkpoint(forecast_id="F2"))
    assert row["evaluation_status"] == "NOT_SCORABLE"
    assert row["reason"] == "FORECAST_ID_MISMATCH"


def test_missing_frozen_forecast_input_fails_closed():
    row = checkpoint_to_efficacy(forecast(zone_low=None), checkpoint())
    assert row["evaluation_status"] == "NOT_SCORABLE"
    assert "zone_low" in row["reason"]


def test_build_records_does_not_invent_missing_forecast():
    rows = build_efficacy_records([], [checkpoint()])
    assert rows[0]["evaluation_status"] == "NOT_SCORABLE"
    assert rows[0]["reason"] == "FORECAST_NOT_FOUND"


def test_final_checkpoint_is_not_double_counted_as_horizon():
    rows = build_efficacy_records([forecast()], [checkpoint(checkpoint_type="FINAL")])
    assert rows == []


def test_records_feed_existing_d1_to_d5_aggregator():
    rows = build_efficacy_records([forecast()], [checkpoint()])
    summary = aggregate_all_horizons(rows)
    assert summary["D+1"]["scorable_count"] == 1
    assert summary["D+1"]["directional_hits"] == 1
    assert summary["D+2"]["scorable_count"] == 0
