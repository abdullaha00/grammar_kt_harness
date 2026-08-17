# KT

**Purpose:** Run technical prediction baselines on observable chronological interactions.

**Inputs:** Observable interactions, KC inventory, and fixed technique configuration; oracle data is not an input.

**Procedure:** Compute pre-event features and dispatch the configured empirical, BKT-style, and/or logistic implementation.

**Outputs:** `predictions.jsonl`, `metrics.json`, and `manifest.json`.

**Command:** `python scripts/run_experiment.py experiments/current.yaml --only kt`

**Configurable components:** Technique list and per-technique parameters.

