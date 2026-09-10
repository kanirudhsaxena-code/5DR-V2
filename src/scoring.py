"""Deterministic scoring primitives for 5DR V2."""
REGIME_WEIGHTS={
"TREND":{"PRICE_STRUCTURE":40.0,"PVPO":30.0,"PARTICIPATION":15.0,"MACRO_CATALYSTS":15.0},
"RANGE":{"PRICE_STRUCTURE":30.0,"PVPO":35.0,"PARTICIPATION":15.0,"MACRO_CATALYSTS":20.0},
"TRANSITION":{"PRICE_STRUCTURE":35.0,"PVPO":25.0,"PARTICIPATION":15.0,"MACRO_CATALYSTS":25.0},
"EVENT_SHOCK":{"PRICE_STRUCTURE":30.0,"PVPO":20.0,"PARTICIPATION":10.0,"MACRO_CATALYSTS":40.0},}
RAW_NORMALIZED={-2:-1.0,-1:-0.5,0:0.0,1:0.5,2:1.0}
def weighted_component(raw_scores,internal_weights):
    if abs(sum(internal_weights.values())-100.0)>1e-9: raise ValueError('internal weights must total 100')
    total=0.0
    for k,w in internal_weights.items():
        raw=raw_scores[k]
        if raw not in RAW_NORMALIZED: raise ValueError('raw scores must be -2,-1,0,1,2')
        total+=(w/100.0)*RAW_NORMALIZED[raw]
    return round(100.0*total,3)
def des5(component_scores,regime):
    total=0.0
    for c,w in REGIME_WEIGHTS[regime].items():
        s=float(component_scores[c])
        if s < -100 or s > 100: raise ValueError('component score outside -100..100')
        total+=(w/100.0)*s
    return round(total,3)
def directional_label(score):
    if score>=60:return 'STRONG_BULL'
    if score>=30:return 'BULL'
    if score>=15:return 'MILD_BULL'
    if score>=-14:return 'RANGE'
    if score>=-29:return 'MILD_BEAR'
    if score>=-59:return 'BEAR'
    return 'STRONG_BEAR'
