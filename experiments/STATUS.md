# Experimental 5DR autonomous market-data status

PR #30 remains experimental, draft and unmerged. The Drive canonical specification is 5DR V2.2.3, an operational automation amendment only. Production forecasting/scoring semantics remain frozen and no experimental code is connected to the canonical production consumer without explicit approval.

## Current gate summary

- G1 CORE OPEN-MARKET ACQUISITION RELIABILITY: PASS — live proven.
- G2 OPTION IDENTITY / FRESHNESS / DUPLICATE / READ-ONLY BOUNDARY: PASS — live proven.
- G3 BROAD 5DR QUANTITATIVE UPSTOX UNIVERSE: PASS — live proven.
- G4 REPRESENTATIVE MULTI-TIMEFRAME HISTORICAL RETRIEVAL: PASS — live proven.
- G5 DETERMINISTIC CHART-STRUCTURE DERIVATION: PASS — offline tests and live Upstox historical proof; routine screenshots are technically replaceable at the chart-evidence layer.
- G6 FROZEN SCREENSHOT-FREE EVIDENCE BUNDLE CONTRACT: PASS — quantitative/chart/external evidence is fail-closed and bundle integrity is reverified at engine handoff.
- G7 DURABLE HISTORICAL CACHE / RUN LEDGER: PASS FOR ISOLATED SMOKE — hardened store, Postgres/Neon adapter, isolated Neon branch/schema and one provenance-bound durable NIFTY document have been written/read back successfully. Full historical backfill remains disabled.
- G8-A MARKET-CALENDAR-AWARE SCHEDULING POLICY: PASS offline; final production run windows not yet approved/activated.
- G8-B WATCHDOG / IDEMPOTENCY / MISSED-RUN POLICY: PASS offline; production trigger not yet activated.
- G9 AUTONOMOUS WEB-CONTEXT INGESTION: CONTRACT PASS, RUNTIME INCOMPLETE — governed V2.2.3 research facts are bounded, timestamped, source-hashed and research-fingerprinted. A fully autonomous live research executor is not yet connected.
- G10 END-TO-END AUTONOMOUS 5DR RUN: SHADOW PATH PASS OFFLINE — frozen structured evidence can be bound to a governed 5DR judgment and executed by the existing source-neutral engine with publish/write/trading disabled. A full live market + web + governed-judgment run is not yet proven.
- G11 SHADOW COMPARISON: MECHANICS PASS OFFLINE — comparison records DES5/Market Trust/Execution Edge/probability deltas and directional/tradeability agreement without making an acceptance decision. Actual screenshot-assisted versus structured-data paired runs are not yet started.
- G12 PRODUCTION RUNTIME / PERSISTENCE ACTIVATION: BLOCKED pending later approval and prior gates.
- G13 PRODUCTION MERGE / INTEGRATION: BLOCKED pending explicit user approval.
- ROUTINE SCREENSHOT RETIREMENT: NOT YET ACTIVATED pending real shadow comparison.

## Open-market reliability proof — 16 Sep 2026

Burst run `35054637198`, job `104662116005`, completed successfully:

- 09:45: PASS / ADVANCED; 79.302s pair.
- 10:00: PASS / ADVANCED; 79.306s pair.
- 10:15: PASS / ADVANCED; 79.251s pair.
- 10:30: PASS / ADVANCED; 78.994s pair.
- NFO remained `NORMAL_OPEN`; selected expiry remained 22 Sep 2026.
- Every checkpoint had distinct first/second snapshot fingerprints and manifest hashes.
- `production_5dr_write_enabled=false`; `trading_enabled=false` throughout.

Latest regression/live verification after G9/G10 shadow hardening: run `35069494948`, job `104707391688`, SUCCESS.

- 168 experimental tests + 7 original Upstox safety tests = 175/175 PASS.
- authenticated Upstox preflight HTTP 200.
- manifested live sample: PASS / `NORMAL_OPEN` / `FRESHNESS_PASS` / `LIVE_OPEN`.
- 75-second reliability pair: `ADVANCED`, duplicate=false, `RELIABILITY_PAIR_PASSED`.
- first latest candle 13:06 IST; second latest candle 13:08 IST.
- first spot approximately 23271.8; second spot approximately 23276.9.
- no production 5DR writes and no trading actions.

## Broad quantitative live proof

Run `35060738861`, job `104680311692`, status `5DR_QUANT_BACKBONE_BROAD_PROBE_PASSED`.

