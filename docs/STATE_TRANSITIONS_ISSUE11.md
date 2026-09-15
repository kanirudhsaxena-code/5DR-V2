# State transitions

Allowed high-level progression:

`SCREENSHOTS_READY`
→ `AUTONOMOUS_EVIDENCE_BLOCKED` while research is incomplete/unverifiable, or
→ `AUTONOMOUS_EVIDENCE_READY` when system evidence passes validation
→ `NORMALIZATION_BLOCKED` or `NORMALIZED_READY`
→ governed engine execution.

No acquisition component may jump directly from screenshots to normalized/executed/published state.
