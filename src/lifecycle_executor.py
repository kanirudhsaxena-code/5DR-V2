"""Approval-gated V2.2.2 lifecycle action executor.

This module translates already-planned actions into persistence operations.
It contains no scheduler, evidence acquisition, or broker execution capability.
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Callable, Iterable

from .lifecycle_orchestrator import ProposedAction
from .lifecycle_persistence import (
    assert_append_only_event_sql,
    checkpoint_capture_sql,
    recommendation_event_insert,
)


@dataclass(frozen=True)
class ExecutionResult:
    attempted: int
    persisted: int
    skipped: int
    reasons: tuple[str, ...]


def execute_actions(
    forecast_id: str,
    actions: Iterable[ProposedAction],
    *,
    execute_sql: Callable[[str, dict], int],
    writes_enabled: bool = False,
) -> ExecutionResult:
    """Persist planned actions only when the explicit write switch is enabled.

    execute_sql must return the affected-row count. NO_WRITE is always skipped.
    With writes_enabled=False, all write-capable actions are dry-run skipped.
    """
    attempted = persisted = skipped = 0
    reasons: list[str] = []

    for action in actions:
        attempted += 1
        if action.kind == 'NO_WRITE':
            skipped += 1
            reasons.append(str(action.payload.get('reason', 'NO_WRITE')))
            continue
        if not writes_enabled:
            skipped += 1
            reasons.append('WRITES_DISABLED')
            continue

        if action.kind in {'EVENT', 'MARK'}:
            payload = dict(action.payload)
            event_type = payload.pop('event_type', 'MARK')
            sql = recommendation_event_insert(event_type)
            assert_append_only_event_sql(sql)
            params = {
                'forecast_id': forecast_id,
                'event_type': event_type,
                'event_timestamp': payload.get('observed_at'),
                'premium': payload.get('premium'),
                'pnl_pct': payload.get('pnl_pct'),
                'r_multiple': payload.get('r_multiple'),
                'source_ref': payload.get('source_ref'),
                'notes': payload.get('note') or payload.get('notes'),
            }
        elif action.kind == 'CHECKPOINT':
            sql = checkpoint_capture_sql()
            params = {
                'checkpoint_id': action.payload['checkpoint_id'],
                'observed_at': action.payload.get('observed_at'),
                'actual_nifty': action.payload.get('actual_nifty'),
                'period_high': action.payload.get('period_high'),
                'period_low': action.payload.get('period_low'),
                'option_premium': action.payload.get('option_premium'),
                'source_ref': action.payload.get('source_ref'),
                'notes': action.payload.get('notes'),
            }
        else:
            raise ValueError(f'unsupported proposed action: {action.kind}')

        persisted += int(execute_sql(sql, params) or 0)

    return ExecutionResult(attempted, persisted, skipped, tuple(reasons))
