# Realization

Purpose: attach executable, source-linked `RealizationSpec`s without changing grammar identity.

Input types: exact canonical cells and explicit `SourceCellEdge` information. See `contract.yaml` and `schemas/`.

Scientific/configuration inputs: split config and lexicon in `configs/`, rules in `rules/`, and schema in `schemas/`.

Output types: validated realization records and cell splits.

Try the default fixture (`before` → `after`): `python -m modules.stage_4_realization.run_one`

Single unit: `python -m modules.stage_4_realization.run_one CELL_ID --experiment current`

Fixture batch: `python -m modules.stage_4_realization.run --input modules/stage_4_realization/fixtures/core.jsonl --experiment current`

Complete stage: `python scripts/run_experiment.py current --only realization`

Adjustable research variables: lexicon, source-linked realization conditions, and held-out split.

Example questions: Which realization conditions change a surface operation? Do perfect, passive, negation, question, and imperative fixtures still realize deterministically?
