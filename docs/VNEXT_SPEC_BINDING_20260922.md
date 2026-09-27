# MDOS VNext specification binding — 22 Sep 2026

Status: IMPLEMENTATION BINDING / NON-PRODUCTION

This repository branch is governed by the approved additive VNext specification package. This binding authorizes implementation and validation only. It does not authorize a change to frozen production methodology, canonical selection, official efficacy, recommendation semantics, or trading execution.

## Accepted production baseline

- 5DR-V2 main: `4c04992e17a785c06c1d4d5c6a2df95af14d19c5`
- EDGE-CONSOLE main: `000e3ecd93712c525de4a19aac70337b3b58b67f`
- EDGE---V1 main: `cc6539832356ff0881388e5f23039fc23de76d5a`

## Approved Drive authorities

- MDOS Output, Learning Lab & Core Zone Amendment V1.0 — APPROVED FOR VNEXT BUILD — Drive ID `1lwqZEhZVCWOAH2mZ-YIDyGqTk6v7h112-vnogm3kyz4`
- MDOS Learning Lab Daily Output & Approval Governance V1.0 — APPROVED FOR VNEXT BUILD — Drive ID `1ooExDRSuFED7xLLNk1Wb2DlYeg3BDCtWW1LRsq1T1qw`
- MDOS Core Zone Master Specification V1.0 — APPROVED SHADOW DESIGN — Drive ID `1tRhB75r44OvhFlN4m1sWsTk4VrTLD1iTJZjTrIn1c0w`
- 5DR V2.2.3 - CANONICAL SPECIFICATION — Drive ID `1bXpByuaDvBSE8caviNxROOl5OhHraTHRo77FX6tw41U`
- 00 - EDGE Console Master Specification — Drive ID `154KpSBHfmRUEDlClnYZLA1iYjuAkSchIlDZMCw4pUQo`
- Market & Evidence Data Architecture - Master Specification V1.0 — Drive ID `1c3NbYZCIfi5LOuKBGxQDePuTdInnlJ45eV62Zjh3JPE`
- EDGE V1 Master Specification - Production Backbone Addendum — Drive ID `1QkdyzEFrQZQnyuxipYQvd5NkuWc3hq_sYvY7Bqg5SoE`

## VNext implementation invariants

1. Official efficacy stays canonical-only.
2. Learning evidence may include CANONICAL, DIAGNOSTIC, MANUAL and SHADOW runs, with explicit run-role metadata and target-date normalization.
3. Learning Lab failures never invalidate an otherwise valid production forecast.
4. User approval of a Learning Lab candidate authorizes governed build/validation only; production promotion is a separate explicit event.
5. Core Zone remains SHADOW until separately promoted.
6. PVPO Grid V1 is explanatory/read-model only until separately promoted.
7. Forecast payload completeness, assessment state and official-efficacy eligibility are separate states.
8. Exact-run report views are immutable and identified by a version and content hash.
9. Historical missing issuance-time evidence is never reconstructed as official forward evidence.
10. No branch in this workstream may place orders or enable trading execution.

## G6/Core SHADOW horizon lock — authoritative clarification 26 Sep 2026

For both EDGE NIFTY and EDGE Stocks, the only valid G6/Core SHADOW horizon sequence is exactly `D,D+1,D+2,D+3,D+4`, in that order. `D` is mandatory and `D+5` is forbidden. Any payload with a missing `D`, any `D+5`, any row count other than five, duplicates, or any different ordering must fail closed and must not enter SHADOW evidence or Learning Lab populations.

Audit history: an earlier NIFTY implementation correction described `D+1,D+2,D+3,D+4,D+5`. That wording is superseded, retained only as audit/version history, and MUST NOT be implemented. This clarification does not change frozen production EDGE/5DR methodology; it binds G6/Core SHADOW only until governed promotion.

## G6-A readiness contract

- Information: freeze immutable issuance identity, target trading session, Expected Centre, Core/Outer bounds, width, regime/confidence/event state, evidence/source references, calibration version, verification state and lineage; bulky reconstructible market history is reference/pull-on-demand rather than duplicated per forecast.
- Methodology: Core is a narrower precision challenger around Expected Centre; Outer remains the broader risk envelope. NIFTY and Stocks share semantics but retain engine-specific calibration. Outcome scoring uses full-session OHLC interaction plus close/touch, centre error, miss distance, normalized width/miss and direction diagnostics. Forecast-zone efficacy remains separate from execution MFE/MAE/R.
- Output: one immutable canonical Core Zone read-model object per run, carrying report version/hash and the exact ordered five horizons. Console and ChatGPT must consume that same object rather than independently recalculating values.
- Learning: matured outcomes append immutable evaluation/observation records with horizon, regime, confidence, actionable/NO TRADE, Core-vs-Outer, width and interaction metadata. Learning may propose improvements but cannot auto-promote them; APPROVE/REJECT/DEFER remains explicit user governance.
- Isolation: synthetic fixtures are engineering-only. Missing issuance evidence or outcome evidence fails closed. No SHADOW record may mutate production probabilities, DES/tradeability, Market Trust, recommendation, canonical selection, official efficacy or trading behavior.

## Build sequence

G3 — shared read-only/additive Learning Lab data model, observation ingestion, daily snapshots, hypotheses/challenger records and approval ledger.
G4 — Console Learning Lab overview/drill-down and stale/failure/approval UI.
G5 — EDGE Stocks D through D+4 forecast path.
G6 — Core Zone SHADOW implementation after G6-A0:A5 readiness acceptance.
G7 — PVPO Grid V1 read model/rendering.
G8 — exact-run report view and Console/ChatGPT parity.
G9 — regression and non-disruption acceptance before any promotion.

## Repository role

5DR remains the authority for NIFTY engine methodology and NIFTY learning observations. VNext changes here are limited initially to richer immutable learning envelopes/snapshots and governed handoff contracts; 5DR_V2_1 analytical methodology remains frozen.
