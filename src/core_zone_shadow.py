"""G6-B NIFTY Core Zone SHADOW canonical read-model builder.

This module intentionally does not calibrate Core bounds. It accepts only already-
calibrated SHADOW rows backed by issuance-time evidence, freezes their lineage, and
produces the deterministic object that Console/ChatGPT and prospective evidence
collection may share. Production 5DR methodology is never called or mutated here.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

from .core_zone_contract import CORE_ZONE_CONTRACT_VERSION, validate_core_zone_report

VIEW_MODEL_VERSION = "G6-B-NIFTY-CORE-SHADOW-1"


class CoreZoneShadowError(ValueError):
    """Raised when calibrated SHADOW evidence is incomplete or unsafe."""


def _canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def build_nifty_core_shadow(*, run_id: str, issuance_id: str, calibration_version: str,
                            evidence_refs: list[str], horizons: list[dict]) -> dict:
    """Freeze one NIFTY Core SHADOW object without inventing calibration values."""
    if not run_id or not issuance_id or not calibration_version:
        raise CoreZoneShadowError("run, issuance and calibration lineage are mandatory")
    if not evidence_refs or any(not isinstance(ref, str) or not ref.strip() for ref in evidence_refs):
        raise CoreZoneShadowError("issuance-time evidence references are mandatory")

    frozen_rows = []
    required = ("horizon", "target_session", "expected_centre", "core_low", "core_high",
                "outer_low", "outer_high", "verification_state")
    for row in horizons:
        missing = [key for key in required if key not in row or row[key] is None]
        if missing:
            raise CoreZoneShadowError(f"Core SHADOW row missing required fields: {missing}")
        if row["verification_state"] != "VERIFIED":
            raise CoreZoneShadowError("unverified Core SHADOW rows fail closed")
        centre = float(row["expected_centre"])
        core_low, core_high = float(row["core_low"]), float(row["core_high"])
        outer_low, outer_high = float(row["outer_low"]), float(row["outer_high"])
        if not (0 < outer_low <= core_low <= centre <= core_high <= outer_high):
            raise CoreZoneShadowError("Core/Outer geometry is invalid")
        frozen_rows.append({key: row[key] for key in required})

    payload = {
        "mode": "SHADOW",
        "engine": "EDGE_NIFTY",
        "run_id": run_id,
        "issuance_id": issuance_id,
        "contract_version": CORE_ZONE_CONTRACT_VERSION,
        "view_model_version": VIEW_MODEL_VERSION,
        "calibration_version": calibration_version,
        "evidence_refs": list(evidence_refs),
        "horizons": frozen_rows,
    }
    payload["report_hash"] = hashlib.sha256(_canonical_json(payload).encode("utf-8")).hexdigest()
    validate_core_zone_report(payload)
    return payload
