# Next implementation step

The acquisition boundaries are now isolated and testable. The next material code step is the cross-repository bridge:

1. EDGE Console accepts a signed/service-authenticated autonomous-evidence envelope for a specific governed `request_id`.
2. Console validates category completeness, timestamps, provenance references, blocker state and shadow release flags.
3. Console persists the envelope into `analysis_requests.metadata.autonomous_evidence` and advances only valid READY envelopes to `AUTONOMOUS_EVIDENCE_READY`.
4. Existing normalization endpoint remains inaccessible before that state.
5. 5DR-V2 shadow workflow posts the bounded envelope using the existing Cloudflare service-token pattern; secrets remain repository secrets.

This bridge should be implemented on the EDGE-CONSOLE Issue #9/PR #10 lineage before a live end-to-end shadow run.
