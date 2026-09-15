-- 5DR V2.2.2 historical recommendation reconstruction
-- APPEND-ONLY. Run only after migration 007 is applied.
-- This script establishes standardized model-entry references and verified threshold events
-- for historical recommendations where stored/visual evidence already exists.
-- It does not modify forecasts, execution plans, old events or old assessment snapshots.

-- 10 Sep 15:47 — NIFTY 23500 PE 22 Sep, issuance premium 182.55, SL 150, T1 250, T2 295.
INSERT INTO public.recommendation_events
(forecast_id,event_type,event_timestamp,premium,pnl_pct,r_multiple,source_ref,notes)
SELECT '5DR-20260910-1547-01','ENTRY_REFERENCE_SET','2026-09-10 15:47:00+05:30',182.55,0,0,
       'Stored issuance premium / execution plan',
       'V2.2.2 standardized model-entry reference. Preferred band 175-190 is execution guidance, not an efficacy trigger.'
WHERE NOT EXISTS (
  SELECT 1 FROM public.recommendation_events
  WHERE forecast_id='5DR-20260910-1547-01' AND event_type='ENTRY_REFERENCE_SET'
);

INSERT INTO public.recommendation_events
(forecast_id,event_type,event_timestamp,premium,pnl_pct,r_multiple,source_ref,notes)
SELECT '5DR-20260910-1547-01','T1_HIT','2026-09-11 09:52:00+05:30',250,36.949,2.0722,
       'User Sensibull 22 Sep LTP screenshot at 09:52 IST; 23500 PE verified at 310.25',
       'T1=250 was exceeded by first verified 11 Sep observation. Exact earlier touch time is not inferred.'
WHERE NOT EXISTS (
  SELECT 1 FROM public.recommendation_events
  WHERE forecast_id='5DR-20260910-1547-01' AND event_type='T1_HIT'
);

INSERT INTO public.recommendation_events
(forecast_id,event_type,event_timestamp,premium,pnl_pct,r_multiple,source_ref,notes)
SELECT '5DR-20260910-1547-01','T2_HIT','2026-09-11 09:52:00+05:30',295,61.5996,3.4547,
       'User Sensibull 22 Sep LTP screenshot at 09:52 IST; 23500 PE verified at 310.25',
       'T2=295 was exceeded by first verified 11 Sep observation. Exact earlier touch time is not inferred.'
WHERE NOT EXISTS (
  SELECT 1 FROM public.recommendation_events
  WHERE forecast_id='5DR-20260910-1547-01' AND event_type='T2_HIT'
);

-- 10 Sep 18:26 — NIFTY 23500 PE 22 Sep, issuance premium 182.55, SL 150, T1 250.
-- Exact T2 is not currently verified from the authoritative record, so no T2 event is created.
INSERT INTO public.recommendation_events
(forecast_id,event_type,event_timestamp,premium,pnl_pct,r_multiple,source_ref,notes)
SELECT '5DR-20260910-1826-01','ENTRY_REFERENCE_SET','2026-09-10 18:26:00+05:30',182.55,0,0,
       'Stored issuance premium / execution plan',
       'V2.2.2 standardized model-entry reference. Preferred band 175-183 is execution guidance, not an efficacy trigger.'
WHERE NOT EXISTS (
  SELECT 1 FROM public.recommendation_events
  WHERE forecast_id='5DR-20260910-1826-01' AND event_type='ENTRY_REFERENCE_SET'
);

INSERT INTO public.recommendation_events
(forecast_id,event_type,event_timestamp,premium,pnl_pct,r_multiple,source_ref,notes)
SELECT '5DR-20260910-1826-01','T1_HIT','2026-09-11 09:52:00+05:30',250,36.949,2.0722,
       'User Sensibull 22 Sep LTP screenshot at 09:52 IST; 23500 PE verified at 310.25',
       'T1=250 was exceeded by first verified 11 Sep observation. Exact T2 remains NOT VERIFIED and is not invented.'
WHERE NOT EXISTS (
  SELECT 1 FROM public.recommendation_events
  WHERE forecast_id='5DR-20260910-1826-01' AND event_type='T1_HIT'
);

