# Shadow mode semantics

Shadow mode may fetch and validate live read-only evidence, build provenance, test state transitions and exercise non-publishing integration paths.

Shadow mode must not publish a production forecast, alter the current published result, place/modify/cancel an order, mutate historical checkpoints or silently change framework parameters.
