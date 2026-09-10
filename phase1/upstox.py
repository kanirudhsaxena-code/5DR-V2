"""NIFTY-only read-only Upstox probe. Standard library; no broker SDK.

Use only an Analytics Token injected via UPSTOX_ANALYTICS_TOKEN.
This bootstrap checks acquisition, not market freshness or forecast readiness.
"""
import hashlib
import json
import math
import os
import time
from datetime import date, datetime, timedelta, timezone
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import Request, build_opener, HTTPRedirectHandler

NIFTY = 'NSE_INDEX|Nifty 50'
KEY = quote(NIFTY, safe='')
BASE = 'https://api.upstox.com'

class PipelineError(RuntimeError):
    pass

def safe_failure(error):
    """Return only allowlisted diagnostics, never arbitrary exception text."""
    messages = {
        'UPSTOX_ANALYTICS_TOKEN is missing': 'TOKEN_MISSING',
        'Analytics Token expired, invalid, or lacks access': 'AUTH_REJECTED',
        'Upstox network request failed': 'NETWORK_FAILED',
        'Invalid JSON response': 'INVALID_JSON',
        'Unexpected Upstox response schema': 'RESPONSE_SCHEMA_INVALID',
        'No active NIFTY expiries returned': 'NO_ACTIVE_EXPIRIES',
        'Contract array missing': 'CONTRACT_SCHEMA_INVALID',
        'Candle schema mismatch': 'CANDLE_SCHEMA_INVALID',
        'Candle array missing': 'CANDLE_ARRAY_MISSING',
        'Historical daily candles are empty': 'DAILY_CANDLES_EMPTY',
        'Option chain is empty': 'OPTION_CHAIN_EMPTY',
        'Chain contract identity mismatch': 'CHAIN_IDENTITY_INVALID',
        'Non-finite or missing numeric data': 'NUMERIC_DATA_INVALID',
    }
    if isinstance(error, PipelineError):
        message = str(error)
        if message in messages:
            return messages[message]
        for status in range(400, 600):
            if message == f'Upstox HTTP {status}; response withheld':
                return f'HTTP_{status}'
    return 'DATA_VALIDATION_FAILED'

def progress(stage):
    print(json.dumps({'stage': stage, 'trading_enabled': False}), flush=True)

class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None

class ReadOnlyClient:
    def __init__(self, token, opener=None, sleep=time.sleep):
        if not token or not token.strip():
            raise PipelineError('UPSTOX_ANALYTICS_TOKEN is missing')
        self._token = token.strip()
        self._opener = opener or build_opener(NoRedirect())
        self._sleep = sleep

    def _get(self, path, params=None):
        # Every path originates in a fixed high-level method, never caller URLs.
        allowed = {
            '/v2/option/contract', '/v2/option/chain',
            f'/v3/historical-candle/intraday/{KEY}/minutes/1',
        }
        prefix = f'/v3/historical-candle/{KEY}/days/1/'
        historical = False
        if path.startswith(prefix):
            parts = path[len(prefix):].split('/')
            if len(parts) == 2:
                try:
                    end, start = (date.fromisoformat(p) for p in parts)
                    historical = start <= end
                except ValueError:
                    pass
        if path not in allowed and not historical:
            raise PipelineError('Endpoint is not permitted')
        params = dict(params or {})
        if path.startswith('/v2/option/'):
            permitted = {'instrument_key'} | ({'expiry_date'} if path.endswith('/chain') else set())
            if set(params) != permitted or params.get('instrument_key') != NIFTY:
                raise PipelineError('Only NIFTY option data is permitted')
            if 'expiry_date' in params:
                date.fromisoformat(params['expiry_date'])
        elif params:
            raise PipelineError('Unexpected query parameters')
        url = BASE + path + ('?' + urlencode(params) if params else '')
        for attempt in range(3):
            self._sleep(1)  # <=1 request/second including retry attempts
            request = Request(url, headers={'Accept':'application/json',
                              'Authorization':'Bearer ' + self._token}, method='GET')
            try:
                with self._opener.open(request, timeout=20) as response:
                    raw = response.read(8_000_001)
                if len(raw) > 8_000_000:
                    raise PipelineError('Response exceeds size limit')
                payload = json.loads(raw)
                if not isinstance(payload, dict) or payload.get('status') != 'success' or 'data' not in payload:
                    raise PipelineError('Unexpected Upstox response schema')
                return {'received_at':datetime.now(timezone.utc).isoformat(),
                        'source_path':path,'parameters':params,
                        'sha256':hashlib.sha256(raw).hexdigest(),'payload':payload}
            except HTTPError as err:
                if err.code in (401,403):
                    raise PipelineError('Analytics Token expired, invalid, or lacks access') from None
                if err.code not in (429,500,502,503,504) or attempt == 2:
                    raise PipelineError(f'Upstox HTTP {err.code}; response withheld') from None
                self._sleep(2 ** (attempt + 1))
            except (URLError, TimeoutError, OSError):
                if attempt == 2:
                    raise PipelineError('Upstox network request failed') from None
                self._sleep(2 ** (attempt + 1))
            except (ValueError, UnicodeError):
                raise PipelineError('Invalid JSON response') from None
        raise PipelineError('Retry budget exhausted')

    def contracts(self):
        return self._get('/v2/option/contract', {'instrument_key':NIFTY})

    def chain(self, expiry):
        return self._get('/v2/option/chain', {'instrument_key':NIFTY, 'expiry_date':date.fromisoformat(expiry).isoformat()})

    def intraday(self):
        return self._get(f'/v3/historical-candle/intraday/{KEY}/minutes/1')

    def daily(self, start, end):
        if start > end or (end-start).days > 366:
            raise PipelineError('Invalid bootstrap history range')
        return self._get(f'/v3/historical-candle/{KEY}/days/1/{end.isoformat()}/{start.isoformat()}')

