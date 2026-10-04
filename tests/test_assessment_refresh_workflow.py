from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]


def test_on_demand_assessment_refresh_reuses_canonical_builder():
    workflow=(ROOT/'.github/workflows/assessment-refresh.yml').read_text(encoding='utf-8')
    wrapper=(ROOT/'.github/workflows/lifecycle-production-wrapper.yml').read_text(encoding='utf-8')
    assert 'workflow_dispatch:' in workflow
    assert 'python -m src.assessment_handoff_cli' in workflow
    assert 'python -m src.assessment_handoff_cli' in wrapper
    assert 'UPSTOX_ANALYTICS_TOKEN' not in workflow
    assert 'LIFECYCLE_WRITES_ENABLED' not in workflow
    assert 'state/assessment-handoff' in workflow


def test_assessment_refresh_stays_fresh_at_authoritative_source():
    workflow=(ROOT/'.github/workflows/assessment-refresh.yml').read_text(encoding='utf-8')
    assert "cron: '7,27,47 * * * *'" in workflow
    assert 'branches:' in workflow
    assert '- main' in workflow
    assert "'src/assessment_handoff_cli.py'" in workflow
    assert "'public.canonical_selections'" in workflow
    assert "'public.forecasts'" in workflow
    assert "'public.outcome_checkpoints'" in workflow
    assert 'FIVEDR_DATABASE_CONTRACT=PASS' in workflow


def test_on_demand_refresh_keeps_freshness_and_completeness_checks():
    workflow=(ROOT/'.github/workflows/assessment-refresh.yml').read_text(encoding='utf-8')
    required=(
        "5DR_ASSESSMENT_HANDOFF_V1",
        "assessment_snapshot_complete",
        "recommendation_ledger_complete",
        "D+4",
        "all_recommendations_count",
        "ASSESSMENT_HANDOFF_REFRESH_READY=PASS",
    )
    for token in required:
        assert token in workflow


def test_canonical_builder_generates_new_snapshot_timestamp():
    source=(ROOT/'src/assessment_handoff_cli.py').read_text(encoding='utf-8')
    assert '"generated_at": datetime.now(timezone.utc)' in source
    assert '"source": "5DR_CANONICAL_LIFECYCLE"' in source
    assert '"recommendation_ledger_complete": True' in source
    assert '"assessment_snapshot_complete": all(' in source


def test_assessment_refresh_has_multiple_attempts_inside_freshness_window():
    workflow=(ROOT/'.github/workflows/assessment-refresh.yml').read_text(encoding='utf-8')
    assert "cron: '7,27,47 * * * *'" in workflow
    assert "six scheduled opportunities inside" in workflow
