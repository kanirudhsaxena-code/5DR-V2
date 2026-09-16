# Experimental 5DR autonomous market-data status

PR #30 remains experimental, draft and unmerged. The Drive canonical specification is now 5DR V2.2.3, an operational automation amendment only. Production forecasting/scoring semantics remain frozen and no experimental code is connected to the canonical production consumer without explicit approval.

## Current gate summary

- G1 CORE OPEN-MARKET ACQUISITION RELIABILITY: PASS.
- G2 OPTION IDENTITY / FRESHNESS / DUPLICATE / READ-ONLY BOUNDARY: PASS.
- G3 BROAD 5DR QUANTITATIVE UPSTOX UNIVERSE: PASS — live proven.
- G4 REPRESENTATIVE MULTI-TIMEFRAME HISTORICAL RETRIEVAL: PASS — live proven.
- G5 DETERMINISTIC CHART-STRUCTURE DERIVATION: PASS — offline tests and live Upstox historical proof.
- G6 FROZEN SCREENSHOT-FREE EVIDENCE BUNDLE CONTRACT: PASS offline; full production orchestration not yet connected.
- G7 DURABLE HISTORICAL CACHE / RUN LEDGER: IN PROGRESS — hardened store boundary plus isolated Postgres/Neon-capable adapter pass offline; no real durable backend has been approved or connected.
- G8-A MARKET-CALENDAR-AWARE SCHEDULING POLICY: PASS offline; final production run windows not yet approved/activated.
- G8-B WATCHDOG / IDEMPOTENCY / MISSED-RUN POLICY: PASS offline; production trigger not yet activated.
- G9 AUTONOMOUS WEB-CONTEXT INGESTION: PARTIAL SCAFFOLDING EXISTS; existing governed event/web modules must be adapted to V2.2.3 evidence-bundle semantics and live-proven before production use.
- G10 END-TO-END AUTONOMOUS 5DR RUN: IN PROGRESS. Existing source-neutral engine/orchestrator can accept AUTOMATED normalized evidence, but deterministic V2.2.3 evidence-to-engine normalization is the current missing forecast-generation bridge.
- G11 SHADOW COMPARISON: EXISTING V2.2.2 SHADOW SCAFFOLDING EXISTS but is lifecycle/evidence oriented and still assumes the legacy screenshot/web EvidencePacket boundary; V2.2.3 structured-data forecast shadow path is not yet live-proven.
- G12 PRODUCTION RUNTIME / PERSISTENCE ACTIVATION: BLOCKED pending later approval and prior gates.
- G13 PRODUCTION MERGE / INTEGRATION: BLOCKED pending explicit user approval.
- ROUTINE SCREENSHOT RETIREMENT: NOT YET ACTIVATED; evidence-layer chart dependency is now technically replaceable.

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

Live-proven families include NIFTY/India VIX/nearest NIFTY future; NIFTY 15m/30m/1h; FII cash/index futures/index options; DII cash; OI/change-OI/PCR/max pain; GIFT Nifty, S&P 500, Dow, US Tech 100, DAX, FTSE 100, Nikkei 225, Hang Seng, Brent, WTI and USD/INR. Provider-declared latency remains explicit and derivative expiry identity is normalized strictly.

Qualitative/event fields unavailable from Upstox remain OFFICIAL_WEB / WEB_RESEARCH evidence. They are never fabricated or proxied as authenticated broker data.

## Representative historical proof

Run `35061881459`, job `104683799954`, used exactly eight authenticated read-only GETs and returned `5DR_REPRESENTATIVE_HISTORY_PROBE_PASSED`.

Validated counts:

- NIFTY 5m: 300 candles.
- NIFTY 15m: 100 candles.
- NIFTY 30m: 52 candles.
- NIFTY 1h: 28 candles.
- NIFTY 1d: 31 candles.
- India VIX 1d: 31 candles.
- S&P 500 1d: 32 candles.
- Brent 1d: 31 candles.

No full backfill, persistent cache write, production 5DR write, canonical integration or trading action occurred.

## Live chart-derivation proof

Commit `27edaa729b2f7b19ab3a11c25cd9c3f2e70e6f40`; run `35065714571`, job `104695407603`.

Status: `5DR_LIVE_CHART_DERIVATION_PASSED` using exactly five authenticated read-only historical GETs.

Real NIFTY candle history processed:

- 5m: 675 bars; execution-only.
- 15m: 225 bars.
- 30m: 117 bars.
- 1h: 63 bars.
- 1d: 62 bars.

The engine derived swing/trend structure, prior-range acceptance/break state, liquidity-sweep state, failed-breakout state, recent gaps and multi-timeframe alignment directly from OHLC history. The live sample produced a mixed multi-timeframe alignment, which is evidence rather than a forecast or recommendation.

NIFTY index volume was zero/non-applicable in the sampled series. The engine therefore returned `VOLUME_NOT_APPLICABLE_OR_UNAVAILABLE` and `VOLUME_UNAVAILABLE` for anchored VWAP rather than manufacturing volume evidence. Futures/derivative participation remains the valid lane for volume/OI confirmation.

The probe explicitly returned `screenshot_required=false`, `directional_score_assigned=false`, `forecast_released=false`, `cache_storage_write_enabled=false`, `production_5dr_write_enabled=false`, `canonical_integration_enabled=false` and `trading_enabled=false`.

## Backfill and durable-cache safeguards

The bounded initial 5DR historical plan contains 29 series / 90 planned calls / 115,305-row upper bound under explicit ceilings of 250 calls, 250,000 retained rows and zero planned billable units.

