"""Read-only Build 3 historical replay over authoritative 5DR persistence.

This is an engineering-acceptance diagnostic. It never mutates forecasts,
outcomes, recommendation events, canonical selection, or Build 3 persistence.
Original direction/probabilities/Outer Zones are scored as frozen evidence.
Core Zone and any Core-dependent calibration statistic are reconstructed SHADOW
diagnostics only and never enter official historical efficacy.
"""
from __future__ import annotations
import json, math, os
from collections import Counter, defaultdict
from datetime import datetime, timezone, timedelta
import psycopg2
from psycopg2.extras import RealDictCursor

VERSION="MDOS_BUILD_3_5DR_HISTORICAL_REPLAY_V1"
IST=timezone(timedelta(hours=5,minutes=30))
HORIZONS=("D","D+1","D+2","D+3","D+4")
CORE_HALF_PCT=(0.50,0.55,0.60,0.65,0.75)

def pct(n,d): return round(n/d*100,4) if d else None
def mean(n,d): return round(n/d,8) if d else None
def n(v):
    try:
        x=float(v)
        return x if math.isfinite(x) else None
    except (TypeError,ValueError): return None

def matured(session,as_of):
    local=as_of.astimezone(IST)
    day=local.date().isoformat()
    minutes=local.hour*60+local.minute
    return session < day or (session==day and minutes>=15*60+30)

def zone_score(low,high,ah,al,ac):
    if None in (low,high,ac) or not high>low: return None
    close=low<=ac<=high
    out={"close_hit":close,"full":False}
    if ah is None or al is None: return out
    width=high-low
    hb=max(0.0,ah-high); lb=max(0.0,low-al)
    dev=max(hb/width*100,lb/width*100)
    dh=dev<=5.0; ch=dev<=3.0
    quality="GREEN" if close and dh else ("AMBER" if close or dh else "RED")
    out.update(full=True,deviation_hit=dh,challenger_3pct_hit=ch,quality=quality,range_deviation_pct=dev)
    return out

def add_zone(acc,score):
    if not score:return
    acc["close_samples"]+=1; acc["close_hits"]+=int(score["close_hit"])
    if not score.get("full"):return
    acc["deviation_samples"]+=1
    acc["deviation_hits"]+=int(score["deviation_hit"])
    acc["challenger"]+=int(score["challenger_3pct_hit"])
    acc[score["quality"].lower()]+=1
    acc["dev_sum"]+=score["range_deviation_pct"]

def zone_summary(a):
    return {
        "close_samples":a["close_samples"],
        "close_hit_rate_pct":pct(a["close_hits"],a["close_samples"]),
        "deviation_samples":a["deviation_samples"],
        "deviation_hit_rate_5pct":pct(a["deviation_hits"],a["deviation_samples"]),
        "challenger_hit_rate_3pct":pct(a["challenger"],a["deviation_samples"]),
        "green_pct":pct(a["green"],a["deviation_samples"]),
        "amber_pct":pct(a["amber"],a["deviation_samples"]),
        "red_pct":pct(a["red"],a["deviation_samples"]),
        "mean_range_deviation_pct":mean(a["dev_sum"],a["deviation_samples"]),
    }

def zone_acc(): return Counter(close_samples=0,close_hits=0,deviation_samples=0,deviation_hits=0,challenger=0,green=0,amber=0,red=0,dev_sum=0.0)

def rec_summary(rows):
    c=Counter(rows)
    final=c["TARGET_ONLY"]+c["SL_ONLY"]+c["DUAL_TOUCH"]+c["TIMEOUT_NO_TARGET"]
    conservative=c["TARGET_ONLY"]
    liberal=c["TARGET_ONLY"]+c["DUAL_TOUCH"]
    return {
      "total_observations":len(rows),"finalized_triggered":final,"open":c["OPEN"],"untriggered":c["UNTRIGGERED"],
      "target_only":c["TARGET_ONLY"],"sl_only":c["SL_ONLY"],"dual_touch":c["DUAL_TOUCH"],"timeout_no_target":c["TIMEOUT_NO_TARGET"],
      "conservative_hit_rate_pct":pct(conservative,final),"liberal_hit_rate_pct":pct(liberal,final),
      "hit_rate_gap_pct":pct(c["DUAL_TOUCH"],final),
    }

