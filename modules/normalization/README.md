# Normalization

**Purpose:** Convert the source subset into final v1.3 `EGPMapping` records.

**Inputs:** Source subset, annotation units, frozen schema/rulebook/prompts, and model configuration.

**Procedure:** Run Phase 1 per unit in a fresh context; route only partial/unresolved units to fresh Phase 2 with unchanged Phase 1 plus examples; validate every mapping and transition.

**Outputs:** `phase1.jsonl`, `phase2.jsonl`, `final_mappings.jsonl`, result partitions, non-gating duplicate diagnostics, `raw/`, mapping provenance, and `manifest.json`.

**Command:** `python scripts/run_experiment.py experiments/current.yaml --from normalization --to normalization`

**Configurable components:** Backend, model, reasoning effort, workers, prompts, rulebook, schema, and attempt limit.
