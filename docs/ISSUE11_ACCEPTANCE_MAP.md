# Issue #11 acceptance map

| Requirement | Current implementation |
| --- | --- |
| Read-only authenticated market acquisition | Existing `phase1/upstox.py`, adapted by `src/upstox_evidence.py` |
| Provenance | source path/URL + SHA-256 references |
| Derivatives corroboration | authenticated NIFTY option-chain observation |
| Controlled event registry | `src/event_evidence.py` + `src/source_registry.py` |
| Execution risk system-owned | `src/execution_risk_evidence.py` provenance derivation boundary |
| Missing/unavailable/stale fail closed | `src/autonomous_acquisition.py` |
| Retry discipline | existing Upstox client; web registry currently bounded single-attempt per approved source |
| Secret-safe diagnostics | existing Upstox `safe_failure` + bounded acquisition diagnostics |
| Tests | dedicated Issue #11 test modules + PR CI |
| Non-publishing shadow | `src/acquisition_shadow_runner.py` + shadow workflow |
| Console persistence | pending cross-repository bridge |
| Full live cross-market evidence | pending |
| Semantic event/shock extraction | pending |
| Full end-to-end shadow | pending until above wiring is complete |
