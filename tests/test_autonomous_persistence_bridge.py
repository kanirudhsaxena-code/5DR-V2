import pytest

from experiments.autonomous_persistence_bridge import persist_release_candidate
from experiments.data_contract import DataArchitectureError


def _candidate():
    return {
        "schema":"5dr-v2-2-3-release-candidate-v1",
        "status":"RELEASE_CANDIDATE_VALIDATED",
        "bundle_sha256":"a"*64,
        "engine_result_sha256":"b"*64,
        "engine_result":{"model_version":"5DR_V2_1","output_contract_version":"5DR_V2_1_2"},
        "forecast_assessment":"present",
        "recommendation_assessment":"present",
        "horizon_slots":{f"D+{i}":{} for i in range(1,6)},
        "recommendation":{"action":"NO_TRADE"},
        "assessment_snapshot_complete":True,
        "recommendation_ledger_complete":True,
        "published":False,
        "production_5dr_write_enabled":False,
        "lifecycle_write_enabled":False,
        "learning_lab_write_enabled":False,
        "trading_execution_enabled":False,
        "methodology_changed":False,
    }


def test_persistence_receipt_must_bind_to_exact_candidate():
    def provider(context):
        return {
            "release_candidate_sha256":context["release_candidate_sha256"],
            "status":"PERSISTED",
            "forecast_id":"F-AUTO-1",
            "trading_execution_enabled":False,
            "methodology_changed":False,
        }
    out=persist_release_candidate(_candidate(),provider)
    assert out["status"]=="PERSISTED"
    assert out["forecast_released"] is True
    assert out["production_5dr_write_enabled"] is True
    assert out["trading_execution_enabled"] is False


def test_persistence_rejects_wrong_binding():
    def provider(_):
        return {
            "release_candidate_sha256":"0"*64,
            "status":"PERSISTED",
            "forecast_id":"F-AUTO-1",
            "trading_execution_enabled":False,
            "methodology_changed":False,
        }
    with pytest.raises(DataArchitectureError,match="binding mismatch"):
        persist_release_candidate(_candidate(),provider)


def test_persistence_rejects_trading_or_methodology_mutation():
    def provider(context):
        return {
            "release_candidate_sha256":context["release_candidate_sha256"],
            "status":"PERSISTED",
            "forecast_id":"F-AUTO-1",
            "trading_execution_enabled":True,
            "methodology_changed":False,
        }
    with pytest.raises(DataArchitectureError,match="trading boundary"):
        persist_release_candidate(_candidate(),provider)
