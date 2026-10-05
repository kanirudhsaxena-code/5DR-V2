"""Generate a deterministic BT100 quantitative backfill plan.

This module performs no network and no storage writes. Unlike the live-production
planner, replay coverage is continuous across the full frozen cohort so an older
target date is not accidentally deprived of its own historical lookback.
"""
from __future__ import annotations

import hashlib
import json
from datetime import date, timedelta

from experiments.data_requirements import requirements
from experiments.upstox_history_policy import TIMEFRAME_MAP, plan_history_chunks

LOOKBACK_BUFFER_DAYS = 7


def _hash(value):
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def build_plan(target_dates_doc):
    sessions = target_dates_doc.get("sessions")
    if not isinstance(sessions, list) or len(sessions) != 100:
        raise ValueError("BT100 target manifest must contain exactly 100 sessions")
    first_target = date.fromisoformat(sessions[0]["target_date"])
    last_outcome = date.fromisoformat(sessions[-1]["horizon_dates"]["D+5"])

    rows = []
    for requirement in requirements("5DR"):
        if not requirement.get("enabled_experiment"):
            continue
        lookbacks = requirement.get("lookback_days") or {}
        if not isinstance(lookbacks, dict) or not lookbacks:
            continue

        timeframe_plans = []
        for timeframe in requirement.get("timeframes", ()):
            days = lookbacks.get(timeframe)
            if days is None:
                continue
            if timeframe not in TIMEFRAME_MAP:
                raise ValueError(f"unsupported timeframe {timeframe}")
            if isinstance(days, bool) or not isinstance(days, int) or days <= 0:
                raise ValueError(f"invalid lookback for {timeframe}")
            unit, interval = TIMEFRAME_MAP[timeframe]
            desired_start = first_target - timedelta(days=(days - 1) + LOOKBACK_BUFFER_DAYS)
            desired_end = last_outcome
            chunks = plan_history_chunks(desired_start, desired_end, unit, interval)
            timeframe_plans.append({
                "timeframe": timeframe,
                "lookback_days": days,
                "desired_start": desired_start.isoformat(),
                "desired_end": desired_end.isoformat(),
                "chunks": [
                    {
                        "start": item["start"].isoformat(),
                        "end": item["end"].isoformat(),
                        "unit": item["unit"],
                        "interval": item["interval"],
                    }
                    for item in chunks
                ],
            })

        if timeframe_plans:
            rows.append({
                "variable_id": requirement["variable_id"],
                "category": requirement["category"],
                "source_preference": requirement["source_preference"],
                "timeframes": timeframe_plans,
            })

    plan = {
        "schema": "bt100-quantitative-backfill-plan-v2",
        "target_count": 100,
        "first_target_date": first_target.isoformat(),
        "last_outcome_date": last_outcome.isoformat(),
        "variables": rows,
        "read_only_plan": True,
        "production_writes": 0,
        "production_neuron_calls": 0,
        "trading_enabled": False,
    }
    plan["plan_sha256"] = _hash(plan)
    return plan


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("target_dates_json")
    args = parser.parse_args()
    with open(args.target_dates_json, "r", encoding="utf-8") as handle:
        target_dates = json.load(handle)
    print(json.dumps(build_plan(target_dates), sort_keys=True, indent=2, default=str))


if __name__ == "__main__":
    main()
