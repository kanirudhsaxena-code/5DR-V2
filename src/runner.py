"""Console-facing 5DR execution runner.

Consumes an explicit normalized EngineRequest payload, executes the governed
5DR composition, and emits the immutable V2.1.2 envelope expected by
EDGE Console. It does not inspect screenshots or infer missing evidence.
"""

from __future__ import annotations

import argparse
import json
import sys
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Iterable

from .composed_engine import domain_execute
from .engine_contract import EngineRequest, EvidenceItem, MODEL_VERSION, OUTPUT_CONTRACT_VERSION
from .orchestrator import execute
from .output_contract import validate_output_contract

CONSOLE_CONTRACT_VERSION = "1.0"


def _parse_evidence(items: Iterable[Dict[str, Any]]) -> list[EvidenceItem]:
    evidence: list[EvidenceItem] = []
    for raw in items:
        if not isinstance(raw, dict):
            raise ValueError("5DR runner blocked: each evidence item must be an object")
        evidence.append(
            EvidenceItem(
                evidence_type=str(raw.get("evidence_type", "")),
                source_ref=str(raw.get("source_ref", "")),
                captured_at=raw.get("captured_at"),
                normalized=raw.get("normalized", {}),
            )
        )
    return evidence


def engine_request_from_payload(payload: Dict[str, Any]) -> EngineRequest:
    if not isinstance(payload, dict):
        raise ValueError("5DR runner blocked: request payload must be an object")
    evidence_raw = payload.get("evidence")
    if not isinstance(evidence_raw, list):
        raise ValueError("5DR runner blocked: evidence must be an array")
    return EngineRequest(
        request_id=str(payload.get("request_id", "")),
        provenance_mode=str(payload.get("provenance_mode", "")),
        evidence=_parse_evidence(evidence_raw),
        framework_version=str(payload.get("framework_version", MODEL_VERSION)),
        output_contract_version=str(payload.get("output_contract_version", OUTPUT_CONTRACT_VERSION)),
    )


def _latest_freshness(request: EngineRequest) -> str | None:
    values = [item.captured_at for item in request.evidence if item.captured_at]
    return max(values) if values else None


def _merged_normalized(request: EngineRequest) -> Dict[str, Any]:
    merged: Dict[str, Any] = {}
    for item in request.evidence:
        for key, value in item.normalized.items():
            if key in merged and merged[key] != value:
                raise ValueError(f"5DR runner blocked: conflicting normalized evidence for {key}")
            merged[key] = value
    return merged


def _scenario_key(direction: str) -> str:
    direction = str(direction or "").upper()
    if direction == "BULLISH":
        return "BULL"
    if direction == "BEARISH":
        return "BEAR"
    if direction == "RANGE":
        return "RANGE"
    raise ValueError("5DR runner blocked: invalid horizon direction")


def _validate_probability_vectors(result: Dict[str, Any]) -> None:
    overall = result.get("probabilities")
    if not isinstance(overall, dict):
        raise ValueError("5DR runner blocked: overall probabilities are mandatory")
    try:
        values = [float(overall[key]) for key in ("BULL", "RANGE", "BEAR")]
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("5DR runner blocked: overall BULL/RANGE/BEAR probabilities are mandatory") from exc
    if any(value < 0 or value > 100 for value in values) or abs(sum(values) - 100.0) > 0.02:
        raise ValueError("5DR runner blocked: overall probabilities must total 100")

    slots = result.get("horizon_slots")
    if not isinstance(slots, dict):
        raise ValueError("5DR runner blocked: horizon slots are mandatory")
    for horizon in ("D+1", "D+2", "D+3", "D+4", "D+5"):
        slot = slots.get(horizon)
        if not isinstance(slot, dict):
            raise ValueError(f"5DR runner blocked: {horizon} slot is mandatory")
        scenario = slot.get("probabilities")
        if not isinstance(scenario, dict):
            raise ValueError(f"5DR runner blocked: {horizon} requires BULL/RANGE/BEAR probabilities")
        try:
            probs = {key: float(scenario[key]) for key in ("BULL", "RANGE", "BEAR")}
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError(f"5DR runner blocked: {horizon} probability vector is incomplete") from exc
        if any(value < 0 or value > 100 for value in probs.values()) or abs(sum(probs.values()) - 100.0) > 0.02:
            raise ValueError(f"5DR runner blocked: {horizon} probabilities must total 100")
        selected = _scenario_key(str(slot.get("direction") or ""))
        if abs(probs[selected] - max(probs.values())) > 0.02:
            raise ValueError(f"5DR runner blocked: {horizon} direction must match highest scenario probability")
        try:
            low = float(slot["zone_low"])
            high = float(slot["zone_high"])
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError(f"5DR runner blocked: {horizon} expected zone is mandatory") from exc
        if low <= 0 or high < low:
            raise ValueError(f"5DR runner blocked: {horizon} expected zone is invalid")
        if not str(slot.get("basis") or "").strip():
            raise ValueError(f"5DR runner blocked: {horizon} evidence basis is mandatory")


