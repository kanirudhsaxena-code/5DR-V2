# Experimental Upstox acquisition status

Canonical 5DR V2.2.2 remains untouched. This branch must not be merged without explicit approval.

## Gate status

- BUILT: PASS — isolated read-only live sample runner, exact CE/PE contract sanitizer, and curl-backed transport adapter exist.
- TESTED: PASS — existing 7 Upstox safety tests and 3 experimental exact-identity/fail-closed tests pass in GitHub Actions.
- LIVE VERIFIED: PASS — GitHub Actions run `35002686745` completed successfully on commit `e325e7149dfd4f8c314bf32889f1b886f551317d`. The run retrieved and strictly validated NIFTY option contracts, intraday candles, the nearest-expiry option chain, exact CE/PE instrument identities, LTP, OI, volume, provider timestamps and SHA-256 provenance. The sanitized sample reported `LIVE_SAMPLE_PASSED`.
- RELIABILITY VERIFIED: IN PROGRESS — live retrieval is proven; repeated-run, freshness, malformed/stale-data and transport-failure behavior still require verification before this gate can pass.
- READY FOR 5DR INTEGRATION: NO — integration requires reliability proof plus explicit user approval.

## Transport finding

The current Upstox Analytics Token is valid: the curl market-quote preflight returned HTTP 200. Python `urllib` requests from the same runner returned HTTP 403 / provider error code 1010, consistent with an upstream browser-signature/WAF transport rejection rather than token expiry. The experimental runner therefore uses curl only as the HTTP transport while retaining the existing `ReadOnlyClient` endpoint allowlist, NIFTY restriction, GET-only behavior, retry controls, response validation and envelope hashing.

## Security boundary observed

GitHub Actions workflow permissions are `contents: read`. Checkout credentials are not persisted. No database credential or lifecycle writer is used. No order/trading endpoint is allowlisted. The Analytics Token is supplied only through the repository secret and is never emitted. The curl adapter passes authorization headers through stdin rather than process arguments. No Upstox payload is classified as SCREENSHOT or WEB_RESEARCH.

## Live-proof reference

- Workflow: `Experimental Upstox read-only live verification`
- Run: `35002686745`
- Commit: `e325e7149dfd4f8c314bf32889f1b886f551317d`
- Result: PASS
- Transport: curl
- Read-only: true
- Trading enabled: false
- Production 5DR writes: false

## Next gate

Reliability hardening and repeated validation remain confined to this experimental branch. Do not merge or connect this source to canonical 5DR until the reliability gate passes and the user explicitly approves integration.
