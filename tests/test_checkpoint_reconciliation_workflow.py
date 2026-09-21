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


def test_cloudflare_access_secret_names_have_repo_compatible_fallbacks():
    text = Path(".github/workflows/lifecycle-production-wrapper.yml").read_text(encoding="utf-8")
    assert "secrets.CF_ACCESS_CLIENT_ID || secrets.CLOUDFLARE_ACCESS_CLIENT_ID" in text
    assert "secrets.CF_ACCESS_CLIENT_SECRET || secrets.CLOUDFLARE_ACCESS_CLIENT_SECRET" in text


def test_headline_recommendation_efficacy_is_selected_canonical_only():
    text = Path(".github/workflows/lifecycle-production-wrapper.yml").read_text(encoding="utf-8")
    assert "SELECT recommendation_metrics\n                      FROM assessment_snapshots" not in text
    assert "SELECTED_DAILY_CANONICAL_ONLY" in text
    assert "JOIN canonical_selections c" in text
    assert "c.selected_forecast_id=re.forecast_id" in text
    assert "COUNT(*) FILTER (WHERE s.recommendation='NO_TRADE')" in text


def test_headline_returns_exclude_noncanonical_recommendations():
    text = Path(".github/workflows/lifecycle-production-wrapper.yml").read_text(encoding="utf-8")
    assert "selected DAILY_CANONICAL actionable recommendations only" in text
    terminal_start = text.index("WITH terminal AS (", text.index("population_rule"))
    terminal_slice = text[terminal_start:terminal_start + 1800]
    assert "JOIN canonical_selections c" in terminal_slice
    assert "c.selected_forecast_id=re.forecast_id" in terminal_slice


def test_assessment_clock_advances_on_canonical_recommendation_events():
    text = Path(".github/workflows/lifecycle-production-wrapper.yml").read_text(encoding="utf-8")
    assert "recommendation_as_of" in text
    assert "forecast_assessed_at" in text
    assert "assessed_at = max(" in text


def test_assessment_reports_matured_eligible_vs_scorable_coverage():
    text = Path(".github/workflows/lifecycle-production-wrapper.yml").read_text(encoding="utf-8")
    assert "eligible_matured" in text
    assert "missing_unscorable" in text
    assert "scorable_coverage_pct" in text
    assert "matured eligible checkpoints scorable" in text

def test_lifecycle_prefers_current_cloudflare_service_token_and_probes_access():
    text = Path(".github/workflows/lifecycle-production-wrapper.yml").read_text(encoding="utf-8")
    assert "secrets.CLOUDFLARE_ACCESS_CLIENT_ID || secrets.CF_ACCESS_CLIENT_ID" in text
    assert "Verify authenticated EDGE Console service access" in text
    assert "edge_console_service_access_ok" in text
