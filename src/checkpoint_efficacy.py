"""Convert immutable captured D+1..D+5 checkpoints into efficacy records.

Pure transformation only: no database writes and no methodology mutation. Missing
forecast inputs or uncaptured checkpoints fail closed as NOT_SCORABLE records.
"""
from __future__ import annotations

from .assessment import evaluate_forecast_checkpoint

PRIMARY_CHECKPOINTS = {f"D+{day}": day for day in range(1, 6)}


def checkpoint_to_efficacy(forecast: dict, checkpoint: dict) -> dict:
    checkpoint_type = checkpoint.get("checkpoint_type")
    if checkpoint_type not in PRIMARY_CHECKPOINTS:
        raise ValueError("only D+1 through D+5 checkpoints are efficacy horizons")

    base = {
        "forecast_id": forecast.get("forecast_id"),
        "checkpoint_id": checkpoint.get("checkpoint_id"),
        "checkpoint_type": checkpoint_type,
        "day_number": PRIMARY_CHECKPOINTS[checkpoint_type],
    }
    if forecast.get("forecast_id") != checkpoint.get("forecast_id"):
        return {**base, "evaluation_status": "NOT_SCORABLE", "reason": "FORECAST_ID_MISMATCH"}
    if checkpoint.get("status") != "CAPTURED" or checkpoint.get("actual_nifty") is None:
        return {**base, "evaluation_status": "NOT_SCORABLE", "reason": "CHECKPOINT_NOT_CAPTURED"}

    required = ("bias", "reference_spot", "zone_low", "zone_high")
    missing = [name for name in required if forecast.get(name) is None]
    if missing:
        return {**base, "evaluation_status": "NOT_SCORABLE", "reason": "MISSING_FORECAST_INPUTS:" + ",".join(missing)}

    try:
        metrics = evaluate_forecast_checkpoint(
            bias=forecast["bias"],
            reference_spot=forecast["reference_spot"],
            actual_close=checkpoint["actual_nifty"],
            zone_low=forecast["zone_low"],
            zone_high=forecast["zone_high"],
        )
    except (TypeError, ValueError) as exc:
        return {**base, "evaluation_status": "NOT_SCORABLE", "reason": str(exc) or "INVALID_FORECAST_INPUTS"}

    return {
        **base,
        "evaluation_status": "SCORABLE",
        "actual_close": float(checkpoint["actual_nifty"]),
        "source_ref": checkpoint.get("source_ref"),
        **metrics,
    }


def build_efficacy_records(forecasts: list[dict], checkpoints: list[dict]) -> list[dict]:
    """Build deterministic D+1..D+5 efficacy rows for captured/due ledger data."""
    by_forecast = {row.get("forecast_id"): row for row in forecasts if row.get("forecast_id")}
    rows = []
    for checkpoint in checkpoints:
        if checkpoint.get("checkpoint_type") not in PRIMARY_CHECKPOINTS:
            continue
        forecast = by_forecast.get(checkpoint.get("forecast_id"))
        if forecast is None:
            rows.append({
                "forecast_id": checkpoint.get("forecast_id"),
                "checkpoint_id": checkpoint.get("checkpoint_id"),
                "checkpoint_type": checkpoint.get("checkpoint_type"),
                "day_number": PRIMARY_CHECKPOINTS[checkpoint["checkpoint_type"]],
                "evaluation_status": "NOT_SCORABLE",
                "reason": "FORECAST_NOT_FOUND",
            })
            continue
        rows.append(checkpoint_to_efficacy(forecast, checkpoint))
    return rows
