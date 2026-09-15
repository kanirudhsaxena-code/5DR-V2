# 5DR governed autonomous evidence acquisition (shadow)

Execution-layer implementation for Issue #11. Reuses the existing hardened read-only Upstox boundary and adds bounded provenance adapters, autonomous evidence validation, controlled event-source registry, Market Trust corroboration, execution-input provenance derivation, security/diagnostic guards, offline CI and a non-publishing live shadow workflow.

No 5DR V2.1 scoring, probability, threshold, gate, learning, lifecycle or historical-checkpoint changes. No trading. No production forecast release.

Still required before merge/production: EDGE Console autonomous-evidence ingestion/persistence, live cross-market acquisition, semantic event/shock extraction, and a complete current non-publishing end-to-end shadow run.
