# Items

Purpose: deterministically construct controlled transformations, run hard checks, then run an independent model diagnostic.

Input types: realization records, frozen `KCActivation`s, and `KCSpec`s. The module never reopens raw EGP or normalization output. See `contract.yaml` and `schemas/`.

Scientific/configuration inputs: generation/diagnostic prompts in `prompts/`, deterministic and model rules in `rules/`, schemas in `schemas/`, and backend settings in `configs/`.

Output types: candidate/accepted/rejected `ItemSpec`s, `ValidationResult`s, and exact model-unit evidence.

Try one deterministic fixture (`before` → `after`): `python -m modules.stage_6_items.run_one`

Single opportunity: `python -m modules.stage_6_items.run_one OPPORTUNITY_ID --experiment current`. To preserve the accepted global uniqueness/sampling rule, this reconstructs the small deterministic target allocation in memory, writes only the selected opportunity, and invokes no diagnostic model.

Inspect item: `python -m modules.stage_6_items.inspect ITEM_ID --experiment current`

Fixture batch: `python -m modules.stage_6_items.run --input modules/stage_6_items/fixtures/core.jsonl --experiment current`

Complete stage: `python scripts/run_experiment.py current --only items`

Adjustable research variables: item family/template, replicate counts, hard rules, diagnostic prompt/backend/model.

Example questions: How does another item family affect determinacy or rejection? Which validation category changed, and did the accepted answer change?
