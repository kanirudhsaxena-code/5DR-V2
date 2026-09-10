"""Execution Edge and tradeability gate for 5DR V2."""
WEIGHTS={'rr_score':30.0,'premium_iv_theta_score':25.0,'strike_expiry_fit_score':15.0,'liquidity_spread_score':15.0,'entry_invalidation_score':15.0}
def execution_edge(values):
    total=0.0
    for k,w in WEIGHTS.items():
        v=float(values[k]);
        if v<0 or v>100: raise ValueError('execution inputs must be 0..100')
        total+=(w/100.0)*v
    return round(total,3)
def tradeability(*,data_adequate,market_trust,des5,execution_edge,event_kill_switch,expected_rr):
    f=[]
    if not data_adequate:f.append('DATA_INADEQUATE')
    if market_trust<50:f.append('MARKET_TRUST_LT_50')
    if abs(des5)<30:f.append('DES5_LT_30')
    if execution_edge<65:f.append('EXECUTION_EDGE_LT_65')
    if event_kill_switch:f.append('EVENT_KILL_SWITCH')
    if expected_rr<2.0:f.append('RR_LT_2')
    return (len(f)==0,f)
