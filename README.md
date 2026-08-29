# Grammar–KT: dataset and executable research methodology

This repository turns grammar-resource evidence into a fixed learner-item bank,
derives and selects interpretable Knowledge Components (KCs) from development
grammar and learner evidence, freezes the resulting Q-matrix, and evaluates
knowledge tracing under grammar holdouts.

The retained research outcome is
[`data/grammar_kt_medium_v1/`](data/grammar_kt_medium_v1/README.md): 139 typed
English Grammar Profile descriptors, 24 canonical GrammarCells, 44 curated
model-validated items, 1,000 synthetic learners, and 204,000 fixed events. The
active automated policy contains nine feature KCs and one selected interaction.
The evidence supports a small overall mixed-world prediction gain over the
factorized representation; it does **not** establish human cognitive validity
or a compositional advantage for the automated policy.

## Method in one view

```text
typed grammar resource
→ constrained resource-specific normalisation
→ canonical GrammarCells
→ N=3 contextual item generation
→ deterministic checks + independent validation
→ frozen curated item bank
→ semantic development/compositional/novel-value fold
→ development acquisition + non-updating frozen probes
→ development-only KC candidates
→ support and activation-equivalence filtering
→ predictive loss + KC-count selection
→ frozen policy and Q-matrix
→ empirical / BKT / observable-logistic KT
→ regime metrics and learner-paired comparisons
```

Open [`scripts/run.py`](scripts/run.py) for the short, linear paper-facing
implementation. It names every active scientific declaration and invokes the
actual stage functions in order. There is no workflow engine, registry,
configuration inheritance, or policy-conditioned item generation.

The key boundary is enforced in code and tests:

> Generation and simulation receive no KC policy. Candidate construction sees
> development cells and fixed items but no outcomes. Selection sees only
> development train/validation events. The selected policy is frozen before
> grammar-holdout evaluation, and every policy uses the same items and events.

## Final evidence

| Object | Final retained value |
|---|---:|
| Source descriptors | 139 |
| Complete / partial / unresolved / out-of-scope mappings | 44 / 77 / 2 / 16 |
| Canonical cells | 24 |
| Generation attempts / valid payloads | 78 / 77 |
| Curated validator accepts / selected items | 54 / 44 |
| Development / compositional / novel-value cells | 18 / 5 / 1 |
| Development / compositional / novel-value items | 32 / 10 / 2 |
| Learners / fixed events | 1,000 / 204,000 |
| Raw / activation-class / selection-eligible candidates | 55 / 38 / 28 |
| Factorized / automated / all-interaction / exact-cell KCs | 9 / 10 / 16 / 24 |

Primary no-oracle logistic test log loss is .643731 factorized, .643356
automated, .643334 with every supported interaction, and .657507 for the
labelled exact-all-cell oracle. Automated minus factorized is −.000375 with a
5,000-repeat whole-learner 95% interval [−.000631, −.000109] overall; its
compositional interval [−.000836, .000375] crosses zero. All five retained
1,000-learner mixed-world seeds select the same 10-KC inventory, while one
120-learner subsample swaps the interaction.

Trace every value through:

- [`reports/full_dataset_investigation.md`](reports/full_dataset_investigation.md)
- [`reports/final_methodology.md`](reports/final_methodology.md)
- [`reports/final_rq_ledger.md`](reports/final_rq_ledger.md)
- [`reports/experiment_log.md`](reports/experiment_log.md)
- [`reports/research_state.md`](reports/research_state.md)
- [`ACL/paper.pdf`](ACL/paper.pdf)

## Researcher-facing declarations

Only files that change a scientific assumption remain under `modules/`:

```text
modules/
├── model_backends.yaml
├── grammar/
│   ├── canonical/{schema.yaml,english_operations.yaml,rationale.md}
│   └── resource/egp/
│       ├── schema.yaml
│       └── normalisation/{phase1.txt,phase1_self_check.txt,phase2.txt,rulebook.md}
├── items/
│   ├── generation/{prompt.txt,prompt_contextual.txt,rulebook.md,design.yaml}
│   │   ├── formats/controlled_production.yaml
│   │   └── ablations/{controlled_lexicon.jsonl,determinacy_explicit_construction_prompt.txt}
│   └── validation/{prompt.txt,criteria.yaml}
├── simulation/
│   ├── folds/semantic.yaml
│   ├── protocol.yaml
│   └── worlds/{phase3_*.yaml,phase4_*.yaml}
├── kcs/{candidate_design.yaml,selection.yaml}
└── evaluation/{protocol.yaml,kt/protocol.yaml}
```

Examples of genuine interventions are the background values and pair-support
thresholds in `candidate_design.yaml`, the complexity penalty in
`selection.yaml`, the semantic holdout requirements, the four latent worlds,
the generation prompt, the validation criteria, and the per-stage model and
reasoning settings in `model_backends.yaml`. Manual KC policies, ID-specific
folds, fixture worlds, and historical generator-tag rules live under
`data/fixtures/`, not the active declaration tree.

## Active code

