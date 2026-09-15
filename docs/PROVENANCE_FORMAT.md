# Acquisition provenance format

Provider evidence references are intentionally compact:

- Upstox: `upstox:<fixed-api-path>#sha256=<response-digest>`
- Controlled web source: `web:<allowlisted-https-url>#sha256=<response-digest>`
- System-derived provenance: `derived:<derivation-name>#sha256=<sorted-input-reference-digest>`

The digest proves which fetched/derived observation underpinned the evidence without passing credentials or raw provider bodies through the Console handoff.
