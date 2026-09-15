# PR notes

The branch deliberately reuses `phase1/upstox.py` rather than creating another broker client. This keeps authentication, endpoint allowlisting, retry discipline, schema validation and safe failure behavior in one existing hardened boundary.

New adapters reduce provider responses to provenance references and keep autonomous evidence separate from scoring/forecast semantics.
