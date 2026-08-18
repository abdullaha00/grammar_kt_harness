# Normalization

Purpose: map one source descriptor to the frozen two-phase `EGPMapping` contract.

Input types: `SourceDescriptor`, Phase-1 source projection, and `AnnotationUnit`. See `contract.yaml` and `schemas/`.

Scientific/configuration inputs: versioned phase prompts and their explicit invocation wrapper in `prompts/`, rulebook/model instructions in `rules/`, output schema in `schemas/`, validator in `v1_3/`, and backend/model settings in `configs/`.

Output types: Phase-1/Phase-2/final mappings plus one evidence directory per invocation containing `input.json`, `rendered_prompt.txt`, `invocation.json`, raw output, parsed output, and validation.

Try the default fixture (`before` → `after`): `python -m modules.stage_2_normalization.run_one`. This invokes the configured model backend.

Single unit: `python -m modules.stage_2_normalization.run_one EGP_ID --experiment current`

Inspect: `python -m modules.stage_2_normalization.inspect EGP_ID --experiment current`

Fixture batch: `python -m modules.stage_2_normalization.run --input modules/stage_2_normalization/fixtures/core.jsonl --experiment current`

Complete stage: `python scripts/run_experiment.py current --only normalization`

Adjustable research variables: Phase-1/2 prompt, rulebook, backend, model, reasoning effort, timeout, and retry count.

Example questions: What changes under Phase-1 prompt wording or another backend? Which descriptors change partial→complete, and which exact cell values differ?
