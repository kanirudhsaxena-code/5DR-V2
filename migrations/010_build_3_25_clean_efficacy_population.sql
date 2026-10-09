-- MDOS Build 3.25 — Clean NIFTY efficacy populations.
-- Additive only. Historical forecasts/evaluations/canonical selections are not mutated.

create or replace view public.v_build_3_25_nifty_checkpoint_population as
with selected as (
  select cs.target_trading_date, cs.selected_forecast_id as forecast_id
    from public.canonical_selections cs
   where cs.selection_status='SELECTED'
     and cs.selected_forecast_id is not null
),
path_counts as (
  select s.forecast_id,
         (select count(*) from public.daily_forecasts df where df.forecast_id=s.forecast_id) as daily_count,
         (select count(*) from public.outcome_checkpoints oc2
           where oc2.forecast_id=s.forecast_id
             and oc2.checkpoint_type in ('D+1','D+2','D+3','D+4','D+5')) as checkpoint_count
    from selected s
),
base as (
  select s.target_trading_date,
         oc.forecast_id,
         oc.checkpoint_type,
         cast(substring(oc.checkpoint_type from 3) as integer) as day_number,
         case cast(substring(oc.checkpoint_type from 3) as integer)
           when 1 then 'D' when 2 then 'D+1' when 3 then 'D+2'
           when 4 then 'D+3' else 'D+4' end as display_horizon,
         oc.due_date,
         oc.status as checkpoint_status,
         pc.daily_count,
         pc.checkpoint_count,
         e.evaluation_id,
         e.evaluation_status,
         e.actual_close,
         e.reference_spot,
         e.bias,
         e.directional_hit,
         e.directional_margin_points,
         e.zone_hit,
         e.zone_error_points,
         e.probability,
         e.brier_score,
         e.source_ref as evaluation_source_ref,
         e.evaluated_at,
         (
           oc.due_date < (current_timestamp at time zone 'Asia/Kolkata')::date
           or (
             oc.due_date=(current_timestamp at time zone 'Asia/Kolkata')::date
             and (current_timestamp at time zone 'Asia/Kolkata')::time >= time '15:40'
           )
         ) as matured
    from selected s
    join public.outcome_checkpoints oc
      on oc.forecast_id=s.forecast_id
     and oc.checkpoint_type in ('D+1','D+2','D+3','D+4','D+5')
    join path_counts pc on pc.forecast_id=s.forecast_id
    left join public.v_latest_forecast_checkpoint_evaluation e
      on e.forecast_id=oc.forecast_id
     and e.day_number=cast(substring(oc.checkpoint_type from 3) as integer)
)
select *,
       case
         when not matured then 'NOT_DUE'
         when daily_count<>5 or checkpoint_count<>5 then 'AUDIT_ONLY_INCOMPLETE'
         when evaluation_status='SCORABLE' then 'OFFICIAL_SCORABLE'
         when checkpoint_status='DUE' or evaluation_id is null then 'REPAIR_PENDING'
         else 'AUDIT_ONLY_INCOMPLETE'
       end as population_state,
       case
         when matured and (daily_count<>5 or checkpoint_count<>5)
           then 'FROZEN_FIVE_SESSION_PATH_INCOMPLETE'
         when matured and evaluation_status='NOT_SCORABLE'
           then 'EVALUATION_NOT_SCORABLE'
         when matured and (checkpoint_status='DUE' or evaluation_id is null)
           then 'MATURED_EVALUATION_PENDING'
         else null
       end as population_reason
  from base;

create or replace view public.v_official_5dr_efficacy_population as
select *
  from public.v_build_3_25_nifty_checkpoint_population
 where population_state='OFFICIAL_SCORABLE';

create or replace view public.v_5dr_efficacy_audit_exclusions as
select *
  from public.v_build_3_25_nifty_checkpoint_population
 where population_state in ('AUDIT_ONLY_INCOMPLETE','REPAIR_PENDING');

create or replace view public.v_official_5dr_horizon_efficacy as
select day_number,
       display_horizon,
       count(*) as scorable_count,
       count(*) filter (where directional_hit) as directional_hits,
       round(100.0*count(*) filter (where directional_hit)/nullif(count(*),0),2) as directional_accuracy_pct,
       count(*) filter (where zone_hit) as zone_hits,
       round(100.0*count(*) filter (where zone_hit)/nullif(count(*),0),2) as zone_hit_rate_pct,
       round(avg(directional_margin_points),2) as avg_directional_margin_points,
       round(avg(zone_error_points),2) as avg_zone_error_points,
       round(avg(brier_score) filter (where brier_score is not null),4) as avg_brier_score
  from public.v_official_5dr_efficacy_population
 group by day_number,display_horizon
 order by day_number;

create or replace view public.v_build_3_25_5dr_population_summary as
select
  count(*) filter (where matured) as raw_matured_count,
  count(*) filter (where population_state in ('OFFICIAL_SCORABLE','REPAIR_PENDING')) as eligible_matured_count,
  count(*) filter (where population_state='OFFICIAL_SCORABLE') as official_scorable_count,
  count(*) filter (where population_state='REPAIR_PENDING') as repair_pending_count,
  count(*) filter (where population_state='AUDIT_ONLY_INCOMPLETE') as audit_exclusion_count,
  round(
    100.0*count(*) filter (where population_state='OFFICIAL_SCORABLE')
    / nullif(count(*) filter (where population_state in ('OFFICIAL_SCORABLE','REPAIR_PENDING')),0),2
  ) as official_coverage_pct
from public.v_build_3_25_nifty_checkpoint_population;

insert into public.change_log(model_version,schema_version,change_type,description,rationale)
select '5DR_V2_1',5,'AMENDMENT',
       'Build 3.25 clean efficacy population views: official eligible/scorable checkpoints are separated from repair-pending and audit-only incomplete legacy rows.',
       'Remove persistence-incomplete legacy observations from official efficacy without deleting or rewriting immutable forecasts, while disclosing audit exclusions and coverage.'
where not exists (
  select 1 from public.change_log
   where description='Build 3.25 clean efficacy population views: official eligible/scorable checkpoints are separated from repair-pending and audit-only incomplete legacy rows.'
);
