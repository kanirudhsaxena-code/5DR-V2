"""Fail-closed activation wrapper for the 5DR V2.2.2 lifecycle chain.

This module connects only already-normalized evidence to the approved runner and DB
adapter. It does not acquire evidence, research the web, interpret screenshots, or
place trades. Missing/invalid evidence therefore cannot be converted into a write.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .evidence_handoff import load_packets
from .production_lifecycle_runner import RunSummary, run_lifecycle


@dataclass(frozen=True)
class ActivationResult:
    mode: str
    writes_enabled: bool
    evidence_file_present: bool
    summary: RunSummary | None
    reason: str | None = None


def activate(db, evidence_path: str | Path | None, *, writes_enabled: bool = False) -> ActivationResult:
    """Run one governed lifecycle iteration.

    Production writes require BOTH explicit writes_enabled=True and a valid evidence
    handoff file. No evidence path/file is a normal NO_WRITE result, not an error.
    """
    if evidence_path is None:
        return ActivationResult('NO_WRITE', writes_enabled, False, None, 'NO_EVIDENCE_HANDOFF')
    path = Path(evidence_path)
    if not path.is_file():
        return ActivationResult('NO_WRITE', writes_enabled, False, None, 'NO_EVIDENCE_HANDOFF')

    packets = load_packets(path)  # validation failures intentionally fail closed
    recommendations = db.actionable_recommendations()
    summary = run_lifecycle(
        recommendations,
        packets,
        db.existing_event_types,
        execute_sql=lambda sql, params: db.execute_lifecycle_sql(
            sql, params, writes_enabled=writes_enabled
        ),
        writes_enabled=writes_enabled,
    )
    mode = 'WRITE_ENABLED' if writes_enabled else 'DRY_RUN'
    return ActivationResult(mode, writes_enabled, True, summary)
