from pathlib import Path

import pytest

from src.presentation_snapshot import (
    assert_presentation_snapshot,
    build_presentation_snapshot,
    semantic_presentation_hash,
)


def test_cross_language_semantic_hash_vector_matches_console():
    basis = {
        "presentation_contract_version": "P0_11_PRESENTATION_V1",
        "engine": "5DR",
        "identity": {"run_id": "42", "result_id": "forecast-7", "checkpoint_id": None},
        "governance_state": "SELECTED",
        "sections": [
            {"name": "TABLE_1_5DR_ASSESSMENT_EFFICACY", "value": 1.0, "probability": 42.5, "verified": True},
            {"name": "TABLE_2_CURRENT_5DR_RUN", "items": ["PVPO", None, -0.0]},
        ],
        "source_payload_hash": "source-abc",
    }
    assert semantic_presentation_hash(basis) == "c7ab9fc4e43a3d10460f99b1e8bada4147e85f4878880ddd12c08bf66c4b0127"


def test_5dr_snapshot_requires_current_v212_two_table_order():
    snapshot = build_presentation_snapshot(
        run_id=42,
        result_id="forecast-1",
        governance_state="SELECTED",
        source_payload_hash="source-1",
        sections=[
            {"name": "TABLE_1_5DR_ASSESSMENT_EFFICACY", "rows": []},
            {"name": "TABLE_2_CURRENT_5DR_RUN", "rows": []},
        ],
    )
    assert snapshot["engine"] == "5DR"
    assert snapshot["identity"] == {"run_id": "42", "result_id": "forecast-1", "checkpoint_id": None}
    assert_presentation_snapshot(snapshot)

    with pytest.raises(ValueError, match="PRESENTATION_5DR_SECTION_ORDER_MISMATCH"):
        build_presentation_snapshot(
            run_id=42,
            result_id="forecast-1",
            governance_state="SELECTED",
            source_payload_hash="source-1",
            sections=[
                {"name": "TABLE_2_CURRENT_5DR_RUN"},
                {"name": "TABLE_1_5DR_ASSESSMENT_EFFICACY"},
            ],
        )

    with pytest.raises(ValueError, match="PRESENTATION_5DR_SECTION_ORDER_MISMATCH"):
        build_presentation_snapshot(
            run_id=42,
            result_id="forecast-1",
            governance_state="SELECTED",
            source_payload_hash="source-1",
            sections=[
                {"name": "TABLE_1_5DR_OUTCOME"},
                {"name": "TABLE_2_5DR_DRILL_DOWN"},
            ],
        )


def test_5dr_issuance_presentation_cannot_bind_to_outcome_checkpoint():
    with pytest.raises(ValueError, match="PRESENTATION_5DR_CHECKPOINT_MUST_BE_NULL"):
        build_presentation_snapshot(
            run_id=42,
            result_id="forecast-1",
            checkpoint_id="D+1",
            governance_state="SELECTED",
            source_payload_hash="source-1",
            sections=[
                {"name": "TABLE_1_5DR_ASSESSMENT_EFFICACY"},
                {"name": "TABLE_2_CURRENT_5DR_RUN"},
            ],
        )


def test_tamper_fails_closed():
    snapshot = build_presentation_snapshot(
        run_id=42,
        result_id="forecast-1",
        governance_state="SELECTED",
        source_payload_hash="source-1",
        sections=[
            {"name": "TABLE_1_5DR_ASSESSMENT_EFFICACY", "decision": "NO_TRADE"},
            {"name": "TABLE_2_CURRENT_5DR_RUN", "status": "VERIFIED"},
        ],
    )
    snapshot["governance_state"] = "REJECTED"
    with pytest.raises(ValueError, match="PRESENTATION_HASH_MISMATCH"):
        assert_presentation_snapshot(snapshot)


def test_migration_binds_native_run_and_forecast_identity_and_is_append_only():
    sql = Path("migrations/009_p0_11_presentation_snapshots.sql").read_text(encoding="utf-8")
    assert "CREATE UNIQUE INDEX IF NOT EXISTS uq_5dr_forecasts_run_forecast_identity" in sql
    assert "ON public.forecasts(run_id,forecast_id)" in sql
    assert "run_id bigint NOT NULL REFERENCES public.runs(run_id)" in sql
    assert "result_id text NOT NULL REFERENCES public.forecasts(forecast_id)" in sql
    assert "FOREIGN KEY (run_id,result_id)" in sql
    assert "REFERENCES public.forecasts(run_id,forecast_id)" in sql
    assert "checkpoint_id text CHECK (checkpoint_id IS NULL)" in sql
    assert "jsonb_array_length(sections)=2" in sql
    assert "ON public.presentation_snapshots(run_id,result_id)" in sql
    assert "CREATE OR REPLACE FUNCTION" not in sql
    assert "CREATE TRIGGER" not in sql
    assert "presentation_snapshots_no_update" in sql
    assert "presentation_snapshots_no_delete" in sql
    assert "INSERT INTO public.presentation_snapshots" not in sql
