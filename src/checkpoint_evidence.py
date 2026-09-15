"""Verified evidence boundary for D+1..D+5 checkpoint capture.

This module never acquires or infers market data. It accepts an already-normalized
manual screenshot/web-research observation and plans a CHECKPOINT action only when
it exactly matches a due checkpoint and passes provenance/freshness validation.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from math import isfinite

from .lifecycle_orchestrator import ProposedAction

ALLOWED_SOURCE_TYPES = {"SCREENSHOT", "WEB_RESEARCH"}


@dataclass(frozen=True)
class CheckpointEvidence:
    forecast_id: str
    checkpoint_type: str
    observed_at: datetime
    actual_nifty: float
    source_type: str
    source_ref: str
    verified: bool
    fresh: bool
    period_high: float | None = None
    period_low: float | None = None
    option_premium: float | None = None
    notes: str | None = None


def _finite_nonnegative(value: float | None) -> bool:
    return value is None or (isfinite(float(value)) and float(value) >= 0)


def plan_checkpoint_capture(checkpoint: dict, evidence: CheckpointEvidence) -> ProposedAction:
    """Fail closed unless evidence exactly belongs to the supplied due checkpoint."""
    if checkpoint.get("status") != "DUE":
        return ProposedAction("NO_WRITE", {"reason": "CHECKPOINT_NOT_DUE"})
    if evidence.forecast_id != checkpoint.get("forecast_id"):
        return ProposedAction("NO_WRITE", {"reason": "FORECAST_ID_MISMATCH"})
    if evidence.checkpoint_type != checkpoint.get("checkpoint_type"):
        return ProposedAction("NO_WRITE", {"reason": "CHECKPOINT_TYPE_MISMATCH"})
    if evidence.source_type not in ALLOWED_SOURCE_TYPES:
        return ProposedAction("NO_WRITE", {"reason": "SOURCE_TYPE_REJECTED"})
    if not evidence.source_ref.strip() or not evidence.verified or not evidence.fresh:
        return ProposedAction("NO_WRITE", {"reason": "UNVERIFIED_OR_STALE_EVIDENCE"})
    if evidence.observed_at.tzinfo is None:
        return ProposedAction("NO_WRITE", {"reason": "TIMEZONE_REQUIRED"})

    due_date = checkpoint.get("due_date")
    if isinstance(due_date, str):
        due_date = date.fromisoformat(due_date)
    if due_date != evidence.observed_at.date():
        return ProposedAction("NO_WRITE", {"reason": "DUE_DATE_MISMATCH"})
    if not _finite_nonnegative(evidence.actual_nifty) or evidence.actual_nifty == 0:
        return ProposedAction("NO_WRITE", {"reason": "INVALID_NIFTY_VALUE"})
    for value in (evidence.period_high, evidence.period_low, evidence.option_premium):
        if not _finite_nonnegative(value):
            return ProposedAction("NO_WRITE", {"reason": "INVALID_OPTIONAL_VALUE"})
    if evidence.period_high is not None and evidence.period_low is not None and evidence.period_high < evidence.period_low:
        return ProposedAction("NO_WRITE", {"reason": "HIGH_BELOW_LOW"})

    return ProposedAction("CHECKPOINT", {
        "checkpoint_id": checkpoint["checkpoint_id"],
        "observed_at": evidence.observed_at,
        "actual_nifty": float(evidence.actual_nifty),
        "period_high": evidence.period_high,
        "period_low": evidence.period_low,
        "option_premium": evidence.option_premium,
        "source_ref": evidence.source_ref,
        "notes": evidence.notes,
    })
