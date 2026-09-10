-- 5DR V2.1 additive governance migration
-- This migration does not alter immutable V2 forecast content.

CREATE TABLE IF NOT EXISTS trading_calendar (
  trading_date date PRIMARY KEY,
  is_trading_day boolean NOT NULL DEFAULT true,
  session_open_ist time NOT NULL DEFAULT TIME '09:15:00',
  session_close_ist time NOT NULL DEFAULT TIME '15:30:00',
  source_ref text,
  verified_at timestamptz,
  notes text
);

CREATE TABLE IF NOT EXISTS forecast_governance (
  forecast_id text PRIMARY KEY REFERENCES forecasts(forecast_id),
  target_trading_date date NOT NULL,
  run_class text NOT NULL CHECK(run_class IN ('CANONICAL_CANDIDATE','INTRADAY_SNAPSHOT')),
  validity_status text NOT NULL CHECK(validity_status IN ('VALID','INVALID')),
  validity_reason text,
  evidence_mode text NOT NULL CHECK(evidence_mode IN ('LIVE_MARKET','MARKET_CLOSED_CARRY_FORWARD','PREOPEN_REFRESH','MIXED')),
  predecessor_forecast_id text REFERENCES forecasts(forecast_id),
  sequence_in_lineage integer NOT NULL DEFAULT 1 CHECK(sequence_in_lineage >= 1),
  canonical_window_open timestamptz NOT NULL,
  canonical_window_close timestamptz NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  CHECK(canonical_window_close > canonical_window_open)
);

CREATE INDEX IF NOT EXISTS idx_forecast_governance_target_time
ON forecast_governance(target_trading_date, created_at);

CREATE INDEX IF NOT EXISTS idx_forecast_governance_class
ON forecast_governance(run_class, validity_status, target_trading_date);

CREATE TABLE IF NOT EXISTS canonical_selections (
  target_trading_date date PRIMARY KEY,
  selection_status text NOT NULL CHECK(selection_status IN ('SELECTED','NO_VALID_CANDIDATE')),
  selected_forecast_id text REFERENCES forecasts(forecast_id),
  first_candidate_forecast_id text REFERENCES forecasts(forecast_id),
  selected_at timestamptz NOT NULL DEFAULT now(),
  window_open_at timestamptz NOT NULL,
  window_close_at timestamptz NOT NULL,
  selection_rule text NOT NULL DEFAULT 'LATEST_VALID_CANDIDATE_IN_WINDOW',
  selection_reason text,
  CHECK(window_close_at > window_open_at),
  CHECK((selection_status='SELECTED' AND selected_forecast_id IS NOT NULL)
     OR (selection_status='NO_VALID_CANDIDATE' AND selected_forecast_id IS NULL))
);

CREATE RULE canonical_selections_no_update AS
ON UPDATE TO canonical_selections DO INSTEAD NOTHING;
CREATE RULE canonical_selections_no_delete AS
ON DELETE TO canonical_selections DO INSTEAD NOTHING;

CREATE TABLE IF NOT EXISTS lineage_deltas (
  forecast_id text PRIMARY KEY REFERENCES forecasts(forecast_id),
  prior_forecast_id text REFERENCES forecasts(forecast_id),
  des5_delta numeric(8,3),
  market_trust_delta numeric(8,3),
  bull_probability_delta numeric(8,3),
  range_probability_delta numeric(8,3),
  bear_probability_delta numeric(8,3),
  recommendation_changed boolean NOT NULL DEFAULT false,
  direction_changed boolean NOT NULL DEFAULT false,
  evidence_delta_summary text,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE RULE lineage_deltas_no_update AS
ON UPDATE TO lineage_deltas DO INSTEAD NOTHING;
CREATE RULE lineage_deltas_no_delete AS
ON DELETE TO lineage_deltas DO INSTEAD NOTHING;

CREATE TABLE IF NOT EXISTS revision_metrics (
  revision_metric_id bigserial PRIMARY KEY,
  target_trading_date date NOT NULL,
  prior_forecast_id text NOT NULL REFERENCES forecasts(forecast_id),
  later_forecast_id text NOT NULL REFERENCES forecasts(forecast_id),
  checkpoint_type text NOT NULL CHECK(checkpoint_type IN ('D+1','D+2','D+3','D+4','D+5','FINAL')),
  revision_scope text NOT NULL CHECK(revision_scope IN ('INTRADAY','OVERNIGHT','CANONICAL_WINDOW')),
  prior_brier numeric,
  later_brier numeric,
  brier_improvement numeric,
  directional_revision_result text
    CHECK(directional_revision_result IN ('IMPROVED','UNCHANGED','WORSENED','NOT_SCORABLE')),
  computed_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE(prior_forecast_id,later_forecast_id,checkpoint_type)
);

CREATE TABLE IF NOT EXISTS lineage_efficacy_summary (
  target_trading_date date PRIMARY KEY,
  canonical_forecast_id text REFERENCES forecasts(forecast_id),
  raw_snapshot_accuracy numeric,
  day_normalized_snapshot_accuracy numeric,
  stability_score numeric CHECK(stability_score BETWEEN 0 AND 100),
  directional_flip_count integer CHECK(directional_flip_count >= 0),
  early_recognition_forecast_id text REFERENCES forecasts(forecast_id),
  early_recognition_at timestamptz,
  early_recognition_status text
    CHECK(early_recognition_status IN ('RECOGNIZED','NOT_RECOGNIZED','NOT_SCORABLE')),
  overnight_revision_brier_improvement numeric,
  overnight_revision_result text
    CHECK(overnight_revision_result IN ('IMPROVED','UNCHANGED','WORSENED','NOT_SCORABLE')),
  computed_at timestamptz NOT NULL DEFAULT now()
);

CREATE VIEW v_latest_valid_canonical_candidate AS
SELECT DISTINCT ON (g.target_trading_date)
  g.target_trading_date,g.forecast_id,f.run_timestamp,f.definitive_forecast,
  f.bull_probability,f.range_probability,f.bear_probability,f.des5,f.market_trust_score
FROM forecast_governance g
JOIN forecasts f ON f.forecast_id=g.forecast_id
WHERE g.run_class='CANONICAL_CANDIDATE'
  AND g.validity_status='VALID'
ORDER BY g.target_trading_date,f.run_timestamp DESC;

CREATE VIEW v_daily_canonical_forecasts AS
SELECT c.target_trading_date,c.selected_forecast_id,f.run_timestamp,
       f.definitive_forecast,f.bull_probability,f.range_probability,
       f.bear_probability,f.des5,f.market_trust_score,f.recommendation
FROM canonical_selections c
LEFT JOIN forecasts f ON f.forecast_id=c.selected_forecast_id
WHERE c.selection_status='SELECTED';

INSERT INTO schema_meta(schema_version) VALUES (2)
ON CONFLICT (schema_version) DO NOTHING;

INSERT INTO model_versions(model_version,status,freeze_date,specification_ref)
VALUES ('5DR_V2_1','FROZEN',DATE '2026-09-10','5DR_V2_1_CANONICAL_SPECIFICATION')
ON CONFLICT (model_version) DO NOTHING;
