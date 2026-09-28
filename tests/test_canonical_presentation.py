from pathlib import Path

import pytest

from src.canonical_presentation import build_selected_canonical_presentation
from src.presentation_snapshot import assert_presentation_snapshot


def _records():
    run = {"run_id": 42, "command_type": "5DR", "status": "COMMITTED"}
    forecast = {
        "forecast_id": "forecast-42",
        "run_id": 42,
        "output_contract_version": "5DR_V2_1_2",
        "definitive_forecast": "RANGE",
    }
    assessment = {
        "assessment_snapshot_id": 9,
        "run_id": 42,
        "forecast_id": "forecast-42",
        "output_contract_version": "5DR_V2_1_2",
        "completeness_status": "COMPLETE",
        "day_metrics": {f"D+{day}": {} for day in range(1, 6)},
    }
    daily = [
        {
            "forecast_id": "forecast-42",
            "day_number": day,
            "bias": "RANGE",
            "probability": 50.0,
            "zone_low": 23000 + day,
            "zone_high": 23500 + day,
        }
        for day in range(1, 6)
    ]
    components = [
        {"forecast_id": "forecast-42", "component": name, "component_score": 0.0}
        for name in ("PRICE_STRUCTURE", "PVPO", "PARTICIPATION", "MACRO_CATALYSTS")
    ]
    execution = {"forecast_id": "forecast-42", "instrument": "NONE", "execution_edge": 20.0}
    return run, forecast, assessment, daily, components, execution


def test_selected_canonical_builder_locks_current_v212_two_table_presentation():
    run, forecast, assessment, daily, components, execution = _records()
    snapshot = build_selected_canonical_presentation(
        run_id=42,
        forecast_id="forecast-42",
        run=run,
        forecast=forecast,
        assessment_snapshot=assessment,
        daily_forecasts=daily,
        component_scores=components,
        execution_plan=execution,
    )
    assert snapshot["governance_state"] == "SELECTED"
    assert snapshot["identity"] == {"run_id": "42", "result_id": "forecast-42", "checkpoint_id": None}
    assert [section["name"] for section in snapshot["sections"]] == [
        "TABLE_1_5DR_ASSESSMENT_EFFICACY",
        "TABLE_2_CURRENT_5DR_RUN",
    ]
    assert snapshot["sections"][1]["run"]["run_id"] == 42
    assert [row["day_number"] for row in snapshot["sections"][1]["daily_forecasts"]] == [1, 2, 3, 4, 5]
    assert len(snapshot["source_payload_hash"]) == 64
    assert_presentation_snapshot(snapshot)


def test_selected_canonical_builder_fails_closed_on_wrong_or_incomplete_identity():
    run, forecast, assessment, daily, components, execution = _records()
    with pytest.raises(ValueError, match="DAILY_PATH_INCOMPLETE"):
        build_selected_canonical_presentation(
            run_id=42,
            forecast_id="forecast-42",
            run=run,
            forecast=forecast,
            assessment_snapshot=assessment,
            daily_forecasts=daily[:4],
            component_scores=components,
            execution_plan=execution,
        )

    wrong_assessment = {**assessment, "run_id": 41}
    with pytest.raises(ValueError, match="ASSESSMENT_RUN_MISMATCH"):
        build_selected_canonical_presentation(
            run_id=42,
            forecast_id="forecast-42",
            run=run,
            forecast=forecast,
            assessment_snapshot=wrong_assessment,
            daily_forecasts=daily,
            component_scores=components,
            execution_plan=execution,
        )


def test_finalizer_persists_only_new_prospective_selected_canonical_before_commit():
    source = Path("src/console_forecast_sync.py").read_text(encoding="utf-8")
    assert "P0_11_PRESENTATION_ACTIVATION_TARGET_DATE = date(2026, 9, 29)" in source
    finalizer = source[source.index("def finalize_closed_canonical_windows"):]
    canonical_insert = finalizer.index("INSERT INTO canonical_selections")
    inserted_guard = finalizer.index("if inserted and target >= P0_11_PRESENTATION_ACTIVATION_TARGET_DATE")
    presentation_write = finalizer.index("_persist_selected_canonical_presentation(cur, selected_id)")
    commit = finalizer.index("conn.commit()")
    assert canonical_insert < inserted_guard < presentation_write < commit
    assert "VALUES (%s,'NO_VALID_CANDIDATE',NULL,NULL" in finalizer


def test_presentation_writer_is_db_derived_and_has_no_backfill_path():
    source = Path("src/console_forecast_sync.py").read_text(encoding="utf-8")
    helper = source[source.index("def _persist_selected_canonical_presentation"):source.index("def finalize_closed_canonical_windows")]
    assert "to_jsonb(r)" in helper
    assert "to_jsonb(f)" in helper
    assert "FROM assessment_snapshots" in helper
    assert "FROM daily_forecasts" in helper
    assert "FROM component_scores" in helper
    assert "FROM execution_plans" in helper
    assert "INSERT INTO presentation_snapshots" in helper
    serialization_line = next(line for line in helper.splitlines() if "sections_json = json.dumps(" in line)
    assert "default=" not in serialization_line