def _headline_scenario(result: Dict[str, Any]) -> str:
    probs = result.get("probabilities") or {}
    return max(("BULL", "RANGE", "BEAR"), key=lambda key: float(probs.get(key, -1)))


def _change_classification(result: Dict[str, Any], predecessor: Any) -> tuple[str, str]:
    current = _headline_scenario(result)
    if not isinstance(predecessor, dict) or not isinstance(predecessor.get("result"), dict):
        return "NEW_BASELINE", "No predecessor run was supplied."
    previous_result = predecessor["result"]
    try:
        previous = _headline_scenario(previous_result)
    except (TypeError, ValueError):
        return "NEW_BASELINE", "Predecessor did not contain a complete probability vector."
    if previous != current:
        return "REVERSED", f"Leading scenario changed from {previous} to {current}."
    return "UNCHANGED", f"Leading scenario remains {current}."


def _supporting_evidence(data: Dict[str, Any]) -> str:
    scores = data.get("component_scores")
    if not isinstance(scores, dict):
        return "component evidence unavailable"
    ranked = []
    for key, value in scores.items():
        try:
            score = float(value)
        except (TypeError, ValueError):
            continue
        ranked.append((abs(score), str(key), score))
    ranked.sort(reverse=True)
    if not ranked:
        return "component evidence unavailable"
    return ", ".join(f"{key} {score:+.1f}" for _, key, score in ranked[:4])


def _principal_risk(result: Dict[str, Any], data: Dict[str, Any]) -> str:
    event = str(data.get("event_shock") or "UNKNOWN").upper()
    if bool(data.get("event_kill_switch")):
        return f"Event Kill Switch active ({event})."
    des = float(result.get("des5") or 0.0)
    if abs(des) < 30:
        return f"Directional evidence is below the frozen |DES5| >= 30 trade threshold ({des:.1f})."
    if float(result.get("market_trust") or 0.0) < 50:
        return f"Market Trust is below the frozen 50 trade threshold ({float(result.get('market_trust') or 0.0):.1f})."
    return "Thesis weakens if the governed evidence no longer supports the current leading scenario."


def _build_assessments(
    result: Dict[str, Any],
    data: Dict[str, Any],
    predecessor: Any,
) -> tuple[str, str, str]:
    change, change_detail = _change_classification(result, predecessor)
    probs = result["probabilities"]
    lead = _headline_scenario(result)
    forecast_assessment = (
        f"{change} — {result['directional_label']}. "
        f"DES5 {float(result['des5']):.1f}; Market Trust {float(result['market_trust']):.1f}/100 "
        f"({result['market_trust_band']}); leading scenario {lead} {float(probs[lead]):.1f}%. "
        f"Governed component evidence: {_supporting_evidence(data)}. "
        f"{change_detail} Principal risk/invalidation: {_principal_risk(result, data)}"
    )

    data_ok = bool(data.get("data_adequate"))
    kill = bool(data.get("event_kill_switch"))
    expected_rr = float(data.get("expected_rr") or 0.0)
    des = float(result["des5"])
    mt = float(result["market_trust"])
    edge = float(result["execution_edge"])
    permitted = bool(result.get("tradeable"))
    if permitted:
        recommendation = "BUY_CE" if des > 0 else "BUY_PE"
    else:
        recommendation = "NO_TRADE"
    gate = (
        f"data adequate {'YES' if data_ok else 'NO'}; "
        f"Market Trust >=50 {'YES' if mt >= 50 else 'NO'} ({mt:.1f}); "
        f"|DES5| >=30 {'YES' if abs(des) >= 30 else 'NO'} ({abs(des):.1f}); "
        f"Execution Edge >=65 {'YES' if edge >= 65 else 'NO'} ({edge:.1f}); "
        f"Kill Switch inactive {'YES' if not kill else 'NO'}; "
        f"R:R >=2.0 {'YES' if expected_rr >= 2.0 else 'NO'} ({expected_rr:.2f})"
    )
    event = str(data.get("event_shock") or "UNKNOWN").upper()
    recommendation_assessment = (
        f"{'PERMITTED' if permitted else 'REJECTED'} — {recommendation}. "
        f"Single Tradeability Gate: {gate}. Event Shock {event}. "
        f"Trade-specific risk: exact contract, premium, liquidity and invalidation controls must remain verified; "
        f"no missing execution detail may be inferred."
    )
    return forecast_assessment, recommendation_assessment, recommendation


