# Experimental 5DR autonomous market-data status

PR #30 remains experimental, draft and unmerged. The Drive canonical specification is 5DR V2.2.3, an operational automation amendment only. Production forecasting/scoring semantics remain frozen and no experimental code is connected to the canonical production consumer without explicit approval.

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
- G11 PAIRED SCREENSHOT-ASSISTED VS STRUCTURED VALIDATION: ACTIVE under protocol v2. One comparable manual pair is counted on 17 Sep 2026. A second structured capture is preserved but has no verified screenshot-assisted mate within the pairing window and therefore does not count.
- G12 PRODUCTION RUNTIME / PERSISTENCE ACTIVATION: BLOCKED pending G11 review and explicit user approval.
- G13 PRODUCTION MERGE / INTEGRATION: BLOCKED pending explicit user approval.
- ROUTINE SCREENSHOT RETIREMENT: NOT ACTIVATED pending G11 evidence review.

## G11 active validation protocol — v2

`experiments/g11_validation_protocol.json` is authoritative for the active experiment-only G11 collection protocol.

- schema: `5dr-v2-2-3-g11-validation-protocol-v2`.
- required manual paired observations: 3.
- required distinct sessions for the primary series: 1.
- all three primary manual runs must belong to the same live NSE session.
- every run requires an explicit user-approved manual trigger and a distinct manual run id.
- reference mode: `SCREENSHOT_ASSISTED`.
- structured mode: `UPSTOX_STRUCTURED`.
- same manual run / comparison-window identity is required.
- exact same evidence timestamp is not required.
- <=180 seconds evidence-time delta is preferred.
- >180 and <=300 seconds remains comparable-with-tolerance and must preserve the measured delta.
- >300 seconds is observational-only and cannot count.
- after three distinct comparable manual runs in one session, status may become `REVIEW_READY` only.
- `REVIEW_READY` is not PASS, screenshot-retirement approval, production activation, methodology change or merge approval.
- after the primary three-run series, one lightweight next-session rollover validation remains required to verify new-session identity and prior-session stale-data rejection.
- no numeric market-output discrepancy threshold or automatic acceptance rule is invented by this execution-layer experiment.

`experiments/shadow_validation.py` records DES5, Market Trust, Execution Edge, BULL/RANGE/BEAR probability deltas, directional-label agreement and tradeability-semantics agreement while forcing acceptance and production-activation decisions false.

The historical `experiments/gate_records/G11_observational_temporal_mismatch_2026-09-16.json` remains retained for audit. That earlier pair was about 56.6 minutes apart and is NOT_COMPARABLE.

### 17 Sep scheduled 09:45 structured capture — preserved, not counted

The earlier scheduled structured capture `G11-20260917-0945` remains valid structured evidence but has no matching 09:45 screenshot-assisted reference and therefore cannot count as a G11 pair.

- evidence cutoff: 09:45:00 IST.
- capture start: 09:45:00.000323 IST.
- capture start lag: 0.000 seconds.
- bundle freeze: 09:45:45.243133 IST.
- bundle freeze lag: 45.243 seconds.
- bundle SHA-256: `af79ffc940260053b388a7420d9f435e589baa6659ffc3f133f40d218604a04a`.
- capture SHA-256: `b24e472725ef9ea3cde7305eb4a9d830485b15407348a09841c552fb5357181a`.
- cache save succeeded.
- no forecast release, canonical integration, production/lifecycle write or trading was enabled.

### Manual Run 1 — counted comparable observation

Manual Run 1 `G11-20260917-104405` is the first counted comparable v2 observation.

- session: 17 Sep 2026.
- structured cutoff: 10:44:05.440624 IST.
- bundle freeze: 10:44:51.945028 IST.
- bundle SHA-256: `6fe9de7c379feecd5bb759e6a7eedec328af08f0a8278ae1b66abc8e621f105e`.
- screenshot-assisted evidence was captured around 10:42:53–10:43:41 IST and was within the protocol's preferred <=180-second pairing tolerance.
- immutable cache restore/public-summary verification succeeded.
- no production/lifecycle write, canonical integration or trading was enabled.

This is one comparable observation only; it is not an overall G11 PASS decision.

### Manual Run 2 — structured side preserved, pair incomplete

Manual Run 2 `G11-20260917-134141` was explicitly marked user-approved in `.g11/trigger.txt` and its structured workflow succeeded.

- structured workflow run: `35198366973`.
- structured cutoff / capture start: 13:41:41.840036 IST.
- capture start lag: 0.000 seconds.
- bundle freeze: 13:42:24.256125 IST.
- bundle freeze lag: 42.416 seconds.
- bundle SHA-256: `afe6d95ec65abbc3f5e3f53c1a084f84d693cbfb91b54bf214e013658573603a`.
- capture SHA-256: `38c3b1af59666db58e9a439a53e52cd7fc19150f5c07f5089a9d4a53678c5eb0`.
- cache save succeeded and cached-summary restoration succeeded.
- no forecast release, canonical integration, production/lifecycle write or trading was enabled.
- no verified screenshot-assisted Run 2 reference is available within the <=300-second pairing window.

Therefore Run 2 is retained as valid structured evidence but is NOT COUNTED as a paired G11 observation. No screenshot reference is fabricated or borrowed from another time window.

### Current G11 count

