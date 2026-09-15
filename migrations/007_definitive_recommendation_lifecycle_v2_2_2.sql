-- 5DR V2.2.2 — Definitive Recommendation Lifecycle & Efficacy Amendment
-- Additive lifecycle/accounting patch only. Core forecast methodology is unchanged.
-- Historical forecasts, execution plans, recommendation events and assessment snapshots remain immutable.

ALTER TABLE public.recommendation_events
  DROP CONSTRAINT IF EXISTS recommendation_events_event_type_check;

ALTER TABLE public.recommendation_events
  ADD CONSTRAINT recommendation_events_event_type_check
  CHECK (event_type IN (
    'ISSUED',
    'ENTRY_TRIGGERED',              -- legacy compatibility only
    'ENTRY_REFERENCE_SET',          -- V2.2.2 standardized model-entry reference
    'ENTRY_NOT_VERIFIABLE',         -- exceptional data-quality state
    'MARK',
    'T1_HIT',
    'T2_HIT',
    'SL_HIT',
    'THESIS_EXIT',
    'TIME_EXIT',
    'NOT_SCORABLE',
    'NO_TRADE_ASSESSED'
  ));

ALTER TABLE public.production_config
  ADD COLUMN IF NOT EXISTS recommendation_lifecycle_version TEXT NOT NULL
  DEFAULT '5DR_V2_2_2';

UPDATE public.production_config
SET recommendation_lifecycle_version = '5DR_V2_2_2',
    updated_at = now();

-- ---------------------------------------------------------------------------
-- Append-only historical normalization.
-- Every definitive actionable recommendation with a verified issuance premium
-- receives a standardized model-entry reference. This does not claim a user
-- fill and does not alter the immutable execution plan or earlier events.
-- ---------------------------------------------------------------------------
INSERT INTO public.recommendation_events (
  forecast_id,
  event_type,
  event_timestamp,
  premium,
  source_ref,
  notes
)
SELECT
  f.forecast_id,
  'ENTRY_REFERENCE_SET',
  f.run_timestamp,
  ep.observed_premium,
  'MIGRATION_007_V2_2_2',
  'Append-only V2.2.2 standardized model-entry reference from verified issuance premium; not a user-fill claim.'
FROM public.forecasts f
JOIN public.execution_plans ep USING (forecast_id)
WHERE f.recommendation IN ('BUY_CE', 'BUY_PE', 'BUY_CONVEXITY')
  AND ep.observed_premium IS NOT NULL
  AND NOT EXISTS (
    SELECT 1
    FROM public.recommendation_events r
    WHERE r.forecast_id = f.forecast_id
      AND r.event_type IN ('ENTRY_REFERENCE_SET', 'ENTRY_TRIGGERED')
  );

-- Exceptional data-quality state only: no verified issuance premium and no
-- later entry reference exists yet. These calls stay in the ledger but are not
-- forced into a fabricated WIN/LOSS denominator.
INSERT INTO public.recommendation_events (
  forecast_id,
  event_type,
  event_timestamp,
  premium,
  source_ref,
  notes
)
SELECT
  f.forecast_id,
  'ENTRY_NOT_VERIFIABLE',
  f.run_timestamp,
  NULL,
  'MIGRATION_007_V2_2_2',
  'No verified issuance premium available at V2.2.2 normalization; retain in ledger as data-quality exception until objectively resolvable.'
FROM public.forecasts f
LEFT JOIN public.execution_plans ep USING (forecast_id)
WHERE f.recommendation IN ('BUY_CE', 'BUY_PE', 'BUY_CONVEXITY')
  AND ep.observed_premium IS NULL
  AND NOT EXISTS (
    SELECT 1
    FROM public.recommendation_events r
    WHERE r.forecast_id = f.forecast_id
      AND r.event_type IN ('ENTRY_REFERENCE_SET', 'ENTRY_TRIGGERED', 'ENTRY_NOT_VERIFIABLE')
  );

CREATE OR REPLACE VIEW public.v_latest_recommendation_event AS
SELECT DISTINCT ON (forecast_id)
  event_id,
  forecast_id,
  event_type,
  event_timestamp,
  premium,
  pnl_pct,
  r_multiple,
  source_ref,
  notes,
  created_at
FROM public.recommendation_events
ORDER BY forecast_id, event_timestamp DESC, event_id DESC;

