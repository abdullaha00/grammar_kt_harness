# Provenance

**Purpose:** Build a complete typed lineage graph across all executable interfaces.

**Inputs:** Source subset, normalization indices/mappings, canonical edges, item realizations, Q edges, and observable interactions.

**Procedure:** Emit deterministic typed edges and audit one accepted item per primary KC plus every chain join.

**Outputs:** `provenance_edges.jsonl`, `provenance_audit.json`, and `manifest.json`.

**Command:** `python scripts/run_experiment.py experiments/current.yaml --only provenance`

**Configurable components:** Enable/disable and provenance module version.

