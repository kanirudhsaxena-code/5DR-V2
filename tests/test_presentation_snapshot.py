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
        "identity": {"run_id": "run-42", "result_id": "forecast-7", "checkpoint_id": None},
        "governance_state": "SELECTED",
        "sections": [
            {"name": "TABLE_1_5DR_OUTCOME", "value": 1.0, "probability": 42.5, "verified": True},
            {"name": "TABLE_2_5DR_DRILL_DOWN", "items": ["PVPO", None, -0.0]},
        ],
        "source_payload_hash": "source-abc",
    }
    assert semantic_presentation_hash(basis) == "43cab49103f841c9a85d2213756ecb6db2ee54cbdbb5c0ec6545cc7dbb80b020"


def test_5dr_snapshot_requires_exact_two_table_master_order():
    snapshot = build_presentation_snapshot(
        run_id="run-1",
        result_id="forecast-1",
        governance_state="SELECTED",
        source_payload_hash="source-1",
        sections=[
            {"name": "TABLE_1_5DR_OUTCOME", "rows": []},
            {"name": "TABLE_2_5DR_DRILL_DOWN", "rows": []},
        ],
    )
    assert snapshot["engine"] == "5DR"
    assert snapshot["identity"]["result_id"] == "forecast-1"
    assert_presentation_snapshot(snapshot)

    with pytest.raises(ValueError, match="PRESENTATION_5DR_SECTION_ORDER_MISMATCH"):
        build_presentation_snapshot(
            run_id="run-1",
            result_id="forecast-1",
            governance_state="SELECTED",
            source_payload_hash="source-1",
            sections=[
                {"name": "TABLE_2_5DR_DRILL_DOWN"},
                {"name": "TABLE_1_5DR_OUTCOME"},
            ],
        )


def test_tamper_fails_closed():
    snapshot = build_presentation_snapshot(
        run_id="run-1",
        result_id="forecast-1",
        governance_state="SELECTED",
        source_payload_hash="source-1",
        sections=[
            {"name": "TABLE_1_5DR_OUTCOME", "decision": "NO_TRADE"},
            {"name": "TABLE_2_5DR_DRILL_DOWN", "status": "VERIFIED"},
        ],
    )
    snapshot["governance_state"] = "REJECTED"
    with pytest.raises(ValueError, match="PRESENTATION_HASH_MISMATCH"):
        assert_presentation_snapshot(snapshot)


def test_migration_is_append_only_and_null_checkpoint_identity_is_unique():
    sql = Path("migrations/009_p0_11_presentation_snapshots.sql").read_text(encoding="utf-8")
    assert "CREATE TABLE IF NOT EXISTS presentation_snapshots" in sql
    assert "jsonb_array_length(sections)=2" in sql
    assert "COALESCE(checkpoint_id,'')" in sql
    assert "presentation_snapshots_no_update" in sql
    assert "presentation_snapshots_no_delete" in sql
    assert "INSERT INTO presentation_snapshots" not in sql
