# KC projection

Purpose: apply one declared KC policy to frozen cell/realization opportunities.

Input types: canonical cell records and realization records. See `contract.yaml` and `schemas/`.

Scientific/configuration inputs: exactly one policy from `policies/`.

Output types: `KCSpec[]` and `KCActivation[]`.

Try the default fixture (`before` → `after`): `python -m modules.stage_5_kc.run_one`

Single unit: `python -m modules.stage_5_kc.run_one CELL_ID --experiment current`

Explain/compare: `python -m modules.stage_5_kc.explain CELL_ID --experiment current --compare-policy full_cell`

Fixture batch: `python -m modules.stage_5_kc.run --input modules/stage_5_kc/fixtures/core.jsonl --policy factorized`

Complete stage: `python scripts/run_experiment.py current --only kc`

Adjustable research variables: `factorized`, `full_cell`, or `factorized_plus_interactions` policy.

Example questions: What changes under full-cell versus factorized projection? Which opportunities gain or lose activations, and which exact rule caused each edge?