- Dry run: PASS — run `35062522905`, job `104685665398`; zero provider calls and zero writes.
- Single-chunk live smoke: PASS — run `35062661078`, job `104686085567`; one NIFTY 5m historical GET, 300 rows, process-local ephemeral memory only.
- Reconciliation: PASS — overlap dedupe, provider correction audit, retention, tamper detection and deterministic dataset fingerprinting.
- Provider-neutral `MarketCacheStore`: PASS with atomic test-only reference backend.
- Store-backed executor bridge: PASS — commit `3035937b6ba8f745193f5e741145549267fc2f8b`; executor writes must traverse reconciliation + validated document + compare-and-swap boundary.
- Canonical/lifecycle storage is explicitly rejected by the cache adapter.
- Test reference storage cannot be promoted by configuration accident.
- Isolated Postgres/Neon-capable backend: PASS offline — commits `98c0ce3535715fc398e79378eec263b606406ca8` and test-fix `1ca414309ba9ae9243cc111586f7d65433c853e3`; JSONB document storage, transactional readback validation, compare-and-swap conflict protection, provider-neutral descriptor and `canonical_5dr_storage=false` are enforced. `production_approved=false` remains the default.
- CI for the corrected durable adapter: run `35066068737`, job `104696520531`, SUCCESS. No network, cache, production or lifecycle writes occurred.

READY FOR DURABLE CACHE BACKEND SELECTION: YES.
READY FOR FULL HISTORICAL BACKFILL: NO — no real durable backend has been approved/connected.

## Screenshot-free evidence and timing controls

Commit `1833cd659fe651488190c6dfcc63b91d2ced09fa` finalized deterministic chart-structure tests without weakening fail-closed validation.

Commit `b1c69457e132e3cc131a66e7c396a8ac7967ad68` added the pure autonomous schedule/watchdog policy:

- Asia/Kolkata canonical timezone.
- existing 15:20 prior-day / 09:15 target-day canonical boundary preserved.
- configurable bounded run windows.
- NSE closed-date and special-open-date injection.
- deterministic per-window run key for idempotency.
- `UPCOMING`, `DUE`, `COMPLETED`, `MISSED` states.
- a missed run is exposed as `MISSED`; late evidence is not silently masqueraded as an on-time forecast.

Commit `16b06ae0037c57886b4df2e629498750d16da089` added `5dr-frozen-evidence-bundle-v1`:

- only validated 5DR quantitative records may enter.
- required machine variables must be present.
- 1d/1h/30m/15m chart evidence is mandatory at the bundle boundary; 5m remains execution-only.
- official/web context remains a separate explicit evidence lane.
- required missing web context blocks the bundle rather than being inferred.
- duplicate evidence is rejected.
- screenshot dependency is visible and can be prohibited.
- the bundle itself cannot score, forecast, trade or write production 5DR.

## Existing V2.2.2 autonomy scaffold audit

The repository already contains reusable source-neutral forecast-engine components: `src/engine_contract.py`, `src/composed_engine.py`, `src/orchestrator.py` and `src/runner.py`. The engine contract already accepts provenance mode `AUTOMATED` and the deterministic composed engine preserves the existing model/output versions and scoring primitives.

Separate V2.2.2 modules such as `src/evidence_bridge.py`, `src/evidence_handoff.py`, `src/production_activation.py` and `src/shadow_e2e.py` are primarily recommendation-lifecycle/evidence-accounting infrastructure. Their EvidencePacket source types remain intentionally limited to `SCREENSHOT` and `WEB_RESEARCH`; authenticated Upstox evidence must not be falsely relabelled to cross that boundary.

Therefore V2.2.3 should reuse the source-neutral forecast engine while adding a distinct structured-data forecast handoff. The next bridge must transform governed V2.2.3 machine/chart/web evidence into the already-approved engine inputs without changing the frozen scoring semantics. Hard-coding new numeric/raw-score thresholds that are not already specified would constitute a methodology change and is not authorized by this automation amendment.

Latest offline CI before the chart live proof: run `35065505693`, job `104694767102` — 145 experimental tests + 7 original safety tests = 152/152 PASS. The chart live-proof run repeated the same 145 + 7 tests successfully before completing the authenticated chart derivation.

## Security and isolation

- GET/read-only market-information paths only.
- No order placement/modification/cancellation surface.
- No portfolio, funds or account action surface.
- Analytics Token only via GitHub secret; no token/header in audit manifests.
- No production lifecycle/database writer is connected to the experimental data path.
- No canonical scoring, weight, probability, recommendation, efficacy or Learning Lab mutation.
- No production 5DR/EDGE writes.
- PR #30 remains draft/unmerged.

## Current next gate

1. Implement the V2.2.3 structured-evidence-to-existing-engine handoff without relabelling Upstox as screenshot/web evidence and without inventing new scoring thresholds. Preserve the intelligence/judgment layer wherever the frozen specification does not define a deterministic machine threshold.
2. Adapt the existing governed official/web research scaffold into the V2.2.3 frozen evidence bundle and prove that missing/failed sources block rather than imply `no event`.
3. Select/connect an isolated durable market-cache backend only after explicit approval, then run the bounded historical backfill through the hardened adapter.
4. Propose final production run windows for approval, then wire the heartbeat/watchdog only after approval.
5. Run structured-data versus screenshot-assisted shadow comparisons before retiring routine screenshots.
6. Production integration/merge remains a final explicit approval gate.
