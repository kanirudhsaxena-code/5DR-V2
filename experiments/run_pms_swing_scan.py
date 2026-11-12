import json, os, subprocess, math
from datetime import datetime, date
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import quote, urlencode
from experiments.upstox_catalog import PublicInstrumentCatalog

SYMS=["BSE","HCLTECH","ICICIBANK","PNB","VBL","AUROPHARMA","BOSCHLTD","HINDCOPPER","INDHOTEL","IPCALAB","LTTS","MEESHO","SONACOMS","ACUTAAS","EBGNG","JAYNECOIND","JSWCEMENT","KROSS","LLOYDSENGG","NELCO","NEWGEN","OMNI","PINELABS","SOUTHBANK","STLTECH","TATAELXSI"]
TODAY=date(2026,11,12)

def curlj(url,tok):
    p=subprocess.run(["curl","--fail-with-body","--silent","--show-error","-H","Accept: application/json","-H",f"Authorization: Bearer {tok}",url],text=True,capture_output=True,timeout=35)
    if p.returncode: raise RuntimeError(p.stderr[:300])
    return json.loads(p.stdout)

def candles(url,tok):
    d=curlj(url,tok)
    cs=((d.get("data") or {}).get("candles") or [])
    out=[]
    for c in cs:
        if isinstance(c,list) and len(c)>=6:
            out.append({"ts":str(c[0]),"o":float(c[1]),"h":float(c[2]),"l":float(c[3]),"c":float(c[4]),"v":float(c[5]),"oi":float(c[6]) if len(c)>6 and c[6] is not None else 0.0})
    out.sort(key=lambda x:x["ts"])
    return out

def ema(vals,n):
    if not vals:return None
    a=2/(n+1); e=vals[0]
    for x in vals[1:]: e=a*x+(1-a)*e
    return e

def rsi(vals,n=14):
    if len(vals)<n+1:return None
    gains=[]; losses=[]
    for a,b in zip(vals[-n-1:-1],vals[-n:]):
        d=b-a; gains.append(max(d,0)); losses.append(max(-d,0))
    ag=sum(gains)/n; al=sum(losses)/n
    if al==0:return 100.0
    rs=ag/al
    return 100-100/(1+rs)

def atr(cs,n=14):
    if len(cs)<n+1:return None
    trs=[]
    for i in range(1,len(cs)):
        tr=max(cs[i]["h"]-cs[i]["l"],abs(cs[i]["h"]-cs[i-1]["c"]),abs(cs[i]["l"]-cs[i-1]["c"]))
        trs.append(tr)
    return sum(trs[-n:])/n

def latest_bull_fvg(cs,look=12):
    # 3-candle imbalance: candle i low > candle i-2 high. Return latest still-not-fully-filled zone.
    for i in range(len(cs)-1,max(1,len(cs)-look)-1,-1):
        lo=cs[i]["l"]; hi2=cs[i-2]["h"]
        if lo>hi2:
            zone=(hi2,lo)
            after=cs[i+1:]
            filled=any(x["l"]<=zone[0] for x in after)
            if not filled:return zone
    return None

def latest_bear_fvg(cs,look=12):
    for i in range(len(cs)-1,max(1,len(cs)-look)-1,-1):
        hi=cs[i]["h"]; lo2=cs[i-2]["l"]
        if hi<lo2:
            zone=(hi,lo2)
            after=cs[i+1:]
            filled=any(x["h"]>=zone[1] for x in after)
            if not filled:return zone
    return None

def resolve_cash(records,s):
    m=[r for r in records if isinstance(r,dict) and r.get("exchange")=="NSE" and r.get("segment")=="NSE_EQ" and str(r.get("trading_symbol","")).upper()==s]
    if not m: raise RuntimeError("cash resolve "+s)
    return m[0]

def expiry_val(x):
    e=x.get("expiry")
    try:
        if isinstance(e,(int,float)):
            return datetime.fromtimestamp(e/1000).date() if e>1e11 else datetime.fromtimestamp(e).date()
        return datetime.fromisoformat(str(e)[:10]).date()
    except: return date(2099,1,1)

