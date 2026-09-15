# Review order

1. Confirm core 5DR files are unchanged.
2. Review autonomous evidence validation/fail-closed behavior.
3. Review Upstox provenance adapter.
4. Review event source allowlist/fallback behavior.
5. Review Market Trust and execution provenance boundaries.
6. Review Console handoff contract.
7. Run offline CI.
8. Run live non-publishing shadow only after offline CI is green.
9. Do not merge to production solely because the first shadow probe reaches Upstox; full Console end-to-end acceptance remains required.
