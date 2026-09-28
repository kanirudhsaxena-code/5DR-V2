-- P0-11 immutable 5DR presentation snapshot storage.
--
-- IMPORTANT: repository presence is NOT production activation. Validate this
-- migration on a temporary Neon branch before any production application.
-- It is additive only and does not alter 5DR scoring, forecast methodology,
-- canonical selection, efficacy populations, recommendations or trading logic.

-- The live 5DR schema already makes run_id and forecast_id individually unique.
-- This redundant composite unique index exists solely to let PostgreSQL enforce
-- the exact run/forecast pair with a declarative composite foreign key below.
CREATE UNIQUE INDEX IF NOT EXISTS uq_5dr_forecasts_run_forecast_identity
ON public.forecasts(run_id,forecast_id);

CREATE TABLE IF NOT EXISTS public.presentation_snapshots (
  presentation_snapshot_id bigserial PRIMARY KEY,
  presentation_contract_version text NOT NULL
    CHECK (presentation_contract_version='P0_11_PRESENTATION_V1'),
  engine text NOT NULL CHECK (engine='5DR'),
  run_id bigint NOT NULL REFERENCES public.runs(run_id) ON DELETE RESTRICT,
  result_id text NOT NULL REFERENCES public.forecasts(forecast_id) ON DELETE RESTRICT,
  checkpoint_id text CHECK (checkpoint_id IS NULL),
  governance_state text NOT NULL CHECK (btrim(governance_state) <> ''),
  sections jsonb NOT NULL
    CHECK (jsonb_typeof(sections)='array' AND jsonb_array_length(sections)=2),
  source_payload_hash text NOT NULL CHECK (btrim(source_payload_hash) <> ''),
  presentation_hash text NOT NULL CHECK (presentation_hash ~ '^[0-9a-f]{64}$'),
  created_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT presentation_snapshots_exact_forecast_identity_fkey
    FOREIGN KEY (run_id,result_id)
    REFERENCES public.forecasts(run_id,forecast_id)
    ON DELETE RESTRICT
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_5dr_presentation_exact_identity
ON public.presentation_snapshots(run_id,result_id);

CREATE INDEX IF NOT EXISTS idx_5dr_presentation_result
ON public.presentation_snapshots(result_id,created_at DESC);

CREATE RULE presentation_snapshots_no_update AS
ON UPDATE TO public.presentation_snapshots DO INSTEAD NOTHING;

CREATE RULE presentation_snapshots_no_delete AS
ON DELETE TO public.presentation_snapshots DO INSTEAD NOTHING;

-- No INSERT/backfill is performed by this migration. Existing canonicals remain
-- presentation-unavailable until a contemporaneous governed snapshot is written.
-- The live 5DR project currently exposes only its owner role, so no unverified
-- runtime-role grant is invented here.
