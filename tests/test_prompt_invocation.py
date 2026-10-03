from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from experiments.data_contract import DataArchitectureError
from experiments.prompt_invocation import PromptInvocation, normalize_command, plan_prompt_invocation

IST = ZoneInfo("Asia/Kolkata")


def invoke(at, request_id="req"):
    return plan_prompt_invocation(PromptInvocation(
        command="5DR",
        requested_at=at,
        request_id=request_id,
    ))


def test_prompt_aliases_are_strict_and_normalized():
    assert normalize_command("5dr") == "5DR"
    assert normalize_command(" 5dr   nifty ") == "5DR NIFTY"
    with pytest.raises(DataArchitectureError):
        normalize_command("edge nifty")


def test_user_invocation_is_ready_during_live_session():
    result = invoke(datetime(2026, 9, 18, 10, 30, tzinfo=IST), "req-live")
    assert result["status"] == "READY_TO_ACQUIRE"
    assert result["evidence_state"]["evidence_mode"] == "LIVE_INTRADAY"
    assert result["evidence_state"]["run_class"] == "USER_CANONICAL_SNAPSHOT"
    assert result["trigger_type"] == "USER"
    assert result["benchmark_role"] == "NONE"
    assert result["acquire_structured_evidence"] is True


def test_user_invocation_is_ready_after_close():
    result = invoke(datetime(2026, 9, 18, 18, 42, tzinfo=IST), "req-final")
    assert result["status"] == "READY_TO_ACQUIRE"
    assert result["evidence_mode"] == "SESSION_FINAL"
    assert result["acquire_structured_evidence"] is True


def test_user_invocation_is_ready_on_weekend_using_closed_session_mode():
    result = invoke(datetime(2026, 9, 19, 10, 30, tzinfo=IST), "req-weekend")
    assert result["status"] == "READY_TO_ACQUIRE"
    assert result["evidence_mode"] == "CLOSED_SESSION"
    assert result["evidence_state"]["live_freshness_may_be_inferred"] is False


def test_user_invocation_routes_genuine_preopen_clock_without_claiming_benchmark_role():
    result = invoke(datetime(2026, 9, 18, 9, 12, tzinfo=IST), "req-preopen")
    assert result["status"] == "READY_TO_ACQUIRE"
    assert result["evidence_mode"] == "PREOPEN"
    assert result["benchmark_role"] == "NONE"


def test_user_invocation_before_preopen_uses_closed_session_evidence():
    result = invoke(datetime(2026, 9, 18, 8, 0, tzinfo=IST), "req-overnight")
    assert result["status"] == "READY_TO_ACQUIRE"
    assert result["evidence_mode"] == "CLOSED_SESSION"


def test_naive_invocation_time_fails_closed():
    with pytest.raises(DataArchitectureError):
        invoke(datetime(2026, 9, 18, 10, 30), "req-naive")


def test_invocation_adapter_never_enables_side_effects():
    result = invoke(datetime(2026, 9, 19, 10, 30, tzinfo=IST), "req-safe")
    assert result["forecast_release_enabled"] is False
    assert result["production_5dr_write_enabled"] is False
    assert result["lifecycle_write_enabled"] is False
    assert result["learning_lab_write_enabled"] is False
    assert result["trading_execution_enabled"] is False
    assert result["methodology_changed"] is False
