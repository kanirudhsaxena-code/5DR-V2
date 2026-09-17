# Experimental 5DR autonomous market-data status

PR #30 remains experimental, draft and unmerged. The Drive canonical specification remains 5DR V2.2.3. Production forecasting/scoring semantics remain frozen and no experimental code is connected to the canonical production consumer without explicit approval.

## Current gate summary

- G1 CORE OPEN-MARKET ACQUISITION RELIABILITY: PASS — live proven.
- G2 OPTION IDENTITY / FRESHNESS / DUPLICATE / READ-ONLY BOUNDARY: PASS — live proven.
- G3 BROAD 5DR QUANTITATIVE UPSTOX UNIVERSE: PASS — live proven.
- G4 REPRESENTATIVE MULTI-TIMEFRAME HISTORICAL RETRIEVAL: PASS — live proven.
- G5 DETERMINISTIC CHART-STRUCTURE DERIVATION: PASS — offline tests and live Upstox historical proof; routine screenshots are technically replaceable at the chart-evidence layer.
- G6 FROZEN SCREENSHOT-FREE EVIDENCE BUNDLE CONTRACT: PASS — quantitative/chart/external evidence is fail-closed and bundle integrity is reverified at engine handoff.
- G7 DURABLE HISTORICAL CACHE / RUN LEDGER: PASS FOR ISOLATED SMOKE — isolated Neon branch/schema and provenance-bound durable NIFTY smoke record proven. Full bounded historical backfill remains disabled/not run.
- G8-A MARKET-CALENDAR-AWARE SCHEDULING POLICY: PASS offline; production run windows not activated.
- G8-B WATCHDOG / IDEMPOTENCY / MISSED-RUN POLICY: PASS offline; production trigger not activated.
- G9 AUTONOMOUS WEB-CONTEXT INGESTION: PASS FOR GOVERNED LIVE EXECUTOR — live official/web source acquisition, bounded deterministic fact extraction, hashing, freshness and fail-closed reference-only handling proven.
- G10 END-TO-END AUTONOMOUS 5DR SHADOW: PASS FOR NON-PUBLISHING LIVE SHADOW — frozen current structured evidence was bundle-bound to governed judgment and executed through the existing source-neutral engine with all side effects disabled.
- G10-B MACRO-ENRICHED LIVE SHADOW: PASS_DIAGNOSTIC — governed official macro facts were incorporated without methodology change; diagnostic only, not production acceptance.
- G11 PAIRED SCREENSHOT-ASSISTED VS STRUCTURED VALIDATION: PRIMARY MANUAL SERIES COMPLETE — 3/3 same-session manual pairs PASS on 17 Sep 2026. Consolidated state: `MANUAL_SERIES_PASS_ROLLOVER_PENDING`.
- G12 PRODUCTION RUNTIME / PERSISTENCE ACTIVATION: BLOCKED pending final G11 rollover completion, screenshot-retirement readiness assessment, and explicit user approval.
- G13 PRODUCTION MERGE / INTEGRATION: BLOCKED pending explicit user approval.
- ROUTINE SCREENSHOT RETIREMENT: NOT ACTIVATED pending next-session rollover and final G11 readiness assessment.

## G11 active validation protocol — v2

`experiments/g11_validation_protocol.json` remains the active experiment-only G11 collection protocol.

- required manual paired observations: 3.
- required distinct sessions for the primary series: 1.
- all three primary manual runs must belong to the same live NSE session.
- every primary run requires an explicit user-approved manual trigger and a distinct manual run id.
- reference mode: `SCREENSHOT_ASSISTED`.
- structured mode: `UPSTOX_STRUCTURED`.
- exact same evidence timestamp is not required.
- <=180 seconds evidence-time delta is preferred.
- >180 and <=300 seconds remains comparable-with-tolerance and must preserve the measured delta.
- >300 seconds is observational-only and cannot count.
- primary same-session manual series is now COMPLETE 3/3 PASS.
- one separate lightweight next-session rollover validation remains required.
- the rollover is not another screenshot-parity run unless an actual rollover anomaly requires diagnostic screenshots.
- no production activation, forecast release, lifecycle write, trading execution, methodology change, screenshot retirement, or PR merge is authorized by the manual-series PASS alone.

The historical `experiments/gate_records/G11_observational_temporal_mismatch_2026-09-16.json` remains retained for audit and does not count toward the primary series.

### 17 Sep scheduled 09:45 structured capture — preserved, not counted

The scheduled structured capture `G11-20260917-0945` remains valid structured evidence but had no matching screenshot-assisted reference and therefore is not part of the 3-run primary series.

- evidence cutoff: 09:45:00 IST.
- bundle SHA-256: `af79ffc940260053b388a7420d9f435e589baa6659ffc3f133f40d218604a04a`.
- no forecast release, canonical integration, production/lifecycle write or trading was enabled.

### Manual Run 1 — PASS

Gate record: `experiments/gate_records/G11_manual_run1_2026-09-17.json`.

- manual run id: `G11-20260917-104405`.
- evidence cutoff: 10:44:05 IST.
- bundle SHA-256: `6fe9de7c379feecd5bb759e6a7eedec328af08f0a8278ae1b66abc8e621f105e`.
- screenshot timing was within the preferred <=180-second pairing tolerance.
- spot, futures construction, option-chain structure, all five chart timeframes and PVS interpretation reconciled without material divergence.
- all production/trading/write safety flags remained false.

### Manual Run 2 — PASS

Gate record: `experiments/gate_records/G11_manual_run2_2026-09-17.json`.

