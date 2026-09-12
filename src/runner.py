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


def build_run_envelope(
    payload: Dict[str, Any],
    *,
    run_id: str | None = None,
    generated_at: str | None = None,
    published: bool = False,
) -> Dict[str, Any]:
    request = engine_request_from_payload(payload)
    result = execute(request, domain_execute)
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
