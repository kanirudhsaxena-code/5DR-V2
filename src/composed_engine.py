"""Deterministic composition of existing 5DR domain primitives.

Consumes already-normalized market evidence. It does not inspect screenshots and does
not invent missing inputs. Missing required execution evidence fails closed.

Lifecycle outputs (forecast/recommendation assessment and ledger completion) are
created after a forecast exists and therefore are intentionally not upstream engine
inputs.
"""

from typing import Any, Dict

from .engine_contract import EngineRequest, MODEL_VERSION, OUTPUT_CONTRACT_VERSION, validate_horizon_slots
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
        "event_transmission", "convexity_warranted",
        "execution_inputs", "data_adequate", "event_kill_switch", "expected_rr",
        "horizon_slots",
    }
    missing = sorted(required - set(data))
    if missing:
        raise ValueError(f"5DR execution blocked: missing normalized inputs {missing}")

    validate_horizon_slots(data["horizon_slots"])
    directional_score = des5(data["component_scores"], data["regime"])
    trust_score = market_trust(data["market_trust_inputs"])
    scenario_probabilities = probabilities(directional_score, trust_score, data["event_shock"])
    winning_scenario = max(("BULL", "RANGE", "BEAR"), key=lambda key: scenario_probabilities[key])
    definitive_forecast = {"BULL": "BULLISH", "RANGE": "RANGE", "BEAR": "BEARISH"}[winning_scenario]
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
        "horizon_slots": data["horizon_slots"],
        "expected_zone": {
            "low": float(data["horizon_slots"]["D+5"]["zone_low"]),
            "high": float(data["horizon_slots"]["D+5"]["zone_high"]),
        },
        "regime": data["regime"],
        "des5": directional_score,
        "directional_label": directional_label(directional_score),
        "definitive_forecast": definitive_forecast,
        "market_trust": trust_score,
        "market_trust_band": trust_band(trust_score),
        "probabilities": scenario_probabilities,
        "event_shock": {
            "level": data["event_shock"],
            "transmission": data["event_transmission"],
            "convexity_warranted": bool(data["convexity_warranted"]),
            "kill_switch": bool(data["event_kill_switch"]),
        },
        "execution_edge": edge_score,
        "expected_rr": float(data["expected_rr"]),
        "tradeable": is_tradeable,
        "tradeability_blockers": blockers,
        "engine_diagnostics": {
            "component_scores": data["component_scores"],
            "market_trust_inputs": data["market_trust_inputs"],
            "execution_inputs": data["execution_inputs"],
            "data_adequate": bool(data["data_adequate"]),
        },
    }