CREATE OR REPLACE VIEW public.v_recommendation_lifecycle_v222 AS
WITH actionable AS (
  SELECT
    f.forecast_id,
    f.run_timestamp AS issuance_timestamp,
    f.recommendation,
    ep.instrument,
    ep.strike,
    ep.expiry,
    ep.observed_premium,
    ep.entry_low,
    ep.entry_high,
    ep.stop_premium,
    ep.target1_premium,
    ep.target2_premium
  FROM public.forecasts f
  LEFT JOIN public.execution_plans ep USING (forecast_id)
  WHERE f.recommendation IN ('BUY_CE', 'BUY_PE', 'BUY_CONVEXITY')
),
entry_reference AS (
  SELECT DISTINCT ON (forecast_id)
    forecast_id,
    premium AS model_entry_premium,
    event_timestamp AS model_entry_timestamp,
    event_type AS model_entry_event_type,
    event_id AS model_entry_event_id
  FROM public.recommendation_events
  WHERE event_type IN ('ENTRY_REFERENCE_SET', 'ENTRY_TRIGGERED')
  ORDER BY forecast_id, event_timestamp, event_id
),
first_primary_event AS (
  SELECT DISTINCT ON (forecast_id)
    forecast_id,
    event_type AS first_primary_event_type,
    event_timestamp AS first_primary_event_timestamp,
    event_id AS first_primary_event_id
  FROM public.recommendation_events
  WHERE event_type IN ('T1_HIT', 'SL_HIT')
  ORDER BY forecast_id, event_timestamp, event_id
),
terminal_times AS (
  SELECT
    forecast_id,
    MIN(event_timestamp) FILTER (WHERE event_type = 'T1_HIT') AS t1_hit_at,
    MIN(event_timestamp) FILTER (WHERE event_type = 'T2_HIT') AS t2_hit_at,
    MIN(event_timestamp) FILTER (WHERE event_type = 'SL_HIT') AS sl_hit_at,
    MIN(event_timestamp) FILTER (WHERE event_type = 'THESIS_EXIT') AS thesis_exit_at,
    MIN(event_timestamp) FILTER (WHERE event_type = 'TIME_EXIT') AS time_exit_at,
    MIN(event_timestamp) FILTER (WHERE event_type = 'NOT_SCORABLE') AS not_scorable_at,
    MIN(event_timestamp) FILTER (WHERE event_type = 'ENTRY_NOT_VERIFIABLE') AS entry_not_verifiable_at
  FROM public.recommendation_events
  GROUP BY forecast_id
)
SELECT
  a.*,
  er.model_entry_premium,
  er.model_entry_timestamp,
  er.model_entry_event_type,
  tt.t1_hit_at,
  tt.t2_hit_at,
  tt.sl_hit_at,
  tt.thesis_exit_at,
  tt.time_exit_at,
  tt.not_scorable_at,
  tt.entry_not_verifiable_at,
  fpe.first_primary_event_type,
  CASE
    WHEN tt.not_scorable_at IS NOT NULL THEN 'NOT_SCORABLE'
    WHEN er.model_entry_timestamp IS NULL AND tt.entry_not_verifiable_at IS NOT NULL THEN 'ENTRY_NOT_VERIFIABLE'
    WHEN tt.t2_hit_at IS NOT NULL THEN 'CLOSED_T2'
    WHEN tt.sl_hit_at IS NOT NULL THEN 'CLOSED_SL'
    WHEN tt.thesis_exit_at IS NOT NULL THEN 'CLOSED_THESIS_EXIT'
    WHEN tt.time_exit_at IS NOT NULL THEN 'CLOSED_TIME_EXIT'
    WHEN tt.t1_hit_at IS NOT NULL THEN 'OPEN_T1_HIT'
    ELSE 'OPEN'
  END AS lifecycle_status,
  CASE
    WHEN fpe.first_primary_event_type = 'T1_HIT' THEN 'WIN'
    WHEN fpe.first_primary_event_type = 'SL_HIT' THEN 'LOSS'
    ELSE NULL
  END AS primary_outcome
FROM actionable a
LEFT JOIN entry_reference er USING (forecast_id)
LEFT JOIN first_primary_event fpe USING (forecast_id)
LEFT JOIN terminal_times tt USING (forecast_id);

INSERT INTO public.schema_meta(schema_version)
SELECT 7
WHERE NOT EXISTS (SELECT 1 FROM public.schema_meta WHERE schema_version = 7);

INSERT INTO public.change_log(
  model_version, schema_version, change_type, description, rationale
)
VALUES (
  '5DR_V2_1',
  7,
  'AMENDMENT',
  'V2.2.2 definitive recommendation lifecycle: actionable calls are tracked from issuance; standardized model-entry references are explicit and historical issuance premiums are normalized append-only; UNTRIGGERED is removed as a normal current lifecycle; thesis exits and entry-verification exceptions are supported.',
  'Align recommendation efficacy with the definitive 5DR decision contract while preserving historical immutability and leaving the production forecasting methodology and Learning Lab promotion firewall unchanged.'
);
