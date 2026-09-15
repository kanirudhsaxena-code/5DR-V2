# Issue #11 test plan

Offline tests cover:
- complete system evidence;
- missing category;
- all-source unavailable;
- stale evidence;
- missing provenance;
- conflicting evidence;
- Upstox provenance adaptation;
- event primary success/fallback/all-source failure;
- source allowlist and redirect rejection;
- Market Trust corroboration requirement;
- execution input provenance derivation;
- bounded handoff/security invariants;
- shadow release disabled;
- no core-framework-file modification.

Live shadow test covers authenticated Upstox acquisition only until the Console handoff and live event/cross-market fetch stages are wired. A blocked result due to deliberately missing unimplemented system evidence is the expected safe result, not a failure to be bypassed.
