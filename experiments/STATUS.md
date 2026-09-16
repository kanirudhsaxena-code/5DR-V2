# Experimental market-data acquisition status

Canonical 5DR V2.2.2 remains untouched. PR #30 stays experimental and must not be merged or connected to production consumers without explicit approval.

## Core acquisition gates

- BUILT: PASS — isolated read-only Upstox acquisition, hardened curl transport, exact CE/PE identity, NFO session guard, freshness validation, deterministic snapshot fingerprints, duplicate policy and sanitized manifests exist.
- TESTED: PASS — before the current cache-reconciliation checkpoint, run `35062661078` passed 101 experimental tests plus 7 original Upstox safety tests = 108/108 PASS.
- LIVE VERIFIED: PASS — authenticated NIFTY spot/candles/options plus the broader provisioned quantitative families are live proven.
- RELIABILITY VERIFIED: PASS — closed-session behavior, open-session advancement and the four-window burst are proven.
- REPRESENTATIVE HISTORY VERIFIED: PASS — eight bounded historical calls completed successfully in run `35061881459`, job `104683799954`.
- BACKFILL PLAN DRY RUN: PASS — 29 series / 90 planned calls / 115,305-row upper bound; zero provider calls and zero writes in run `35062522905`, job `104685665398`.
- SINGLE-CHUNK EXECUTION SMOKE: PASS — one authenticated NIFTY 5m historical call, 300 rows, one ephemeral-memory write and zero persistent writes in run `35062661078`, job `104686085567`.
- READY FOR DURABLE CACHE BACKEND DESIGN: YES.
- READY FOR FULL HISTORICAL BACKFILL: NO — no durable cache backend has been approved or connected.
- READY FOR PRODUCTION 5DR INTEGRATION: NO — integration remains a separate explicit approval gate.

## Open-market reliability proof — 16 Sep 2026

Burst run `35054637198`, job `104662116005`, completed successfully:

- 09:45: PASS / ADVANCED; 79.302s pair; zero startup lateness.
- 10:00: PASS / ADVANCED; 79.306s pair; zero startup lateness.
- 10:15: PASS / ADVANCED; 79.251s pair; zero startup lateness.
- 10:30: PASS / ADVANCED; 78.994s pair; zero startup lateness.
- NFO remained `NORMAL_OPEN`; selected expiry remained 22 Sep 2026.
- Every checkpoint had distinct first/second snapshot fingerprints and manifest hashes.
- `production_5dr_write_enabled=false`; `trading_enabled=false` throughout.

## Broad quantitative live proof

Run `35060738861`, job `104680311692`, status `5DR_QUANT_BACKBONE_BROAD_PROBE_PASSED`.

Live-proven families include NIFTY/India VIX/nearest NIFTY future; NIFTY 15m/30m/1h; FII cash/index futures/index options; DII cash; OI/change-OI/PCR/max pain; GIFT Nifty, S&P 500, Dow, US Tech 100, DAX, FTSE 100, Nikkei 225, Hang Seng, Brent, WTI and USD/INR. Global indices use the quote surface; Brent/WTI/USDINR use the candle surface. Provider-declared latency remains explicit. OI/change-OI expiry identity is compared semantically after strict ISO/DD-MM-YYYY normalization.

## Representative historical proof

Run `35061881459`, job `104683799954`, used exactly eight authenticated read-only GETs and returned `5DR_REPRESENTATIVE_HISTORY_PROBE_PASSED`.

Validated counts:

- NIFTY 5m: 300 candles (9–15 Sep 2026).
- NIFTY 15m: 100 candles.
- NIFTY 30m: 52 candles.
- NIFTY 1h: 28 candles.
- NIFTY 1d: 31 candles (3 Aug–15 Sep 2026 trading dates).
- India VIX 1d: 31 candles.
- S&P 500 1d: 32 candles.
- Brent 1d: 31 candles.

The probe explicitly reported `full_backfill_started=false`, `cache_storage_write_enabled=false`, `production_5dr_write_enabled=false`, `canonical_integration_enabled=false` and `trading_enabled=false`.

## Backfill/cache execution safeguards

Commit `bac4535fbdbb34d933462c129ea99dc8b502b83d` introduced a bounded 5DR-only candle inventory and dry-run-first executor. The initial plan contains 29 series and 90 calls under explicit ceilings of 250 calls, 250,000 retained rows and zero billable units. A complete cache eliminates all calls; a partial cache plans only the missing tail with a one-day overlap for safe deduplication.

Commit `dc5220f2a4fed8cdd8a5ddb477edbd3597cd6e37` added plan integrity verification and the first live executor smoke. Plan fingerprint, series count, call count and row estimate are verified before any provider call. Network and storage writes have independent explicit gates. The live smoke made exactly one authenticated GET for NIFTY 5m (9–15 Sep), received 300 candles and wrote them only to process-local ephemeral memory. No persistent cache, database or canonical lifecycle write occurred.

## Provider-neutral data-core checkpoint

The experiment contains a common normalized evidence contract, declarative requirements for 5DR/EDGE Stocks/IPO EDGE, cost-aware request policy, incremental planning, usage budgets, generic read-only provider boundary and Upstox adapter. EDGE Stocks and IPO EDGE remain provisioned but background-disabled. There is no all-stock collection, all-option-chain archive, tick archive or 30-level depth archive.

Consumers depend on the normalized data contract rather than Upstox response schemas. Upstox remains semantically `UPSTOX_AUTHENTICATED`; it is never relabelled as SCREENSHOT or WEB_RESEARCH. Qualitative/event fields unavailable from Upstox remain external evidence rather than being fabricated or proxied.

## Security and isolation

- GET/read-only market-information paths only.
- No order placement/modification/cancellation surface.
- No portfolio, funds or account action surface.
- Analytics Token only via GitHub secret; no token/header in audit manifests.
- No database credential or production lifecycle writer in this experiment.
- No canonical scoring, weights, probability, recommendation, efficacy or Learning Lab changes.
- No production 5DR/EDGE writes.
- PR #30 remains draft/unmerged.

## Current next gate

Validate the storage-neutral cache reconciliation contract (exact-overlap deduplication, explicit provider-correction audit, deterministic dataset fingerprints and retention) entirely offline. After that, durable cache persistence is a separate architecture/approval gate. Full 6/12-month backfill remains disabled until a durable backend is explicitly approved and isolated from canonical lifecycle storage.
