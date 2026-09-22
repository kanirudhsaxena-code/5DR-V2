from datetime import datetime, timezone
from pathlib import Path

from src.console_forecast_sync_cli import _validate_handoff
from src.console_forecast_sync import (
    IST,
    REGIME_WEIGHTS,
    classify_run,
    complete_horizon_slots,
)


def complete_result():
    return {
        "horizon_slots": {
            f"D+{day}": {
                "direction": "RANGE",
                "probabilities": {"BULL": 25, "RANGE": 50, "BEAR": 25},
                "zone_low": 23000 + day * 10,
                "zone_high": 23500 + day * 10,
                "basis": f"day {day}",
            }
            for day in range(1, 6)
        }
    }


def test_previous_day_post_close_run_cannot_become_new_regime_canonical():
    run_at = datetime(2026, 9, 21, 16, 23, tzinfo=IST)
    classification = classify_run(run_at)
    assert classification["target_trading_date"].isoformat() == "2026-09-22"
    assert classification["run_class"] == "INTRADAY_SNAPSHOT"
    assert classification["canonical_type"] == "DIAGNOSTIC_SNAPSHOT"
    assert [d.isoformat() for d in classification["daily_dates"]] == [
        "2026-09-22", "2026-09-23", "2026-09-24", "2026-09-25", "2026-09-28"
    ]


def test_preopen_run_uses_current_session_as_d1():
    run_at = datetime(2026, 9, 22, 8, 53, tzinfo=IST)
    request_metadata={"invocation":{"requested_at":"2026-09-22T08:50:00+05:30"}}
    classification = classify_run(run_at,request_metadata)
    assert classification["target_trading_date"].isoformat() == "2026-09-22"
    assert classification["run_class"] == "CANONICAL_CANDIDATE"
    assert classification["canonical_type"] == "PREOPEN_CANONICAL"
    assert classification["daily_dates"][0].isoformat() == "2026-09-22"


def test_0855_request_can_finish_before_0900_and_remain_preopen_eligible():
    run_at = datetime(2026, 9, 22, 8, 59, tzinfo=IST)
    request_metadata={"invocation":{"requested_at":"2026-09-22T08:55:00+05:30"}}
    classification = classify_run(run_at,request_metadata)
    assert classification["canonical_type"] == "PREOPEN_CANONICAL"
    assert classification["run_class"] == "CANONICAL_CANDIDATE"


def test_completed_after_0900_cannot_be_preopen_canonical():
    run_at = datetime(2026, 9, 22, 9, 0, 1, tzinfo=IST)
    request_metadata={"invocation":{"requested_at":"2026-09-22T08:55:00+05:30"}}
    classification = classify_run(run_at,request_metadata)
    assert classification["canonical_type"] == "DIAGNOSTIC_SNAPSHOT"
    assert classification["run_class"] == "INTRADAY_SNAPSHOT"


def test_post_us_close_overnight_run_is_fallback_candidate():
    run_at = datetime(2026, 9, 22, 2, 45, tzinfo=IST)
    classification = classify_run(run_at)
    assert classification["canonical_type"] == "OVERNIGHT_FALLBACK_CANONICAL"
    assert classification["run_class"] == "CANONICAL_CANDIDATE"


def test_legacy_target_preserves_historical_candidate_rule():
    run_at = datetime(2026, 9, 16, 16, 41, tzinfo=IST)
    classification = classify_run(run_at)
    assert classification["target_trading_date"].isoformat() == "2026-09-17"
    assert classification["canonical_type"] == "LEGACY_CANONICAL"
    assert classification["run_class"] == "CANONICAL_CANDIDATE"


def test_intraday_run_cannot_replace_closed_canonical_candidate():
    run_at = datetime(2026, 9, 22, 10, 30, tzinfo=IST)
    classification = classify_run(run_at)
    assert classification["target_trading_date"].isoformat() == "2026-09-22"
    assert classification["run_class"] == "INTRADAY_SNAPSHOT"
    assert classification["canonical_type"] == "DIAGNOSTIC_SNAPSHOT"
    assert classification["daily_dates"][0].isoformat() == "2026-09-22"


def test_complete_horizon_contract_requires_all_five_frozen_slots():
    clean = complete_horizon_slots(complete_result())
    assert clean is not None
    assert list(clean) == ["D+1", "D+2", "D+3", "D+4", "D+5"]

    broken = complete_result()
    broken["horizon_slots"]["D+3"] = {}
    assert complete_horizon_slots(broken) is None


