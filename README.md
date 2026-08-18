# Grammar-to-KT research harness

This repository is a small experimental laboratory around the accepted grammar-to-KT pipeline. It preserves the methodology while making each scientific input, one-unit decision, run difference, and lineage edge inspectable.

```text
source → normalization → canonical → realization → kc → items
       → qmatrix → simulation → kt
provenance references every declared interface and methodology hash
```

The package folders are numbered in pipeline order for file-explorer browsing:

```text
modules/
  stage_1_source/
  stage_2_normalization/
  stage_3_canonical/
  stage_4_realization/
  stage_5_kc/
  stage_6_items/
  stage_7_qmatrix/
  stage_8_simulation/
  stage_9_kt/
  stage_10_provenance/
```

The semantic stage names inside run directories and manifests remain stable
(`source`, `normalization`, …, `provenance`).

Each module contains a concise README, `contract.yaml`, its behavior-defining prompts/rules/configs/schemas, representative fixtures where useful, executable stage code, and unit-level commands. Generated observations live only in `runs/`.

## Install and reference experiment

Use Python 3.11+:

```bash
python -m pip install -e .
python scripts/run_experiment.py current
python scripts/validate_experiment.py runs/current
```

The external EGP source is hash-pinned but not redistributed. Its current local path can be overridden with `--source-path`.

The accepted reference manifest still declares:

```text
139 unique descriptors → 44 complete mappings → 24 exact cells
→ 9 factorized KCs → 45 accepted items → 45×9 Q / 99 edges
→ 180 learners / 16,200 observable interactions
```

These are operational reference counts. Synthetic states are simulator truth; automated diagnostics are not human item validation; KT metrics are technical sanity checks.

## Unit and fixture workflow

Every `run_one` command has a representative default and prints explicit
`before` and `after` JSON. These demonstrations write to `runs/run_one_demo/`:

```bash
python -m modules.stage_1_source.run_one
python -m modules.stage_2_normalization.run_one  # invokes the configured model
python -m modules.stage_3_canonical.run_one
python -m modules.stage_4_realization.run_one
python -m modules.stage_5_kc.run_one
python -m modules.stage_6_items.run_one
python -m modules.stage_8_simulation.run_one
```

Pass an identifier to replace the representative default:

```bash
python -m modules.stage_2_normalization.run_one EGP_ID --experiment current
python -m modules.stage_2_normalization.inspect EGP_ID --experiment current
python -m modules.stage_4_realization.run_one CELL_ID --experiment current
python -m modules.stage_5_kc.run_one CELL_ID --experiment full_cell
python -m modules.stage_5_kc.explain CELL_ID --experiment full_cell
python -m modules.stage_6_items.run_one OPPORTUNITY_ID --experiment current
python -m modules.stage_6_items.inspect ITEM_ID --experiment current
python -m modules.stage_7_qmatrix.explain ITEM_ID --experiment current
python -m modules.stage_8_simulation.run_one LEARNER_ID --experiment current
```

Representative deterministic fixtures run without scaling the experiment:

```bash
python -m modules.stage_4_realization.run --input modules/stage_4_realization/fixtures/core.jsonl
python -m modules.stage_5_kc.run --input modules/stage_5_kc/fixtures/core.jsonl
python -m modules.stage_6_items.run --input modules/stage_6_items/fixtures/core.jsonl
```

Normalization fixtures invoke the configured backend and therefore are explicit:

```bash
python -m modules.stage_2_normalization.run \
  --input modules/stage_2_normalization/fixtures/core.jsonl \
  --experiment current
```

## Controlled variants, reuse, and comparison

Variant YAML files deep-merge `extends: current`. `runs/<id>/experiment_manifest.json` stores the fully resolved manifest and scientific-file hashes; `diff_from_parent.json` stores leaf-level interventions.

```bash
python scripts/run_experiment.py kt_bkt_only --only kt
python scripts/compare_runs.py runs/current runs/kt_bkt_only --stage kt
```

The runner fingerprints each stage from its declared input hashes, scientific configuration/resource hashes, and relevant implementation hashes. An identical completed stage is symlink-reused and recorded as `reused` in `stage_status.json`; otherwise it is `executed`. `--force` deliberately bypasses reuse for selected stages.

See [DESIGN.md](DESIGN.md), [experiments/README.md](experiments/README.md), and the module READMEs for exact contracts and research variables.
