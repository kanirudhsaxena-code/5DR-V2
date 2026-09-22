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
        "event_shock": "LOW",
        "event_transmission": "TWO_SIDED",
        "convexity_warranted": False,
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
        "horizon_slots": {
            "D+1": {"direction":"BULLISH","probabilities":{"BULL":55,"RANGE":35,"BEAR":10},"zone_low":23000,"zone_high":23300,"basis":"Price structure"},
            "D+2": {"direction":"BULLISH","probabilities":{"BULL":52,"RANGE":36,"BEAR":12},"zone_low":23050,"zone_high":23400,"basis":"Price and PVPO"},
            "D+3": {"direction":"RANGE","probabilities":{"BULL":28,"RANGE":50,"BEAR":22},"zone_low":23000,"zone_high":23450,"basis":"Mixed confirmation"},
            "D+4": {"direction":"RANGE","probabilities":{"BULL":27,"RANGE":49,"BEAR":24},"zone_low":22950,"zone_high":23500,"basis":"Mixed confirmation"},
            "D+5": {"direction":"RANGE","probabilities":{"BULL":26,"RANGE":48,"BEAR":26},"zone_low":22900,"zone_high":23550,"basis":"Wider uncertainty"},
        },
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
        "assessment_context": {
            "source_id": "5DR-ASSESSMENT-TEST",
            "assessed_at": "2026-09-12T09:30:00Z",
            "headline": "Assessment complete",
            "snapshot_complete": True,
            "recommendation_ledger_complete": True,
            "metrics": {
                "day_metrics": {label: {"status":"NOT DUE"} for label in ("D","D+1","D+2","D+3","D+4")},
                "recommendation_ledger": [],
                "all_recommendations_count": 0,
                "recommendation_ledger_complete": True,
                "assessment_snapshot_complete": True,
            },
        },
        "predecessor": None,
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
    assert envelope["result"]["assessment_snapshot_complete"] is True
    assert envelope["result"]["recommendation_ledger_complete"] is True
    assert "DES5" in envelope["result"]["forecast_assessment"]
    assert "Single Tradeability Gate" in envelope["result"]["recommendation_assessment"]
    assert envelope["result"]["horizon_slots"]["D+1"]["probabilities"]["BULL"] == 55
    assert envelope["result"]["expected_nifty_zone"] == {"low": 22900.0, "high": 23550.0}
    assert envelope["result"]["event_shock"]["level"] == "LOW"


def test_runner_cli_fails_closed_on_missing_evidence(tmp_path, capsys):
    bad = _payload()
    bad["evidence"] = []
    path = tmp_path / "request.json"
    path.write_text(json.dumps(bad), encoding="utf-8")
    code = main(["--input", str(path)])
    captured = capsys.readouterr()
    assert code == 2
    assert "evidence is mandatory" in captured.err


def test_published_runner_blocks_missing_assessment_context():
    payload = _payload()
    payload.pop("assessment_context")
    try:
        build_run_envelope(payload, published=True)
    except ValueError as exc:
        assert "assessment-first context is mandatory" in str(exc)
    else:
        raise AssertionError("published run should fail closed without assessment context")


def test_runner_rejects_invalid_daily_probability_vector():
    payload = _payload()
    payload["evidence"][0]["normalized"]["horizon_slots"]["D+1"]["probabilities"] = {"BULL": 60, "RANGE": 35, "BEAR": 15}
    try:
        build_run_envelope(payload, published=True)
    except ValueError as exc:
        assert "probabilities must total 100" in str(exc)
    else:
        raise AssertionError("invalid horizon probability vector should fail closed")
