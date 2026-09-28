-- P0-11 immutable 5DR presentation snapshot storage.
--
-- IMPORTANT: repository presence is NOT production activation. Validate this
-- migration on a temporary Neon branch before any production application.
-- It is additive only and does not alter 5DR scoring, forecast methodology,
-- canonical selection, efficacy populations, recommendations or trading logic.

CREATE TABLE IF NOT EXISTS presentation_snapshots (
  presentation_snapshot_id bigserial PRIMARY KEY,
  presentation_contract_version text NOT NULL
    CHECK (presentation_contract_version='P0_11_PRESENTATION_V1'),
  engine text NOT NULL CHECK (engine='5DR'),
  run_id text NOT NULL,
  result_id text NOT NULL,
  checkpoint_id text,
  governance_state text NOT NULL CHECK (btrim(governance_state) <> ''),
  sections jsonb NOT NULL
    CHECK (jsonb_typeof(sections)='array' AND jsonb_array_length(sections)=2),
  source_payload_hash text NOT NULL CHECK (btrim(source_payload_hash) <> ''),
  presentation_hash text NOT NULL CHECK (presentation_hash ~ '^[0-9a-f]{64}$'),
  created_at timestamptz NOT NULL DEFAULT now()
);

-- NULL checkpoint identity must still be unique. Plain UNIQUE would allow
-- duplicate NULL checkpoint rows and weaken immutable exact-result binding.
CREATE UNIQUE INDEX IF NOT EXISTS uq_5dr_presentation_exact_identity
ON presentation_snapshots(run_id,result_id,COALESCE(checkpoint_id,''));

CREATE INDEX IF NOT EXISTS idx_5dr_presentation_result
ON presentation_snapshots(result_id,created_at DESC);

CREATE RULE presentation_snapshots_no_update AS
ON UPDATE TO presentation_snapshots DO INSTEAD NOTHING;

CREATE RULE presentation_snapshots_no_delete AS
ON DELETE TO presentation_snapshots DO INSTEAD NOTHING;

-- No INSERT/backfill is performed by this migration. Existing canonicals remain
-- presentation-unavailable until a contemporaneous governed snapshot is written.
