# Experimental Upstox acquisition status

Canonical 5DR V2.2.2 remains untouched. This branch must not be merged without explicit approval.

## Gate status

- BUILT: PASS — isolated read-only live sample runner, exact CE/PE contract sanitizer, and hardened curl-backed transport adapter exist.
- TESTED: PASS — 16 tests pass in GitHub Actions: 7 existing Upstox read-only safety tests plus 9 experimental identity, fail-closed and transport-boundary tests.
- LIVE VERIFIED: PASS — full authenticated retrieval has passed repeatedly. Run `35002686745` first proved the sanitized live path; run `35003039325` re-proved it after extracting and hardening the curl transport. Both returned `LIVE_SAMPLE_PASSED`.
- RELIABILITY VERIFIED: IN PROGRESS — repeatability and transport failure boundaries are now proven. Freshness/session-state enforcement, duplicate-run handling and broader time-separated live checks remain before this gate can pass.
- READY FOR 5DR INTEGRATION: NO — integration requires reliability proof plus explicit user approval.

## Transport finding

The current Upstox Analytics Token is valid: curl market-quote preflights return HTTP 200. Python `urllib` requests from the same runner returned HTTP 403 / provider error code 1010, consistent with an upstream browser-signature/WAF transport rejection rather than token expiry. The experimental runner therefore uses curl only as the HTTP transport while retaining the existing `ReadOnlyClient` endpoint allowlist, NIFTY restriction, GET-only behavior, retry controls, response validation and envelope hashing.

The curl adapter is isolated in `experiments/upstox_transport.py`. Boundary tests verify GET-only behavior, no redirect following, secret absence from process arguments, fail-closed handling for non-2xx/missing status/oversize/timeout conditions, and preservation of HTTP errors for the existing client.

## Security boundary observed

GitHub Actions workflow permissions are `contents: read`. Checkout credentials are not persisted. No database credential or lifecycle writer is used. No order/trading endpoint is allowlisted. The Analytics Token is supplied only through the repository secret and is never emitted. The curl adapter passes authorization headers through stdin rather than process arguments. No Upstox payload is classified as SCREENSHOT or WEB_RESEARCH.

## Live-proof references

- Run `35002686745` / commit `e325e7149dfd4f8c314bf32889f1b886f551317d`: PASS — first end-to-end live sanitized sample.
- Run `35003039325` / commit `279c8af11bd6df4fd352039b4e80ab1ed7f379b8`: PASS — hardened transport tests, HTTP 200 preflight, and end-to-end live sanitized sample all passed.
- Transport: curl
- Read-only: true
- Trading enabled: false
- Production 5DR writes: false

## Next gate

Reliability hardening and time-separated validation remain confined to this experimental branch. Do not merge or connect this source to canonical 5DR until the reliability gate passes and the user explicitly approves integration.