INSERT INTO public.recommendation_events
(forecast_id,event_type,event_timestamp,premium,pnl_pct,r_multiple,source_ref,notes)
SELECT '5DR-20260910-1826-01','MARK','2026-09-11 09:52:00+05:30',310.25,69.9534,3.922,
       'User Sensibull 22 Sep LTP screenshot at 09:52 IST',
       'Verified mark only. No T2 event is inferred because the frozen T2 value for this forecast has not been re-established.'
WHERE NOT EXISTS (
  SELECT 1 FROM public.recommendation_events
  WHERE forecast_id='5DR-20260910-1826-01' AND event_type='MARK' AND event_timestamp='2026-09-11 09:52:00+05:30'
);

-- 10 Sep 20:52 — NIFTY 23500 PE 22 Sep, issuance premium 182.55, SL 150, T1 255, T2 300.
INSERT INTO public.recommendation_events
(forecast_id,event_type,event_timestamp,premium,pnl_pct,r_multiple,source_ref,notes)
SELECT '5DR-20260910-2052-01','ENTRY_REFERENCE_SET','2026-09-10 20:52:00+05:30',182.55,0,0,
       'Stored issuance premium / execution plan',
       'V2.2.2 standardized model-entry reference. Preferred band 175-185 is execution guidance, not an efficacy trigger.'
WHERE NOT EXISTS (
  SELECT 1 FROM public.recommendation_events
  WHERE forecast_id='5DR-20260910-2052-01' AND event_type='ENTRY_REFERENCE_SET'
);

INSERT INTO public.recommendation_events
(forecast_id,event_type,event_timestamp,premium,pnl_pct,r_multiple,source_ref,notes)
SELECT '5DR-20260910-2052-01','T1_HIT','2026-09-11 09:52:00+05:30',255,39.688,2.2258,
       'User Sensibull 22 Sep LTP screenshot at 09:52 IST; 23500 PE verified at 310.25',
       'T1=255 was exceeded by first verified 11 Sep observation. Exact earlier touch time is not inferred.'
WHERE NOT EXISTS (
  SELECT 1 FROM public.recommendation_events
  WHERE forecast_id='5DR-20260910-2052-01' AND event_type='T1_HIT'
);

INSERT INTO public.recommendation_events
(forecast_id,event_type,event_timestamp,premium,pnl_pct,r_multiple,source_ref,notes)
SELECT '5DR-20260910-2052-01','T2_HIT','2026-09-11 09:52:00+05:30',300,64.3385,3.6083,
       'User Sensibull 22 Sep LTP screenshot at 09:52 IST; 23500 PE verified at 310.25',
       'T2=300 was exceeded by first verified 11 Sep observation. Exact earlier touch time is not inferred.'
WHERE NOT EXISTS (
  SELECT 1 FROM public.recommendation_events
  WHERE forecast_id='5DR-20260910-2052-01' AND event_type='T2_HIT'
);

-- 11 Sep 09:54 — NIFTY 23250 PE 22 Sep, verified entry 174.15, SL 140, T1 250, T2 310.
-- On 15 Sep 08:04 the same contract was verified at 100.70, below the frozen SL.
-- Record the stop as first verified by this observation; do not invent an earlier touch time.
INSERT INTO public.recommendation_events
(forecast_id,event_type,event_timestamp,premium,pnl_pct,r_multiple,source_ref,notes)
SELECT '5DR-20260911-0954-01','SL_HIT','2026-09-15 08:04:00+05:30',140,-19.6095,-1.0,
       'User Sensibull 22 Sep LTP screenshot on 15 Sep 08:04 IST; 23250 PE verified at 100.70',
       'Frozen SL=140 is verified breached by the first available later quote below stop. Exact earlier touch time is not inferred; no verified T1/T2 observation exists before this stop evidence.'
WHERE NOT EXISTS (
  SELECT 1 FROM public.recommendation_events
  WHERE forecast_id='5DR-20260911-0954-01' AND event_type='SL_HIT'
);

-- V2.2.2 intentionally does not rewrite prior assessment_snapshots.
-- Future assessment snapshots must rebuild cumulative recommendation metrics from the corrected event ledger.
