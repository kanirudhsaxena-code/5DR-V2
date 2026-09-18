"""Fixed allowlisted diagnostics for the isolated Upstox experiment.

Never emit arbitrary provider payloads, URLs, credentials, or exception text.
"""
from phase1.upstox import PipelineError, safe_failure

_EXACT = {
    "Contract array missing": "CONTRACT_ARRAY_MISSING",
    "Contract identity missing": "CONTRACT_IDENTITY_MISSING",
    "Duplicate option instrument key": "DUPLICATE_OPTION_INSTRUMENT_KEY",
    "No active NIFTY expiries returned": "NO_ACTIVE_EXPIRIES",
    "No session-valid NIFTY expiry returned": "NO_SESSION_VALID_EXPIRY",
    "Selected expiry invalid": "SELECTED_EXPIRY_INVALID",
    "Selected expiry not in contract master": "SELECTED_EXPIRY_NOT_IN_MASTER",
    "Intraday candles empty": "INTRADAY_CANDLES_EMPTY",
    "Candle array missing": "CANDLE_ARRAY_MISSING",
    "Candle schema mismatch": "CANDLE_SCHEMA_INVALID",
    "Invalid OHLC geometry": "OHLC_INVALID",
    "Option chain is empty": "OPTION_CHAIN_EMPTY",
    "Chain contract identity mismatch": "CHAIN_IDENTITY_INVALID",
    "Invalid or duplicate strike": "STRIKE_INVALID_OR_DUPLICATE",
    "Inconsistent underlying spot across chain": "UNDERLYING_SPOT_INCONSISTENT",
    "CE leg missing": "CE_LEG_MISSING",
    "PE leg missing": "PE_LEG_MISSING",
    "CE contract not found": "CE_CONTRACT_NOT_FOUND",
    "PE contract not found": "PE_CONTRACT_NOT_FOUND",
    "CE identity mismatch": "CE_IDENTITY_MISMATCH",
    "PE identity mismatch": "PE_IDENTITY_MISMATCH",
    "CE strike mismatch": "CE_STRIKE_MISMATCH",
    "PE strike mismatch": "PE_STRIKE_MISMATCH",
    "CE market data missing": "CE_MARKET_DATA_MISSING",
    "PE market data missing": "PE_MARKET_DATA_MISSING",
    "Market status request failed": "MARKET_STATUS_REQUEST_FAILED",
    "Unexpected market status schema": "MARKET_STATUS_SCHEMA_INVALID",
    "Market status is stale": "MARKET_STATUS_STALE",
    "Market status timestamp is in the future": "MARKET_STATUS_FUTURE_TIMESTAMP",
    "Global instrument master missing": "GLOBAL_MASTER_MISSING",
    "BOD instrument master missing": "NSE_MASTER_MISSING",
    "Full quote data missing": "FULL_QUOTE_DATA_MISSING",
    "Full quote identity set mismatch": "FULL_QUOTE_IDENTITY_MISMATCH",
    "Institutional response identity mismatch": "INSTITUTIONAL_IDENTITY_MISMATCH",
    "Institutional response empty": "INSTITUTIONAL_DATA_EMPTY",
    "Option analytics response missing": "OPTION_ANALYTICS_DATA_MISSING",
    "OI strike data missing": "OI_STRIKE_DATA_MISSING",
    "OI expiry mismatch": "OI_EXPIRY_MISMATCH",
    "Change OI strike data missing": "CHANGE_OI_STRIKE_DATA_MISSING",
    "Change OI expiry mismatch": "CHANGE_OI_EXPIRY_MISMATCH",
    "Option analytics underlying mismatch": "OPTION_ANALYTICS_UNDERLYING_MISMATCH",
    "Option analytics insights missing": "OPTION_ANALYTICS_INSIGHTS_MISSING",
    "Instrument catalog network request failed": "INSTRUMENT_CATALOG_NETWORK_FAILED",
    "Instrument catalog gzip invalid": "INSTRUMENT_CATALOG_GZIP_INVALID",
    "Instrument catalog JSON invalid": "INSTRUMENT_CATALOG_JSON_INVALID",
    "Instrument catalog schema invalid": "INSTRUMENT_CATALOG_SCHEMA_INVALID",
}

_PREFIX = {
    "strike ": "STRIKE_VALUE_INVALID",
    "underlying spot ": "UNDERLYING_SPOT_INVALID",
    "contract strike ": "CONTRACT_STRIKE_INVALID",
    "CE ltp ": "CE_LTP_INVALID",
    "CE oi ": "CE_OI_INVALID",
    "CE volume ": "CE_VOLUME_INVALID",
    "PE ltp ": "PE_LTP_INVALID",
    "PE oi ": "PE_OI_INVALID",
    "PE volume ": "PE_VOLUME_INVALID",
    "Global instrument identity ambiguous or missing:": "GLOBAL_IDENTITY_AMBIGUOUS_OR_MISSING",
}


def diagnostic_code(error):
    if isinstance(error, PipelineError):
        message = str(error)
        if message in _EXACT:
            return _EXACT[message]
        for prefix, code in _PREFIX.items():
            if message.startswith(prefix):
                return code
    return safe_failure(error)
