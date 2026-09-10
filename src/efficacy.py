"""Core efficacy helpers for immutable 5DR forecasts."""
def direction_hit(predicted,start_price,end_price,flat_band_pct=0.25):
    move_pct=100.0*(end_price-start_price)/start_price
    actual='RANGE' if abs(move_pct)<=flat_band_pct else ('BULLISH' if move_pct>0 else 'BEARISH')
    if predicted==actual:return 'HIT'
    if actual=='RANGE':return 'NEUTRAL_AMBIGUOUS'
    return 'MISS'
def brier_three_class(probabilities,actual):
    score=0.0
    for label in ('BULL','RANGE','BEAR'):
        p=probabilities[label]/100.0; y=1.0 if label==actual else 0.0; score+=(p-y)**2
    return round(score,6)
