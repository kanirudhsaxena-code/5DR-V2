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
SCENARIOS = ("BULL", "RANGE", "BEAR")
HORIZON_DIRECTIONS = {"BULLISH": "BULL", "RANGE": "RANGE", "BEARISH": "BEAR"}


def validate_horizon_slots(slots: Any) -> bool:
    if not isinstance(slots, dict) or set(slots) != set(REQUIRED_HORIZONS):
        raise ValueError("5DR execution blocked: horizon_slots must contain exactly D+1 through D+5")
    for horizon in REQUIRED_HORIZONS:
        slot = slots[horizon]
        if not isinstance(slot, dict):
            raise ValueError(f"5DR execution blocked: {horizon} slot must be an object")
        direction = slot.get("direction")
        if direction not in HORIZON_DIRECTIONS:
            raise ValueError(f"5DR execution blocked: {horizon} direction must be BULLISH, RANGE or BEARISH")
        probs = slot.get("probabilities")
        if not isinstance(probs, dict) or set(probs) != set(SCENARIOS):
            raise ValueError(f"5DR execution blocked: {horizon} probabilities must contain exactly BULL, RANGE and BEAR")
        try:
            values = {key: float(probs[key]) for key in SCENARIOS}
            low = float(slot["zone_low"])
            high = float(slot["zone_high"])
        except (TypeError, ValueError, KeyError):
            raise ValueError(f"5DR execution blocked: {horizon} scenario probabilities and zone must be numeric")
        if any(value < 0 or value > 100 for value in values.values()):
            raise ValueError(f"5DR execution blocked: {horizon} scenario probabilities must be 0..100")
        if abs(sum(values.values()) - 100.0) > 0.02:
            raise ValueError(f"5DR execution blocked: {horizon} scenario probabilities must total 100")
        selected = values[HORIZON_DIRECTIONS[direction]]
        if abs(selected - max(values.values())) > 0.02:
            raise ValueError(f"5DR execution blocked: {horizon} direction must match the highest scenario probability")
        if low <= 0 or high < low:
            raise ValueError(f"5DR execution blocked: {horizon} requires positive zone_low <= zone_high")
        if not isinstance(slot.get("basis"), str) or not slot["basis"].strip():
            raise ValueError(f"5DR execution blocked: {horizon} evidence basis is mandatory")
    return True


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
