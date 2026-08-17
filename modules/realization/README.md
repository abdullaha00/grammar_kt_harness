# Realization

**Purpose:** Attach executable `RealizationSpec`s to exact cells while keeping realization outside grammar identity.

**Inputs:** Canonical cells, source edges, final mapping notes, frozen rules, split config, and lexicon.

**Procedure:** Select deterministic source-linked cases, preserve imperative subtype notes, validate conditions, and derive the surface/auxiliary operations.

**Outputs:** `realizations.jsonl`, `cell_splits.jsonl`, and `manifest.json`.

**Command:** `python scripts/run_experiment.py experiments/current.yaml --only realization`

**Configurable components:** Realization config, lexicon, rules, and schema.

