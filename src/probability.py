"""Provisional probability calibration for 5DR V2."""
def _cap(mt,event):
    if event=='EXTREME': return 55.0
    if event=='HIGH': return 62.0
    if mt>=80:return 80.0
    if mt>=65:return 72.0
    if mt>=50:return 65.0
    return 58.0
def probabilities(des5,market_trust,event_shock):
    s=abs(float(des5)); lead=38.0+0.48*s+0.08*(market_trust-50.0); base=55.0-0.45*s-0.08*(market_trust-50.0); opp=max(100.0-lead-base,8.0); lead=min(lead,_cap(market_trust,event_shock)); base=max(base,0.0)
    if -14<=des5<=14:
        r=min(max(base,lead),_cap(market_trust,event_shock)); rem=100.0-r; return {'BULL':round(rem/2,3),'RANGE':round(r,3),'BEAR':round(rem/2,3)}
    t=lead+base+opp; lead,base,opp=[100.0*x/t for x in (lead,base,opp)]
    bull,bear=(lead,opp) if des5>14 else (opp,lead)
    return {'BULL':round(bull,3),'RANGE':round(base,3),'BEAR':round(bear,3)}
