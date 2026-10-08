#!/usr/bin/env python3
import json, os
from collections import Counter, defaultdict
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
import psycopg2

IST=ZoneInfo("Asia/Kolkata")
now=datetime.now(timezone.utc)
local=now.astimezone(IST)
today=local.date()
clock=local.time().replace(tzinfo=None)

conn=psycopg2.connect(os.environ["DATABASE_URL"])
conn.set_session(readonly=True, autocommit=False)
try:
    with conn.cursor() as cur:
        cur.execute("select current_database(), current_schema()")
        database_name,schema_name=cur.fetchone()

        cur.execute("""
          with selected as (
            select cs.target_trading_date, cs.selected_forecast_id as forecast_id
              from canonical_selections cs
             where cs.selection_status='SELECTED'
               and cs.selected_forecast_id is not null
          ),
          counts as (
            select s.forecast_id,
                   (select count(*) from daily_forecasts df where df.forecast_id=s.forecast_id) as daily_count,
                   (select count(*) from outcome_checkpoints oc
                     where oc.forecast_id=s.forecast_id
                       and oc.checkpoint_type in ('D+1','D+2','D+3','D+4','D+5')) as checkpoint_count
              from selected s
          )
          select s.target_trading_date,s.forecast_id,c.daily_count,c.checkpoint_count,
                 coalesce(v.completeness_status,'UNKNOWN') as output_completeness,
                 f.model_version,f.output_contract_version
            from selected s
            join counts c using(forecast_id)
            join forecasts f using(forecast_id)
            left join v_forecast_output_completeness v using(forecast_id)
           order by s.target_trading_date,s.forecast_id
        """)
        forecast_rows=cur.fetchall()

        cur.execute("""
          with selected as (
            select cs.target_trading_date, cs.selected_forecast_id as forecast_id
              from canonical_selections cs
             where cs.selection_status='SELECTED'
               and cs.selected_forecast_id is not null
          ),
          counts as (
            select s.forecast_id,
                   (select count(*) from daily_forecasts df where df.forecast_id=s.forecast_id) as daily_count,
                   (select count(*) from outcome_checkpoints oc2
                     where oc2.forecast_id=s.forecast_id
                       and oc2.checkpoint_type in ('D+1','D+2','D+3','D+4','D+5')) as checkpoint_count
              from selected s
          )
          select s.target_trading_date,oc.forecast_id,oc.checkpoint_type,oc.due_date,oc.status,
                 c.daily_count,c.checkpoint_count,
                 coalesce(v.completeness_status,'UNKNOWN') as output_completeness,
                 e.evaluation_id,e.evaluation_status,e.source_ref,e.notes,e.evaluated_at
            from selected s
            join outcome_checkpoints oc
              on oc.forecast_id=s.forecast_id
             and oc.checkpoint_type in ('D+1','D+2','D+3','D+4','D+5')
            join counts c on c.forecast_id=s.forecast_id
            left join v_forecast_output_completeness v on v.forecast_id=s.forecast_id
            left join v_latest_forecast_checkpoint_evaluation e
              on e.forecast_id=oc.forecast_id
             and e.day_number=cast(substring(oc.checkpoint_type from 3) as integer)
           order by s.target_trading_date,oc.forecast_id,oc.checkpoint_type
        """)
        checkpoint_rows=cur.fetchall()

        cur.execute("""
          select
            (select count(*) from forecasts) as forecasts,
            (select count(*) from canonical_selections) as canonical_selections,
            (select count(*) from daily_forecasts) as daily_forecasts,
            (select count(*) from outcome_checkpoints) as outcome_checkpoints,
            (select count(*) from forecast_checkpoint_evaluations) as checkpoint_evaluations,
            (select count(*) from assessment_snapshots) as assessment_snapshots
        """)
        counts=cur.fetchone()
finally:
    conn.rollback()
    conn.close()

def matured(due_date):
    if due_date is None:
        return False
    return due_date < today or (due_date == today and clock >= datetime.strptime("15:40","%H:%M").time())

forecast_inventory=[]
for target_date,forecast_id,daily_count,checkpoint_count,complete,model_version,output_version in forecast_rows:
    if int(daily_count or 0) < 5 or int(checkpoint_count or 0) < 5 or complete != "COMPLETE":
        classification="AUDIT_ONLY_INCOMPLETE"
    else:
        classification="CANONICAL_COMPLETE"
    forecast_inventory.append({
        "target_trading_date":target_date.isoformat(),
        "forecast_id":forecast_id,
        "daily_count":int(daily_count or 0),
        "checkpoint_count":int(checkpoint_count or 0),
        "output_completeness":complete,
        "model_version":model_version,
        "output_contract_version":output_version,
        "classification":classification,
    })

checkpoints=[]
classes=Counter()
by_horizon=defaultdict(Counter)
for row in checkpoint_rows:
    (target_date,forecast_id,checkpoint_type,due_date,status,daily_count,checkpoint_count,
     complete,evaluation_id,evaluation_status,source_ref,notes,evaluated_at)=row
    is_matured=matured(due_date)
    if not is_matured:
        classification="NOT_DUE"
    elif int(daily_count or 0) < 5 or int(checkpoint_count or 0) < 5 or complete != "COMPLETE":
        classification="AUDIT_ONLY_INCOMPLETE"
    elif evaluation_status == "SCORABLE":
        classification="OFFICIAL_SCORABLE"
    elif status == "DUE" or evaluation_status is None:
        classification="REPAIR_PENDING"
    else:
        classification="AUDIT_ONLY_INCOMPLETE"
    classes[classification]+=1
    by_horizon[checkpoint_type][classification]+=1
    checkpoints.append({
        "target_trading_date":target_date.isoformat(),
        "forecast_id":forecast_id,
        "checkpoint_type":checkpoint_type,
        "due_date":due_date.isoformat() if due_date else None,
        "checkpoint_status":status,
        "matured":is_matured,
        "daily_count":int(daily_count or 0),
        "checkpoint_count":int(checkpoint_count or 0),
        "output_completeness":complete,
        "evaluation_id":evaluation_id,
        "evaluation_status":evaluation_status,
        "evaluation_source_ref":source_ref,
        "evaluation_notes":notes,
        "evaluated_at":evaluated_at.isoformat() if evaluated_at else None,
        "classification":classification,
    })

matured_total=sum(v for k,v in classes.items() if k!="NOT_DUE")
official=int(classes["OFFICIAL_SCORABLE"])
report={
    "version":"MDOS_BUILD_3_25_5DR_DATA_AUDIT_V1",
    "generated_at":now.isoformat().replace("+00:00","Z"),
    "read_only":True,
    "database":{"name":database_name,"schema":schema_name},
    "table_counts":{
        "forecasts":int(counts[0] or 0),
        "canonical_selections":int(counts[1] or 0),
        "daily_forecasts":int(counts[2] or 0),
        "outcome_checkpoints":int(counts[3] or 0),
        "checkpoint_evaluations":int(counts[4] or 0),
        "assessment_snapshots":int(counts[5] or 0),
    },
    "forecast_inventory":forecast_inventory,
    "checkpoint_summary":{
        "matured_total":matured_total,
        "official_scorable":official,
        "official_coverage_pct":round(100.0*official/matured_total,2) if matured_total else None,
        "classification_counts":dict(classes),
        "by_horizon":{k:dict(v) for k,v in sorted(by_horizon.items())},
    },
    "checkpoints":checkpoints,
}
print(json.dumps(report,indent=2,sort_keys=True))
