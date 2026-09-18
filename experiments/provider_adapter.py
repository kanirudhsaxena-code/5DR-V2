"""Provider-neutral read-only adapter boundary."""
from experiments.data_contract import DataArchitectureError


class ReadOnlyProviderAdapter:
    provider_id = "ABSTRACT"
    source_semantic = "ABSTRACT_SOURCE"
    capabilities = frozenset()

    def require(self, capability):
        if capability not in self.capabilities:
            raise DataArchitectureError(f"provider capability unavailable: {capability}")

    def get_quotes(self, instrument_keys):
        raise NotImplementedError

    def get_candles(self, instrument_key, timeframe):
        raise NotImplementedError

    def get_historical_candles(self, instrument_key, timeframe, start, end):
        raise NotImplementedError

    def get_institutional(self, kind, data_types, interval="1D"):
        raise NotImplementedError

    def get_option_analytics(self, kind, **kwargs):
        raise NotImplementedError

    def describe(self):
        return {"provider_id": self.provider_id, "source_semantic": self.source_semantic, "read_only": True, "capabilities": sorted(self.capabilities)}
