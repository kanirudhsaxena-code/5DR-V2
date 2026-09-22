-- 5DR V2.2.3 additive output-contract persistence
-- New day-wise BULL/RANGE/BEAR vectors. Historical rows remain NULL.

ALTER TABLE public.daily_forecasts
  ADD COLUMN IF NOT EXISTS bull_probability NUMERIC,
  ADD COLUMN IF NOT EXISTS range_probability NUMERIC,
  ADD COLUMN IF NOT EXISTS bear_probability NUMERIC;

ALTER TABLE public.daily_forecasts
  DROP CONSTRAINT IF EXISTS daily_forecasts_scenario_probability_bundle_check,
  ADD CONSTRAINT daily_forecasts_scenario_probability_bundle_check
  CHECK (
    (bull_probability IS NULL AND range_probability IS NULL AND bear_probability IS NULL)
    OR (
      bull_probability BETWEEN 0 AND 100
      AND range_probability BETWEEN 0 AND 100
      AND bear_probability BETWEEN 0 AND 100
      AND abs((bull_probability + range_probability + bear_probability) - 100) <= 0.02
    )
  );

ALTER TABLE public.daily_forecasts
  DROP CONSTRAINT IF EXISTS daily_forecasts_scenario_direction_check,
  ADD CONSTRAINT daily_forecasts_scenario_direction_check
  CHECK (
    bull_probability IS NULL
    OR (
      (bias='BULLISH' AND bull_probability >= range_probability AND bull_probability >= bear_probability)
      OR (bias='RANGE' AND range_probability >= bull_probability AND range_probability >= bear_probability)
      OR (bias='BEARISH' AND bear_probability >= bull_probability AND bear_probability >= range_probability)
    )
  );

ALTER TABLE public.daily_forecasts
  DROP CONSTRAINT IF EXISTS daily_forecasts_selected_probability_check,
  ADD CONSTRAINT daily_forecasts_selected_probability_check
  CHECK (
    bull_probability IS NULL
    OR abs(probability - CASE bias
      WHEN 'BULLISH' THEN bull_probability
      WHEN 'RANGE' THEN range_probability
      WHEN 'BEARISH' THEN bear_probability
    END) <= 0.02
  );

INSERT INTO public.schema_meta(schema_version)
SELECT 8
WHERE NOT EXISTS (SELECT 1 FROM public.schema_meta WHERE schema_version=8);

INSERT INTO public.change_log(model_version,schema_version,change_type,description,rationale)
VALUES (
  '5DR_V2_1',8,'AMENDMENT',
  'Add immutable per-horizon BULL RANGE BEAR scenario probabilities to daily_forecasts with legacy rows left NULL',
  'Remove ambiguous standalone daily confidence probability while preserving historical records and frozen methodology'
);
