"""Generate a deterministic BT100 quantitative backfill plan.

This module performs no network and no storage writes. It derives bounded historical
requests from the frozen 5DR consumer registry and the 100-session target manifest.
"""
from __future__ import annotations

import hashlib
import json
from datetime import date, timedelta

from experiments.data_requirements import requirements
from experiments.upstox_history_policy import plan_requirement_history

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
        if not requirement.get("lookback_days"):
            continue
        # Plan enough history for the earliest replay cutoff, not merely the latest.
        max_lookback = max(requirement["lookback_days"].values())
        anchor = last_outcome
        desired_start = first_target - timedelta(days=max_lookback + LOOKBACK_BUFFER_DAYS)
        provider_plan = plan_requirement_history(requirement, anchor)
        provider_plan = [
            item for item in provider_plan
            if item["end"] >= desired_start
        ]
        rows.append({
            "variable_id": requirement["variable_id"],
            "category": requirement["category"],
            "source_preference": requirement["source_preference"],
            "desired_start": desired_start.isoformat(),
            "desired_end": last_outcome.isoformat(),
            "chunks": [
                {
                    **item,
                    "start": item["start"].isoformat(),
                    "end": item["end"].isoformat(),
                }
                for item in provider_plan
            ],
        })

    plan = {
        "schema": "bt100-quantitative-backfill-plan-v1",
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