def test_regime_weights_match_canonical_0_to_100_schema():
    assert REGIME_WEIGHTS["TRANSITION"] == {
        "PRICE_STRUCTURE": 35.0,
        "PVPO": 25.0,
        "PARTICIPATION": 15.0,
        "MACRO_CATALYSTS": 25.0,
    }
    assert sum(REGIME_WEIGHTS["TRANSITION"].values()) == 100.0


def test_lifecycle_runs_console_sync_before_checkpoint_reconciliation():
    workflow = Path(".github/workflows/lifecycle-production-wrapper.yml").read_text(encoding="utf-8")
    sync = workflow.index("python -m src.console_forecast_sync_cli")
    reconcile = workflow.index("python -m src.checkpoint_reconcile_cli")
    assert sync < reconcile
    assert "cron: '15 3-11 * * 1-5'" in workflow
    assert "console-canonical-sync.json" in workflow


def test_bridge_uses_canonical_execution_and_evidence_schema_values():
    source = Path("src/console_forecast_sync.py").read_text(encoding="utf-8")
    assert "'HIGH'" in source
    assert '"CE" if recommendation=="BUY_CE"' in source
    assert '"PE" if recommendation=="BUY_PE"' in source
    assert '"CONVEXITY"' in source
    assert "NIFTY_OPTION" not in source


def test_sync_cli_fails_closed_on_missing_canonical_integrity():
    source = Path("src/console_forecast_sync_cli.py").read_text(encoding="utf-8")
    assert "CANONICAL_SYNC_INTEGRITY_FAILED" in source
    assert "unaccounted_complete" in source
    assert "broken_imports" in source
    assert "unfinalized_closed_windows" in source
    assert "COUNT(*) FROM daily_forecasts" in source


def test_canonical_selection_requires_complete_five_day_path():
    source = Path("src/console_forecast_sync.py").read_text(encoding="utf-8")
    assert "COUNT(*)=5" in source
    assert "COUNT(DISTINCT df.day_number)=5" in source
    assert "MIN(df.day_number)=1" in source
    assert "MAX(df.day_number)=5" in source


def test_console_state_handoff_contract_is_sanitized_and_parseable():
    now=datetime.now(timezone.utc).isoformat().replace("+00:00","Z")
    payload={
        "schema_version":"5DR_CONSOLE_HANDOFF_V1",
        "generated_at":now,
        "source":"EDGE_CONSOLE_PUBLISHED_RUNS",
        "runs":[{
            "run":{"run_id":"5drrun_demo","published":True,"result":complete_result()},
            "request":{"request_id":"5drreq_demo","metadata":{
                "intelligence_handoff":{"normalized":{}},
                "automated_market_evidence":{},
            }},
        }],
    }
    runs,requests=_validate_handoff(payload)
    assert runs[0]["run_id"]=="5drrun_demo"
    assert requests["5drrun_demo"]["request_id"]=="5drreq_demo"


def test_console_state_handoff_rejects_duplicate_run_ids():
    now=datetime.now(timezone.utc).isoformat().replace("+00:00","Z")
    entry={"run":{"run_id":"dup","result":complete_result()},"request":{}}
    payload={"schema_version":"5DR_CONSOLE_HANDOFF_V1","generated_at":now,"runs":[entry,entry]}
    try:
        _validate_handoff(payload)
        assert False, "duplicate run ids must fail closed"
    except SystemExit as exc:
        assert "DUPLICATE_RUN_ID" in str(exc)


def test_post_amendment_horizon_contract_rejects_legacy_single_probability():
    legacy = complete_result()
    legacy["horizon_slots"]["D+5"] = {
        "direction": "BULLISH",
        "probability": 35,
        "zone_low": 23250,
        "zone_high": 23600,
        "basis": "legacy confidence",
    }
    assert complete_horizon_slots(legacy) is None
    assert complete_horizon_slots(legacy, allow_legacy=True) is not None


def test_canonical_selection_requires_post_amendment_scenario_vectors():
    source = Path("src/console_forecast_sync.py").read_text(encoding="utf-8")
    assert "df.bull_probability IS NULL" in source
    assert "df.range_probability IS NULL" in source
    assert "df.bear_probability IS NULL" in source
    assert "target_trading_date >= DATE '2026-09-22'" in source
