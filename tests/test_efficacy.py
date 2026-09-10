from src.efficacy import direction_hit,brier_three_class
def test_direction_hit(): assert direction_hit('BULLISH',25000,25200)=='HIT'
def test_brier(): assert brier_three_class({'BULL':60,'RANGE':25,'BEAR':15},'BULL')>=0
