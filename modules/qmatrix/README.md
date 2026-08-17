# Q-matrix

**Purpose:** Derive item-to-KC assignments from accepted items and the frozen activation policy.

**Inputs:** Accepted items, KC inventory, canonical cells, realization rules/lexicon, and KC policy.

**Procedure:** Recompute activation from each item's `GrammarCell` and `RealizationSpec`; never special-case the primary KC.

**Outputs:** `q_matrix.csv`, `item_kc_edges.jsonl`, `audit.json`, and `manifest.json`.

**Command:** `python scripts/run_experiment.py experiments/current.yaml --only qmatrix`

**Configurable components:** KC policy and maximum reported row width.

