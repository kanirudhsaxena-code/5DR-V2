# MDOS Consumer Contract Registry

Status: CANONICAL ROUTING REGISTRY

This registry binds each consumer to its authoritative output contract while preserving analytical independence.

| Consumer | Authoritative output contract | Owner repository | Methodology boundary |
| --- | --- | --- | --- |
| 5DR | Existing 5DR V2 output contract | `kanirudhsaxena-code/5DR-V2` | Frozen 5DR methodology remains unchanged |
| EDGE Stocks | `EDGE_STOCKS_V1_2` | `kanirudhsaxena-code/EDGE---V1` + enforcement in `kanirudhsaxena-code/EDGE-CONSOLE` | Frozen EDGE V1 methodology remains unchanged |
| IPO EDGE | Existing IPO EDGE V1.1 output contract | IPO EDGE canonical repository/specification | IPO scoring and lifecycle remain independent |

## Routing rule

A request of the form `EDGE <stock/company/ticker>` resolves to consumer `EDGE_STOCKS` and must use `EDGE_STOCKS_V1_2`.

The shared Market & Evidence Data Architecture supplies evidence only. It must not replace or reinterpret consumer-specific output contracts.

## EDGE Stocks V1.2 invariant

- exactly two standard user-facing tables;
- Table 1: EDGE Outcome / Decision;
- Table 2: Institutional Drill-down;
- efficacy appears separately after the two standard tables;
- missing/unverified evidence is explicitly labelled and never inferred;
- presentation validation fails closed;
- no presentation-layer code may change DES, Market Trust, probability, recommendation, execution, efficacy, learning, or historical semantics.

Authoritative implementation details live in:
- `EDGE---V1/docs/EDGE_STOCKS_OUTPUT_CONTRACT_V1_2.md`
- `EDGE-CONSOLE/contracts/edge-stocks-output-v1.2.schema.json`
