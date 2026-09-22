-- 5DR V2.2.3 day-wise three-class scenario probability persistence.
-- Additive only: historical rows remain immutable with NULL scenario vectors.
-- New post-amendment rows must carry BULL/RANGE/BEAR probabilities summing to 100.

ALTER TABLE daily_forecasts
  ADD COLUMN IF NOT EXISTS bull_probability NUMERIC,
  ADD COLUMN IF NOT EXISTS range_probability NUMERIC,
  ADD COLUMN IF NOT EXISTS bear_probability NUMERIC;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint WHERE conname='daily_forecasts_scenario_probability_bounds'
  ) THEN
    ALTER TABLE daily_forecasts ADD CONSTRAINT daily_forecasts_scenario_probability_bounds CHECK (
      (bull_probability IS NULL OR bull_probability BETWEEN 0 AND 100)
      AND (range_probability IS NULL OR range_probability BETWEEN 0 AND 100)
      AND (bear_probability IS NULL OR bear_probability BETWEEN 0 AND 100)
    );
  END IF;

  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint WHERE conname='daily_forecasts_scenario_vector_integrity'
  ) THEN
    ALTER TABLE daily_forecasts ADD CONSTRAINT daily_forecasts_scenario_vector_integrity CHECK (
      (bull_probability IS NULL AND range_probability IS NULL AND bear_probability IS NULL)
      OR (
        bull_probability IS NOT NULL
        AND range_probability IS NOT NULL
        AND bear_probability IS NOT NULL
        AND abs((bull_probability + range_probability + bear_probability) - 100) <= 0.02
        AND (
          (bias='BULLISH' AND bull_probability >= greatest(range_probability,bear_probability)-0.02)
          OR (bias='RANGE' AND range_probability >= greatest(bull_probability,bear_probability)-0.02)
          OR (bias='BEARISH' AND bear_probability >= greatest(bull_probability,range_probability)-0.02)
        )
      )
    );
  END IF;
END $$;
