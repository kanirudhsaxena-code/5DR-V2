# Schema V6 — V2.2 Learning Lab Additions

Schema version 6 is additive. It does not rewrite production forecasts, execution plans, efficacy history or production configuration.

## Source lineage

Every observation should link to one or more of:

- `forecasts.forecast_id`
- `forecast_checkpoint_evaluations.evaluation_id`
- `recommendation_events.event_id`

Every challenger preserves `base_model_version` and its exact JSON change specification.

## Immutability

Learning cycles, observations, hypotheses, challenger definitions, predictions, evaluations, proposals, decisions and reports are protected from UPDATE/DELETE by database rules. New facts are appended.

## Promotion decisions

`promotion_proposals` can only be created with `PENDING_USER_APPROVAL`.
`promotion_decisions.decided_by` is constrained to `USER`.

This makes approval a separate audit record rather than a field the learner can silently rewrite.