- comparable paired manual observations counted: 1 / 3.
- valid structured-only observations retained but not counted: scheduled 09:45 capture and Manual Run 2.
- `REVIEW_READY`: NO.
- screenshot retirement: NO.
- production structured-data runtime activation: NO.
- PR #30 merge approval: NO.

## G9 live governed web-context proof — 16 Sep 2026

Run `35079212997`, job `104739176929`, completed successfully.

- live governed web-context executor returned `5DR_LIVE_WEB_CONTEXT_PASSED`.
- Fed H.15 official source: FACT_EXTRACTED, including source-dated 10Y Treasury and effective fed-funds observations.
- FOMC official calendar: FACT_EXTRACTED, including 15–16 Sep 2026 meeting and decision-day match.
- RBI official source: FACT_EXTRACTED, including policy repo rate and source-dated displayed USD/INR.
- ICE Dollar Index owner page: REFERENCE_ONLY where no approved numeric DXY extraction was available from the bounded page surface.
- OFAC/geopolitical pages: REFERENCE_ONLY where no approved deterministic event interpretation was defined.
- REFERENCE_ONLY is not treated as neutral/no-event evidence and cannot fabricate a score.
- every governed item carries source URL, source-content SHA-256, research SHA-256 and retrieval timestamp.
- `forecast_released=false`, `production_5dr_write_enabled=false`, `trading_enabled=false`.

## G10 live shadow proof — 16 Sep 2026

Gate record `experiments/gate_records/G10_live_bound_shadow_2026-09-16.json` records PASS for workflow run `35078188409`, job `104735888140`.

- exact frozen evidence bundle SHA-256 was recomputed at handoff.
- screenshot dependency was false.
- governed judgment was bound to the exact bundle.
- existing source-neutral 5DR engine executed without publishing, recommendation release, production/lifecycle writes or trading.
- `methodology_changed=false`.
- D+1 through D+5 release zones remained deliberate non-release shadow placeholders; this proves handoff/engine execution rather than a production forecast release.

Gate record `experiments/gate_records/G10B_macro_enriched_shadow_2026-09-16.json` records `PASS_DIAGNOSTIC` for workflow run `35079827793`, job `104741049991`.

- official macro facts materially changed the diagnostic shadow interpretation while retaining NO_TRADE.
- this is evidence-quality progress, not a production methodology change and not a G11 parity verdict.

## Current-head regression state

Branch head immediately before this status reconciliation was `c05b78869869100b73dbe6eb7920945b05918c67` (`[g11-compare] summarize manual run 2 cached evidence`).

CI run `35198481895`, job `105127257879`, SUCCESS:

- 424 tests passed + 5 subtests passed.
- no production activation is implied by CI success.

## Core market-data proof retained

Open-market burst run `35054637198`, job `104662116005`: 09:45 / 10:00 / 10:15 / 10:30 all PASS and ADVANCED during `NORMAL_OPEN`.

Broad quantitative run `35060738861`, job `104680311692`: PASS for NIFTY, India VIX, nearest NIFTY future, NIFTY 15m/30m/1h, FII/DII, OI/change-OI/PCR/max-pain, GIFT Nifty, S&P 500, Dow, US Tech 100, DAX, FTSE 100, Nikkei 225, Hang Seng, Brent, WTI and USD/INR. Provider latency remains explicit.

Representative history run `35061881459`, job `104683799954`: PASS with exactly eight authenticated read-only GETs. Validated sample counts: NIFTY 5m 300; 15m 100; 30m 52; 1h 28; 1d 31; India VIX 1d 31; S&P 500 1d 32; Brent 1d 31.

Live chart derivation run `35065714571`, job `104695407603`: PASS. Real NIFTY history processed at 5m/15m/30m/1h/1d and deterministic chart structure derived without assigning forecast direction or fabricating index volume/VWAP.

## Durable-cache and cost boundary

The bounded initial 5DR historical plan remains 29 series / 90 planned calls / 115,305-row upper bound under ceilings of 250 calls, 250,000 retained rows and zero planned billable units.

- dry run `35062522905`: PASS, zero provider calls/writes.
- one-chunk ephemeral smoke `35062661078`: PASS, one NIFTY 5m GET / 300 rows / no persistent write.
- isolated Neon experimental branch `market-data-cache-v223-experiment`; canonical Neon `main` unchanged.
- isolated schema `market_data_cache`; canonical lifecycle tables unchanged.
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

1. Preserve the one counted 17 Sep Manual Run 1 observation and the non-counted structured-only captures without relabelling them.
2. Any next counted manual pair must begin only after explicit user approval at the time of capture and the screenshot-assisted evidence must be captured immediately for the same manual run, within the v2 <=300-second maximum pairing window.
3. The primary G11 series requires three comparable manual runs in one live NSE session. Do not combine observations from different sessions to reach 3/3.
4. After a valid same-session 3/3 primary series is collected, perform the separate next-session rollover check. Only then produce `REVIEW_READY` for governed user review; do not auto-pass, retire screenshots, activate production or merge PR #30.
5. The full 29-series / 90-call historical backfill remains optional and disabled unless separately justified/approved for the isolated cache. It must never target canonical Neon `main` without explicit approval.
6. Final production run windows, persistent runtime activation, canonical integration and merge remain explicit later approval gates.
