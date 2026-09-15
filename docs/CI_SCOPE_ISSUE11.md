# CI scope

Offline PR CI validates acquisition contracts without external network dependencies. Live provider availability is tested separately through manual shadow workflow because it requires repository secrets and current external services.

A green offline CI is necessary but not sufficient for Issue #11 completion.
