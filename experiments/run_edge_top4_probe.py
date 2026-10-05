"""Experimental authenticated EDGE probe for selected delivery stocks.
Pulls live quote + 60 calendar days of daily candles from Upstox, computes
transparent technical inputs, then runs existing deterministic 5DR primitives.
This is NOT the canonical G5 stock-specific producer.
"""
import json, math, os, subprocess
from datetime import datetime, timedelta
from urllib.parse import quote, urlencode

from experiments.upstox_catalog import PublicInstrumentCatalog
from src.scoring import des5, directional_label
from src.market_trust import market_trust, trust_band
from src.probability import probabilities
from src.execution import execution_edge, tradeability

SYMBOLS = {
    "CGPOWER": {"symbol":"CGPOWER","catalyst_score":82},
    "REDINGTON": {"symbol":"REDINGTON","catalyst_score":80},
    "LLOYDSENGG": {"symbol":"LLOYDSENGG","catalyst_score":74},
    "VBL": {"symbol":"VBL","catalyst_score":70},
}

def clamp(x,a=-100,b=100): return max(a,min(b,x))
def sma(vals,n): return sum(vals[-n:])/n if len(vals)>=n else None

def rsi14(closes):
    if len(closes)<15: return None
    gains=[]; losses=[]
    for a,b in zip(closes[-15:-1],closes[-14:]):
        d=b-a; gains.append(max(d,0)); losses.append(max(-d,0))
    ag=sum(gains)/14; al=sum(losses)/14
    if al==0: return 100.0
    rs=ag/al
    return 100-(100/(1+rs))

def atr14(c):
    if len(c)<15: return None
    tr=[]
    prev=c[-15]["close"]
    for x in c[-14:]:
        tr.append(max(x["high"]-x["low"],abs(x["high"]-prev),abs(x["low"]-prev)))
        prev=x["close"]
    return sum(tr)/len(tr)

def hist(meta, token, to_date, from_date):
    key=quote(meta["instrument_key"],safe="")
    url=f"https://api.upstox.com/v3/historical-candle/{key}/days/1/{to_date}/{from_date}"
    p=subprocess.run(["curl","--fail-with-body","--silent","--show-error",
        "-H","Accept: application/json","-H",f"Authorization: Bearer {token}",url],
        text=True,capture_output=True,timeout=25)
    if p.returncode: raise RuntimeError(p.stderr[:300])
    raw=((json.loads(p.stdout).get("data") or {}).get("candles") or [])
    out=[]
    for z in raw:
        if not isinstance(z,list) or len(z)<6: continue
        out.append({"ts":z[0],"open":float(z[1]),"high":float(z[2]),"low":float(z[3]),"close":float(z[4]),"volume":float(z[5])})
    out.sort(key=lambda x:x["ts"])
    return out

def regime_for(ltp,s5,s10,s20,rsi,ret10):
    if s5 and s10 and s20 and ltp>s5>s10>s20 and (rsi or 50)>=55: return "TREND"
    if s5 and s10 and s20 and ltp<s5<s10<s20 and (rsi or 50)<=45: return "TREND"
    if abs(ret10)<4 and s20 and abs(ltp/s20-1)<0.04: return "RANGE"
    return "TRANSITION"

