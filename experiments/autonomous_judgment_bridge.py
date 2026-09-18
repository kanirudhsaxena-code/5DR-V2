"""Governed judgment-provider bridge for autonomous 5DR V2.2.3.

This module creates no scoring rules and defines no evidence-to-score thresholds.
It only provides a stable, fail-closed interface through which an approved
intelligence-layer provider can return normalized inputs for the existing frozen
5DR engine. The provider must bind its judgment to the exact evidence bundle SHA.
"""
from __future__ import annotations

from copy import deepcopy
from typing import Callable, Mapping, Any

from experiments.data_contract import DataArchitectureError
from experiments.engine_handoff import (
    JUDGMENT_SCHEMA,
    JUDGMENT_SOURCE,
    REQUIRED_ENGINE_INPUTS,
    build_engine_request,
)

JudgmentProvider = Callable[[dict], Mapping[str, Any]]


def build_governed_judgment(bundle: dict, provider: JudgmentProvider) -> dict:
    """Build and validate one bundle-bound governed judgment.

    The provider supplies interpretation only. This bridge owns the canonical
    judgment envelope and forbids methodology mutation or release side effects.
    """
    if not callable(provider):
        raise DataArchitectureError("judgment provider is not callable")
    expected_sha = bundle.get("bundle_sha256")
    if not isinstance(expected_sha, str) or len(expected_sha) != 64:
        raise DataArchitectureError("evidence bundle SHA missing before judgment")

    supplied = provider(deepcopy(bundle))
    if not isinstance(supplied, Mapping):
        raise DataArchitectureError("judgment provider returned invalid payload")
    if supplied.get("bundle_sha256") != expected_sha:
        raise DataArchitectureError("judgment provider bundle binding mismatch")

    normalized = supplied.get("normalized_engine_inputs")
    if not isinstance(normalized, Mapping):
        raise DataArchitectureError("judgment provider normalized inputs missing")
    missing = sorted(REQUIRED_ENGINE_INPUTS - set(normalized))
    if missing:
        raise DataArchitectureError(f"judgment provider missing engine inputs: {missing}")

    audit = supplied.get("judgment_audit", {})
    if not isinstance(audit, Mapping):
        raise DataArchitectureError("judgment provider audit must be an object")

    judgment = {
        "schema": JUDGMENT_SCHEMA,
        "source": JUDGMENT_SOURCE,
        "bundle_sha256": expected_sha,
        "methodology_changed": False,
        "release_complete": False,
        "shadow_only": True,
        "normalized_engine_inputs": deepcopy(dict(normalized)),
        "judgment_audit": {
            **deepcopy(dict(audit)),
            "provider_contract": "5DR_V2_2_3_AUTONOMOUS_JUDGMENT_PROVIDER_V1",
            "production_methodology_source": "5DR_V2_1_FROZEN",
            "release_side_effects_enabled": False,
        },
    }

    # Reuse the existing handoff validator as the canonical acceptance boundary.
    build_engine_request(bundle, judgment)
    return judgment
