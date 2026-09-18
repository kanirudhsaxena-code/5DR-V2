from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from experiments.data_contract import DataArchitectureError
from experiments.prompt_invocation import PromptInvocation, normalize_command, plan_prompt_invocation

IST = ZoneInfo("Asia/Kolkata")


def test_prompt_aliases_are_strict_and_normalized():
    assert normalize_command("5dr") == "5DR"
    assert normalize_command(" 5dr   nifty ") == "5DR NIFTY"
    with pytest.raises(DataArchitectureError):
        normalize_command("edge nifty")


def test_prompt_ready_only_inside_existing_validated_window():
    result = plan_prompt_invocation(PromptInvocation(
        command="5DR",
        requested_at=datetime(2026, 9, 18, 10, 30, tzinfo=IST),
        request_id="req-1",
    ))
    assert result["status"] == "READY_TO_ACQUIRE"
    assert result["approved_window"]["label"] == "LATE_MORNING_SNAPSHOT"
    assert result["acquire_structured_evidence"] is True


def test_prompt_fails_closed_after_market_validated_windows():
    result = plan_prompt_invocation(PromptInvocation(
        command="5DR",
        requested_at=datetime(2026, 9, 18, 18, 42, tzinfo=IST),
        request_id="req-2",
    ))
    assert result["status"] == "BLOCKED_OUTSIDE_VALIDATED_WINDOW"
    assert result["acquire_structured_evidence"] is False
    assert result["forecast_release_enabled"] is False
    assert result["production_5dr_write_enabled"] is False
    assert result["trading_execution_enabled"] is False
