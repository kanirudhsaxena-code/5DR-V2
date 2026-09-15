"""V2.2.2 integration boundary: validated evidence packet -> lifecycle actions.

This is deliberately dependency-injected. ChatGPT/5DR produces screenshot/web
research packets; this module validates and plans/persists them. It contains no
broker feed, scraping, image interpretation, scheduler, or order capability.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from .evidence_bridge import EvidenceBridgeError, EvidencePacket
from .lifecycle_executor import ExecutionResult, execute_actions
from .lifecycle_orchestrator import ProposedAction, plan_recommendation


@dataclass(frozen=True)
class BridgeResult:
    forecast_id: str
    actions: tuple[ProposedAction, ...]
    execution: ExecutionResult


def process_evidence_packet(
    recommendation: dict,
    lifecycle_status: str,
    existing_types: set[str],
    packet: EvidencePacket,
    *,
    execute_sql: Callable[[str, dict], int],
    writes_enabled: bool = False,
) -> BridgeResult:
    """Fail closed from normalized packet through the existing executor."""
    forecast_id = recommendation['forecast_id']
    if packet.forecast_id != forecast_id:
        actions = (ProposedAction('NO_WRITE', {'reason': 'FORECAST_ID_MISMATCH'}),)
    else:
        try:
            evidence = packet.to_option_evidence()
            actions = tuple(plan_recommendation(
                recommendation, lifecycle_status, evidence, existing_types
            ))
        except (EvidenceBridgeError, ValueError, KeyError, TypeError) as exc:
            actions = (ProposedAction('NO_WRITE', {'reason': str(exc) or 'EVIDENCE_REJECTED'}),)

    execution = execute_actions(
        forecast_id,
        actions,
        execute_sql=execute_sql,
        writes_enabled=writes_enabled,
    )
    return BridgeResult(forecast_id, actions, execution)
