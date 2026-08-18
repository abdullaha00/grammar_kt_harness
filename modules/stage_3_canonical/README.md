# Canonical

Purpose: deduplicate complete scalar mappings into exact `GrammarCell`s while preserving typed source edges.

Input type: `EGPMapping[]`. See `contract.yaml` and `schemas/`.

Scientific/configuration inputs: canonical module version and the six-field identity schema; no model prompt.

Output types: `GrammarCellRecord[]` and `SourceCellEdge[]`.

Try the default fixture (`before` → `after`): `python -m modules.stage_3_canonical.run_one`

Single unit: `python -m modules.stage_3_canonical.run_one EGP_ID --experiment current` (or add `--input MAPPINGS.jsonl`).

Batch: `python scripts/run_experiment.py current --only canonical`

Adjustable research variables: none in the accepted identity contract.

Example question: Which source mappings merge into the same exact cell?
