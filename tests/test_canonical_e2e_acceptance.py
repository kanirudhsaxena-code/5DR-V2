"""Canonical 5DR V2.2.2 end-to-end acceptance proof.

Uses deterministic fixtures only. No network, broker, or production database writes.
The proof spans normalized evidence, checkpoint capture, efficacy, Learning Lab
observations, hypothesis eligibility and approval-gated challenger promotion.
"""
from datetime import datetime, timezone

from src.checkpoint_efficacy import checkpoint_to_efficacy
from src.checkpoint_evidence import CheckpointEvidence, plan_checkpoint_capture
from src.evidence_handoff import packet_from_dict
from src.learning_governance import hypothesis_gate, promotion_gate
from src.learning_lab import PromotionEvidence
from src.learning_observations import build_learning_observations


def test_canonical_chain_reaches_learning_lab_without_production_mutation():
    packet = packet_from_dict({
        "forecast_id": "E2E-F1", "source_type": "SCREENSHOT", "source_ref": "fixture-option-shot",
        "observed_at": "2026-09-16T10:00:00+05:30", "captured_at": "2026-09-16T10:01:00+05:30",
        "instrument": "PE", "strike": 23200, "expiry": "2026-09-22", "premium": 180.0,
        "verified": True, "fresh": True, "contract_matched": True, "continuous_path": False,
    })
    assert packet.forecast_id == "E2E-F1"

    due = {"checkpoint_id": 101, "forecast_id": "E2E-F1", "checkpoint_type": "D+1", "status": "DUE", "due_date": "2026-09-16"}
    cp_evidence = CheckpointEvidence(
        forecast_id="E2E-F1", checkpoint_type="D+1",
        observed_at=datetime(2026, 9, 16, 15, 30, tzinfo=timezone.utc),
        actual_nifty=23100.0, source_type="WEB_RESEARCH", source_ref="fixture-close",
        verified=True, fresh=True,
    )
    # UTC date is intentionally the same fixture date; production evidence remains timezone-aware.
    action = plan_checkpoint_capture(due, cp_evidence)
    assert action.action_type == "CHECKPOINT"

    efficacy = checkpoint_to_efficacy(
        {"forecast_id": "E2E-F1", "bias": "BEARISH", "reference_spot": 23400.0, "zone_low": 23000.0, "zone_high": 23200.0},
        {"checkpoint_id": 101, "forecast_id": "E2E-F1", "checkpoint_type": "D+1", "status": "CAPTURED", "actual_nifty": 23100.0, "source_ref": "fixture-close"},
    )
    assert efficacy["evaluation_status"] == "SCORABLE"
    observations = build_learning_observations([efficacy], [])
    assert len(observations) == 1
    assert observations[0]["dimension"] == "PROBABILITY_CALIBRATION"

    # Repeat immutable observations only to exercise the governance threshold; no production writes exist here.
    support = hypothesis_gate(observations * 12, dimension="PROBABILITY_CALIBRATION")
    assert support["ready_for_challenger_testing"] is True
    assert support["production_change_allowed"] is False

    candidate = promotion_gate(PromotionEvidence(
        backtest_target_dates=40, shadow_target_dates=15, scoped=False,
        directional_improvement_pp=6.0, brier_relative_improvement=0.09,
        primary_horizon_deltas_pp={"D+1": 6.0, "D+3": 5.0, "D+5": 5.5},
        data_quality_passed=True, anti_leakage_passed=True,
        concentrated_on_single_day_or_event=False,
    ), challenger_code="E2E-C1", proposed_model_version="candidate-e2e")
    assert candidate["status"] == "PENDING_USER_APPROVAL"
    assert candidate["explicit_user_approval_required"] is True
    assert candidate["production_change_allowed"] is False


def test_incomplete_or_unverified_evidence_fails_closed_before_learning():
    try:
        packet_from_dict({
            "forecast_id": "E2E-BAD", "source_type": "SCREENSHOT", "source_ref": "fixture",
            "observed_at": "2026-09-16T10:00:00+05:30", "captured_at": "2026-09-16T10:01:00+05:30",
            "instrument": "PE", "premium": 180.0, "verified": False, "fresh": True, "contract_matched": True,
        })
    except ValueError:
        pass
    else:
        raise AssertionError("unverified evidence must fail closed")

    efficacy = checkpoint_to_efficacy(
        {"forecast_id": "E2E-BAD", "bias": "BEARISH", "reference_spot": 23400.0, "zone_low": None, "zone_high": 23200.0},
        {"checkpoint_id": 102, "forecast_id": "E2E-BAD", "checkpoint_type": "D+1", "status": "CAPTURED", "actual_nifty": 23100.0},
    )
    assert efficacy["evaluation_status"] == "NOT_SCORABLE"
    assert build_learning_observations([efficacy], []) == []
