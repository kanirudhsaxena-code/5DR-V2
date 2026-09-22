"""MDOS VNext Learning Lab immutable envelope and daily snapshot builders.

Pure transformation only. These helpers do not write databases, alter forecasts,
change efficacy membership, or promote challengers.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from hashlib import sha256
import json
from typing import Any, Iterable, Mapping, Sequence

RUN_ROLES = {"CANONICAL", "DIAGNOSTIC", "MANUAL", "SHADOW"}
PRESENTATION_HORIZONS = {"D+1": "D", "D+2": "D+1", "D+3": "D+2", "D+4": "D+3", "D+5": "D+4"}


def _canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def content_hash(value: Any) -> str:
    return sha256(_canonical_json(value).encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class LearningRunContext:
    run_id: str
    run_role: str
    official_efficacy_eligible: bool
    target_trading_date: str
    source_ref: str
    exclusion_reason: str | None = None

    def validate(self) -> None:
        if not self.run_id:
            raise ValueError("run_id is mandatory")
        if self.run_role not in RUN_ROLES:
            raise ValueError("run_role must be CANONICAL, DIAGNOSTIC, MANUAL or SHADOW")
        if not self.target_trading_date:
            raise ValueError("target_trading_date is mandatory")
        if not self.source_ref:
            raise ValueError("source_ref is mandatory")
        if not self.official_efficacy_eligible and not self.exclusion_reason:
            raise ValueError("non-official observations require an exclusion_reason")


def build_observation_envelope(observation: Mapping[str, Any], context: LearningRunContext) -> dict[str, Any]:
    """Bind an existing immutable observation to explicit run-role/governance context."""
    context.validate()
    source_horizon = str(observation.get("horizon") or "")
    horizon = PRESENTATION_HORIZONS.get(source_horizon, source_horizon)
    if not horizon:
        raise ValueError("observation horizon is mandatory")
    dimension = str(observation.get("dimension") or "")
    observation_type = str(observation.get("observation_type") or "")
    if not dimension or not observation_type:
        raise ValueError("observation dimension and observation_type are mandatory")

    identity = {
        "run_id": context.run_id,
        "target_trading_date": context.target_trading_date,
        "horizon": horizon,
        "dimension": dimension,
        "observation_type": observation_type,
        "checkpoint_evaluation_id": observation.get("checkpoint_evaluation_id"),
        "recommendation_event_id": observation.get("recommendation_event_id"),
    }
    observation_id = "llobs-" + content_hash(identity)[:24]
    envelope = {
        "observation_id": observation_id,
        "engine": "5DR",
        "source_run_id": context.run_id,
        "run_role": context.run_role,
        "official_efficacy_eligible": context.official_efficacy_eligible,
        "target_trading_date": context.target_trading_date,
        "horizon": horizon,
        "source_horizon": source_horizon,
        "dimension": dimension,
        "observation_type": observation_type,
        "outcome_classification": observation.get("outcome_classification"),
        "metrics": dict(observation.get("metrics") or {}),
        "evidence": dict(observation.get("evidence") or {}),
        "diagnosis": observation.get("diagnosis"),
        "confidence": observation.get("confidence"),
        "exclusion_reason": context.exclusion_reason,
        "source_ref": context.source_ref,
        "production_change_allowed": False,
    }
    return envelope


def _day_normalized_rate(observations: Sequence[Mapping[str, Any]], success_type: str = "SUCCESS") -> float | None:
    grouped: dict[str, list[float]] = defaultdict(list)
    for row in observations:
        target_date = str(row.get("target_trading_date") or "")
        if not target_date:
            continue
        grouped[target_date].append(1.0 if row.get("observation_type") == success_type else 0.0)
    daily = [sum(values) / len(values) for values in grouped.values() if values]
    return None if not daily else sum(daily) / len(daily)


def build_daily_snapshot(
    *,
    cycle_id: str,
    as_of: str,
    runs: Sequence[Mapping[str, Any]],
    observations: Sequence[Mapping[str, Any]],
    matured_outcomes: Sequence[Mapping[str, Any]],
    hypotheses: Sequence[Mapping[str, Any]] = (),
    challengers: Sequence[Mapping[str, Any]] = (),
    methodology_versions: Mapping[str, Any] | None = None,
    source_lineage: Mapping[str, Any] | None = None,
    data_quality_state: str = "PASS",
) -> dict[str, Any]:
    """Create one deterministic NIFTY daily read-model payload.

    Repeated intraday runs remain visible in counts, while the snapshot records
    independent target-date counts and a day-normalized observation success rate.
    """
    if not cycle_id or not as_of:
        raise ValueError("cycle_id and as_of are mandatory")

    role_counts = Counter(str(row.get("run_role") or "") for row in runs)
    unknown_roles = set(role_counts) - RUN_ROLES
    if unknown_roles:
        raise ValueError(f"unknown run roles: {sorted(unknown_roles)}")

    scorable = sum(1 for row in matured_outcomes if row.get("scorable") is True)
    data_gaps = sum(1 for row in matured_outcomes if row.get("data_gap") is True)
    if scorable + data_gaps > len(matured_outcomes):
        raise ValueError("outcome populations overlap or exceed matured outcomes")

    active_hypotheses = sum(1 for row in hypotheses if row.get("status") not in {"REJECTED", "DEFERRED"})
    active_challengers = sum(1 for row in challengers if row.get("status") in {"CANDIDATE", "VALIDATING", "PENDING_USER_APPROVAL"})
    approval_required = sum(1 for row in challengers if row.get("status") == "PENDING_USER_APPROVAL")
    independent_target_dates = sorted({str(row.get("target_trading_date")) for row in runs if row.get("target_trading_date")})

    dimensions = Counter(str(row.get("dimension") or "UNCLASSIFIED") for row in observations)
    outcomes = Counter(str(row.get("outcome_classification") or "UNCLASSIFIED") for row in observations)
    content = {
        "independent_target_date_count": len(independent_target_dates),
        "independent_target_dates": independent_target_dates,
        "dimension_counts": dict(sorted(dimensions.items())),
        "outcome_counts": dict(sorted(outcomes.items())),
        "day_normalized_success_rate": _day_normalized_rate(observations),
        "official_efficacy_population": "CANONICAL_ONLY",
        "learning_population": "ALL_ELIGIBLE_RUN_ROLES_DAY_NORMALIZED",
        "production_change_allowed": False,
    }
    counts = {
        "runs_analyzed": len(runs),
        "canonical_runs": role_counts["CANONICAL"],
        "diagnostic_runs": role_counts["DIAGNOSTIC"],
        "manual_runs": role_counts["MANUAL"],
        "shadow_runs": role_counts["SHADOW"],
        "matured_outcomes": len(matured_outcomes),
        "scorable_outcomes": scorable,
        "data_gap_outcomes": data_gaps,
        "new_observations": len(observations),
        "active_hypotheses": active_hypotheses,
        "active_challengers": active_challengers,
        "approval_required": approval_required,
    }
    payload = {
        "engine": "5DR",
        "cycle_id": cycle_id,
        "as_of": as_of,
        "snapshot_status": "PARTIAL" if data_gaps else "COMPLETE",
        "counts": counts,
        "data_quality_state": data_quality_state,
        "methodology_versions": dict(methodology_versions or {}),
        "source_lineage": dict(source_lineage or {}),
        "snapshot": content,
    }
    digest = content_hash(payload)
    return {"snapshot_id": f"llsnap-5dr-{digest[:24]}", **payload, "content_hash": digest}
