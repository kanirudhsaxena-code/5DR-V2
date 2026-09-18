# Experimental 5DR autonomous market-data status

PR #30 is merged into canonical `main` under explicit user approval dated 18 Sep 2026. The Drive canonical specification remains 5DR V2.2.3. Production forecasting/scoring semantics remain frozen. The validated V2.2.3 structured-evidence acquisition layer is active on canonical `main` for approved live windows; forecast publication, production forecast writes, lifecycle writes and trading remain disabled.

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
- G11 PAIRED SCREENSHOT-ASSISTED VS STRUCTURED VALIDATION: PASS — 3/3 same-session manual pairs PASS on 17 Sep 2026 and next-session rollover PASS on 18 Sep 2026. Final gate: `experiments/gate_records/G11_final_2026-09-18.json`.
- G12 STRUCTURED-EVIDENCE PRODUCTION RUNTIME: ACTIVE FOR VALIDATED LIVE WINDOWS — 10:30 IST intraday snapshot and 15:25 IST prior-close canonical-candidate evidence acquisition are scheduled on canonical `main`; first live production smoke PASS on 18 Sep 2026.
- G13 PRODUCTION MERGE / INTEGRATION: PASS — PR #30 merged into `main` at `7972d660078d28d0631f822e21cb1fc6b495776b`; activation PR #37 merged at `d611576b8e2a0f5d316d9bc849f81fc9141696c7`.
- ROUTINE SCREENSHOT POLICY: RETIRED FOR NORMAL VALIDATED LIVE EVIDENCE WINDOWS — structured evidence is primary; screenshots remain diagnostic/anomaly fallback only.
- FORECAST PUBLICATION / CANONICAL FORECAST WRITE / LIFECYCLE WRITE / TRADING: DISABLED — structured evidence activation does not itself authorize these side effects.
- PREOPEN STRUCTURED REFRESH: BLOCKED/FAIL-CLOSED pending separate validation of prior-session carry-forward plus overnight/global refresh.

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
- one separate lightweight next-session rollover validation was completed PASS on 18 Sep 2026.
- the rollover was not another screenshot-parity run; no anomaly required diagnostic screenshots.
- final screenshot-retirement readiness is PASS for normal autonomous validation, while diagnostic screenshots remain available as an anomaly fallback.
- G11 PASS plus the user's explicit 18 Sep 2026 approval authorized the subsequent structured-evidence production integration. That approval did not alter frozen methodology and did not enable automatic forecast publication, lifecycle writes or trading.

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

## G11 completion — next-session rollover PASS

Gate record: `experiments/gate_records/G11_rollover_2026-09-18.json`.

- rollover workflow run: `35306193306` — SUCCESS.
- session advanced from 2026-09-17 to 2026-09-18.
- NFO status: `NORMAL_OPEN`.
- selected current NIFTY expiry: `2026-09-22`.
- rollover bundle SHA-256: `bdf82263ff69ef914849251160293cac7047829c06d7adf830decd9a78c434e7`.
- capture SHA-256: `6ca2b19038e7b9a3e83fbffd23f1b8dc83e313766dd36fe3e0c9b3778b6869cd`.
- rollover gate SHA-256: `7c63967cc3e9d3e651ae1316626599b35902fc7a5900d6c65cb505f4d9410d4a`.
- new-session identity: PASS.
- stale prior-session evidence rejection: PASS.
- current-session date binding: PASS.
- current expiry identity: PASS.
- deterministic replay: PASS.
- capture/evidence fingerprint integrity: PASS.
- duplicate/idempotency guard: PASS.
- side-effect isolation: PASS.
- published / forecast release / production write / lifecycle write / trading execution: all FALSE.

Final G11 record: `experiments/gate_records/G11_final_2026-09-18.json`.

Final G11 status: **PASS**.
Screenshot-retirement readiness: **PASS / SCREENSHOT_FREE_READY**. Under explicit user approval, routine screenshots are now retired for the validated production evidence windows; diagnostic screenshots remain permitted as an anomaly fallback.

## Current production state

Canonical `main` contains the merged V2.2.3 structured-evidence backbone and guarded production scheduler. First production evidence smoke: workflow `35309563909` — SUCCESS on 18 Sep 2026, run class `INTRADAY_SNAPSHOT`, evidence bundle `166bf25613447b593bd14b94a21f073f95815768df2c8ab695a1d30846939c92`. Immutable artifact `10533165774` uploaded successfully. Main regression CI `35309563911` — SUCCESS. Activation audit: `experiments/gate_records/V223_structured_production_activation_2026-09-18.json`.

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

POST-G11 BOUNDED BACKFILL READINESS: PASS — 29 series / 90 planned calls / 115,305-row upper bound; dry run executed 0 network calls and 0 storage writes on 18 Sep 2026.
ISOLATED CACHE PERSISTENCE RECONCILIATION: PASS — existing smoke document integrity verified on `market-data-cache-v223-experiment`; canonical `main` has no market-data-cache table.
READY FOR BOUNDED FULL HISTORICAL BACKFILL INTO ISOLATED CACHE: TECHNICALLY YES; NOT YET RUN.
READY FOR CANONICAL/PRODUCTION CACHE ACTIVATION: NO — explicit user approval required.

## Security and isolation

- GET/read-only Upstox market-information paths only.
- no order placement/modification/cancellation surface.
- no portfolio, funds or account action surface.
- Analytics Token only via GitHub secret; no token/header in audit manifests.
- no production lifecycle/database writer connected to the experimental data path.
- no canonical scoring, weight, probability, recommendation, efficacy or Learning Lab mutation.
- no production 5DR/EDGE writes.
- isolated Neon cache branch only; canonical Neon `main` unchanged.
- PR #30 merged under explicit user approval. Upstox remains read-only and the production evidence workflow has no broker-order, account, funds or portfolio action surface.

## Current next gate

1. G11 is complete PASS; do not reacquire or repeat Manual Runs 1–3 or the 18 Sep rollover.
2. V2.2.3 structured evidence production is ACTIVE for the validated late-morning and prior-close windows.
3. Validate the first scheduled 15:25 IST prior-close production evidence run on canonical `main`.
4. Build and separately validate the PREOPEN carry-forward + overnight/global refresh path before enabling the 08:45–09:00 window.
5. Automatic forecast publication/persistence remains disabled until a reusable exact-bundle-bound governed intelligence/release path is implemented without inventing methodology.
6. Historical backfill/export work is owned by the parallel chat and must not be duplicated here.
7. Trading remains disabled.
