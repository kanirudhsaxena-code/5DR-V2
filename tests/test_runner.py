import json

from src.runner import build_run_envelope, main


def _payload():
    normalized = {
        "regime": "TREND",
        "component_scores": {
            "PRICE_STRUCTURE": 50,
            "PVPO": 40,
            "PARTICIPATION": 30,
            "MACRO_CATALYSTS": 20,
        },
        "market_trust_inputs": {
            "price_confirmation": 80,
            "pvpo_confirmation": 75,
            "participation_confirmation": 70,
            "cross_engine_consistency": 65,
            "closing_confirmation": 80,
            "evidence_freshness_completeness": 90,
        },
        "event_shock": "NORMAL",
        "execution_inputs": {
            "rr_score": 80,
            "premium_iv_theta_score": 70,
            "strike_expiry_fit_score": 80,
            "liquidity_spread_score": 80,
            "entry_invalidation_score": 75,
        },
        "data_adequate": True,
        "event_kill_switch": False,
        "expected_rr": 2.5,
        "forecast_assessment": "Forecast assessment present",
        "recommendation_assessment": "Recommendation assessment present",
        "horizon_slots": {f"D+{i}": {} for i in range(1, 6)},
        "recommendation_ledger_complete": True,
        "assessment_snapshot_complete": True,
    }
    return {
        "request_id": "5drreq_test",
        "provenance_mode": "HYBRID",
        "framework_version": "5DR_V2_1",
        "output_contract_version": "5DR_V2_1_2",
        "evidence": [
            {
                "evidence_type": "NORMALIZED",
                "source_ref": "console:test",
                "captured_at": "2026-09-12T09:00:00Z",
                "normalized": normalized,
            }
        ],
    }


def test_runner_emits_console_release_envelope():
    envelope = build_run_envelope(
        _payload(),
        run_id="5drrun_test",
        generated_at="2026-09-12T10:00:00Z",
        published=True,
    )
    assert envelope["contract_version"] == "1.0"
    assert envelope["engine"] == "5DR"
    assert envelope["request_id"] == "5drreq_test"
    assert envelope["run_id"] == "5drrun_test"
    assert envelope["framework_version"] == "5DR_V2_1"
    assert envelope["status"] == "SUCCESS"
    assert envelope["published"] is True
    assert envelope["provenance"]["mode"] == "HYBRID"
    assert envelope["provenance"]["freshness_at"] == "2026-09-12T09:00:00Z"
    assert envelope["result"]["output_contract_version"] == "5DR_V2_1_2"


def test_runner_cli_fails_closed_on_missing_evidence(tmp_path, capsys):
    bad = _payload()
    bad["evidence"] = []
    path = tmp_path / "request.json"
    path.write_text(json.dumps(bad), encoding="utf-8")
    code = main(["--input", str(path)])
    captured = capsys.readouterr()
    assert code == 2
    assert "evidence is mandatory" in captured.err
