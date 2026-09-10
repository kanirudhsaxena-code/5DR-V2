from src.market_trust import market_trust,trust_band
from src.execution import execution_edge,tradeability
from src.probability import probabilities
def test_market_trust():
    s=market_trust({'price_confirmation':80,'pvpo_confirmation':75,'participation_confirmation':65,'cross_engine_consistency':70,'closing_confirmation':75,'evidence_freshness_completeness':90}); assert round(s,2)==75.5; assert trust_band(s)=='GOOD'
def test_tradeability():
    e=execution_edge({'rr_score':80,'premium_iv_theta_score':70,'strike_expiry_fit_score':75,'liquidity_spread_score':80,'entry_invalidation_score':70}); ok,f=tradeability(data_adequate=True,market_trust=72,des5=55,execution_edge=e,event_kill_switch=False,expected_rr=2.3); assert ok and f==[]
def test_probabilities_total_100():
    p=probabilities(55,72,'LOW'); assert abs(sum(p.values())-100)<0.01
