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
- G11 PAIRED SCREENSHOT-ASSISTED VS STRUCTURED VALIDATION: ACTIVE / EVIDENCE COLLECTION PENDING — synchronization guard and multi-session observation harness are built and tested. The earlier ~57-minute temporal mismatch remains observational-only and does not count.
- G12 PRODUCTION RUNTIME / PERSISTENCE ACTIVATION: BLOCKED pending later approval and G11 review.
- G13 PRODUCTION MERGE / INTEGRATION: BLOCKED pending explicit user approval.
- ROUTINE SCREENSHOT RETIREMENT: NOT ACTIVATED pending G11 evidence review.

## G9 live governed web-context proof — 16 Sep 2026

Run `35079212997`, job `104739176929`, completed successfully.

- 198 experimental tests + 7 original Upstox safety tests = 205/205 PASS.
- live governed web-context executor returned `5DR_LIVE_WEB_CONTEXT_PASSED`.
- Fed H.15 official source: FACT_EXTRACTED, including source-dated 10Y Treasury and effective fed-funds observations.
- FOMC official calendar: FACT_EXTRACTED, including 15–16 Sep 2026 meeting and decision-day match.
- RBI official source: FACT_EXTRACTED, including policy repo rate and source-dated displayed USD/INR.
- ICE Dollar Index owner page: REFERENCE_ONLY because no approved numeric DXY extraction was available from the bounded page surface.
- OFAC geopolitics/sanctions page: REFERENCE_ONLY because no approved deterministic event interpretation was defined.
- REFERENCE_ONLY is not treated as neutral/no-event evidence and cannot fabricate a score.
- every item carries source URL, source-content SHA-256, research SHA-256 and retrieval timestamp.
- `forecast_released=false`, `production_5dr_write_enabled=false`, `trading_enabled=false`.

## G10 live shadow proof — 16 Sep 2026

Gate record `experiments/gate_records/G10_live_bound_shadow_2026-09-16.json` records PASS for workflow run `35078188409`, job `104735888140`.

- exact frozen evidence bundle SHA-256 was recomputed at handoff.
- screenshot dependency was false.
- governed judgment was bound to the exact bundle.
- existing source-neutral 5DR engine executed without publishing, recommendation release, production/lifecycle writes or trading.
- methodology_changed=false.
- D+1 through D+5 release zones remained deliberate non-release shadow placeholders; this proves handoff/engine execution rather than a production forecast release.

Gate record `experiments/gate_records/G10B_macro_enriched_shadow_2026-09-16.json` records `PASS_DIAGNOSTIC` for workflow run `35079827793`, job `104741049991`.

- official macro facts materially changed the diagnostic shadow interpretation while retaining NO_TRADE.
- this is evidence-quality progress, not a production methodology change and not a G11 parity verdict.

## G11 synchronized validation protocol

`experiments/g11_validation_protocol.json` is the active experiment-only protocol.

- required distinct comparable sessions: 3.
- target sessions: 17 Sep, 18 Sep and 21 Sep 2026.
- preferred experimental validation cutoff: 09:45 IST.
- reference mode: `SCREENSHOT_ASSISTED`.
- structured mode: `UPSTOX_STRUCTURED`.
- exact same comparison-window ID and exact same evidence cutoff are mandatory.
- temporal mismatch becomes observational-only and cannot count toward the three sessions.
- duplicate comparable trading sessions fail closed.
- `REVIEW_READY` means only three valid sessions were collected; it is not a PASS/FAIL or activation decision.
- no discrepancy threshold, acceptance threshold or production-activation rule is invented by this execution-layer experiment.

`experiments/shadow_validation.py` records DES5, Market Trust, Execution Edge, scenario-probability deltas, directional-label agreement and tradeability agreement while forcing `acceptance_decision_made=false` and `production_activation_decision_made=false`.

The previous record `experiments/gate_records/G11_observational_temporal_mismatch_2026-09-16.json` remains retained for audit. The two runs were about 56.6 minutes apart, so it is explicitly NOT_COMPARABLE and does not count toward G11.

Current-head regression run `35105317029`, job `104824888779`, SUCCESS:

- 207 experimental tests + 7 original Upstox safety tests = 214/214 PASS.
- authenticated Upstox preflight HTTP 200.
- manifested after-hours sample: PASS / `NORMAL_CLOSE` / `FRESHNESS_PASS` / `CLOSED_SESSION_FINAL`.
- 80.257-second after-hours pair correctly classified `EXPECTED_STATIC_NONTRADING_SESSION`, duplicate=true, `DUPLICATE_POLICY_PASS`.
- no production writes, lifecycle writes or trading.

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

1. Collect G11 same-cutoff paired observations for 17 Sep, 18 Sep and 21 Sep 2026 at the experimental 09:45 IST cutoff.
2. A screenshot-assisted reference and structured run count only if they share the same declared comparison window and evidence cutoff; otherwise record NOT_COMPARABLE.
3. After three distinct comparable sessions, produce `REVIEW_READY` observational summary for user review; do not auto-accept screenshot retirement or production activation.
4. The full 29-series / 90-call historical backfill remains optional and may run only into the isolated cache branch under existing budgets; it must never target canonical Neon `main` without explicit approval.
5. Final production run windows, persistent runtime activation, canonical integration and merge remain explicit later approval gates.
