# Experimental market-data acquisition status

Canonical 5DR V2.2.2 remains untouched. PR #30 stays experimental and must not be merged or connected to production consumers without explicit approval.

## Core acquisition gates

- BUILT: PASS — isolated read-only Upstox acquisition, hardened curl transport, exact CE/PE identity, NFO session guard, freshness validation, deterministic snapshot fingerprints, duplicate policy and sanitized manifests exist.
- TESTED: PASS — current-head CI run `35059388654` passed 7 original Upstox safety tests plus 76 experimental tests = 83/83 PASS.
- LIVE VERIFIED: PASS — authenticated NIFTY spot, intraday candles, expiry/contract discovery, exact CE/PE contracts, LTP/OI/volume, timestamps and SHA-256 provenance are live proven.
- RELIABILITY VERIFIED: PASS — both closed-session and open-session behavior are proven; the four-window 09:45/10:00/10:15/10:30 burst run `35054637198` passed all checkpoints and every >=75-second pair advanced.
- READY FOR DATA-BACKBONE BUILD: YES.
- READY FOR PRODUCTION 5DR INTEGRATION: NO — integration remains a separate explicit approval gate.

## Open-market burst proof — 16 Sep 2026

Run `35054637198`, job `104662116005`, completed successfully.

- 09:45: PASS / ADVANCED; 79.302s pair; zero startup lateness.
- 10:00: PASS / ADVANCED; 79.306s pair; zero startup lateness.
- 10:15: PASS / ADVANCED; 79.251s pair; zero startup lateness.
- 10:30: PASS / ADVANCED; 78.994s pair; zero startup lateness.
- NFO remained `NORMAL_OPEN`.
- Selected expiry remained 22 Sep 2026.
- Every checkpoint had distinct first/second snapshot fingerprints and manifest hashes.
- `production_5dr_write_enabled=false`; `trading_enabled=false` throughout.
- Final result: `BURST_RELIABILITY_PASSED` with `all_advanced=true`.

A further current-head validation run `35059388654` passed 83/83 tests, HTTP 200 preflight, manifested live acquisition and an 80.705s open-session pair classified `ADVANCED` / `DUPLICATE_POLICY_PASS`.

## Provider-neutral data-core checkpoint

Commit `dc1c6919aeb5622714c7b78b5c2931c5d82fdb54` added the first provider-neutral market/evidence data core:

- `experiments/data_contract.py` — common normalized evidence contract independent of Upstox.
- `experiments/data_requirements.py` — requirements registry for 5DR, EDGE Stocks and IPO EDGE.
- `experiments/data_policy.py` — cost-aware enabled/provisioned request policy.
- `experiments/data_cache.py` — storage-neutral incremental/backfill planning and retention cutoffs.
- `experiments/usage_ledger.py` — API/storage/billable-usage budgets; billable use defaults to blocked.
- `experiments/provider_adapter.py` — generic read-only provider boundary.
- `experiments/upstox_adapter.py` — Upstox implementation over the hardened read-only quant client.

Cost posture is explicit: 5DR variables needed for the experiment may be exercised; EDGE Stocks and IPO EDGE are provisioned but background-disabled. There is no all-stock collection, all-option-chain archive, tick archive or 30-level depth archive.

## Source/provider boundary

Consumers must depend on the normalized data contract rather than on Upstox response schemas. Upstox is the first provider, not the architecture. A future provider can implement the same read-only adapter boundary without changing 5DR/EDGE methodology.

Upstox evidence remains semantically `UPSTOX_AUTHENTICATED`; it is never relabelled as SCREENSHOT or WEB_RESEARCH. Qualitative/event fields unavailable from Upstox remain external evidence rather than being fabricated or proxied.

## Security and isolation

- GET/read-only market-information paths only.
- No order placement/modification/cancellation surface.
- No portfolio, funds or account action surface.
- Analytics Token only via GitHub secret; no token/header in audit manifests.
- No database credential or production lifecycle writer in this experiment.
- No canonical scoring, weights, probability, recommendation, efficacy or Learning Lab changes.
- No production 5DR/EDGE writes.

## Current next gate

Run the isolated broad quantitative live probe to verify the provisioned 5DR quantitative families: global instrument identities/latencies, India VIX, nearest NIFTY future, 15m/30m/1H NIFTY candles, FII/DII, OI/change-OI/PCR/max-pain. Only fields proven live move from SUPPORTED_UNPROVEN to LIVE_PROVEN. Historical backfill and additional consumer profiles remain separate subsequent gates.
