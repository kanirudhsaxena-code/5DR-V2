"""Prompt invocation contract for MDOS 5DR V2.2.3.

Maps the human command "5DR" / "5DR NIFTY" to the already-approved structured
production evidence runtime. The adapter never broadens approved acquisition
windows and never enables forecast publication, persistence, lifecycle writes,
Learning Lab mutation, or trading.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from experiments.data_contract import DataArchitectureError
from experiments.production_evidence import classify_production_window


ALLOWED_COMMANDS = {"5DR", "5DR NIFTY"}


@dataclass(frozen=True)
class PromptInvocation:
    command: str
    requested_at: datetime
    request_id: str


def normalize_command(command: str) -> str:
    if not isinstance(command, str):
        raise DataArchitectureError("5DR prompt command must be text")
    normalized = " ".join(command.strip().upper().split())
    if normalized not in ALLOWED_COMMANDS:
        raise DataArchitectureError("unsupported 5DR prompt command")
    return normalized


def plan_prompt_invocation(invocation: PromptInvocation) -> dict:
    command = normalize_command(invocation.command)
    if not isinstance(invocation.request_id, str) or not invocation.request_id.strip():
        raise DataArchitectureError("5DR prompt request_id is mandatory")
    if not isinstance(invocation.requested_at, datetime) or invocation.requested_at.tzinfo is None:
        raise DataArchitectureError("5DR prompt requested_at must be timezone-aware")

    try:
        window = classify_production_window(invocation.requested_at)
    except DataArchitectureError as error:
        return {
            "schema": "5dr-v2-2-3-prompt-invocation-v1",
            "status": "BLOCKED_OUTSIDE_VALIDATED_WINDOW",
            "request_id": invocation.request_id.strip(),
            "command": command,
            "reason": str(error),
            "acquire_structured_evidence": False,
            "forecast_release_enabled": False,
            "production_5dr_write_enabled": False,
            "lifecycle_write_enabled": False,
            "learning_lab_write_enabled": False,
            "trading_execution_enabled": False,
            "methodology_changed": False,
        }

    return {
        "schema": "5dr-v2-2-3-prompt-invocation-v1",
        "status": "READY_TO_ACQUIRE",
        "request_id": invocation.request_id.strip(),
        "command": command,
        "acquire_structured_evidence": True,
        "approved_window": window,
        "next_step": "RUN_STRUCTURED_PRODUCTION_EVIDENCE",
        "forecast_release_enabled": False,
        "production_5dr_write_enabled": False,
        "lifecycle_write_enabled": False,
        "learning_lab_write_enabled": False,
        "trading_execution_enabled": False,
        "methodology_changed": False,
    }