def main():
    token=os.environ["UPSTOX_ANALYTICS_TOKEN"].strip()
    catalog=PublicInstrumentCatalog().nse_instruments()["records"]
    resolved={}
    for app,h in SYMBOLS.items():
        m=[r for r in catalog if isinstance(r,dict) and r.get("exchange")=="NSE" and r.get("segment")=="NSE_EQ" and str(r.get("trading_symbol","")).upper()==h["symbol"]]
        if len(m)!=1: raise RuntimeError(f"resolution {app}: {len(m)}")
        resolved[app]=m[0]

    query=urlencode({"instrument_key":",".join(resolved[a]["instrument_key"] for a in SYMBOLS)})
    qurl="https://api.upstox.com/v3/market-quote/quotes?"+query
    p=subprocess.run(["curl","--fail-with-body","--silent","--show-error","-H","Accept: application/json","-H",f"Authorization: Bearer {token}",qurl],text=True,capture_output=True,timeout=25)
    if p.returncode: raise RuntimeError("batch quote failed")
    data=(json.loads(p.stdout).get("data") or {})
    bytoken={x.get("instrument_token"):x for x in data.values() if isinstance(x,dict)}
    qts=max(x.get("timestamp") for x in bytoken.values() if x.get("timestamp"))
    qdate=datetime.fromisoformat(qts.replace("Z","+00:00")).date()
    to_date=(qdate-timedelta(days=1)).isoformat()
    from_date=(qdate-timedelta(days=90)).isoformat()

    results=[]
    for app,h in SYMBOLS.items():
        meta=resolved[app]; q=bytoken[meta["instrument_key"]]
        ltp=float(q["last_price"]); candles=hist(meta,token,to_date,from_date)
        if len(candles)<25: raise RuntimeError(f"insufficient daily candles {app}")
        closes=[x["close"] for x in candles]
        vols=[x["volume"] for x in candles]
        s5,s10,s20=sma(closes,5),sma(closes,10),sma(closes,20)
        a14=atr14(candles); r14=rsi14(closes)
        ret5=(ltp/closes[-5]-1)*100
        ret10=(ltp/closes[-10]-1)*100
        ret20=(ltp/closes[-20]-1)*100
        hi20=max(x["high"] for x in candles[-20:]); lo20=min(x["low"] for x in candles[-20:])
        avgvol20=sum(vols[-20:])/20
        curvol=float(q.get("volume") or 0); volratio=curvol/avgvol20 if avgvol20 else 0
        prev_close=closes[-1]; daychg=(ltp/prev_close-1)*100

        align=0
        if ltp>s20: align+=25
        else: align-=25
        if s5>s10>s20: align+=25
        elif s5<s10<s20: align-=25
        price=clamp(align+clamp(ret20*2.5,-30,30)+(20 if ltp>=0.98*hi20 else 0)+(-20 if ltp<=1.02*lo20 else 0))
        pvpo=clamp(clamp(daychg*8,-40,40)+clamp(ret5*4,-30,30)+clamp((volratio-1)*25*(1 if daychg>=0 else -1),-30,30))

        upvol=[]; downvol=[]
        for x0,x1 in zip(candles[-11:-1],candles[-10:]):
            (upvol if x1["close"]>=x0["close"] else downvol).append(x1["volume"])
        u=sum(upvol)/len(upvol) if upvol else avgvol20
        d=sum(downvol)/len(downvol) if downvol else avgvol20
        part=clamp((u/d-1)*55 + clamp((volratio-1)*20*(1 if daychg>=0 else -1),-30,30)) if d else 50
        catalyst=float(h["catalyst_score"])
        reg=regime_for(ltp,s5,s10,s20,r14,ret10)
        comps={"PRICE_STRUCTURE":round(price,2),"PVPO":round(pvpo,2),"PARTICIPATION":round(part,2),"MACRO_CATALYSTS":catalyst}
        dscore=des5(comps,reg)

        signs=[1 if v>10 else -1 if v<-10 else 0 for v in comps.values()]
        dsign=1 if dscore>14 else -1 if dscore<-14 else 0
        agree=sum(1 for x in signs if x==dsign and x!=0)
        mti={
            "price_confirmation":clamp(50+abs(price)*0.5,0,100),
            "pvpo_confirmation":clamp(50+abs(pvpo)*0.5,0,100),
            "participation_confirmation":clamp(50+abs(part)*0.5,0,100),
            "cross_engine_consistency":85 if agree>=3 else 70 if agree==2 else 55,
            "closing_confirmation":45,
            "evidence_freshness_completeness":95,
        }
        mt=market_trust(mti)
        probs=probabilities(dscore,mt,"NORMAL")

        stop=max(s10 if s10<ltp else ltp-1.15*a14, ltp-1.4*a14)
        if stop>=ltp: stop=ltp-1.15*a14
        target=max(hi20 if hi20>ltp else ltp+1.8*a14, ltp+1.5*a14)
        risk=max(ltp-stop,0.01); reward=max(target-ltp,0.01); rr=reward/risk
        liq=clamp(55+20*math.log10(max(avgvol20,1)/100000),35,95)
        horizon_fit=clamp(55+abs(dscore)*0.4,45,90)
        carry=75.0
        invalid=80.0 if s10 and s20 else 60.0
        exi={"rr_score":clamp(rr/2.5*100,0,100),"premium_iv_theta_score":carry,"strike_expiry_fit_score":horizon_fit,"liquidity_spread_score":liq,"entry_invalidation_score":invalid}
        ee=execution_edge(exi)
        trade,block=tradeability(data_adequate=True,market_trust=mt,des5=dscore,execution_edge=ee,event_kill_switch=False,expected_rr=rr)

        # Non-canonical provisional D:D+4 zones from ATR + score drift.
        zones=[]
        drift=(dscore/100.0)*0.22*a14
        for k in range(5):
            center=ltp+drift*(k+1)
            band=a14*0.55*math.sqrt(k+1)
            zones.append({"slot":"D" if k==0 else f"D+{k}","low":round(center-band,2),"mid":round(center,2),"high":round(center+band,2)})

        results.append({
            "symbol":app,"ltp":ltp,"prev_close":prev_close,"day_change_pct":round(daychg,2),
            "regime":reg,"sma5":round(s5,2),"sma10":round(s10,2),"sma20":round(s20,2),
            "atr14":round(a14,2),"rsi14":round(r14,1),"ret5_pct":round(ret5,2),"ret10_pct":round(ret10,2),"ret20_pct":round(ret20,2),
            "high20":round(hi20,2),"low20":round(lo20,2),"volume_ratio_partial_day":round(volratio,2),
            "component_scores":comps,"des5":dscore,"directional_label":directional_label(dscore),
            "market_trust":mt,"market_trust_band":trust_band(mt),"probabilities":probs,
            "execution_edge_delivery_adapted":ee,"expected_rr":round(rr,2),"tradeable_delivery_adapted":trade,"blockers":block,
            "provisional_stop":round(stop,2),"provisional_target":round(target,2),"d_to_d4_zones_noncanonical":zones
        })
    print("EDGE_TOP4_RESULT="+json.dumps({"mode":"EXPERIMENTAL_DELIVERY_ADAPTED_EDGE","canonical_g5":False,"quote_timestamp":qts,"results":results},separators=(",",":"),sort_keys=True))

if __name__=="__main__":
    main()
