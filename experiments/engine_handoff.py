"""V2.2.3 handoff from a frozen evidence bundle to the existing 5DR engine.

This module deliberately does NOT derive new scoring thresholds. The frozen evidence
bundle provides auditable facts; the 5DR intelligence/judgment layer supplies the
normalized fields already required by the existing source-neutral engine contract.
The judgment must be cryptographically bound to the exact bundle it interpreted.
"""
from copy import deepcopy

from experiments.data_contract import DataArchitectureError
from src.engine_contract import EngineRequest, EvidenceItem

BUNDLE_SCHEMA = "5dr-frozen-evidence-bundle-v1"
JUDGMENT_SCHEMA = "5dr-v2-2-3-governed-judgment-v1"
JUDGMENT_SOURCE = "5DR_INTELLIGENCE_LAYER_V2_2_3"
REQUIRED_ENGINE_INPUTS = frozenset({
    "regime",
    "component_scores",
    "market_trust_inputs",
    "event_shock",
    "execution_inputs",
    "data_adequate",
    "event_kill_switch",
    "expected_rr",
    "horizon_slots",
})


def _validate_bundle(bundle):
    if not isinstance(bundle, dict) or bundle.get("schema") != BUNDLE_SCHEMA:
        raise DataArchitectureError("engine handoff bundle schema invalid")
    if bundle.get("status") != "READY":
        raise DataArchitectureError("engine handoff bundle is not ready")
    digest = bundle.get("bundle_sha256")
    if not isinstance(digest, str) or len(digest) != 64 or any(c not in "0123456789abcdef" for c in digest.lower()):
        raise DataArchitectureError("engine handoff bundle digest invalid")
    policy = bundle.get("screenshot_policy")
    if not isinstance(policy, dict) or policy.get("screenshot_dependency") is not False:
        raise DataArchitectureError("engine handoff requires screenshot-free evidence")
    for key in ("directional_score_assigned", "forecast_released", "trading_enabled", "production_5dr_write_enabled"):
        if bundle.get(key) is not False:
            raise DataArchitectureError("engine handoff bundle crossed isolation boundary")
    return digest.lower()


def _validate_judgment(judgment, expected_bundle_sha256):
    if not isinstance(judgment, dict) or judgment.get("schema") != JUDGMENT_SCHEMA:
        raise DataArchitectureError("governed judgment schema invalid")
    if judgment.get("source") != JUDGMENT_SOURCE:
        raise DataArchitectureError("governed judgment source invalid")
    if judgment.get("bundle_sha256") != expected_bundle_sha256:
        raise DataArchitectureError("governed judgment evidence binding mismatch")
    if judgment.get("methodology_changed") is not False:
        raise DataArchitectureError("governed judgment may not change methodology")
    normalized = judgment.get("normalized_engine_inputs")
    if not isinstance(normalized, dict):
        raise DataArchitectureError("governed judgment normalized inputs missing")
    missing = sorted(REQUIRED_ENGINE_INPUTS - set(normalized))
    if missing:
        raise DataArchitectureError(f"governed judgment missing engine inputs: {missing}")
    return normalized


def build_engine_request(bundle, judgment, *, request_id=None):
    """Build the existing EngineRequest without altering existing scoring semantics."""
    bundle_sha = _validate_bundle(bundle)
    normalized = _validate_judgment(judgment, bundle_sha)
    request_id = request_id or bundle.get("run_id")
    if not isinstance(request_id, str) or not request_id.strip():
        raise DataArchitectureError("engine handoff request id invalid")

    evidence = [
        EvidenceItem(
            evidence_type="V2_2_3_FROZEN_EVIDENCE_BUNDLE",
            source_ref=f"bundle:sha256={bundle_sha}",
            captured_at=bundle.get("frozen_at"),
            normalized={},
        ),
        EvidenceItem(
            evidence_type="V2_2_3_GOVERNED_JUDGMENT",
            source_ref=f"judgment:{JUDGMENT_SOURCE}:bundle={bundle_sha}",
            captured_at=bundle.get("frozen_at"),
            normalized=deepcopy(normalized),
        ),
    ]
    return EngineRequest(
        request_id=request_id.strip(),
        provenance_mode="AUTOMATED",
        evidence=evidence,
    )
