import json
from pathlib import Path

import pytest

from src.autonomous_evidence_gate import AutonomousEvidenceGateBlocked, release_normalized_evidence


def ready():
    return {
        "status": "AUTONOMOUS_EVIDENCE_READY",
        "trading_enabled": False,
        "forecast_release_enabled": False,
    }


def test_blocked_acquisition_cannot_cross(tmp_path: Path):
    path = tmp_path / "evidence.json"
    path.write_text("[]")
    envelope = ready()
    envelope["status"] = "AUTONOMOUS_EVIDENCE_BLOCKED"
    with pytest.raises(AutonomousEvidenceGateBlocked, match="ACQUISITION_NOT_READY"):
        release_normalized_evidence(envelope, path)


def test_ready_acquisition_still_requires_canonical_packet(tmp_path: Path):
    path = tmp_path / "evidence.json"
    path.write_text("[]")
    with pytest.raises(AutonomousEvidenceGateBlocked, match="NORMALIZED_EVIDENCE_REQUIRED"):
        release_normalized_evidence(ready(), path)


def test_acquisition_cannot_self_authorize_forecast(tmp_path: Path):
    path = tmp_path / "evidence.json"
    path.write_text("[]")
    envelope = ready()
    envelope["forecast_release_enabled"] = True
    with pytest.raises(AutonomousEvidenceGateBlocked, match="ACQUISITION_CANNOT_SELF_AUTHORIZE_FORECAST"):
        release_normalized_evidence(envelope, path)
