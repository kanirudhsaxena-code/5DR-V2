import pytest

from src.learning_snapshot import (
    LearningRunContext,
    build_daily_snapshot,
    build_observation_envelope,
    content_hash,
)


def test_hash_is_stable_across_key_order():
    assert content_hash({"b": 2, "a": 1}) == content_hash({"a": 1, "b": 2})


def test_observation_envelope_maps_internal_horizon_and_requires_exclusion_reason():
    observation = {
        "horizon": "D+1",
        "dimension": "PROBABILITY_CALIBRATION",
        "observation_type": "ERROR",
        "outcome_classification": "DIRECTION_MISS",
        "metrics": {"zone_hit": False},
        "evidence": {"source_ref": "checkpoint:1"},
        "checkpoint_evaluation_id": 1,
    }
    with pytest.raises(ValueError):
        build_observation_envelope(
            observation,
            LearningRunContext(
                run_id="r1",
                run_role="DIAGNOSTIC",
                official_efficacy_eligible=False,
                target_trading_date="2026-09-22",
                source_ref="run:r1",
            ),
        )
    row = build_observation_envelope(
        observation,
        LearningRunContext(
            run_id="r1",
            run_role="DIAGNOSTIC",
            official_efficacy_eligible=False,
            target_trading_date="2026-09-22",
            source_ref="run:r1",
            exclusion_reason="NON_CANONICAL",
        ),
    )
    assert row["horizon"] == "D"
    assert row["source_horizon"] == "D+1"
    assert row["production_change_allowed"] is False


def test_daily_snapshot_day_normalizes_repeated_runs():
    runs = [
        {"run_role": "CANONICAL", "target_trading_date": "2026-09-22"},
        {"run_role": "DIAGNOSTIC", "target_trading_date": "2026-09-22"},
        {"run_role": "DIAGNOSTIC", "target_trading_date": "2026-09-22"},
        {"run_role": "CANONICAL", "target_trading_date": "2026-09-23"},
    ]
    observations = [
        {"target_trading_date": "2026-09-22", "dimension": "A", "observation_type": "SUCCESS"},
        {"target_trading_date": "2026-09-22", "dimension": "A", "observation_type": "SUCCESS"},
        {"target_trading_date": "2026-09-22", "dimension": "A", "observation_type": "SUCCESS"},
        {"target_trading_date": "2026-09-23", "dimension": "A", "observation_type": "ERROR"},
    ]
    snap = build_daily_snapshot(
        cycle_id="c1",
        as_of="2026-09-22T17:30:00+05:30",
        runs=runs,
        observations=observations,
        matured_outcomes=[{"scorable": True}],
        challengers=[{"status": "PENDING_USER_APPROVAL"}],
        methodology_versions={"model": "5DR_V2_1"},
    )
    assert snap["counts"]["runs_analyzed"] == 4
    assert snap["snapshot"]["independent_target_date_count"] == 2
    assert snap["snapshot"]["day_normalized_success_rate"] == 0.5
    assert snap["counts"]["approval_required"] == 1
    assert snap["snapshot"]["official_efficacy_population"] == "CANONICAL_ONLY"
    assert snap["snapshot"]["production_change_allowed"] is False


def test_data_gap_makes_snapshot_partial_without_changing_official_population():
    snap = build_daily_snapshot(
        cycle_id="c2",
        as_of="2026-09-22T17:30:00+05:30",
        runs=[],
        observations=[],
        matured_outcomes=[{"scorable": False, "data_gap": True}],
    )
    assert snap["snapshot_status"] == "PARTIAL"
    assert snap["counts"]["data_gap_outcomes"] == 1
