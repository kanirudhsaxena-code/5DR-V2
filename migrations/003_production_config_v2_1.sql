-- 5DR V2.1 runtime configuration
CREATE TABLE IF NOT EXISTS production_config (
  config_id smallint PRIMARY KEY CHECK(config_id=1),
  active_model_version text NOT NULL REFERENCES model_versions(model_version),
  canonical_timezone text NOT NULL DEFAULT 'Asia/Kolkata',
  canonical_window_start time NOT NULL DEFAULT TIME '15:20:00',
  canonical_window_end time NOT NULL DEFAULT TIME '09:14:59',
  canonical_selection_rule text NOT NULL DEFAULT 'LATEST_VALID_CANDIDATE_IN_WINDOW',
  canonical_d1_policy text NOT NULL DEFAULT 'TARGET_TRADING_DATE',
  intraday_d1_policy text NOT NULL DEFAULT 'NEXT_FULL_TRADING_SESSION',
  primary_accuracy_metric text NOT NULL DEFAULT 'CANONICAL_D5_DIRECTIONAL_ACCURACY',
  updated_at timestamptz NOT NULL DEFAULT now()
);

INSERT INTO production_config(
  config_id,active_model_version,canonical_timezone,
  canonical_window_start,canonical_window_end,canonical_selection_rule,
  canonical_d1_policy,intraday_d1_policy,primary_accuracy_metric
)
VALUES (
  1,'5DR_V2_1','Asia/Kolkata',
  TIME '15:20:00',TIME '09:14:59','LATEST_VALID_CANDIDATE_IN_WINDOW',
  'TARGET_TRADING_DATE','NEXT_FULL_TRADING_SESSION',
  'CANONICAL_D5_DIRECTIONAL_ACCURACY'
)
ON CONFLICT (config_id) DO UPDATE SET
  active_model_version=EXCLUDED.active_model_version,
  canonical_timezone=EXCLUDED.canonical_timezone,
  canonical_window_start=EXCLUDED.canonical_window_start,
  canonical_window_end=EXCLUDED.canonical_window_end,
  canonical_selection_rule=EXCLUDED.canonical_selection_rule,
  canonical_d1_policy=EXCLUDED.canonical_d1_policy,
  intraday_d1_policy=EXCLUDED.intraday_d1_policy,
  primary_accuracy_metric=EXCLUDED.primary_accuracy_metric,
  updated_at=now();

INSERT INTO schema_meta(schema_version) VALUES (3)
ON CONFLICT (schema_version) DO NOTHING;
