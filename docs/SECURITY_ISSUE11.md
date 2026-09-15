# Issue #11 security boundary

- Broker credential enters only through GitHub secret environment injection.
- The acquisition client performs GET-only requests against fixed/allowlisted endpoints.
- Arbitrary caller URLs are not accepted.
- Redirects are rejected.
- Network responses have explicit size bounds.
- Raw Upstox payloads are not included in Console handoff envelopes.
- Source references use bounded path/URL + SHA-256 provenance.
- Diagnostics are allowlisted/bounded; arbitrary provider exception text must not cross the boundary.
- Acquisition code has no broker order/trading methods.
- Shadow envelopes explicitly disable trading and forecast release.