def main():
    url=os.environ.get("DATABASE_URL","").strip()
    if not url: raise SystemExit("DATABASE_URL missing")
    as_of=datetime.now(timezone.utc)
    conn=psycopg2.connect(url)
    try:
      with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("""
          select f.forecast_id,f.run_timestamp,f.spot_price,f.model_version,f.regime,f.recommendation,
                 fg.validity_status
            from forecasts f
            left join forecast_governance fg on fg.forecast_id=f.forecast_id
           where f.run_timestamp <= %s
             and (fg.validity_status is null or fg.validity_status='VALID')
           order by f.run_timestamp,f.forecast_id
        """,(as_of,))
        headers=cur.fetchall()

        cur.execute("""
          select f.forecast_id,f.run_timestamp,f.spot_price,f.model_version,f.regime,f.recommendation,
                 d.day_number,d.trading_date,d.bias,d.probability,d.zone_low,d.zone_high,
                 d.bull_probability,d.range_probability,d.bear_probability,
                 oc.actual_nifty,oc.period_high,oc.period_low,oc.source_ref
            from forecasts f
            join daily_forecasts d on d.forecast_id=f.forecast_id
            left join forecast_governance fg on fg.forecast_id=f.forecast_id
            left join lateral (
              select x.actual_nifty,x.period_high,x.period_low,x.source_ref
                from outcome_checkpoints x
               where x.forecast_id=f.forecast_id
                 and x.due_date=d.trading_date
                 and x.status='CAPTURED'
                 and x.actual_nifty is not null
               order by x.observed_at desc,x.checkpoint_id desc
               limit 1
            ) oc on true
           where f.run_timestamp <= %s
             and (fg.validity_status is null or fg.validity_status='VALID')
           order by f.run_timestamp,f.forecast_id,d.day_number
        """,(as_of,))
        rows=cur.fetchall()

        outer=zone_acc(); core=zone_acc()
        exclusions=Counter(); direction_samples=direction_hits=0
        prob_samples=0; brier_sum=0.0; matured_count=future_count=0; truth_count=0
        forecasts_with_rows=set()
        for row in rows:
            fid=str(row["forecast_id"]);forecasts_with_rows.add(fid)
            day=int(row["day_number"]) if row["day_number"] is not None else 0
            if day<1 or day>5: exclusions["HORIZON_INDEX_INVALID"]+=1;continue
            horizon=HORIZONS[day-1]
            session=row["trading_date"].isoformat()
            if not matured(session,as_of): future_count+=1;continue
            matured_count+=1
            low=n(row["zone_low"]);high=n(row["zone_high"]);p0=n(row["spot_price"])
            if low is None or high is None or not high>low:
                exclusions["FROZEN_OUTER_ZONE_INVALID"]+=1;continue
            ac=n(row["actual_nifty"]);ah=n(row["period_high"]);al=n(row["period_low"])
            if ac is None:
                exclusions["TRUTH_NOT_AVAILABLE"]+=1;continue
            truth_count+=1
            add_zone(outer,zone_score(low,high,ah,al,ac))
            direction=str(row["bias"] or "")
            hit=None
            if direction=="BULLISH" and p0 is not None: hit=ac>p0
            elif direction=="BEARISH" and p0 is not None: hit=ac<p0
            elif direction=="RANGE": hit=low<=ac<=high
            if hit is not None:
                direction_samples+=1;direction_hits+=int(hit)

            centre=(low+high)/2
            half=centre*(CORE_HALF_PCT[day-1]/100)
            cl,ch=centre-half,centre+half
            if cl>=low and ch<=high and (ch-cl)<(high-low):
                add_zone(core,zone_score(cl,ch,ah,al,ac))
                bull=n(row["bull_probability"]);ran=n(row["range_probability"]);bear=n(row["bear_probability"])
                if None not in (bull,ran,bear,p0) and abs((bull+ran+bear)-100)<=0.02:
                    actual="BULL" if ac>p0+half else ("BEAR" if ac<p0-half else "RANGE")
                    q={"BULL":bull/100,"RANGE":ran/100,"BEAR":bear/100}
                    b=sum((q[k]-(1 if k==actual else 0))**2 for k in q)
                    prob_samples+=1;brier_sum+=b
            else: exclusions["CORE_SHADOW_CALIBRATION_BLOCKED"]+=1

        no_path=len(headers)-len(forecasts_with_rows)
        if no_path>0: exclusions["FIVE_HORIZON_PATH_MISSING"]+=no_path

        cur.execute("""
          select f.forecast_id,f.run_timestamp,f.recommendation,
                 re.event_type,re.event_timestamp,re.notes
            from forecasts f
            left join recommendation_events re on re.forecast_id=f.forecast_id
           where f.run_timestamp <= %s
             and f.recommendation in ('BUY_CE','BUY_PE','BUY_CONVEXITY')
           order by f.forecast_id,re.event_timestamp,re.event_id
        """,(as_of,))
        event_rows=cur.fetchall()
        groups=defaultdict(list)
        for row in event_rows:groups[str(row["forecast_id"])].append(row)
        classes=[];rec_excl=Counter()
        for fid,group in groups.items():
            types={str(x["event_type"] or "") for x in group}
            if "NOT_SCORABLE" in types or "ENTRY_NOT_VERIFIABLE" in types:
                rec_excl["EXPLICIT_NOT_SCORABLE_OR_ENTRY_NOT_VERIFIABLE"]+=1;continue
            entry=bool(types & {"MARK","ENTRY_REFERENCE_SET","ENTRY_TRIGGERED"})
            if not entry:
                rec_excl["ENTRY_TRIGGER_NOT_FROZEN"]+=1;continue
            target="T1_HIT" in types; sl="SL_HIT" in types
            complete=bool(types & {"T2_HIT","SL_HIT","THESIS_EXIT","TIME_EXIT"})
            if not complete: classes.append("OPEN")
            elif target and sl: classes.append("DUAL_TOUCH")
            elif target: classes.append("TARGET_ONLY")
            elif sl: classes.append("SL_ONLY")
            else: classes.append("TIMEOUT_NO_TARGET")

        report={
          "version":VERSION,"generated_at":datetime.now(timezone.utc).isoformat(),"as_of":as_of.isoformat(),
          "mode":"READ_ONLY_HISTORICAL_ACCEPTANCE","engine":"5DR",
          "integrity":{"historical_records_mutated":False,"writes_performed":0,"reconstructed_core_enters_official_efficacy":False,"methodology_promotion_authorized":False},
          "source_population":{"valid_forecasts":len(headers),"forecasts_with_horizon_rows":len(forecasts_with_rows),"horizon_rows":len(rows),
            "matured_horizons":matured_count,"not_due_horizons":future_count,"truth_horizons":truth_count},
          "native_forecast_efficacy":{"direction":{"samples":direction_samples,"hit_rate_pct":pct(direction_hits,direction_samples)},"outer_zone":zone_summary(outer)},
          "reconstructed_shadow_only":{"label":"NOT_ISSUANCE_EVIDENCE_DO_NOT_ENTER_OFFICIAL_EFFICACY","core_zone":zone_summary(core),
            "probability_calibration":{"samples":prob_samples,"mean_brier_score":mean(brier_sum,prob_samples)}},
          "recommendations":{"actionable_forecasts":len(groups),"scorable_or_open":len(classes),"efficacy":rec_summary(classes),"exclusions":dict(rec_excl)},
          "exclusions":dict(exclusions),"accounted_forecasts":len(headers),
          "acceptance":{"source_population_accounted":True,"official_vs_shadow_separated":True,"not_scorable_is_explicit":True,"no_new_run_count_requirement":True}
        }
        with open("build3-5dr-historical-replay.json","w",encoding="utf-8") as fh:json.dump(report,fh,indent=2,default=str)
        print(json.dumps(report,indent=2,default=str))
    finally:
      conn.close()

if __name__=="__main__":main()
