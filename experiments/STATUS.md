# Experimental Upstox acquisition status

Canonical 5DR V2.2.2 remains untouched. This branch must not be merged without explicit approval.

## Gate status

- BUILT: PASS — isolated read-only acquisition, curl transport, exact CE/PE sanitizer, NFO session guard, formal freshness validator, deterministic snapshot fingerprint, duplicate policy and sanitized acquisition-manifest builder exist.
- TESTED: PASS — 37 tests pass in GitHub Actions: 7 original Upstox read-only safety tests plus 30 experimental identity, session, transport, freshness, fingerprint, duplicate-policy and manifest tests.
- LIVE VERIFIED: PASS — authenticated NIFTY spot, intraday candle, expiry list, exact CE/PE contracts, LTP, OI, volume, timestamps, SHA-256 provenance and a deterministic sanitized acquisition manifest have passed live.
- RELIABILITY VERIFIED: IN PROGRESS — closed-session freshness, duplicate behavior and manifested acquisition are live-proven. An open-market time-separated pair is still required before this gate can pass.
- READY FOR 5DR INTEGRATION: NO — reliability must pass and the user must explicitly approve integration.

## Transport finding

The current Upstox Analytics Token is valid: curl market-quote preflights return HTTP 200. Python `urllib` requests from the same runner returned HTTP 403 / provider error code 1010, consistent with an upstream browser-signature/WAF transport rejection rather than token expiry. The experiment therefore uses curl only as the HTTP transport while retaining the existing `ReadOnlyClient` endpoint allowlist, NIFTY restriction, GET-only behavior, retry controls, schema validation and envelope hashing.

The curl adapter is isolated in `experiments/upstox_transport.py`. Boundary tests verify GET-only behavior, no redirect following, secret absence from process arguments, fail-closed handling for non-2xx/missing status/oversize/timeout conditions, and preservation of HTTP errors for the existing client.

## Session-state finding and fix

A post-close sample on 15 September initially saw the same-day expiry still present in the contract master. The experiment now reads the official NFO exchange-status endpoint and selects expiries according to session state. Live run `35003280216` returned NFO `NORMAL_CLOSE` and correctly rolled the selected chain from 15 September to 22 September. Market-status provenance is hashed and timestamped alongside the other sources.

## Freshness, fingerprint and duplicate proof

Run `35003874222` / commit `18124ed6cc5e920f2549fcb10f7ee2af3d6d7687` first passed the formal reliability controls.

- 7 original safety tests: PASS.
- 25 experimental reliability/boundary tests at that checkpoint: PASS.
- Curl authenticated market-quote preflight: HTTP 200.
- Single live sample: `LIVE_SAMPLE_PASSED`.
- NFO session: `NORMAL_CLOSE`.
- Freshness mode: `CLOSED_SESSION_FINAL` / `FRESHNESS_PASS`.
- Selected expiry: 22 September 2026.
- NIFTY spot: 23118.6.
- Snapshot fingerprint: `6569860a78f912f28c0386e59ed477de70c2866235524e0abe53d3cb981522ee`.
- Time-separated pair interval: 80.209 seconds.
- Pair result: `RELIABILITY_PAIR_PASSED`.
- Duplicate result: true, classified `EXPECTED_STATIC_NONTRADING_SESSION` because the exchange was closed.
- Production 5DR writes: false.
- Trading enabled: false.

The duplicate policy is intentionally session-aware: an unchanged snapshot after >=65 seconds during `NORMAL_OPEN` or a closing phase fails closed; an identical snapshot after `NORMAL_CLOSE` is accepted as an expected static market state and is fingerprinted as a duplicate rather than treated as a new observation.

## Acquisition manifest live proof

Commit `129e458b14da11bcc812f537662efcc606e5dd14` added the isolated `experiments/upstox_manifest.py` audit-manifest builder and five fail-closed manifest tests. GitHub Actions PR run `35006440812` passed 7 original safety tests plus 30 experimental tests, for 37 total PASS.

