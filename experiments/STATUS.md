# Experimental Upstox acquisition status

Canonical 5DR V2.2.2 remains untouched. This branch must not be merged without explicit approval.

## Gate status

- BUILT: PASS — isolated read-only acquisition, curl transport, exact CE/PE sanitizer, NFO session guard, formal freshness validator, deterministic snapshot fingerprint and duplicate policy exist.
- TESTED: PASS — 32 tests pass in GitHub Actions: 7 original Upstox read-only safety tests plus 25 experimental identity, session, transport, freshness, fingerprint and duplicate-policy tests.
- LIVE VERIFIED: PASS — authenticated NIFTY spot, intraday candle, expiry list, exact CE/PE contracts, LTP, OI, volume, timestamps and SHA-256 provenance have passed repeatedly.
- RELIABILITY VERIFIED: IN PROGRESS — closed-session freshness and duplicate behavior are now live-proven. An open-market time-separated pair is still required before this gate can pass.
- READY FOR 5DR INTEGRATION: NO — reliability must pass and the user must explicitly approve integration.

## Transport finding

The current Upstox Analytics Token is valid: curl market-quote preflights return HTTP 200. Python `urllib` requests from the same runner returned HTTP 403 / provider error code 1010, consistent with an upstream browser-signature/WAF transport rejection rather than token expiry. The experiment therefore uses curl only as the HTTP transport while retaining the existing `ReadOnlyClient` endpoint allowlist, NIFTY restriction, GET-only behavior, retry controls, schema validation and envelope hashing.

The curl adapter is isolated in `experiments/upstox_transport.py`. Boundary tests verify GET-only behavior, no redirect following, secret absence from process arguments, fail-closed handling for non-2xx/missing status/oversize/timeout conditions, and preservation of HTTP errors for the existing client.

## Session-state finding and fix

A post-close sample on 15 September initially saw the same-day expiry still present in the contract master. The experiment now reads the official NFO exchange-status endpoint and selects expiries according to session state. Live run `35003280216` returned NFO `NORMAL_CLOSE` and correctly rolled the selected chain from 15 September to 22 September. Market-status provenance is hashed and timestamped alongside the other sources.

## Freshness, fingerprint and duplicate proof

Run `35003874222` / commit `18124ed6cc5e920f2549fcb10f7ee2af3d6d7687` passed all controls.

- 7 original safety tests: PASS.
- 25 experimental reliability/boundary tests: PASS.
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

## Auditability and security boundary

Each live snapshot now carries a schema version, deterministic SHA-256 snapshot fingerprint, GitHub run/attempt/commit context, source-level receipt timestamps and source SHA-256 digests. GitHub Actions permissions remain `contents: read`; checkout credentials are not persisted. No database credential, lifecycle writer or order/trading endpoint is present. The Analytics Token is supplied only through the repository secret and is never emitted. No Upstox payload is classified as SCREENSHOT or WEB_RESEARCH.

Authenticated live steps are skipped on pull-request events so the same branch commit does not make duplicate provider calls through both push and PR workflows.

## Live-proof references

- `35002686745`: first end-to-end authenticated sanitized sample — PASS.
- `35003039325`: hardened curl transport and repeated live sample — PASS.
- `35003280216`: NFO status-aware expiry rollover — PASS.
- `35003874222`: formal freshness, audit fingerprint and 80-second closed-session duplicate pair — PASS.

## Remaining reliability gate

Run the same 75-second pair while NFO is `NORMAL_OPEN`. Both samples must pass `LIVE_OPEN` freshness; after >=65 seconds the second snapshot must advance and must not be accepted as a duplicate. A second open-session check later in the trading day is desirable for broader stability evidence. Until those live checks pass, do not merge this PR and do not connect Upstox to canonical 5DR.
