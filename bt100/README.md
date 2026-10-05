# BT-5DR-100 isolated readiness workstream

Status: **PRE-G5 READINESS ONLY**

This directory implements the research-only readiness boundary for the planned
100-session historical replay of the frozen 5DR production methodology.

## Hard locks

- run role: `REPLAY`
- official efficacy eligibility: `FALSE`
- formal replay: blocked until G5.1 is formally PASS and the accepted 5DR SHA is frozen
- production writes: forbidden
- canonical table writes: forbidden
- trading/actions: forbidden
- production neuron budget: **0**
- missing point-in-time evidence: `DATA_GAP` / `NOT_SCORABLE`
- methodology tuning during BT-5DR-100-V1: forbidden

## Pre-G5 deliverables

1. Exact 100-session target-date selector from authenticated NIFTY daily history.
2. Historical evidence requirements matrix.
3. Bounded expired-derivative capability probe.
4. Readiness validator with safety invariants.
5. Branch-only CI/readiness workflow.
6. Readiness artifact containing target dates, probe result and fail-closed report.

## Important historical-data constraint

Upstox documents its expired-instruments expiry discovery as covering up to six
months of historical expiries. The first BT100 cohort must therefore be selected
and entitlement-tested before the formal replay is frozen.

The expired historical candle API documents OHLC, volume and open interest for
expired derivatives. This is useful for historical option lifecycle and PVPO
reconstruction, but it does **not** by itself prove a point-in-time historical
bid/ask/IV chain snapshot. Those fields remain fail-closed until independently
proven.

## Execution

The workflow `.github/workflows/bt100-readiness.yml` is deliberately isolated.
It has `contents: read` permissions only, calls no production database and is
not given any Cloudflare/AI inference secret.
