# Canonical

**Purpose:** Deduplicate exact complete mappings into canonical `GrammarCell`s without losing source edges.

**Inputs:** `normalization/final_mappings.jsonl`.

**Procedure:** Ignore non-complete mappings, require six scalar dimensions, hash canonical dimension order, and retain every source-cell occurrence.

**Outputs:** `canonical_cells.jsonl`, `source_cell_edges.jsonl`, and `manifest.json`.

**Command:** `python scripts/run_experiment.py experiments/current.yaml --only canonical`

**Configurable components:** Canonical module version; the six-field identity contract is fixed.

