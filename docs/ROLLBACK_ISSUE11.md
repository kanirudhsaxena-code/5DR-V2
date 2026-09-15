# Issue #11 rollback

Because this work is isolated to new acquisition modules/workflows/docs/tests and does not modify the production scoring/execution framework, rollback before production wiring is simply to leave the feature branch/PR unmerged or revert its merge commit.

No database migration, checkpoint mutation or framework-version change is introduced by the 5DR-V2 acquisition branch.

EDGE Console persistence/wiring will be reviewed separately and must preserve last-good-result behavior.
