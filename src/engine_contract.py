"""Governed input contract for 5DR engine orchestration.

This module defines the boundary between EDGE Console run requests and the
5DR Python engine. It deliberately does not infer evidence from screenshots;
classification/normalization must happen upstream and be explicit.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List

MODEL_VERSION = "5DR_V2_1"
OUTPUT_CONTRACT_VERSION = "5DR_V2_1_2"
REQUIRED_HORIZONS = ("D+1", "D+2", "D+3", "D+4", "D+5")


@dataclass(frozen=True)
class EvidenceItem:
    evidence_type: str
    source_ref: str
    captured_at: str | None = None
    normalized: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class EngineRequest:
    request_id: str
    provenance_mode: str
    evidence: List[EvidenceItem]
    framework_version: str = MODEL_VERSION
    output_contract_version: str = OUTPUT_CONTRACT_VERSION


def validate_engine_request(request: EngineRequest) -> bool:
    if not request.request_id.strip():
        raise ValueError("5DR engine request blocked: request_id is mandatory")
    if request.provenance_mode not in {"MANUAL", "HYBRID", "AUTOMATED"}:
        raise ValueError("5DR engine request blocked: invalid provenance mode")
    if request.framework_version != MODEL_VERSION:
        raise ValueError("5DR engine request blocked: invalid framework version")
    if request.output_contract_version != OUTPUT_CONTRACT_VERSION:
        raise ValueError("5DR engine request blocked: invalid output contract version")
    if not request.evidence:
        raise ValueError("5DR engine request blocked: evidence is mandatory")
    for item in request.evidence:
        if not item.evidence_type.strip() or not item.source_ref.strip():
            raise ValueError("5DR engine request blocked: evidence type/source_ref required")
        if not isinstance(item.normalized, dict):
            raise ValueError("5DR engine request blocked: normalized evidence must be a mapping")
    return True
