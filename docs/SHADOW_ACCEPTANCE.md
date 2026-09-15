# Shadow acceptance gate

A live shadow run is considered useful only when it proves the acquisition plumbing without enabling production publication.

Required observations:
- Upstox authentication succeeds with the repository secret; secret value is never printed.
- NIFTY market and option-chain responses pass existing provider validation.
- Provider observations are reduced to bounded provenance references.
- Missing live cross-market or event evidence leaves the envelope BLOCKED, not neutral/ready.
- No forecast or trading action is released.

Full Issue #11 acceptance additionally requires live cross-market corroboration, live controlled event-source acquisition, Console persistence, normalization and a complete non-publishing end-to-end run.
