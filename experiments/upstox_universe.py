"""Build the exact core instrument-key universe allowed for the 5DR quant experiment."""
from experiments.upstox_instruments import GLOBAL_TARGET_NAMES
from experiments.upstox_quant_client import INDIA_VIX
from phase1.upstox import NIFTY, PipelineError


def build_core_5dr_universe(global_instruments, nifty_future):
    if not isinstance(global_instruments, dict) or set(global_instruments) != set(GLOBAL_TARGET_NAMES):
        raise PipelineError("Global 5DR universe incomplete")
    keys = {NIFTY, INDIA_VIX}
    for target, identity in global_instruments.items():
        if not isinstance(identity, dict) or identity.get("exchange") != "GLOBAL":
            raise PipelineError(f"Global 5DR identity invalid: {target}")
        key = identity.get("instrument_key")
        if not isinstance(key, str) or not key.startswith(("GLOBAL_INDEX|", "GLOBAL_INDICATOR|")):
            raise PipelineError(f"Global 5DR key invalid: {target}")
        keys.add(key)
    if not isinstance(nifty_future, dict) or nifty_future.get("underlying_key") != NIFTY or nifty_future.get("instrument_type") != "FUT":
        raise PipelineError("NIFTY future identity invalid")
    future_key = nifty_future.get("instrument_key")
    if not isinstance(future_key, str) or not future_key.startswith("NSE_FO|"):
        raise PipelineError("NIFTY future key invalid")
    keys.add(future_key)
    if len(keys) != 14:
        raise PipelineError("Core 5DR universe identity collision")
    return frozenset(keys)
