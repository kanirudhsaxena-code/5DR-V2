from datetime import date, datetime, timezone

from src.checkpoint_evidence import CheckpointEvidence, plan_checkpoint_capture


def checkpoint(**overrides):
    row = {"checkpoint_id": 7, "forecast_id": "F1", "checkpoint_type": "D+2", "due_date": date(2026, 9, 15), "status": "DUE"}
    row.update(overrides)
    return row


def evidence(**overrides):
    row = dict(
        forecast_id="F1",
        checkpoint_type="D+2",
        observed_at=datetime(2026, 9, 15, 10, 0, tzinfo=timezone.utc),
        actual_nifty=23118.60,
        source_type="WEB_RESEARCH",
        source_ref="verified-close-source",
        verified=True,
        fresh=True,
    )
    row.update(overrides)
    return CheckpointEvidence(**row)


def test_verified_exact_due_evidence_plans_checkpoint_capture():
    action = plan_checkpoint_capture(checkpoint(), evidence())
    assert action.kind == "CHECKPOINT"
    assert action.payload["checkpoint_id"] == 7
    assert action.payload["actual_nifty"] == 23118.60


def test_wrong_forecast_fails_closed():
    assert plan_checkpoint_capture(checkpoint(), evidence(forecast_id="F2")).kind == "NO_WRITE"


def test_wrong_checkpoint_type_fails_closed():
    assert plan_checkpoint_capture(checkpoint(), evidence(checkpoint_type="D+3")).kind == "NO_WRITE"


def test_stale_or_unverified_evidence_fails_closed():
    assert plan_checkpoint_capture(checkpoint(), evidence(fresh=False)).kind == "NO_WRITE"
    assert plan_checkpoint_capture(checkpoint(), evidence(verified=False)).kind == "NO_WRITE"


def test_wrong_due_date_fails_closed():
    assert plan_checkpoint_capture(checkpoint(), evidence(observed_at=datetime(2026, 9, 16, 10, 0, tzinfo=timezone.utc))).kind == "NO_WRITE"


def test_naive_timestamp_fails_closed():
    assert plan_checkpoint_capture(checkpoint(), evidence(observed_at=datetime(2026, 9, 15, 10, 0))).kind == "NO_WRITE"


def test_invalid_market_values_fail_closed():
    assert plan_checkpoint_capture(checkpoint(), evidence(actual_nifty=-1)).kind == "NO_WRITE"
    assert plan_checkpoint_capture(checkpoint(), evidence(period_high=23000, period_low=23100)).kind == "NO_WRITE"


def test_non_due_checkpoint_cannot_be_overwritten():
    assert plan_checkpoint_capture(checkpoint(status="CAPTURED"), evidence()).kind == "NO_WRITE"
