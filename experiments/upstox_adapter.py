"""Upstox implementation of the provider-neutral read-only adapter boundary.

It delegates only to the already-hardened QuantReadOnlyClient. No order/account/funds
surface exists here. More provider capabilities can be added without changing consumers.
"""
from experiments.data_contract import DataArchitectureError
from experiments.provider_adapter import ReadOnlyProviderAdapter


class UpstoxAdapter(ReadOnlyProviderAdapter):
    provider_id = "UPSTOX"
    source_semantic = "UPSTOX_AUTHENTICATED"
    capabilities = frozenset({"QUOTES", "INTRADAY_CANDLES", "HISTORICAL_CANDLES", "INSTITUTIONAL", "OPTION_ANALYTICS"})
    _TIMEFRAMES = {"5m": ("minutes", 5), "15m": ("minutes", 15), "30m": ("minutes", 30), "1h": ("hours", 1)}
    _HISTORICAL_TIMEFRAMES = {**_TIMEFRAMES, "1d": ("days", 1)}

    def __init__(self, quant_client):
        required = ("full_quotes", "intraday", "institutional", "option_analytics")
        if quant_client is None or any(not callable(getattr(quant_client, name, None)) for name in required):
            raise DataArchitectureError("Upstox read-only client invalid")
        self._client = quant_client

    def get_quotes(self, instrument_keys):
        self.require("QUOTES")
        return self._client.full_quotes(instrument_keys)

    def get_candles(self, instrument_key, timeframe):
        self.require("INTRADAY_CANDLES")
        if timeframe not in self._TIMEFRAMES:
            raise DataArchitectureError("Upstox adapter timeframe not wired")
        unit, interval = self._TIMEFRAMES[timeframe]
        return self._client.intraday(instrument_key, unit, interval)

    def get_historical_candles(self, instrument_key, timeframe, start, end):
        self.require("HISTORICAL_CANDLES")
        historical = getattr(self._client, "historical", None)
        if not callable(historical):
            raise DataArchitectureError("Upstox historical capability unavailable")
        if timeframe not in self._HISTORICAL_TIMEFRAMES:
            raise DataArchitectureError("Upstox historical timeframe not wired")
        unit, interval = self._HISTORICAL_TIMEFRAMES[timeframe]
        return historical(instrument_key, unit, interval, start, end)

    def get_institutional(self, kind, data_types, interval="1D"):
        self.require("INSTITUTIONAL")
        return self._client.institutional(kind, data_types, interval)

    def get_option_analytics(self, kind, **kwargs):
        self.require("OPTION_ANALYTICS")
        return self._client.option_analytics(kind, **kwargs)