The manifest was then integrated through the separate safe wrapper `experiments/run_upstox_manifested_sample.py`, avoiding any weakening or bypass of the connector safety guard that protected the original authentication-handling runner.

GitHub Actions push run `35006756235` / commit `7cc1eb67e0c29099328751fb6e73a7b1f0afb768` live-proved the manifested acquisition path:

- 37/37 safety/reliability tests: PASS.
- Curl authenticated market-quote preflight: HTTP 200.
- Authenticated manifested sample: `MANIFESTED_LIVE_SAMPLE_PASSED`.
- Manifest schema: `upstox-experimental-acquisition-manifest-v1`.
- Manifest source count: 4.
- Sampled strikes: 5.
- Exact option legs represented: 10.
- NFO session: `NORMAL_CLOSE`.
- Freshness: `CLOSED_SESSION_FINAL` / `FRESHNESS_PASS`.
- Selected expiry: 22 September 2026.
- Snapshot fingerprint: `6569860a78f912f28c0386e59ed477de70c2866235524e0abe53d3cb981522ee`.
- Manifest SHA-256: `58a3d9b7bf73c387f82b75501041d5f62330d4c5f955160d48d8d9734a555ce5`.
- Follow-up reliability pair interval: 79.477 seconds.
- Pair result: `RELIABILITY_PAIR_PASSED` / `EXPECTED_STATIC_NONTRADING_SESSION`.
- Trading enabled: false.
- Production 5DR writes: false.

A successful manifest contains only sanitized audit metadata: schema version, read-only/trading/production-write boundaries, transport, safe GitHub run context, underlying, selected expiry, NFO session, freshness mode, source count, sampled strike/leg counts, source paths, source receipt timestamps, source SHA-256 digests, snapshot fingerprint, completion time and its own deterministic SHA-256 manifest digest. It intentionally contains no credential, authorization header or raw provider payload.

## Auditability and security boundary

Each live snapshot carries a schema version, deterministic SHA-256 snapshot fingerprint, GitHub run/attempt/commit context, source-level receipt timestamps and source SHA-256 digests. Each manifested live run now also carries a deterministic sanitized acquisition manifest. GitHub Actions permissions remain `contents: read`; checkout credentials are not persisted. No database credential, lifecycle writer or order/trading endpoint is present. The Analytics Token is supplied only through the repository secret and is masked in Actions logs. No Upstox payload is classified as SCREENSHOT or WEB_RESEARCH.

Authenticated live steps are skipped on pull-request events so the same branch commit does not make duplicate provider calls through both push and PR workflows. Workflow concurrency now cancels superseded branch runs so current-head reliability checks are not delayed by obsolete queued development runs.

## Isolation check

The experimental branch remains isolated from canonical 5DR. The current branch-vs-main diff contains only `.github/workflows/upstox-experimental-live.yml`, files under `experiments/`, and `tests/test_experimental_upstox_*`. No canonical 5DR source, methodology, scoring, lifecycle, Learning Lab or production database file has been modified by this experiment.

## Live-proof references

- `35002686745`: first end-to-end authenticated sanitized sample — PASS.
- `35003039325`: hardened curl transport and repeated live sample — PASS.
- `35003280216`: NFO status-aware expiry rollover — PASS.
- `35003874222`: formal freshness, audit fingerprint and 80-second closed-session duplicate pair — PASS.
- `35006440812`: 37-test CI checkpoint including acquisition-manifest tests — PASS; authenticated live steps intentionally skipped on PR event.
- `35006756235`: current-head manifested live acquisition, HTTP 200 preflight, 37/37 tests and 79.477-second closed-session reliability pair — PASS.

## Remaining reliability gate

Run the same 75-second pair while NFO is `NORMAL_OPEN`. Both samples must pass `LIVE_OPEN` freshness; after >=65 seconds the second snapshot must advance and must not be accepted as a duplicate. The first open-session check is scheduled for 09:45 IST and the second for 14:30 IST on 16 September 2026. Both scheduled checks are instructed to test the current branch head, not an obsolete workflow commit. Until those live checks pass, do not merge this PR and do not connect Upstox to canonical 5DR.
