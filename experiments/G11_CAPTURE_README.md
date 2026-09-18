# G11 exact-cutoff capture boundary

This is experiment-only infrastructure for the three-session G11 validation protocol.

A dedicated workflow watches only `.g11/trigger.txt`. A trigger should be created/updated shortly before the approved 09:45 IST validation cutoff. The runner waits until the exact cutoff when necessary, rejects sessions outside the approved dates or more than 120 seconds late, freezes the normal screenshot-free structured bundle, and binds the bundle SHA-256 to the deterministic comparison window ID.

The frozen bundle and capture metadata are kept in GitHub Actions cache, not committed to the repository. This capture does not create a forecast/recommendation release, production or lifecycle write, trading action, methodology change, or canonical integration.

The screenshot-assisted reference remains a separate evidence lane. It must be captured for the same session/cutoff and later finalized with the same comparison-window ID before `shadow_validation.py` can count the pair. A missing or temporally mismatched reference makes the session observational-only and does not count toward the required three comparable sessions.
