"""Deterministic composition of existing 5DR domain primitives.

Consumes already-normalized evidence. It does not inspect screenshots and does not
invent missing inputs. Missing required evidence fails closed.
"""

from typing import Any, Dict

from .engine_contract import EngineRequest, MODEL_VERSION, OUTPUT_CONTRACT_VERSION
from .execution import execution_edge, tradeability
from .market_trust import market_trust, trust_band
from .probability import probabilities
from .scoring import des5, directional_label


def _merged_normalized(request: EngineRequest) -> Dict[str, Any]:
    merged: Dict[str, Any] = {}
    for item in request.evidence:
        for key, value in item.normalized.items():
            if key in merged and merged[key] != value:
                raise ValueError(f"5DR execution blocked: conflicting normalized evidence for {key}")
            merged[key] = value
    return merged


def domain_execute(request: EngineRequest) -> Dict[str, Any]:
    data = _merged_normalized(request)
    required = {
        "regime", "component_scores", "market_trust_inputs", "event_shock",
        "execution_inputs", "data_adequate", "event_kill_switch", "expected_rr",
        "forecast_assessment", "recommendation_assessment", "horizon_slots",
        "recommendation_ledger_complete", "assessment_snapshot_complete",
    }
    missing = sorted(required - set(data))
    if missing:
        raise ValueError(f"5DR execution blocked: missing normalized inputs {missing}")

    directional_score = des5(data["component_scores"], data["regime"])
    trust_score = market_trust(data["market_trust_inputs"])
    scenario_probabilities = probabilities(directional_score, trust_score, data["event_shock"])
    edge_score = execution_edge(data["execution_inputs"])
    is_tradeable, blockers = tradeability(
        data_adequate=bool(data["data_adequate"]),
        market_trust=trust_score,
        des5=directional_score,
        execution_edge=edge_score,
        event_kill_switch=bool(data["event_kill_switch"]),
        expected_rr=float(data["expected_rr"]),
    )

    return {
        "model_version": MODEL_VERSION,
        "output_contract_version": OUTPUT_CONTRACT_VERSION,
        "forecast_assessment": data["forecast_assessment"],
        "recommendation_assessment": data["recommendation_assessment"],
        "assessment_snapshot_complete": bool(data["assessment_snapshot_complete"]),
        "horizon_slots": data["horizon_slots"],
        "recommendation_ledger_complete": bool(data["recommendation_ledger_complete"]),
        "des5": directional_score,
        "directional_label": directional_label(directional_score),
        "market_trust": trust_score,
        "market_trust_band": trust_band(trust_score),
        "probabilities": scenario_probabilities,
        "execution_edge": edge_score,
        "tradeable": is_tradeable,
        "tradeability_blockers": blockers,
    }
