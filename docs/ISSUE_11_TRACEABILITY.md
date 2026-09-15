# Issue #11 traceability

- Governed system-evidence envelope: `src/autonomous_acquisition.py`
- Existing authenticated read-only Upstox client: `phase1/upstox.py`
- Bounded Upstox provenance adapter: `src/upstox_evidence.py`
- Controlled event source registry boundary: `src/event_evidence.py`
- Non-publishing live shadow runner: `src/acquisition_shadow_runner.py`
- Offline fail-closed tests: `tests/test_autonomous_acquisition.py`, `tests/test_upstox_evidence.py`, `tests/test_event_evidence.py`, `tests/test_acquisition_shadow_runner.py`
- PR CI: `.github/workflows/autonomous-acquisition-ci.yml`
- Manual live shadow validation: `.github/workflows/autonomous-acquisition-shadow.yml`

Still required before Issue #11 can close:
1. Implement the live allowlisted event-source fetcher and provenance hashing.
2. Add broader Market Trust/cross-market observations rather than treating NIFTY-only data as complete.
3. Derive EXECUTION_RISK from governed verified inputs rather than accepting it as raw provider evidence.
4. POST the resulting envelope into the EDGE Console autonomous-evidence endpoint/persistence layer.
5. Run live non-publishing end-to-end shadow validation and inspect results.
6. Only then consider production publication wiring.
