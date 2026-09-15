# Autonomous evidence audit fields

Each system-owned observation records:
- category;
- verification/degradation/unavailable status;
- source reference;
- retrieval timestamp;
- authority class;
- fallback-used flag;
- bounded detail.

The aggregate envelope additionally records request ID, assessment timestamp, required categories and blocker sets. These fields are sufficient for Console audit/state transitions without exposing credentials or full third-party payloads.
