"""Approval-gated orchestration for 5DR Learning Lab research.

This module can decide whether observation support is sufficient to test a
hypothesis and whether supplied challenger evidence is promotion-eligible. It
cannot mutate production; every passing promotion is emitted only as a
PENDING_USER_APPROVAL proposal.
"""
from __future__ import annotations

from dataclasses import asdict

from .learning_lab import LearningThresholds, PromotionEvidence, evaluate_promotion, hypothesis_ready


def observation_support(observations: list[dict], *, dimension: str, outcome_classification: str | None = None) -> dict:
    scoped = [row for row in observations if row.get("dimension") == dimension]
    if outcome_classification is None:
        supporting = scoped
    else:
        supporting = [row for row in scoped if row.get("outcome_classification") == outcome_classification]
    total = len(scoped)
    count = len(supporting)
    return {"supporting_observations": count, "total_observations": total, "support_ratio": (count / total if total else 0.0)}


def hypothesis_gate(observations: list[dict], *, dimension: str, outcome_classification: str | None = None,
                    thresholds: LearningThresholds = LearningThresholds()) -> dict:
    support = observation_support(observations, dimension=dimension, outcome_classification=outcome_classification)
    ready = hypothesis_ready(support["supporting_observations"], support["support_ratio"], thresholds)
    return {
        **support,
        "ready_for_challenger_testing": ready,
        "production_change_allowed": False,
        "status": "READY_FOR_CHALLENGER_TESTING" if ready else "INSUFFICIENT_SUPPORT",
    }


def promotion_gate(evidence: PromotionEvidence, *, challenger_code: str, proposed_model_version: str) -> dict:
    decision = evaluate_promotion(evidence)
    if not decision.eligible:
        return {
            "challenger_code": challenger_code,
            "eligible": False,
            "status": "REJECTED_OR_INSUFFICIENT",
            "reasons": list(decision.reasons),
            "production_change_allowed": False,
        }
    return {
        "challenger_code": challenger_code,
        "eligible": True,
        "status": "PENDING_USER_APPROVAL",
        "proposed_model_version": proposed_model_version,
        "eligibility_checks": asdict(evidence),
        "reasons": list(decision.reasons),
        "production_change_allowed": False,
        "explicit_user_approval_required": True,
    }