def _assessment_snapshot(payload: Dict[str, Any]) -> Dict[str, Any]:
    context = payload.get("assessment_context")
    if not isinstance(context, dict):
        raise ValueError("5DR V2.1.2 release blocked: assessment-first context is mandatory")
    metrics = context.get("metrics")
    if not isinstance(metrics, dict):
        raise ValueError("5DR V2.1.2 release blocked: assessment metrics are mandatory")
    if context.get("snapshot_complete") is not True:
        raise ValueError("5DR V2.1.2 release blocked: assessment snapshot is incomplete")
    if context.get("recommendation_ledger_complete") is not True:
        raise ValueError("5DR V2.1.2 release blocked: recommendation ledger is incomplete")
    ledger = metrics.get("recommendation_ledger")
    if not isinstance(ledger, list):
        raise ValueError("5DR V2.1.2 release blocked: recommendation ledger is missing")
    expected = int(metrics.get("all_recommendations_count", len(ledger)))
    if len(ledger) != expected:
        raise ValueError("5DR V2.1.2 release blocked: recommendation ledger count mismatch")
    day = metrics.get("day_metrics")
    if not isinstance(day, dict) or not all(label in day for label in ("D", "D+1", "D+2", "D+3", "D+4")):
        raise ValueError("5DR V2.1.2 release blocked: assessment horizon coverage is incomplete")
    return {
        "source_id": context.get("source_id"),
        "assessed_at": context.get("assessed_at"),
        "headline": context.get("headline"),
        "metrics": metrics,
    }


def build_run_envelope(
    payload: Dict[str, Any],
    *,
    run_id: str | None = None,
    generated_at: str | None = None,
    published: bool = False,
) -> Dict[str, Any]:
    request = engine_request_from_payload(payload)
    result = execute(request, domain_execute)
    _validate_probability_vectors(result)
    data = _merged_normalized(request)
    snapshot = _assessment_snapshot(payload) if published else None
    forecast_assessment, recommendation_assessment, recommendation = _build_assessments(
        result, data, payload.get("predecessor")
    )
    result = {
        **result,
        "forecast_assessment": forecast_assessment,
        "recommendation_assessment": recommendation_assessment,
        "recommendation": recommendation,
        "forecast_horizon": "D+5",
        "expected_nifty_zone": {
            "low": float(result["horizon_slots"]["D+5"]["zone_low"]),
            "high": float(result["horizon_slots"]["D+5"]["zone_high"]),
        },
        "event_shock": {
            "level": str(data.get("event_shock") or "UNKNOWN"),
            "transmission": str(data.get("event_transmission") or "UNKNOWN"),
            "convexity_warranted": data.get("convexity_warranted") if isinstance(data.get("convexity_warranted"), bool) else None,
            "kill_switch": bool(data.get("event_kill_switch")),
        },
        "assessment_snapshot_complete": snapshot is not None,
        "recommendation_ledger_complete": (
            snapshot is not None
            and bool(snapshot["metrics"].get("recommendation_ledger_complete"))
        ),
        "assessment_snapshot": snapshot,
        "tradeability_gate": {
            "data_adequate": bool(data.get("data_adequate")),
            "market_trust_pass": float(result["market_trust"]) >= 50,
            "des5_pass": abs(float(result["des5"])) >= 30,
            "execution_edge_pass": float(result["execution_edge"]) >= 65,
            "event_kill_switch_inactive": not bool(data.get("event_kill_switch")),
            "rr_pass": float(data.get("expected_rr") or 0.0) >= 2.0,
            "expected_rr": float(data.get("expected_rr") or 0.0),
            "event_shock": str(data.get("event_shock") or "UNKNOWN"),
        },
        "engine_diagnostics": {
            "regime": data.get("regime"),
            "component_scores": data.get("component_scores"),
            "market_trust_inputs": data.get("market_trust_inputs"),
            "execution_inputs": data.get("execution_inputs"),
        },
    }
    if published:
        validate_output_contract(
            result["model_version"],
            result["forecast_assessment"],
            result["recommendation_assessment"],
            result["output_contract_version"],
            assessment_snapshot_complete=result["assessment_snapshot_complete"],
            horizon_slots=result["horizon_slots"],
            recommendation_ledger_complete=result["recommendation_ledger_complete"],
        )
    generated = generated_at or datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    run = run_id or f"5drrun_{uuid.uuid4()}"
    sources = [
        {
            "evidence_type": item.evidence_type,
            "source_ref": item.source_ref,
            "captured_at": item.captured_at,
        }
        for item in request.evidence
    ]
    return {
        "contract_version": CONSOLE_CONTRACT_VERSION,
        "engine": "5DR",
        "request_id": request.request_id,
        "run_id": run,
        "framework_version": MODEL_VERSION,
        "status": "SUCCESS",
        "generated_at": generated,
        "provenance": {
            "mode": request.provenance_mode,
            "sources": sources,
            "freshness_at": _latest_freshness(request),
        },
        "result": result,
        "warnings": [],
        "learning_eligible": True,
        "published": bool(published),
    }


def _load_payload(path: str | None) -> Dict[str, Any]:
    if path:
        with open(path, "r", encoding="utf-8") as handle:
            return json.load(handle)
    return json.load(sys.stdin)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Execute normalized 5DR request")
    parser.add_argument("--input", help="JSON request file; stdin when omitted")
    parser.add_argument("--publish", action="store_true", help="Mark successful envelope publishable")
    args = parser.parse_args(argv)
    try:
        payload = _load_payload(args.input)
        envelope = build_run_envelope(payload, published=args.publish)
    except (ValueError, TypeError, KeyError, json.JSONDecodeError) as exc:
        print(json.dumps({"ok": False, "error": str(exc)}), file=sys.stderr)
        return 2
    print(json.dumps(envelope, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
