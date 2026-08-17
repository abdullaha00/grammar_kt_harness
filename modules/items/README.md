# Items

**Purpose:** Generate structurally constrained full-sentence transformations and validate them independently.

**Inputs:** Cells/source edges, realizations, KC projection/inventory, lexicon/rules, generation template, and diagnostic contract.

**Procedure:** Generation deterministically instantiates item-level RealizationSpecs; validation separately rederives structure, morphology, singleton answers, KC activation, provenance, nuisance/contrast constraints, then runs one fresh diagnostic context per unit.

**Outputs:** `generation/candidate_items.jsonl`; `validation/accepted_items.jsonl`, `rejected_items.jsonl`, `validation_results.jsonl`, `raw_validator/`; and separate manifests.

**Command:** `python scripts/run_experiment.py experiments/current.yaml --only items`

**Configurable components:** Item family/template, replicates, deterministic rule config, diagnostic backend/model/effort/prompt.