def resolve_future(records,s):
    c=[]
    for r in records:
        if not isinstance(r,dict): continue
        if r.get("exchange")!="NSE" or r.get("segment")!="NSE_FO": continue
        typ=str(r.get("instrument_type","")).upper()
        ts=str(r.get("trading_symbol","")).upper()
        nm=str(r.get("name","")).upper()
        if "FUT" not in typ and "FUT" not in ts: continue
        exp=expiry_val(r)
        if exp<TODAY: continue
        # underlying key/name matching first, ticker prefix second
        if ts.startswith(s) or nm==s or (" "+s+" " in " "+ts+" "):
            c.append((exp,r))
    if not c:return None
    c.sort(key=lambda z:z[0])
    return c[0][1]

def scan_one(s,cash,fut,tok):
    key=quote(cash["instrument_key"],safe="")
    dcs=candles(f"https://api.upstox.com/v3/historical-candle/{key}/days/1/2026-11-11/2026-08-01",tok)
    ics=candles(f"https://api.upstox.com/v3/historical-candle/intraday/{key}/minutes/15",tok)
    if len(dcs)<35: raise RuntimeError(f"{s} daily candles {len(dcs)}")
    closes=[x["c"] for x in dcs]
    last=dcs[-1]; prev=dcs[-2]
    e20=ema(closes[-40:],20); e50=ema(closes[-60:],50); rr=rsi(closes,14); aa=atr(dcs,14)
    v20=sum(x["v"] for x in dcs[-21:-1])/20
    vr=last["v"]/v20 if v20 else None
    hi20=max(x["h"] for x in dcs[-20:]); lo20=min(x["l"] for x in dcs[-20:])
    # Daily bullish/bearish liquidity sweep in latest 3 sessions
    bull_sweep=False; bear_sweep=False; sweep_desc=None
    for idx in range(max(5,len(dcs)-3),len(dcs)):
        prior=dcs[max(0,idx-6):idx]
        if len(prior)>=5:
            pl=min(x["l"] for x in prior); ph=max(x["h"] for x in prior)
            x=dcs[idx]
            if x["l"]<pl and x["c"]>pl and x["c"]>x["o"]:
                bull_sweep=True; sweep_desc=f"bull sweep {x['ts'][:10]}"
            if x["h"]>ph and x["c"]<ph and x["c"]<x["o"]:
                bear_sweep=True; sweep_desc=f"bear sweep {x['ts'][:10]}"
    bf=latest_bull_fvg(dcs); sf=latest_bear_fvg(dcs)
    # Intraday stats
    vwap=None; intraday_above_vwap=None; last15_break=None; intraday_vol_expand=None
    if ics:
        tv=sum(x["v"] for x in ics); pv=sum(((x["h"]+x["l"]+x["c"])/3)*x["v"] for x in ics)
        vwap=pv/tv if tv else None
        intraday_above_vwap=(ics[-1]["c"]>vwap) if vwap else None
        if len(ics)>=2:last15_break=ics[-1]["c"]>ics[-2]["h"]
        if len(ics)>=6:
            av=sum(x["v"] for x in ics[-6:-1])/5
            intraday_vol_expand=ics[-1]["v"]>1.25*av if av else None
    # Live cash quote
    qd=curlj("https://api.upstox.com/v3/market-quote/quotes?"+urlencode({"instrument_key":cash["instrument_key"]}),tok).get("data") or {}
    qo=next(iter(qd.values())) if qd else {}
    ltp=float(qo.get("last_price",ics[-1]["c"] if ics else last["c"]))
    # Future OI
    oi_state=None; oi_chg=None; fut_sym=None
    if fut:
        fk=fut["instrument_key"]; fut_sym=fut.get("trading_symbol")
        fq=curlj("https://api.upstox.com/v3/market-quote/quotes?"+urlencode({"instrument_key":fk}),tok).get("data") or {}
        fqo=next(iter(fq.values())) if fq else {}
        cur_oi=float(fqo.get("oi") or 0)
        fkey=quote(fk,safe="")
        fcs=candles(f"https://api.upstox.com/v3/historical-candle/{fkey}/days/1/2026-11-11/2026-11-10",tok)
        if fcs and cur_oi and fcs[-1]["oi"]:
            oi_chg=(cur_oi/fcs[-1]["oi"]-1)*100
            fp=float(fqo.get("last_price") or fcs[-1]["c"])
            pchg=(fp/fcs[-1]["c"]-1)*100
            if pchg>0 and oi_chg>0:oi_state="LONG_BUILDUP"
            elif pchg<0 and oi_chg>0:oi_state="SHORT_BUILDUP"
            elif pchg>0 and oi_chg<0:oi_state="SHORT_COVERING"
            elif pchg<0 and oi_chg<0:oi_state="LONG_UNWINDING"
    score=0; notes=[]
    if ltp>e20:score+=14;notes.append("above EMA20")
    else:score-=8
    if e20>e50:score+=10;notes.append("EMA20>EMA50")
    else:score-=4
    if rr is not None:
        if 55<=rr<=72:score+=10;notes.append("RSI constructive")
        elif rr>78:score-=8;notes.append("RSI stretched")
        elif rr<45:score-=6
    if vr is not None:
        if vr>=1.5:score+=10;notes.append("strong daily volume")
        elif vr>=1.1:score+=5
    if bull_sweep:score+=12;notes.append("bull liquidity sweep")
    if bear_sweep:score-=12;notes.append("bear liquidity sweep")
    if bf:
        # support if current above zone and within 2 ATR
        if ltp>=bf[1] and aa and (ltp-bf[1])<=2*aa:score+=8;notes.append("bull FVG support")
    if sf and ltp<sf[1]:score-=5;notes.append("bear FVG overhead")
    if intraday_above_vwap is True:score+=8;notes.append("above intraday VWAP")
    elif intraday_above_vwap is False:score-=5
    if last15_break:score+=5
    if intraday_vol_expand:score+=4
    if oi_state=="LONG_BUILDUP":score+=12;notes.append("futures long buildup")
    elif oi_state=="SHORT_COVERING":score+=6;notes.append("futures short covering")
    elif oi_state=="SHORT_BUILDUP":score-=10;notes.append("futures short buildup")
    elif oi_state=="LONG_UNWINDING":score-=6;notes.append("futures long unwinding")
    dist_high=(ltp/hi20-1)*100
    if -3<=dist_high<=1:score+=5
    return {"symbol":s,"score":score,"ltp":ltp,"ema20":e20,"ema50":e50,"rsi14":rr,"atr14":aa,"vol_ratio":vr,"high20":hi20,"low20":lo20,"dist20high_pct":dist_high,"bull_sweep":bull_sweep,"bear_sweep":bear_sweep,"sweep":sweep_desc,"bull_fvg":bf,"bear_fvg":sf,"intraday_vwap":vwap,"above_vwap":intraday_above_vwap,"last15_break":last15_break,"intraday_vol_expand":intraday_vol_expand,"future":fut_sym,"oi_change_pct":oi_chg,"oi_state":oi_state,"notes":notes}

def main():
    tok=os.environ["UPSTOX_ANALYTICS_TOKEN"].strip()
    records=PublicInstrumentCatalog().nse_instruments()["records"]
    cash={s:resolve_cash(records,s) for s in SYMS}
    fut={s:resolve_future(records,s) for s in SYMS}
    results=[]; errors=[]
    for s in SYMS:
        try: results.append(scan_one(s,cash[s],fut[s],tok))
        except Exception as e: errors.append({"symbol":s,"error":str(e)})
    results.sort(key=lambda x:x["score"],reverse=True)
    print("SWING_SCAN_RESULT="+json.dumps({"timestamp":datetime.now().isoformat(),"results":results,"errors":errors},separators=(",",":"),sort_keys=True))

if __name__=="__main__": main()
