import pytest

from experiments.autonomous_lifecycle_shadow import run_lifecycle_learning_shadow
from experiments.data_contract import DataArchitectureError


def _candidate():
    return {
        "schema": "5dr-v2-2-3-release-candidate-v1",
        "status": "RELEASE_CANDIDATE_VALIDATED",
        "bundle_sha256": "a" * 64,
        "engine_result_sha256": "b" * 64,
        "engine_result": {
            "model_version": "5DR_V2_1",
            "output_contract_version": "5DR_V2_1_2",
        },
        "forecast_assessment": "present",
        "recommendation_assessment": "present",
        "horizon_slots": {f"D+{i}": {} for i in range(1, 6)},
        "recommendation": {"action": "NO_TRADE"},
        "assessment_snapshot_complete": True,
        "recommendation_ledger_complete": True,
        "published": False,
        "production_5dr_write_enabled": False,
        "lifecycle_write_enabled": False,
        "learning_lab_write_enabled": False,
        "trading_execution_enabled": False,
        "methodology_changed": False,
    }


def _provider(context):
    forecast_id = "F-AUTO-1"
    return {
        "release_candidate_sha256": context["release_candidate_sha256"],
        "forecasts": [{
            "forecast_id": forecast_id,
            "bias": "BULLISH",
            "reference_spot": 23000.0,
            "zone_low": 23100.0,
            "zone_high": 23300.0,
        }],
        "checkpoints": [
            {
                "checkpoint_id": i,
                "forecast_id": forecast_id,
                "checkpoint_type": f"D+{i}",
                "status": "CAPTURED" if i <= 2 else "DUE",
                "actual_nifty": 23200.0 if i == 1 else (22900.0 if i == 2 else None),
                "source_ref": f"fixture-{i}",
            }
            for i in range(1, 6)
        ],
        "recommendation_rows": [{
            "forecast_id": forecast_id,
            "recommendation": "NO_TRADE",
            "primary_outcome": None,
        }],
    }


def test_shadow_scores_only_captured_checkpoints_and_generates_learning():
    out = run_lifecycle_learning_shadow(_candidate(), _provider)
    assert out["status"] == "LIFECYCLE_LEARNING_SHADOW_COMPLETE"
    assert out["persistence_plan"]["writes_enabled"] is False
    assert out["efficacy_rows"][0]["evaluation_status"] == "SCORABLE"
    assert out["efficacy_rows"][1]["evaluation_status"] == "SCORABLE"
    assert out["efficacy_rows"][2]["evaluation_status"] == "NOT_SCORABLE"
    assert len(out["learning_observations"]) == 2
    assert out["production_change_allowed"] is False


def test_shadow_rejects_wrong_release_binding():
    def wrong(context):
        payload = _provider(context)
        payload["release_candidate_sha256"] = "0" * 64
        return payload

    with pytest.raises(DataArchitectureError, match="binding mismatch"):
        run_lifecycle_learning_shadow(_candidate(), wrong)


def test_shadow_requires_all_five_checkpoint_slots():
    def incomplete(context):
        payload = _provider(context)
        payload["checkpoints"] = payload["checkpoints"][:-1]
        return payload

    with pytest.raises(DataArchitectureError, match="missing checkpoint slots"):
        run_lifecycle_learning_shadow(_candidate(), incomplete)


def test_shadow_rejects_any_enabled_side_effect():
    candidate = _candidate()
    candidate["lifecycle_write_enabled"] = True
    with pytest.raises(DataArchitectureError, match="safety boundary crossed"):
        run_lifecycle_learning_shadow(candidate, _provider)
