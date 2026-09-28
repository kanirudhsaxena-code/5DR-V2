"""Build the immutable P0-11 presentation for a newly SELECTED 5DR canonical.

The builder consumes only already-persisted canonical 5DR records. It does not
recompute forecasts, efficacy, recommendations, or trading decisions.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from .presentation_snapshot import build_presentation_snapshot, semantic_presentation_hash


def _as_mapping(value: Any, error: str) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(error)
    return dict(value)


def build_selected_canonical_presentation(
    *,
    run_id: int,
    forecast_id: str,
    run: Mapping[str, Any],
    assessment_snapshot: Mapping[str, Any],
    forecast: Mapping[str, Any],
    daily_forecasts: Sequence[Mapping[str, Any]],
    component_scores: Sequence[Mapping[str, Any]],
    execution_plan: Mapping[str, Any],
) -> dict[str, Any]:
    """Return the exact two-section V2.1.2 presentation snapshot.

    Identity and completeness are checked before hashing. Array ordering is part
    of the immutable presentation semantics, so daily rows must be D+1..D+5 and
    component rows are expected to be supplied in deterministic order.
    """
    run_row = _as_mapping(run, "P0_11_5DR_RUN_MISSING")
    forecast_row = _as_mapping(forecast, "P0_11_5DR_FORECAST_MISSING")
    assessment_row = _as_mapping(assessment_snapshot, "P0_11_5DR_ASSESSMENT_MISSING")
    execution_row = _as_mapping(execution_plan, "P0_11_5DR_EXECUTION_PLAN_MISSING")

    if int(run_row.get("run_id") or -1) != int(run_id):
        raise ValueError("P0_11_5DR_RUN_RECORD_IDENTITY_MISMATCH")
    if str(forecast_row.get("forecast_id") or "") != str(forecast_id):
        raise ValueError("P0_11_5DR_FORECAST_IDENTITY_MISMATCH")
    if int(forecast_row.get("run_id") or -1) != int(run_id):
        raise ValueError("P0_11_5DR_RUN_IDENTITY_MISMATCH")
    if str(assessment_row.get("forecast_id") or "") != str(forecast_id):
        raise ValueError("P0_11_5DR_ASSESSMENT_IDENTITY_MISMATCH")
    if int(assessment_row.get("run_id") or -1) != int(run_id):
        raise ValueError("P0_11_5DR_ASSESSMENT_RUN_MISMATCH")
    if assessment_row.get("completeness_status") != "COMPLETE":
        raise ValueError("P0_11_5DR_ASSESSMENT_INCOMPLETE")
    if str(execution_row.get("forecast_id") or "") != str(forecast_id):
        raise ValueError("P0_11_5DR_EXECUTION_IDENTITY_MISMATCH")

    daily_rows = [dict(row) for row in daily_forecasts]
    if len(daily_rows) != 5:
        raise ValueError("P0_11_5DR_DAILY_PATH_INCOMPLETE")
    if [int(row.get("day_number") or -1) for row in daily_rows] != [1, 2, 3, 4, 5]:
        raise ValueError("P0_11_5DR_DAILY_PATH_ORDER_MISMATCH")
    if any(str(row.get("forecast_id") or "") != str(forecast_id) for row in daily_rows):
        raise ValueError("P0_11_5DR_DAILY_PATH_IDENTITY_MISMATCH")

    component_rows = [dict(row) for row in component_scores]
    if any(str(row.get("forecast_id") or "") != str(forecast_id) for row in component_rows):
        raise ValueError("P0_11_5DR_COMPONENT_IDENTITY_MISMATCH")

    current_run = {
        "run": run_row,
        "forecast": forecast_row,
        "daily_forecasts": daily_rows,
        "component_scores": component_rows,
        "execution_plan": execution_row,
    }
    source_payload = {
        "assessment_snapshot": assessment_row,
        "current_run": current_run,
    }
    source_payload_hash = semantic_presentation_hash(source_payload)
    sections = [
        {
            "name": "TABLE_1_5DR_ASSESSMENT_EFFICACY",
            "assessment_snapshot": assessment_row,
        },
        {
            "name": "TABLE_2_CURRENT_5DR_RUN",
            **current_run,
        },
    ]
    return build_presentation_snapshot(
        run_id=run_id,
        result_id=forecast_id,
        governance_state="SELECTED",
        sections=sections,
        source_payload_hash=source_payload_hash,
        checkpoint_id=None,
    )
