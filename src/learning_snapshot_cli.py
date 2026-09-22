"""Build the immutable daily 5DR Learning Lab handoff.

Read-only against the 5DR database. It never mutates forecasts, efficacy,
Learning Lab research tables, production configuration, or promotion decisions.
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path
from typing import Any

from src.learning_observations import efficacy_observation, recommendation_observation
from src.learning_snapshot import LearningRunContext, build_daily_snapshot, build_observation_envelope


def _dict_rows(cur) -> list[dict[str, Any]]:
    cols=[item[0] for item in cur.description]
    return [dict(zip(cols,row)) for row in cur.fetchall()]


def _iso(value: Any) -> str:
    if hasattr(value,"isoformat"):
        return value.isoformat()
    return str(value)


def main() -> int:
    db_url=os.environ.get("DATABASE_URL","").strip()
    if not db_url:
        print(json.dumps({"status":"BLOCKED_CONFIGURATION","diagnostic_code":"DATABASE_URL_MISSING"}))
        return 2
    import psycopg2

    now=datetime.now(timezone.utc)
    handoff_path=Path(os.environ.get("LEARNING_HANDOFF_PATH","5dr-learning-lab-handoff.json"))
    conn=psycopg2.connect(db_url)
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT f.forecast_id,f.run_id,fg.target_trading_date,fg.run_class,fg.validity_status,
                       CASE WHEN cs.selected_forecast_id=f.forecast_id THEN 'CANONICAL' ELSE 'DIAGNOSTIC' END AS run_role,
                       (cs.selected_forecast_id=f.forecast_id) AS official_efficacy_eligible,
                       f.model_version,f.output_contract_version
                  FROM forecast_governance fg
                  JOIN forecasts f USING(forecast_id)
                  LEFT JOIN canonical_selections cs
                    ON cs.target_trading_date=fg.target_trading_date
                   AND cs.selection_status='SELECTED'
                 WHERE fg.target_trading_date=(CURRENT_TIMESTAMP AT TIME ZONE 'Asia/Kolkata')::date
                 ORDER BY f.run_timestamp,f.forecast_id
            """)
            runs=_dict_rows(cur)

            cur.execute("""
                SELECT e.evaluation_id,e.forecast_id,e.day_number,
                       'D+'||e.day_number::text AS checkpoint_type,
                       e.evaluation_status,e.directional_hit,e.directional_margin_points,
                       e.zone_hit,e.zone_error_points,e.source_ref,e.evaluated_at,
                       fg.target_trading_date,
                       CASE WHEN cs.selected_forecast_id=e.forecast_id THEN 'CANONICAL' ELSE 'DIAGNOSTIC' END AS run_role,
                       (cs.selected_forecast_id=e.forecast_id) AS official_efficacy_eligible
                  FROM v_latest_forecast_checkpoint_evaluation e
                  JOIN forecast_governance fg USING(forecast_id)
                  LEFT JOIN canonical_selections cs
                    ON cs.target_trading_date=fg.target_trading_date
                   AND cs.selection_status='SELECTED'
                 WHERE (e.evaluated_at AT TIME ZONE 'Asia/Kolkata')::date =
                       (CURRENT_TIMESTAMP AT TIME ZONE 'Asia/Kolkata')::date
                 ORDER BY e.evaluated_at,e.evaluation_id
            """)
            efficacy_rows=_dict_rows(cur)

            cur.execute("""
                SELECT l.forecast_id,l.recommendation,l.primary_outcome,
                       e.event_id AS terminal_event_id,e.event_timestamp,
                       e.pnl_pct AS final_pnl_pct,e.r_multiple,e.source_ref AS terminal_source_ref,
                       fg.target_trading_date,
                       CASE WHEN cs.selected_forecast_id=l.forecast_id THEN 'CANONICAL' ELSE 'DIAGNOSTIC' END AS run_role,
                       (cs.selected_forecast_id=l.forecast_id) AS official_efficacy_eligible
                  FROM v_recommendation_lifecycle_v222 l
                  JOIN v_latest_recommendation_event e USING(forecast_id)
                  JOIN forecast_governance fg USING(forecast_id)
                  LEFT JOIN canonical_selections cs
                    ON cs.target_trading_date=fg.target_trading_date
                   AND cs.selection_status='SELECTED'
                 WHERE l.primary_outcome IN ('WIN','LOSS')
                   AND (e.event_timestamp AT TIME ZONE 'Asia/Kolkata')::date =
                       (CURRENT_TIMESTAMP AT TIME ZONE 'Asia/Kolkata')::date
                 ORDER BY e.event_timestamp,l.forecast_id
            """)
            recommendation_rows=_dict_rows(cur)

            cur.execute("SELECT COUNT(*) FROM learning_hypotheses")
            hypothesis_count=int(cur.fetchone()[0] or 0)
            cur.execute("SELECT COUNT(*) FROM challenger_models")
            challenger_count=int(cur.fetchone()[0] or 0)
            cur.execute("""
                SELECT *
                  FROM v_learning_promotion_queue
                 WHERE decision IS NULL
                 ORDER BY created_at DESC
            """)
            pending_rows=_dict_rows(cur)

        observations=[]
        matured=[]
        for row in efficacy_rows:
            target=_iso(row["target_trading_date"])[:10]
            observed=_iso(row["evaluated_at"])
            matured.append({
                "scorable":row.get("evaluation_status")=="SCORABLE",
                "data_gap":row.get("evaluation_status")=="NOT_SCORABLE",
            })
            raw=efficacy_observation(row)
            if raw is None:
                continue
            observations.append(build_observation_envelope(
                raw,
                LearningRunContext(
                    run_id=str(row["forecast_id"]),
                    run_role=str(row["run_role"]),
                    official_efficacy_eligible=bool(row["official_efficacy_eligible"]),
                    target_trading_date=target,
                    source_ref=f"forecast:{row['forecast_id']}:evaluation:{row['evaluation_id']}",
                    observed_at=observed,
                    exclusion_reason=None if row["official_efficacy_eligible"] else "NON_CANONICAL",
                ),
            ))

        for row in recommendation_rows:
            target=_iso(row["target_trading_date"])[:10]
            observed=_iso(row["event_timestamp"])
            matured.append({
                "scorable":row.get("primary_outcome") in {"WIN","LOSS"},
                "data_gap":False,
            })
            raw=recommendation_observation(row)
            if raw is None:
                continue
            observations.append(build_observation_envelope(
                raw,
                LearningRunContext(
                    run_id=str(row["forecast_id"]),
                    run_role=str(row["run_role"]),
                    official_efficacy_eligible=bool(row["official_efficacy_eligible"]),
                    target_trading_date=target,
                    source_ref=f"forecast:{row['forecast_id']}:event:{row['terminal_event_id']}",
                    observed_at=observed,
                    exclusion_reason=None if row["official_efficacy_eligible"] else "NON_CANONICAL",
                ),
            ))

        normalized_runs=[
            {
                **row,
                "target_trading_date":_iso(row["target_trading_date"])[:10],
            }
            for row in runs
        ]
        candidates=[]
        for row in pending_rows:
            pid=str(row["promotion_proposal_id"])
            candidates.append({
                "candidate_id":f"5dr-promotion-{pid}",
                "engine":"5DR",
                "status":"PENDING_USER_APPROVAL",
                "proposal":{
                    "promotion_proposal_id":row["promotion_proposal_id"],
                    "challenger_id":row["challenger_id"],
                    "proposed_model_version":row["proposed_model_version"],
                    "known_weaknesses":row["known_weaknesses"],
                    "rollback_plan":row["rollback_plan"],
                    "implementation_plan":row["implementation_plan"],
                },
                "baseline_metrics":{"comparison":row["baseline_vs_challenger"]},
                "challenger_metrics":{},
                "validation_state":{
                    "eligibility_checks":row["eligibility_checks"],
                    "sample_breakdown":row["sample_breakdown"],
                },
                "production_change_allowed":False,
            })

        challengers=[{"status":"PENDING_USER_APPROVAL"} for _ in candidates]
        remaining=max(0,challenger_count-len(candidates))
        challengers.extend({"status":"VALIDATING"} for _ in range(remaining))
        hypotheses=[{"status":"HYPOTHESIS"} for _ in range(hypothesis_count)]
        snapshot=build_daily_snapshot(
            cycle_id=f"5DR-LL-{now.astimezone().date().isoformat()}",
            as_of=now.isoformat(),
            runs=normalized_runs,
            observations=observations,
            matured_outcomes=matured,
            hypotheses=hypotheses,
            challengers=challengers,
            methodology_versions={"forecast":"5DR_V2_1","recommendation_lifecycle":"5DR_V2_2_2"},
            source_lineage={
                "forecast_governance":"forecast_governance",
                "canonical_selection":"canonical_selections",
                "checkpoint_efficacy":"v_latest_forecast_checkpoint_evaluation",
                "recommendation_lifecycle":"v_recommendation_lifecycle_v222",
                "promotion_queue":"v_learning_promotion_queue",
            },
            data_quality_state="PASS",
        )
        handoff={
            "schema_version":"MDOS_LEARNING_LAB_HANDOFF_V1",
            "generated_at":now.isoformat().replace("+00:00","Z"),
            "engine":"5DR",
            "snapshot":snapshot,
            "observations":observations,
            "candidates":candidates,
            "methodology_changed":False,
            "production_change_allowed":False,
        }
        handoff_path.write_text(json.dumps(handoff,sort_keys=True,separators=(",",":"),default=str)+"\n",encoding="utf-8")
        print(json.dumps({
            "status":"COMPLETE",
            "engine":"5DR",
            "snapshot_id":snapshot["snapshot_id"],
            "runs_analyzed":snapshot["counts"]["runs_analyzed"],
            "observations":len(observations),
            "approval_required":snapshot["counts"]["approval_required"],
            "handoff_path":str(handoff_path),
            "methodology_changed":False,
            "production_change_allowed":False,
        },sort_keys=True))
        return 0
    finally:
        conn.close()


if __name__=="__main__":
    raise SystemExit(main())
