import hashlib
import json

import pytest

from experiments.autonomous_5dr_controller import run_autonomous_release_candidate
from experiments.autonomous_release_bridge import build_release_candidate
from experiments.data_contract import DataArchitectureError


ENGINE = {
    "model_version": "5DR_V2_1",
    "output_contract_version": "5DR_V2_1_2",
    "horizon_slots": {
        f"D+{i}": {
            "direction": "RANGE",
            "probabilities": {"BULL": 25.0, "RANGE": 50.0, "BEAR": 25.0},
            "zone_low": 23000 + i * 10,
            "zone_high": 23500 + i * 10,
            "basis": f"governed test horizon {i}",
        }
        for i in range(1, 6)
    },
    "des5": 31.0,
    "directional_label": "BULL",
    "market_trust": 70.0,
    "market_trust_band": "GOOD",
    "probabilities": {"BULL": 55.0, "RANGE": 30.0, "BEAR": 15.0},
    "execution_edge": 72.0,
    "tradeable": True,
    "tradeability_blockers": [],
}


def _esha():
    return hashlib.sha256(
        json.dumps(ENGINE, sort_keys=True, separators=(",", ":"), default=str).encode()
    ).hexdigest()


def _release_provider(context):
    return {
        "bundle_sha256": context["bundle_sha256"],
        "engine_result_sha256": context["engine_result_sha256"],
        "forecast_assessment": "Assessment present and bound to current evidence.",
        "recommendation_assessment": "Recommendation assessment present.",
        "assessment_snapshot_complete": True,
        "horizon_slots": {
            f"D+{i}": {
                "direction": "RANGE",
                "probabilities": {"BULL": 25.0, "RANGE": 50.0, "BEAR": 25.0},
                "zone_low": 23000 + i * 10,
                "zone_high": 23500 + i * 10,
                "basis": f"governed release horizon {i}",
            }
            for i in range(1, 6)
        },
        "recommendation_ledger_complete": True,
        "recommendation": {"action": "NO_TRADE"},
    }


def test_release_candidate_uses_existing_v212_contract():
    out = build_release_candidate(bundle_sha256="a" * 64, engine_result=ENGINE, provider=_release_provider)
    assert out["status"] == "RELEASE_CANDIDATE_VALIDATED"
    assert out["engine_result_sha256"] == _esha()
    assert out["published"] is False
    assert out["production_5dr_write_enabled"] is False


def test_release_candidate_rejects_engine_binding_mismatch():
    def bad(context):
        payload = dict(_release_provider(context))
        payload["engine_result_sha256"] = "0" * 64
        return payload

    with pytest.raises(DataArchitectureError, match="engine binding mismatch"):
        build_release_candidate(bundle_sha256="a" * 64, engine_result=ENGINE, provider=bad)


def test_release_candidate_fails_closed_when_output_contract_incomplete():
    def incomplete(context):
        payload = dict(_release_provider(context))
        payload["recommendation_ledger_complete"] = False
        return payload

    with pytest.raises(ValueError, match="recommendation ledger is incomplete"):
        build_release_candidate(bundle_sha256="a" * 64, engine_result=ENGINE, provider=incomplete)
