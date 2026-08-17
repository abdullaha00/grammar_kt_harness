# KC projection

**Purpose:** Materialize an operational KC inventory and deterministic cell-to-KC activation.

**Inputs:** Canonical cells/source edges, realizations/splits, and one declared KC policy.

**Procedure:** Construct one opportunity per cell and apply only the selected policy's cell/operation rules.

**Outputs:** `kc_inventory.jsonl`, `cell_kc_projection.jsonl`, and `manifest.json`.

**Command:** `python scripts/run_experiment.py experiments/current.yaml --only kc`

**Configurable components:** `full_cell`, `factorized`, or `factorized_plus_interactions` policy path.

