# 5DR V2.2.2 — contract-matched option evidence autonomy gap

Status: BLOCKED / fail-closed

## Proven
- Governed fresh web research can establish market/event/execution context.
- Canonical EvidencePacket firewall is active.
- Shadow lifecycle path is hard-forced DRY_RUN with zero writes.

## Missing proof
A fresh, contract-matched option EvidencePacket requires independently validated:
- exact instrument side (CE/PE)
- strike
- expiry
- premium/LTP
- observed_at and captured_at
- source provenance/digest
- contract identity match
- freshness

Web/event research alone cannot supply or infer these fields.

## Existing candidate acquisition path
The legacy read-only Upstox adapter already retrieves authenticated NIFTY option-chain payloads and validates expiry, underlying identity, strike uniqueness, instrument keys, LTP, OI and volume. It currently emits only bounded SourceObservation provenance and deliberately does NOT convert provider payloads into canonical lifecycle evidence.

## Required next implementation
Build a narrow provider-to-normalized-option producer that:
1. accepts only the hardened read-only Upstox chain envelope;
2. requires an explicit forecast contract binding (side + strike + expiry); no nearest-strike or side inference;
3. finds exactly one matching chain row/leg;
4. validates finite non-negative LTP and exact expiry/underlying/leg identity;
5. emits a canonical EvidencePacket with source_type WEB_RESEARCH only if canonical policy explicitly permits provider-derived market evidence, otherwise use a separately approved source type before production;
6. sets continuous_path=false for a snapshot;
7. never enables trading or forecast release;
8. fails closed on missing/duplicate/mismatched/stale data;
9. remains shadow-only until idempotence and production policy are separately approved.

## Safety decision
Do not relabel Upstox option-chain data as SCREENSHOT. Do not infer a premium from web research. Do not connect this gap directly to the write-enabled lifecycle wrapper.
