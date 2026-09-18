"""Governed production-persistence activation boundary for 5DR V2.2.3.

The bridge does not own forecast semantics or SQL. A canonical persistence provider
must persist the already-validated release candidate and bind its receipt to the
exact candidate SHA. Trading and methodology mutation are explicitly prohibited.
"""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from typing import Any, Callable, Mapping

from experiments.data_contract import DataArchitectureError

PersistenceProvider = Callable[[dict], Mapping[str, Any]]


def _sha256(value: dict) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()
    ).hexdigest()


def persist_release_candidate(candidate: dict, provider: PersistenceProvider) -> dict:
    if not isinstance(candidate, dict):
        raise DataArchitectureError("persistence candidate invalid")
    if candidate.get("schema") != "5dr-v2-2-3-release-candidate-v1":
        raise DataArchitectureError("persistence candidate schema invalid")
    if candidate.get("status") != "RELEASE_CANDIDATE_VALIDATED":
        raise DataArchitectureError("persistence requires validated release candidate")
    for flag in ("published","production_5dr_write_enabled","lifecycle_write_enabled",
                 "learning_lab_write_enabled","trading_execution_enabled","methodology_changed"):
        if candidate.get(flag) is not False:
            raise DataArchitectureError(f"persistence safety boundary crossed: {flag}")
    if not callable(provider):
        raise DataArchitectureError("persistence provider is not callable")

    candidate_sha=_sha256(candidate)
    supplied=provider({
        "release_candidate_sha256": candidate_sha,
        "release_candidate": deepcopy(candidate),
        "required_contract": {
            "append_only": True,
            "idempotent": True,
            "canonical_schema_only": True,
            "trading_execution_enabled": False,
            "methodology_changed": False,
        },
    })
    if not isinstance(supplied, Mapping):
        raise DataArchitectureError("persistence provider returned invalid payload")
    if supplied.get("release_candidate_sha256") != candidate_sha:
        raise DataArchitectureError("persistence receipt binding mismatch")
    if supplied.get("status") not in ("PERSISTED","ALREADY_PERSISTED"):
        raise DataArchitectureError("persistence provider did not confirm canonical persistence")
    if not isinstance(supplied.get("forecast_id"), str) or not supplied["forecast_id"].strip():
        raise DataArchitectureError("persistence receipt forecast_id missing")
    if supplied.get("trading_execution_enabled") is not False:
        raise DataArchitectureError("persistence provider trading boundary crossed")
    if supplied.get("methodology_changed") is not False:
        raise DataArchitectureError("persistence provider methodology boundary crossed")

    return {
        "schema": "5dr-v2-2-3-persistence-receipt-v1",
        "status": supplied["status"],
        "forecast_id": supplied["forecast_id"],
        "release_candidate_sha256": candidate_sha,
        "receipt": deepcopy(dict(supplied)),
        "forecast_released": True,
        "production_5dr_write_enabled": True,
        "lifecycle_write_enabled": False,
        "learning_lab_write_enabled": False,
        "trading_execution_enabled": False,
        "methodology_changed": False,
    }