Live-proven families include NIFTY/India VIX/nearest NIFTY future; NIFTY 15m/30m/1h; FII cash/index futures/index options; DII cash; OI/change-OI/PCR/max pain; GIFT Nifty, S&P 500, Dow, US Tech 100, DAX, FTSE 100, Nikkei 225, Hang Seng, Brent, WTI and USD/INR. Provider-declared latency remains explicit and derivative expiry identity is normalized strictly.

Qualitative/event fields unavailable from Upstox remain `OFFICIAL_WEB` / `WEB_RESEARCH` evidence. They are never fabricated or proxied as authenticated broker data.

## Historical and live chart proof

Representative history run `35061881459`, job `104683799954`, used exactly eight authenticated read-only GETs and returned `5DR_REPRESENTATIVE_HISTORY_PROBE_PASSED`.

Validated sample counts: NIFTY 5m 300; 15m 100; 30m 52; 1h 28; 1d 31; India VIX 1d 31; S&P 500 1d 32; Brent 1d 31.

Live chart derivation run `35065714571`, job `104695407603`, returned `5DR_LIVE_CHART_DERIVATION_PASSED` using exactly five authenticated read-only historical GETs.

Real NIFTY history processed: 5m 675 bars (execution-only), 15m 225, 30m 117, 1h 63, 1d 62. The engine derives swing/trend structure, prior-range acceptance/break state, liquidity sweeps, failed breakouts, recent gaps and multi-timeframe alignment directly from OHLC history. Index volume was zero/non-applicable, so volume/VWAP were explicitly marked unavailable instead of fabricated. Futures/derivative participation remains the valid volume/OI confirmation lane.

The live chart probe explicitly returned `screenshot_required=false`, `directional_score_assigned=false`, `forecast_released=false`, `production_5dr_write_enabled=false` and `trading_enabled=false`.

## Durable-cache proof

The bounded initial 5DR historical plan contains 29 series / 90 planned calls / 115,305-row upper bound under explicit ceilings of 250 calls, 250,000 retained rows and zero planned billable units.

Previous safeguards:

- dry run PASS — run `35062522905`, job `104685665398`; zero provider calls and zero writes.
- one-chunk ephemeral live smoke PASS — run `35062661078`, job `104686085567`; one NIFTY 5m historical GET, 300 rows, process-local memory only.
- reconciliation PASS — overlap dedupe, provider-correction audit, retention, tamper detection and deterministic dataset fingerprinting.
- provider-neutral `MarketCacheStore` PASS with atomic test-only reference backend.
- store-backed executor bridge PASS — writes must traverse reconciliation + validated document + compare-and-swap boundary.
- canonical/lifecycle storage is rejected by the cache adapter.
- test reference storage cannot be promoted by configuration accident.
- `PostgresMarketCacheStore` PASS offline with JSONB document storage, transactional readback validation, compare-and-swap conflict protection and `canonical_5dr_storage=false`; `production_approved=false` remains the default.

Live isolated durable smoke — 16 Sep 2026:

- Neon project: `5DR V2`, project id `flat-fire-21633692`.
- canonical/default branch remains `main` (`br-sweet-queen-aysaf1mw`).
- isolated experimental branch created: `market-data-cache-v223-experiment` (`br-gentle-math-aybvyzt5`), non-default and non-primary.
- isolated schema: `market_data_cache`.
- isolated table: `market_data_cache.market_cache_documents`.
- schema diff versus canonical `main` contains only the new cache schema/table/constraints/index; canonical public lifecycle tables are unchanged.
- one real read-only Upstox NIFTY intraday smoke document was persisted with source provenance from the authenticated live sample and read back successfully.
- persisted series id: `5DR:SMOKE:NIFTY_50:1m:2026-09-16T07:36Z`.
- persisted document SHA-256: `2c8aac84cabc7bf2c9ac5b9912a0cb7669b18877a849a04efc269f49265001ff`.
- persisted dataset SHA-256: `4a99149207ba83c07a52bc58c564be172e3dd799a3bb5613811faaf5ca893525`.
- database and JSON document hashes matched on durable readback; record count was exactly 1.
- direct canonical-main check confirmed `market_data_cache.market_cache_documents` is absent on canonical `main`.

This durable smoke used the validated document/hash contract on the isolated branch. The connected GitHub tool does not expose repository-secret write capability, so a Neon credential was not copied into the repository or logs merely to force an online Python-adapter test. Offline adapter tests plus live isolated schema/document/readback establish the current proof boundary without weakening credential security.

READY FOR BOUNDED FULL HISTORICAL BACKFILL INTO ISOLATED CACHE: TECHNICALLY YES; NOT YET RUN.
READY FOR CANONICAL/PRODUCTION CACHE ACTIVATION: NO.

## V2.2.3 governed web-context contract

