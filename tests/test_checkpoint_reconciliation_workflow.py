from pathlib import Path


def test_lifecycle_workflow_reconciles_due_checkpoints_from_authenticated_upstox():
    text = Path(".github/workflows/lifecycle-production-wrapper.yml").read_text(encoding="utf-8")
    assert "UPSTOX_ANALYTICS_TOKEN" in text
    assert "python -m src.checkpoint_reconcile_cli" in text
    assert "test_checkpoint_reconciliation.py" in text


def test_lifecycle_workflow_publishes_live_canonical_rollup_not_stale_snapshot_forecast_metrics():
    text = Path(".github/workflows/lifecycle-production-wrapper.yml").read_text(encoding="utf-8")
    assert "v_latest_forecast_checkpoint_evaluation" in text
    assert "canonical_scorable_checkpoints" in text
    assert "pending_due_checkpoints" in text
    assert "persistence_integrity_incomplete_forecasts" in text


def test_reconciliation_change_triggers_immediate_main_run():
    text = Path(".github/workflows/lifecycle-production-wrapper.yml").read_text(encoding="utf-8")
    assert "push:" in text
    assert "branches: [main]" in text
    assert "src/checkpoint_reconciliation.py" in text


def test_assessment_callback_uses_cloudflare_service_credentials():
    text = Path(".github/workflows/lifecycle-production-wrapper.yml").read_text(encoding="utf-8")
    assert "CF_ACCESS_CLIENT_ID" in text
    assert "CF_ACCESS_CLIENT_SECRET" in text
    assert "CF-Access-Client-Id" in text
    assert "CF-Access-Client-Secret" in text
