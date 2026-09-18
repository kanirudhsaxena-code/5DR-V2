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
- G12 STRUCTURED-EVIDENCE PRODUCTION RUNTIME: ACTIVE FOR VALIDATED LIVE WINDOWS — 10:30 IST intraday snapshot and 15:25 IST prior-close canonical-candidate evidence acquisition are scheduled on canonical `main`; first live production smoke PASS and first scheduled prior-close production run PASS on 18 Sep 2026.
- G13 PRODUCTION MERGE / INTEGRATION: PASS — PR #30 merged into `main` at `7972d660078d28d0631f822e21cb1fc6b495776b`; activation PR #37 merged at `d611576b8e2a0f5d316d9bc849f81fc9141696c7`.
- ROUTINE SCREENSHOT POLICY: RETIRED FOR NORMAL VALIDATED LIVE EVIDENCE WINDOWS — structured evidence is primary; screenshots remain diagnostic/anomaly fallback only.
- FORECAST PUBLICATION / CANONICAL FORECAST WRITE / LIFECYCLE WRITE / TRADING: DISABLED — structured evidence activation does not itself authorize these side effects.
- PREOPEN STRUCTURED REFRESH: BLOCKED/FAIL-CLOSED pending separate validation of prior-session carry-forward plus overnight/global refresh.

## G11 completion summary

`experiments/g11_validation_protocol.json` remains retained as the experiment-only G11 collection protocol. The primary same-session manual series completed 3/3 PASS on 17 Sep 2026 and the next-session rollover completed PASS on 18 Sep 2026. The historical observational temporal-mismatch record remains retained for audit and does not count toward the primary series. The three immutable manual runs and rollover must not be reacquired or repeated.

Final G11 record: `experiments/gate_records/G11_final_2026-09-18.json`.

Final G11 status: **PASS**.
Screenshot-retirement readiness: **PASS / SCREENSHOT_FREE_READY**. Under explicit user approval, routine screenshots are now retired for the validated production evidence windows; diagnostic screenshots remain permitted as an anomaly fallback.

## Current production state

Canonical `main` contains the merged V2.2.3 structured-evidence backbone and guarded production scheduler.

First production evidence smoke: workflow `35309563909` — SUCCESS on 18 Sep 2026, run class `INTRADAY_SNAPSHOT`, evidence bundle `166bf25613447b593bd14b94a21f073f95815768df2c8ab695a1d30846939c92`. Immutable artifact `10533165774` uploaded successfully. Main regression CI `35309563911` — SUCCESS. Activation audit: `experiments/gate_records/V223_structured_production_activation_2026-09-18.json`.

First scheduled prior-close production evidence run: workflow `35332448007` — **PASS / SUCCESS** on 18 Sep 2026. Scheduled run started at 10:00:16Z (15:30 IST scheduler dispatch for the validated prior-close window), checked out canonical `main` at `c2aaaf53e09fb6825c3e3fee4992b66c8cb6f64d`, emitted label `PRIOR_CLOSE_REFRESH`, run class `CANONICAL_CANDIDATE`, production status `PRODUCTION_EVIDENCE_READY`, and a `READY` screenshot-free bundle with SHA-256 `c2c2c14287ba971fa29413db1b37e42b25f56cfb1a41bc9e54b37df4e3939145`. Immutable artifact `10541217566` uploaded successfully with archive digest `sha256:88c5bf924c3e9c98591e371c6131345df34826bf336a05b70b48b7e9d7f68a3d`. `forecast_release_enabled=false`, `production_5dr_write_enabled=false`, `lifecycle_write_enabled=false`, `trading_execution_enabled=false`, and `methodology_changed=false`. Upstox remained GET/read-only with no order, funds, portfolio or account action surface. Audit record: `experiments/gate_records/V223_scheduled_prior_close_2026-09-18.json`.

## Core market-data proof retained

Open-market burst run `35054637198`: 09:45 / 10:00 / 10:15 / 10:30 all PASS and ADVANCED during `NORMAL_OPEN`.

Broad quantitative run `35060738861`: PASS for NIFTY, India VIX, nearest NIFTY future, NIFTY 15m/30m/1h, FII/DII, OI/change-OI/PCR/max-pain, GIFT Nifty, major global indices, Brent, WTI and USD/INR.

Representative history run `35061881459`: PASS with exactly eight authenticated read-only GETs.

Live chart derivation run `35065714571`: PASS across 5m/15m/30m/1h/1d without assigning forecast direction or fabricating index volume/VWAP.

## Durable-cache and cost boundary

The bounded initial 5DR historical plan remains 29 series / 90 planned calls / 115,305-row upper bound under ceilings of 250 calls, 250,000 retained rows and zero planned billable units.

- full historical backfill: NOT RUN by this workstream.
- isolated Neon branch: `market-data-cache-v223-experiment`.
- isolated schema: `market_data_cache`.
- canonical Neon `main`: unchanged by the experimental cache proof.
- one real provenance-bound NIFTY smoke document persisted/read back successfully on the isolated branch.

POST-G11 BOUNDED BACKFILL READINESS: PASS — 29 series / 90 planned calls / 115,305-row upper bound; dry run executed 0 network calls and 0 storage writes on 18 Sep 2026.
ISOLATED CACHE PERSISTENCE RECONCILIATION: PASS — existing smoke document integrity verified on `market-data-cache-v223-experiment`; canonical `main` has no market-data-cache table.
READY FOR BOUNDED FULL HISTORICAL BACKFILL INTO ISOLATED CACHE: TECHNICALLY YES; execution is owned by the separate backfill workstream and was not touched by the prior-close audit.
READY FOR CANONICAL/PRODUCTION CACHE ACTIVATION: NO — explicit user approval required.

## Security and isolation

- GET/read-only Upstox market-information paths only.
- no order placement/modification/cancellation surface.
- no portfolio, funds or account action surface.
- Analytics Token only via GitHub secret; no token/header in audit manifests.
- no production lifecycle/database writer connected to the structured evidence path.
- no canonical scoring, weight, probability, recommendation, efficacy or Learning Lab mutation.
- no production 5DR/EDGE writes.
- isolated Neon cache branch only; canonical Neon `main` unchanged by cache work.
- Upstox remains read-only and the production evidence workflow has no broker-order, account, funds or portfolio action surface.

## Current next gate

1. G11 is complete PASS; do not reacquire or repeat Manual Runs 1–3 or the 18 Sep rollover.
2. V2.2.3 structured evidence production is ACTIVE and now live-verified for both the late-morning and scheduled prior-close windows.
3. First scheduled prior-close production audit is PASS; do not repeat or reacquire it.
4. Build and separately validate the PREOPEN carry-forward + overnight/global refresh path before enabling the 08:45–09:00 window.
5. Automatic forecast publication/persistence remains disabled until a reusable exact-bundle-bound governed intelligence/release path is implemented without inventing methodology.
6. Historical backfill/export work is owned by the parallel chat and must not be duplicated here.
7. Trading remains disabled.
