"""Market Trust calculation for 5DR V2."""
WEIGHTS={'price_confirmation':25.0,'pvpo_confirmation':25.0,'participation_confirmation':15.0,'cross_engine_consistency':15.0,'closing_confirmation':10.0,'evidence_freshness_completeness':10.0}
def market_trust(values):
    total=0.0
    for k,w in WEIGHTS.items():
        v=float(values[k])
        if v<0 or v>100: raise ValueError('Market Trust inputs must be 0..100')
        total+=(w/100.0)*v
    return round(total,3)
def trust_band(score):
    if score>=80:return 'STRONG'
    if score>=65:return 'GOOD'
    if score>=50:return 'DEVELOPING'
    if score>=35:return 'LOW'
    return 'UNTRUSTED'
