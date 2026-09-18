# MDOS Consumer Contract Registry

Status: CANONICAL ROUTING REGISTRY

This registry binds each consumer to its authoritative output contract while preserving analytical independence.

| Consumer | Authoritative output contract | Owner repository | Methodology boundary |
| --- | --- | --- | --- |
| 5DR | Existing 5DR V2 output contract | `kanirudhsaxena-code/5DR-V2` | Frozen 5DR methodology remains unchanged |
| EDGE Stocks | `EDGE_STOCKS_V1_3 / EFFICACY_V2` | `kanirudhsaxena-code/EDGE---V1` + enforcement in `kanirudhsaxena-code/EDGE-CONSOLE` | Frozen EDGE V1 methodology remains unchanged |
| IPO EDGE | Existing IPO EDGE V1.1 output contract | IPO EDGE canonical repository/specification | IPO scoring and lifecycle remain independent |

## Routing rule

A request of the form `EDGE <stock/company/ticker>` resolves to consumer `EDGE_STOCKS` and must use `EDGE_STOCKS_V1_3 / EFFICACY_V2`.

The shared Market & Evidence Data Architecture supplies evidence only. It must not replace or reinterpret consumer-specific output contracts.

## EDGE Stocks V1.3 / Efficacy V2 invariant

- exactly four standard user-facing sections in mandatory order:
  1. EDGE MASTER ASSESSMENT;
  2. ACTIVE CALLS;
  3. CURRENT STOCK OUTCOME;
  4. DRILL-DOWN;
- assessment must be first;
- OFFICIAL and PROVISIONAL efficacy remain distinct inside the assessment;
- every VERIFIED drill-down component must have a meaningful evidence-grounded Key Outcome and Interpretation;
- missing/unverified evidence is explicitly labelled and never inferred;
- semantic validation fails closed;
- the deprecated V1.2 two-table contract must not be selected for new runs;
- no presentation-layer code may change DES, Market Trust, probability, recommendation, execution, efficacy, learning, or historical semantics.

Authoritative implementation details live in:
- `EDGE---V1/docs/EDGE_STOCKS_OUTPUT_CONTRACT_V1_3.md`
- `EDGE-CONSOLE/contracts/edge-stocks-output-v1.2.schema.json`
