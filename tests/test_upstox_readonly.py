import io
import json
import unittest
from datetime import date
from urllib.error import HTTPError
from phase1.upstox import ReadOnlyClient, PipelineError, NoRedirect, validate_candles, probe, NIFTY

class Fake:
    def __init__(self, responses): self.responses=iter(responses); self.calls=[]
    def open(self, req, timeout):
        self.calls.append(req)
        value=next(self.responses)
        if isinstance(value,Exception): raise value
        return io.BytesIO(json.dumps(value).encode())

def payload(data): return {'status':'success','data':data}

def envelope(rows): return {'payload':payload({'candles':rows})}

class ReadOnlyTests(unittest.TestCase):
    def test_token_required(self):
        with self.assertRaises(PipelineError): ReadOnlyClient('')
    def test_get_only_and_no_redirect(self):
        f=Fake([payload([])])
        c=ReadOnlyClient('fixture-token',f,lambda _:None)
        c.contracts()
        self.assertEqual(f.calls[0].method,'GET')
        self.assertTrue(f.calls[0].full_url.startswith('https://api.upstox.com/v2/option/contract?'))
        self.assertIsNone(NoRedirect().redirect_request(None,None,302,'',{},'https://example.com'))
    def test_forbidden_routes(self):
        f=Fake([]); c=ReadOnlyClient('fixture-token',f,lambda _:None)
        for p in ['/v2/order/place','/v2/portfolio/short-term-positions','https://example.com','/v2/option/chain/../order/place']:
            with self.assertRaises(PipelineError): c._get(p)
        self.assertEqual(f.calls,[])
    def test_auth_no_retry_or_secret_error(self):
        f=Fake([HTTPError('url',401,'fixture-token',{},None)])
        with self.assertRaises(PipelineError) as e: ReadOnlyClient('fixture-token',f,lambda _:None).contracts()
        self.assertNotIn('fixture-token',str(e.exception))
        self.assertEqual(len(f.calls),1)
    def test_bounded_retry(self):
        f=Fake([HTTPError('url',429,'',{},None),payload([])])
        ReadOnlyClient('fixture-token',f,lambda _:None).contracts()
        self.assertEqual(len(f.calls),2)
        f=Fake([HTTPError('url',503,'',{},None)]*3)
        with self.assertRaises(PipelineError): ReadOnlyClient('fixture-token',f,lambda _:None).contracts()
        self.assertEqual(len(f.calls),3)
    def test_candle_bad_values(self):
        good=['2026-09-09T09:15:00+05:30',100,102,99,101,0,0]
        self.assertEqual(validate_candles(envelope([good])),1)
        for row in [good[:4]+[float('nan')]+good[5:],good[:2]+[98]+good[3:]]:
            with self.assertRaises(PipelineError): validate_candles(envelope([row]))
        with self.assertRaises(PipelineError): validate_candles(envelope([good,good]))
    def test_probe_no_forecast(self):
        leg={'instrument_key':'NSE_FO|test','market_data':{'ltp':10,'oi':100,'volume':20}}
        chain=[{'underlying_key':NIFTY,'expiry':'2026-09-15','strike_price':25000,'call_options':leg,'put_options':leg}]
        daily=[['2026-09-09T00:00:00+05:30',100,102,99,101,0,0]]
        f=Fake([payload([{'underlying_key':NIFTY,'expiry':'2026-09-15'}]),payload({'candles':daily}),payload({'candles':[]}),payload(chain)])
        result=probe(ReadOnlyClient('fixture-token',f,lambda _:None),date(2026,9,10))
        self.assertFalse(result['trading_enabled'])
        self.assertFalse(result['forecast_release_enabled'])
        self.assertEqual(len(f.calls),4)
        self.assertTrue(all(r.method=='GET' for r in f.calls))

if __name__=='__main__': unittest.main()
