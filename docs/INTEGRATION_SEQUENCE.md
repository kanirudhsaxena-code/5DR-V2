# Safe integration sequence

1. Keep EDGE Console PR #10 and this 5DR-V2 branch in shadow.
2. Add Console autonomous-evidence ingestion endpoint and tests.
3. Add service-authenticated POST from this runner to that endpoint.
4. Add live cross-market acquisition and semantic event extraction.
5. Run offline CI on both repos.
6. Run one live non-publishing end-to-end request.
7. Inspect provenance/state/normalization/runner output.
8. Merge only after the end-to-end acceptance gate passes.
