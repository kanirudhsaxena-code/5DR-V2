# Deployment gate — Issue #11

Do not enable production publication until all are true:

- acquisition PR CI green;
- PR diff confirms core framework untouched;
- live Upstox shadow acquisition succeeds;
- live cross-market corroboration succeeds or governed degradation rules explicitly permit otherwise;
- live event/shock acquisition verifies approved sources and semantic evidence;
- EDGE Console validates/persists the envelope;
- normalization reaches NORMALIZED_READY without fabricated inputs;
- existing governed 5DR runner executes in non-publishing shadow mode;
- resulting output is reviewed for contract parity;
- last-good-result fallback is verified.

Until then the branch remains shadow/non-publishing.