```text
src/grammar_kt/
├── normalise.py       constrained two-phase mapping
├── canonicalise.py    exact GrammarCell construction
├── generate.py        fixed-cell item generation
├── validate_items.py  deterministic and independent validation/bank selection
├── fold.py            semantic grammar split
├── simulate.py        schema-validated latent worlds and frozen probes
├── kc_candidates.py   generic structural candidate space
├── kc_selection.py    development-only forward/prune selector
├── kc.py              frozen projection and Q-matrix
├── kt.py              empirical, BKT, and observable logistic KT
└── evaluate.py        regime metrics and paired uncertainty
```

Meaningful experiment procedures remain explicit scripts rather than a generic
framework: `run_candidate_analysis.py`, `run_kc_selection_experiments.py`,
`run_phase4_world_audit.py`, `run_phase5_integrated_validation.py`,
`run_full_dataset.py`, `curate_item_packaging.py`,
`finalize_full_dataset.py`, `run_phase6_selection_stability.py`, and
`analyze_full_dataset.py`.

## Reproduce the retained dataset and evidence

The exact language-model calls are checkpointed and reused. Preparation and
analysis modes make no model calls.

```bash
# Verify/rebuild source→fixed-bank artifacts from retained calls.
.venv/bin/python scripts/run_full_dataset.py \
  --prepare-only --output-dir data/grammar_kt_medium_v1

# Rebuild fold, learner evidence, candidate inventory, selected policy,
# projections, KT predictions, and paired evaluation deterministically.
.venv/bin/python scripts/finalize_full_dataset.py \
  --dataset-dir data/grammar_kt_medium_v1 \
  --learners 1000 --seed 20260827 --bootstrap-repeats 5000

# Reuse or verify five retained stability streams and nine selections.
.venv/bin/python scripts/run_phase6_selection_stability.py

# Regenerate paper-facing CSV/Markdown/JSON evidence without simulation.
.venv/bin/python scripts/analyze_full_dataset.py \
  --dataset-dir data/grammar_kt_medium_v1 \
  --output-dir reports/phase6/artifacts/full_dataset_analysis
```

The complete original live-call sequence, including the N=3 generation,
unchanged rescue, explicit-construction intervention, frozen six-item packaging
correction, models, settings, hashes, and output paths, is recorded in the
experiment ledger and dataset README.

## Run the readable pipeline offline

Fixture mode exercises the same active functions with deterministic model
responses and isolated fixture declarations. It is software evidence only.

```bash
.venv/bin/python scripts/run.py --fixture --output runs/fixture
.venv/bin/jupyter nbconvert --to notebook --execute \
  --output /tmp/pipeline_walkthrough.executed.ipynb \
  notebooks/pipeline_walkthrough.ipynb

# Display every retained final-dataset stage as pandas tables.
GRAMMAR_KT_DATA_FOLDER=data/grammar_kt_medium_v1 \
  .venv/bin/jupyter nbconvert --to notebook --execute \
  --output /tmp/final_dataset_results.executed.ipynb \
  --ExecutePreprocessor.timeout=600 \
  notebooks/final_dataset_results.ipynb

.venv/bin/python -m pytest -q
```

Open `notebooks/final_dataset_results.ipynb` interactively and edit its
`DATA_FOLDER` parameter cell to inspect another completed dataset folder. The
notebook is read-only: it derives all tables from that folder, loads no report
artifacts or private simulator truth, and samples rather than prints the full
learner-event and KT-prediction rows.

Live `scripts/run.py` reads `modules/model_backends.yaml`: normalisation uses
`gpt-5.6-sol` at high reasoning, generation uses `gpt-5.6-sol` at medium, and
validation uses `gpt-5.6-terra` at medium. It creates a new output directory
and is not needed to reproduce the retained final dataset, whose original
model settings remain frozen in its manifest and experiment ledger.

Build and check the manuscript:

```bash
cd ACL
latexmk -pdf -interaction=nonstopmode -halt-on-error paper.tex
python tests/regression/run_tests.py
```

## Language-generality boundary

English/resource-specific components are the EGP schema and normalisation,
English GrammarCell dimensions/values, operation declarations, prompts,
realisation rules, and all empirical results. Candidate enumeration,
activation/support/equivalence, learner-evidence selection, policy freezing,
projection, and evaluation consume an arbitrary declared dimension/value
schema. The alternate `mood`/`person` test executes
candidate construction → selection → freezing → projection without English
feature names. That is an interface/generalisation contract, not empirical
cross-lingual validity.

## Claim boundaries

- Items are LLM-generated and model-validated; the exhaustive agent audit is
  not teacher, linguist, or learner validation.
- Learner responses and latent mastery are synthetic. Worlds omit vocabulary
  state, forgetting, cross-KC transfer, strategy mixtures, and classroom effects.
- The empirical grammar inventory is English-only, sparse in WH/modal values,
  and selective rather than a frequency-balanced account of English grammar.
- The compositional regime has five cells; the novel-value regime has one
  `would` cell/two items and no reusable KC coverage.
- Activation equivalence is measured-bank equivalence, not universal linguistic
  equivalence. Background/reference values and protected marginals are
  explicit methodological assumptions.
- No KC representation wins across every declared latent world. The final
  contribution is an auditable selection method and dataset-generation
  pipeline, not discovery of a uniquely true human grammar ontology.
