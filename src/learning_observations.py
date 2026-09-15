"""Create deterministic Learning Lab observations from immutable 5DR results.

Pure transformation only. This module cannot mutate production configuration,
create challengers, or approve promotion. It converts already-assessed efficacy
and recommendation outcomes into research observations for later hypothesis work.
"""
from __future__ import annotations


def efficacy_observation(row: dict) -> dict | None:
    if row.get("evaluation_status") != "SCORABLE":
        return None
    horizon = row.get("checkpoint_type")
    if horizon not in {f"D+{day}" for day in range(1, 6)}:
        return None
    directional_hit = bool(row.get("directional_hit"))
    zone_hit = bool(row.get("zone_hit"))
    if directional_hit and zone_hit:
        observation_type, outcome = "SUCCESS", "DIRECTION_AND_ZONE_HIT"
    elif directional_hit:
        observation_type, outcome = "SUCCESS", "DIRECTION_HIT_ZONE_MISS"
    else:
        observation_type, outcome = "ERROR", "DIRECTION_MISS"
    return {
        "forecast_id": row.get("forecast_id"),
        "checkpoint_evaluation_id": row.get("evaluation_id"),
        "horizon": horizon,
        "dimension": "PROBABILITY_CALIBRATION",
        "observation_type": observation_type,
        "outcome_classification": outcome,
        "metrics": {
            "directional_hit": directional_hit,
            "directional_margin_points": row.get("directional_margin_points"),
            "zone_hit": zone_hit,
            "zone_error_points": row.get("zone_error_points"),
        },
        "evidence": {"source_ref": row.get("source_ref")},
        "diagnosis": "Immutable forecast checkpoint assessment imported for Learning Lab analysis; no causal attribution inferred.",
        "confidence": 100.0,
    }


def recommendation_observation(row: dict) -> dict | None:
    if row.get("recommendation") == "NO_TRADE":
        return None
    outcome = row.get("primary_outcome")
    if outcome not in {"WIN", "LOSS"}:
        return None
    return {
        "forecast_id": row.get("forecast_id"),
        "recommendation_event_id": row.get("terminal_event_id"),
        "horizon": "TRADE",
        "dimension": "EXECUTION_EDGE",
        "observation_type": "SUCCESS" if outcome == "WIN" else "ERROR",
        "outcome_classification": outcome,
        "metrics": {
            "final_pnl_pct": row.get("final_pnl_pct"),
            "r_multiple": row.get("r_multiple"),
        },
        "evidence": {"terminal_source_ref": row.get("terminal_source_ref")},
        "diagnosis": "Resolved immutable recommendation outcome imported for Learning Lab analysis; no causal attribution inferred.",
        "confidence": 100.0,
    }


def build_learning_observations(efficacy_rows: list[dict], recommendation_rows: list[dict]) -> list[dict]:
    observations = []
    for row in efficacy_rows:
        observation = efficacy_observation(row)
        if observation is not None:
            observations.append(observation)
    for row in recommendation_rows:
        observation = recommendation_observation(row)
        if observation is not None:
            observations.append(observation)
    return observations
