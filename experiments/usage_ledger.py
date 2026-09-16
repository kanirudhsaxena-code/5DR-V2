"""In-memory usage accounting and hard budgets for the experimental data layer.

The ledger is intentionally storage/provider neutral. A future persistence adapter can
store summaries, but raw credentials, headers and payloads are never accepted here.
"""
from collections import defaultdict
from copy import deepcopy

from experiments.data_contract import DataArchitectureError


class UsageBudget:
    def __init__(self, *, max_calls=250, max_bytes=25_000_000,
                 max_rows_retained=250_000, max_billable_units=0):
        values = (max_calls, max_bytes, max_rows_retained, max_billable_units)
        if any(isinstance(v, bool) or not isinstance(v, int) or v < 0 for v in values):
            raise DataArchitectureError("usage budget invalid")
        self.max_calls = max_calls
        self.max_bytes = max_bytes
        self.max_rows_retained = max_rows_retained
        self.max_billable_units = max_billable_units


class UsageLedger:
    def __init__(self, budget=None):
        self.budget = budget or UsageBudget()
        self._events = []

    def record(self, *, provider, consumer, operation, rows_received=0,
               rows_retained=0, response_bytes=0, cache_hit=False,
               billable_units=0, status="SUCCESS"):
        strings = (provider, consumer, operation, status)
        if any(not isinstance(v, str) or not v.strip() for v in strings):
            raise DataArchitectureError("usage event identity invalid")
        nums = (rows_received, rows_retained, response_bytes, billable_units)
        if any(isinstance(v, bool) or not isinstance(v, int) or v < 0 for v in nums):
            raise DataArchitectureError("usage event numeric invalid")
        if rows_retained > rows_received:
            raise DataArchitectureError("retained rows exceed received rows")
        if not isinstance(cache_hit, bool):
            raise DataArchitectureError("cache flag invalid")
        event = {
            "provider": provider.upper(), "consumer": consumer.upper(),
            "operation": operation, "rows_received": rows_received,
            "rows_retained": rows_retained, "response_bytes": response_bytes,
            "cache_hit": cache_hit, "billable_units": billable_units,
            "status": status.upper(),
        }
        projected = self.summary(extra=event)
        if projected["calls"] > self.budget.max_calls:
            raise DataArchitectureError("usage call budget exceeded")
        if projected["response_bytes"] > self.budget.max_bytes:
            raise DataArchitectureError("usage byte budget exceeded")
        if projected["rows_retained"] > self.budget.max_rows_retained:
            raise DataArchitectureError("usage retention budget exceeded")
        if projected["billable_units"] > self.budget.max_billable_units:
            raise DataArchitectureError("usage billable budget exceeded")
        self._events.append(event)
        return deepcopy(event)

    def summary(self, extra=None):
        events = list(self._events) + ([extra] if extra else [])
        totals = defaultdict(int)
        totals["calls"] = len(events)
        for event in events:
            totals["rows_received"] += event["rows_received"]
            totals["rows_retained"] += event["rows_retained"]
            totals["response_bytes"] += event["response_bytes"]
            totals["cache_hits"] += int(event["cache_hit"])
            totals["billable_units"] += event["billable_units"]
        return dict(totals)
