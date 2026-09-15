# PR review checklist — Issue #11

Before merge:

- [ ] CI passes all acquisition tests.
- [ ] Diff contains no changes to scoring/probability/gate/lifecycle production modules.
- [ ] No credentials or raw provider payloads are logged or persisted.
- [ ] Upstox remains read-only and NIFTY constrained in this phase.
- [ ] Source registry rejects arbitrary URLs and redirects.
- [ ] Missing/stale/conflicting critical evidence fails closed.
- [ ] Event-source failure is never translated to `no event`.
- [ ] `trading_enabled` remains false.
- [ ] `forecast_release_enabled` remains false during shadow validation.
- [ ] Live shadow run is inspected before production wiring.
- [ ] EDGE Console independently validates and persists the autonomous envelope before normalization.