def finite_number(value):
    if isinstance(value, bool) or not isinstance(value, (int,float)) or not math.isfinite(value):
        raise PipelineError('Non-finite or missing numeric data')
    return value

def validate_candles(envelope):
    data = envelope['payload']['data']
    rows = data.get('candles') if isinstance(data,dict) else None
    if not isinstance(rows,list):
        raise PipelineError('Candle array missing')
    seen=set()
    for row in rows:
        if not isinstance(row,list) or len(row) != 7:
            raise PipelineError('Candle schema mismatch')
        stamp = datetime.fromisoformat(row[0])
        if stamp.tzinfo is None or stamp in seen:
            raise PipelineError('Naive or duplicate candle timestamp')
        seen.add(stamp)
        o,h,l,c = [finite_number(v) for v in row[1:5]]
        if not 0 < l <= min(o,c) <= max(o,c) <= h:
            raise PipelineError('Invalid OHLC geometry')
        for v in row[5:]:
            if v is not None and finite_number(v)<0:
                raise PipelineError('Negative volume/open interest')
    return len(rows)

def probe(client, today):
    progress('OPTION_CONTRACTS')
    contracts = client.contracts()
    rows = contracts['payload']['data']
    if not isinstance(rows,list):
        raise PipelineError('Contract array missing')
    expiries=sorted({r['expiry'] for r in rows if r.get('underlying_key')==NIFTY
                     and date.fromisoformat(r['expiry'])>=today})
    if not expiries:
        raise PipelineError('No active NIFTY expiries returned')
    progress('DAILY_CANDLES')
    daily = client.daily(today-timedelta(days=365),today-timedelta(days=1))
    progress('INTRADAY_CANDLES')
    intraday = client.intraday()
    progress('VALIDATE_CANDLES')
    daily_count=validate_candles(daily)
    intraday_count=validate_candles(intraday)
    if not daily_count:
        raise PipelineError('Historical daily candles are empty')
    chains=[]
    for expiry in expiries[:2]:
        progress('OPTION_CHAIN')
        envelope=client.chain(expiry)
        chain_rows=envelope['payload']['data']
        if not isinstance(chain_rows,list) or not chain_rows:
            raise PipelineError('Option chain is empty')
        strikes=set()
        for row in chain_rows:
            if row.get('expiry')!=expiry or row.get('underlying_key')!=NIFTY:
                raise PipelineError('Chain contract identity mismatch')
            strike=finite_number(row.get('strike_price'))
            if strike<=0 or strike in strikes:
                raise PipelineError('Invalid or duplicate strike')
            strikes.add(strike)
            for side in ('call_options','put_options'):
                leg=row.get(side,{})
                if not leg.get('instrument_key'):
                    raise PipelineError('Option instrument key missing')
                for field in ('ltp','oi','volume'):
                    if finite_number(leg.get('market_data',{}).get(field))<0:
                        raise PipelineError('Negative option market data')
        chains.append(envelope)
    # No data payloads or credentials in console logs; no filesystem/DB writes.
    return {'status':'ACQUISITION_PROBE_PASSED','trading_enabled':False,
            'forecast_release_enabled':False,'daily_candles':daily_count,
            'intraday_candles':intraday_count,'expiries_checked':len(chains),
            'note':'Freshness, Greek coverage, persistence and forecast parity still require validation.'}

if __name__=='__main__':
    from zoneinfo import ZoneInfo
    try:
        print(json.dumps(probe(ReadOnlyClient(os.getenv('UPSTOX_ANALYTICS_TOKEN')),
                               datetime.now(ZoneInfo('Asia/Kolkata')).date())))
    except (PipelineError, ValueError, KeyError, TypeError) as error:
        print(json.dumps({'status':'BLOCKED','trading_enabled':False,
                          'diagnostic_code':safe_failure(error),
                          'reason':'Credential, transport or data validation failed; no forecast released.'}))
        raise SystemExit(2)
