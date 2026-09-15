# No-framework-change declaration — Issue #11

The autonomous acquisition work is isolated to new acquisition/provenance modules, tests, workflows and documentation.

It does not modify the existing 5DR scoring, Market Trust scoring implementation, probability engine, execution thresholds, governance gates, assessment logic, lifecycle accounting, learning governance, historical checkpoints, runner contract or production publishing path.

Any later change to those components must be reviewed separately and cannot be implied by this acquisition PR.