Commits `1d1e1d681872a2e1094d2a9e3928fd900cb6e2a4`, `79765ebd721bb6b217b86390a0fad820bd1fd7d7` and `a2d9c7b641c45dfc508452beb498b4e5afd5ddb4` add and verify the governed external research lane.

- schema `5dr-web-context-evidence-v1`.
- default required external categories: `DXY_RATES` and `MACRO_EVENTS_GEOPOLITICS`.
- source semantic restricted to `OFFICIAL_WEB` or `WEB_RESEARCH`.
- HTTPS source reference, source-content SHA-256, authority, observed/retrieved timestamps and bounded fact summary are mandatory.
- a deterministic `research_sha256` binds the exact fact summary to its provenance.
- tampered facts, stale research, missing required categories, duplicate research fingerprints and non-HTTPS references fail closed.
- rich web facts are preserved inside the frozen evidence bundle rather than reducing web research to a reachability hash.

The missing G9 piece is runtime acquisition/interpretation: GitHub Actions cannot autonomously invoke the ChatGPT research/intelligence layer merely because this contract exists. A governed research executor must supply the validated facts.

## Structured engine handoff and shadow path

Commits `e2dd242f7b7e5ef9053407008ac9c42bcb9d9188`, `921b9bcfe404040a860442f3ff3d33afc05b903d`, `6c29e692fcc7dd24a9dd6d22d4d20eff94fa103e`, `a67e8cc86475aa6c673e3f08490dbf2be278a980`, `49e657624e4509191d2c1e505c54c2017e39caf9` and `c877d51e1a7f634333b08111424e914d8a15d323` establish the V2.2.3 structured forecast shadow boundary.

- frozen bundle status must be `READY` and screenshot dependency must be false.
- bundle SHA-256 is recomputed from contents at handoff; post-freeze mutation is rejected.
- governed judgment schema is `5dr-v2-2-3-governed-judgment-v1`.
- judgment must be cryptographically bound to the exact frozen bundle.
- `methodology_changed` must be false.
- the judgment supplies only the normalized fields already required by the existing source-neutral 5DR engine; no new raw-score thresholds are hard-coded.
- shadow execution uses the existing `src/composed_engine.py` + `src/orchestrator.py` path.
- shadow output forces `published=false`, `forecast_release_enabled=false`, `production_5dr_write_enabled=false`, `lifecycle_write_enabled=false`, `trading_execution_enabled=false` and `methodology_changed=false`.
- comparison mode reports DES5, Market Trust, Execution Edge and BULL/RANGE/BEAR probability deltas plus directional/tradeability agreement, but sets `acceptance_decision_made=false`.

This preserves the intelligence/judgment layer where the frozen specification does not define deterministic machine thresholds. Hard-coding new numeric mappings from raw market facts into ±2 scores would be a methodology change and remains outside this automation amendment.

## Timing controls

The pure autonomous schedule/watchdog policy preserves Asia/Kolkata and the existing 15:20 prior-day / 09:15 target-day canonical boundary, supports configurable bounded windows, NSE closed/special-open dates, deterministic run-key idempotency and `UPCOMING`, `DUE`, `COMPLETED`, `MISSED` states. A missed run is exposed as `MISSED`; late evidence does not silently masquerade as on-time evidence.

Final production run windows and production triggers remain disabled pending approval.

## Security and isolation

- GET/read-only Upstox market-information paths only.
- no order placement/modification/cancellation surface.
- no portfolio, funds or account action surface.
- Analytics Token only via GitHub secret; no token/header in audit manifests.
- no production lifecycle/database writer is connected to the experimental data path.
- no canonical scoring, weight, probability, recommendation, efficacy or Learning Lab mutation.
- no production 5DR/EDGE writes.
- isolated Neon cache branch only; canonical Neon `main` unchanged.
- PR #30 remains draft/unmerged.

## Current next gate

1. Build the live G9 research-executor handoff so current DXY/rates and macro/event/geopolitical facts enter `5dr-web-context-evidence-v1` with auditable provenance; missing/failed sources must block rather than imply `no event`.
2. Execute at least one full non-publishing live shadow run using current Upstox quantitative/chart evidence + current governed web context + a bundle-bound 5DR intelligence judgment.
3. Run paired screenshot-assisted versus structured-data shadow observations before retiring routine screenshots. Comparison is observational; acceptance criteria must be separately governed rather than invented ad hoc.
4. Full 29-series / 90-call historical backfill may now be executed only into the isolated cache branch with the existing call/row/billable-unit budgets; it must not target canonical Neon `main`.
5. Final production run windows, persistent runtime activation, canonical integration and merge remain explicit later approval gates.
