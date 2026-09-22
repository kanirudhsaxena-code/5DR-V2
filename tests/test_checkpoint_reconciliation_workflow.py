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


def test_lifecycle_uses_governed_repository_state_instead_of_cross_repo_cloudflare_credentials():
    text = Path(".github/workflows/lifecycle-production-wrapper.yml").read_text(encoding="utf-8")
    assert "EDGE_CONSOLE_HANDOFF_URL" in text
    assert "state/5dr-handoff/runtime/5dr-canonical-handoff.json" in text
    assert "CF-Access-Client-Id" not in text
    assert "CF-Access-Client-Secret" not in text


def test_assessment_is_published_to_isolated_state_branch():
    text = Path(".github/workflows/lifecycle-production-wrapper.yml").read_text(encoding="utf-8")
    assert "5DR_ASSESSMENT_HANDOFF_V1" in text
    assert "state/assessment-handoff" in text
    assert "runtime/5dr-assessment-handoff.json" in text
    assert "contents: write" in text


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

def test_lifecycle_has_no_direct_console_access_dependency():
    text = Path(".github/workflows/lifecycle-production-wrapper.yml").read_text(encoding="utf-8")
    assert "Verify authenticated EDGE Console service access" not in text
    assert "/api/assessment-import" not in text
    assert "assessment_handoff_built" in text


def test_assessment_handoff_exposes_canonical_regime_metadata():
    text = Path(".github/workflows/lifecycle-production-wrapper.yml").read_text(encoding="utf-8")
    assert '"canonical_selection": canonical_selection' in text
    assert '"canonical_type": canonical_type' in text
    assert '"governance_era": governance_era' in text
    assert 'LEGACY_CANONICAL' in text
    assert 'POST_GOVERNANCE' in text


def test_assessment_presents_canonical_horizons_as_d_through_d_plus_4():
    text = Path(".github/workflows/lifecycle-production-wrapper.yml").read_text(encoding="utf-8")
    assert 'def horizon_label(day_number: int) -> str:' in text
    assert 'return "D" if int(day_number)==1 else f"D+{int(day_number)-1}"' in text
    assert 'day_metrics[horizon_label(int(day_number))]' in text
    assert '**{horizon_label(d): {' in text
