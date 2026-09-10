from src.scoring import weighted_component,des5,directional_label
def test_weighted_component():
    assert weighted_component({'a':2,'b':1,'c':0},{'a':50,'b':30,'c':20})==65.0
def test_des5_trend():
    s=des5({'PRICE_STRUCTURE':60,'PVPO':50,'PARTICIPATION':40,'MACRO_CATALYSTS':30},'TREND'); assert s==49.5; assert directional_label(s)=='BULL'