- manual run id: `G11-20260917-134141`.
- evidence cutoff: 13:41:41.840036 IST.
- bundle SHA-256: `afe6d95ec65abbc3f5e3f53c1a084f84d693cbfb91b54bf214e013658573603a`.
- screenshot evidence was supplied within the approved comparison window.
- spot/listed-future evidence, 22 Sep option-chain LTP/IV/OI/OI-change patterns, all five chart timeframes and PVS interpretation reconciled without material divergence.
- all production/trading/write safety flags remained false.

### Manual Run 3 — PASS

Gate record: `experiments/gate_records/G11_manual_run3_2026-09-17.json`.

- manual run id: `G11-20260917-141937`.
- evidence cutoff: 14:19:37.618705 IST.
- bundle SHA-256: `ca2b93148ecba6585c667ec93b55490425ebb81418435aad66d37e11e7e58881`.
- screenshot evidence remained within the <=300-second hard comparability cap, with the core pair inside the preferred <=180-second window.
- spot, actual 29 Sep future, option-chain parity and all five chart timeframes reconciled without material PVS divergence.
- all production/trading/write safety flags remained false.

### Consolidated same-session manual series

Gate record: `experiments/gate_records/G11_manual_series_2026-09-17.json`.

- Run 1: PASS.
- Run 2: PASS.
- Run 3: PASS.
- comparable paired manual observations: 3 / 3.
- timing comparability: PASS.
- spot cross-source parity: PASS.
- listed-futures / synthetic-future explanation: PASS.
- option LTP / IV / OI reconciliation: PASS.
- all five chart timeframes reconciled for each run: YES.
- material PVS divergence detected: NO.
- production side effects detected: NO.
- consolidated state: `MANUAL_SERIES_PASS_ROLLOVER_PENDING`.
- G11 final gate status: `PENDING_NEXT_SESSION_ROLLOVER`.

These three immutable manual runs must not be reacquired or repeated.

## Only remaining G11 validation — next-session rollover

Perform one lightweight validation in the next live NSE session only. Validate:

1. new NSE session identity is recognized;
2. current session date is bound correctly;
3. stale prior-session market evidence is rejected;
4. prior-session cache/bundle cannot be mistaken for current live evidence;
5. option expiry identity is current and not stale;
6. deterministic replay remains valid;
7. evidence hash / fingerprint integrity remains valid;
8. idempotency / duplicate handling remains fail-safe;
9. `published=false`;
10. `forecast_release_enabled=false`;
11. `production_5dr_write_enabled=false`;
12. `lifecycle_write_enabled=false`;
13. `trading_execution_enabled=false`.

If rollover PASS: consolidate G11 as complete, perform final screenshot-retirement readiness assessment, synchronize status/audit wording and the existing Drive canonical spec only if required, and stop before production activation or PR #30 merge for explicit user approval.

If rollover FAIL: preserve fail-closed state, identify the exact session/date/expiry/staleness defect, and fix only the execution/data-validation layer. Do not alter canonical methodology, scoring, weights, probability engine, tradeability gates or governance.

## Current-head regression state

Current experimental branch head before this documentation sync: `ce1ef468c84a75a524a439e2fd22a20eee825e2d` (`[g11] consolidate three same-session manual PASS runs`). CI run `35202612772` completed successfully. CI success does not imply production activation.

## Core market-data proof retained

Open-market burst run `35054637198`: 09:45 / 10:00 / 10:15 / 10:30 all PASS and ADVANCED during `NORMAL_OPEN`.

Broad quantitative run `35060738861`: PASS for NIFTY, India VIX, nearest NIFTY future, NIFTY 15m/30m/1h, FII/DII, OI/change-OI/PCR/max-pain, GIFT Nifty, major global indices, Brent, WTI and USD/INR.

Representative history run `35061881459`: PASS with exactly eight authenticated read-only GETs.

Live chart derivation run `35065714571`: PASS across 5m/15m/30m/1h/1d without assigning forecast direction or fabricating index volume/VWAP.

## Durable-cache and cost boundary

The bounded initial 5DR historical plan remains 29 series / 90 planned calls / 115,305-row upper bound under ceilings of 250 calls, 250,000 retained rows and zero planned billable units.

- full historical backfill: NOT RUN.
- isolated Neon branch: `market-data-cache-v223-experiment`.
- isolated schema: `market_data_cache`.
- canonical Neon `main`: unchanged by the experimental cache proof.
- one real provenance-bound NIFTY smoke document persisted/read back successfully on the isolated branch.

READY FOR BOUNDED FULL HISTORICAL BACKFILL INTO ISOLATED CACHE: TECHNICALLY YES; NOT YET RUN.
READY FOR CANONICAL/PRODUCTION CACHE ACTIVATION: NO.

## Security and isolation

- GET/read-only Upstox market-information paths only.
- no order placement/modification/cancellation surface.
- no portfolio, funds or account action surface.
- Analytics Token only via GitHub secret; no token/header in audit manifests.
- no production lifecycle/database writer connected to the experimental data path.
- no canonical scoring, weight, probability, recommendation, efficacy or Learning Lab mutation.
- no production 5DR/EDGE writes.
- isolated Neon cache branch only; canonical Neon `main` unchanged.
- PR #30 remains draft/unmerged.

## Current next gate

1. Do not trigger or reacquire G11 Manual Runs 1, 2 or 3; the same-session 3/3 primary series is complete.
2. Perform exactly one lightweight next-session rollover validation.
3. Only after rollover PASS, produce final G11 consolidation and screenshot-retirement readiness assessment.
4. Do not activate production structured-data runtime, canonical integration, forecast release, lifecycle writes, trading execution or PR #30 merge without explicit user approval.
5. The full 29-series / 90-call historical backfill remains optional and disabled unless separately justified/approved for the isolated cache; it must never target canonical Neon `main` without explicit approval.
