# Experimental Upstox acquisition status

Canonical 5DR V2.2.2 remains untouched. This branch must not be merged without explicit approval.

## Gate status

- BUILT: PASS — isolated read-only live sample runner and exact CE/PE contract sanitizer exist.
- TESTED: PASS — existing 7 Upstox safety tests and 3 experimental exact-identity/fail-closed tests pass in GitHub Actions.
- LIVE VERIFIED: BLOCKED — authenticated run reached OPTION_CONTRACTS and returned safe diagnostic AUTH_REJECTED. No market payload was accepted or persisted.
- RELIABILITY VERIFIED: NOT STARTED — gated on successful live retrieval.
- READY FOR 5DR INTEGRATION: NO.

## Security boundary observed

GitHub Actions workflow permissions are contents: read. Checkout credentials are not persisted. No database credential or lifecycle writer is used. No order/trading endpoint is allowlisted. No Upstox payload is classified as SCREENSHOT or WEB_RESEARCH.

## Next gate

Replace the repository secret UPSTOX_ANALYTICS_TOKEN with a currently valid Upstox Analytics Token, then rerun the experimental workflow. The token itself must never be committed, logged, pasted into issues/PRs, or shared in chat.
