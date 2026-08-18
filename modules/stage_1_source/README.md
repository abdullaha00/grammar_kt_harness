# Source

Purpose: select the hash-pinned 139-descriptor subset without redistributing the external EGP source.

Input type: `SourceDescriptor[]` from `source.path`. The exact contract is in `contract.yaml`; the schema is `schemas/source_descriptor.schema.json`.

Scientific/configuration inputs: source hash, selected IDs, sample metadata, and annotation-unit declarations in `configs/current/`.

Output types: source subset, Phase-1 projection, sample metadata, and annotation units.

Try the default fixture (`before` → `after`): `python -m modules.stage_1_source.run_one`

Single unit: `python -m modules.stage_1_source.run_one EGP_ID --experiment current`

Batch: `python scripts/run_experiment.py current --to source`

Adjustable research variables: external path only for the reference experiment; changing IDs or the expected hash defines a different source design.

Example question: Does a result change because the source record changed, or because a downstream method changed?
