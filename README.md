# Grammar–KT: an auditable grammar knowledge-tracing benchmark

This repository turns a grammar resource into an explicit synthetic Knowledge
Tracing (KT) dataset and then uses the known synthetic truth to study KC
misspecification, discovery, and linguistic generalisation.

The active frozen dataset is
[`data/grammar_kt_full_v1/`](data/grammar_kt_full_v1/README.md). It contains the
full 1,222-row English Grammar Profile source census under the declared verbal
morphosyntax scope, 75 canonical GrammarCells, 18 reusable generator KCs, 113
independently model-validated items, a deterministic 113×18 true Q-matrix, and
283,000 events from 1,000 simulated learners.

The central scientific boundary is:

```text
GrammarCell != generator K* != discovered K-hat
```

- A **GrammarCell** describes the linguistic construction instantiated by an
  item.
- **K*** and **Q*** are declared latent truth inside one controlled simulator.
- **K-hat** and **Q-hat** are downstream experimental hypotheses supplied to or
  discovered by KT methods.

K* is not a claim about human cognitive decomposition. LLM item judgments are
not human pedagogical validation, simulator parameters are not human estimates,
and this English study does not establish cross-lingual empirical validity.

## Method in one view

```text
LAYER A — immutable dataset construction

1,222-row typed grammar resource
→ constrained two-phase normalisation with explicit uncertainty
→ exact six-dimensional English GrammarCells
→ outcome-free reusable-operation generator ontology K*
→ N=3 item generation + deterministic checks + independent validation
→ declared rescue/correction evidence + outcome-free max-two curation
→ fixed item bank + deterministic Q*
→ support/rank/equivalence audit
→ simple weakest-link learner simulation
→ public interactions + separate private oracle
→ frozen grammar_kt_full_v1

LAYER B — downstream research

frozen items/events
→ controlled KC merge/split and Q-noise hypotheses
→ observable-only KC discovery
→ semantic grammar-regime evaluation
→ oracle-only state-recovery evaluation
→ simulator and collection-design sensitivity
```

Baseline construction never reads learner outcomes, discovered KCs, or KT
metrics. Downstream representation comparisons reuse exactly the same event
rows whenever only K-hat/Q-hat changes. Probe outcomes never update learner
state and cannot influence KC selection.

## Frozen dataset

| Object | Full-v1 value |
|---|---:|
| Source descriptors processed | 1,222 |
| Complete / partial / unresolved / out-of-scope | 211 / 327 / 9 / 675 |
| Canonical cells / source–cell relations | 75 / 228 |
| Generator KCs K* | 18 |
| Fixed items / Q* edges | 113 / 269 |
| Seen / unseen-combination / unseen-value cells | 54 / 15 / 6 |
| Q* rank / identical columns | 18 of 18 / 0 |
| Learners | 1,000 |
| Acquisition / non-updating probe events | 170,000 / 113,000 |
| Total observable events | 283,000 |

The 15 unseen-combination cells are pairwise-seen but full-tuple-unseen. The six
unseen-value cells all instantiate perfect-progressive aspect. Acquisition uses
seen grammar only; every learner then receives one terminal probe for every
item.

The frozen simulator uses independent learner×KC `Beta(2,2)` initial mastery,
minimum/weakest-link multi-KC response aggregation, guess/slip `.10/.10`, and
an outcome-independent `.02` learning update for every active KC. There is no
baseline forgetting or item difficulty. A Q*-balanced schedule gives every
seen KC at least 12 acquisition opportunities while avoiding saturation.

Core public files are:

```text
data/grammar_kt_full_v1/
├── grammar/cells.jsonl
├── grammar/source_cell_relations.jsonl
├── grammar/regime_assignments.jsonl
├── kcs.jsonl
├── items/items.jsonl
├── q_matrix.csv
├── interactions.jsonl.gz
├── oracle/q_matrix_sparse.jsonl
├── oracle/learner_truth.jsonl.gz
├── provenance/
├── manifest.json
└── README.md
```

Ordinary KT and KC discovery use `interactions.jsonl.gz`, whose rows expose only
learner, item, sequence, correctness, phase, pass index, and grammar regime.
The oracle trajectory is deliberately separate.

## Established full-v1 evidence

The preregistered RQ2 study changes only K-hat/Q-hat over the same 283,000
events. K* obtains all-probe log loss `.670627`. Relative costs are:

| Representation | KCs | Δ log loss vs K* | 95% learner-paired CI |
|---|---:|---:|---:|
| structural split-2 | 35 | +.003165 | [.002744, .003581] |
| structural split-4 | 66 | +.005868 | [.005281, .006473] |
| linguistic-family merge | 6 | +.008132 | [.007450, .008779] |
| all KCs merged | 1 | +.010225 | [.009380, .011029] |
| exact-cell | 75 | +.015039 | [.014108, .015990] |

All nine frozen 10% Q-corruption structures also worsen prediction. Mean costs
are +.001685 for false-positive edges, +.002644 for false negatives, and
+.002294 for mixed noise; three structural seeds do not justify a universal
ordering of those corruption types.

The observable-only RQ3 procedure builds 181 candidates without reading K*,
Q*, oracle state, or probe outcomes. Its 1,000-learner selector retains an
18-feature base, but atomic-feature and compositional-operation hypotheses are
exactly Q-equivalent on seen items. The compositional candidate is a perfect
18/18 structural ceiling; the selected atomic projection recovers 16/18 KCs
exactly (padded activation Jaccard `.970854`, aligned Q-edge F1 `.965385`). The
two hypotheses have identical seen probe loss and differ only on unseen-value
perfect-progressive cells. Unique ontology recovery is therefore unsupported:
prediction identifies an equivalence class, not a uniquely true KC system.

RQ4 shows the value of reusable structure: exact-cell KCs cost +.037609 log
loss on 15 pairwise-seen/full-tuple-unseen combinations, while atomic and
compositional hypotheses remain indistinguishable on seen and combination
rows. Their unseen-value contrast crosses zero over six perfect-progressive
cells, so it cannot resolve the RQ3 equivalence class.

Oracle evaluation favors K* for overall item-prerequisite-state recovery
(RMSE `.123738` versus `.132752`--`.163828`), but a fixed BKT with mismatched
update semantics poorly recovers per-KC state. In 39 compact robustness worlds,
K* wins 38 primary comparisons; unmodelled item difficulty produces the sole
split-2 reversal. Collection controls show that A+B-only response volume cannot
break identical Q columns, anchors restore rank, and full rank still does not
guarantee practically unique recovery of a weak planted interaction.

See the live evidence ledger and final synthesis reports:

- [`reports/research_state.md`](reports/research_state.md)
- [`reports/experiment_log.md`](reports/experiment_log.md)
- [`reports/experiment_bank.md`](reports/experiment_bank.md)
- [`reports/full_dataset_investigation.md`](reports/full_dataset_investigation.md)
- [`reports/final_methodology.md`](reports/final_methodology.md)
- [`reports/final_rq_ledger.md`](reports/final_rq_ledger.md)
- [`reports/final_verification.md`](reports/final_verification.md)
- [`reports/final_release_manifest.json`](reports/final_release_manifest.json)
- [`ACL/paper.pdf`](ACL/paper.pdf)

## Researcher-facing declarations

Scientific assumptions are kept in small, inspectable files:

```text
modules/
├── model_backends.yaml
├── grammar/
│   ├── canonical/{schema.yaml,english_operations.yaml,rationale.md}
│   └── resource/egp/
│       ├── schema.yaml
│       └── normalisation/{phase1.txt,phase1_self_check.txt,phase2.txt,rulebook.md}
├── kcs/
│   ├── generator/{design.yaml,english_kcs.yaml,rationale.md}
│   ├── candidate_design.yaml
│   └── selection.yaml
├── items/
│   ├── generation/{design.yaml,prompt.txt,prompt_contextual.txt,rulebook.md}
│   └── validation/{prompt.txt,criteria.yaml}
├── simulation/
│   ├── baseline.yaml
│   ├── protocol.yaml
│   └── folds/semantic.yaml
└── evaluation/
```

English/resource-specific declarations contain EGP interpretation, the English
grammar schema and operations, and generation/validation prompts. Generator-KC
data models, Q projection/audit, simulation interfaces, representation
perturbations, and evaluation are schema-driven. Tests execute a non-English-
named `mood`/`person` toy contract through K* construction, Q*, scheduling, and
simulation; this proves software abstraction only.

## Active code

The baseline path is deliberately chronological and separate from experiments:

```text
scripts/build_dataset.py
scripts/build_true_q_matrix.py
scripts/investigate_baseline_simulator.py
scripts/freeze_baseline_dataset.py

src/grammar_kt/
├── normalise.py
├── canonicalise.py
├── generator_kcs.py
├── full_items.py
├── measurement_gate.py
├── baseline_simulation.py
└── dataset_freeze.py

scripts/experiments/
├── rq2_kc_misspecification.py
├── rq3_kc_discovery.py
├── full_v1_mastery_recovery.py
├── rq4_grammar_generalisation.py
├── simulator_robustness.py
└── collection_design.py
```

Historical medium-v1 scripts and artifacts remain available as pilot evidence,
but they do not construct K* for full-v1 and are not the source of final claims.

## Reproduce and verify

The LLM-backed source/normalisation/item evidence is frozen with provenance.
The deterministic Q* and complete public/private event streams can be replayed
exactly:

```bash
.venv/bin/python scripts/build_true_q_matrix.py \
  --cells data/grammar_kt_full_v1/grammar/cells.jsonl \
  --items data/grammar_kt_full_v1/items/items.jsonl \
  --kcs data/grammar_kt_full_v1/kcs.jsonl \
  --design modules/kcs/generator/design.yaml \
  --regimes data/grammar_kt_full_v1/grammar/regime_assignments.jsonl \
  --dense-q-matrix data/grammar_kt_full_v1/q_matrix.csv \
  --sparse-q-matrix data/grammar_kt_full_v1/oracle/q_matrix_sparse.jsonl \
  --audit data/grammar_kt_full_v1/provenance/measurement/audit.json \
  --manifest data/grammar_kt_full_v1/provenance/measurement/manifest.json \
  --verify-only

.venv/bin/python scripts/freeze_baseline_dataset.py \
  --dataset-dir data/grammar_kt_full_v1 \
  --pilot reports/baseline/artifacts/full_simulator_v1/pilot_seed_20260829.json \
  --verify-only

.venv/bin/python scripts/experiments/rq2_kc_misspecification.py --stage run

.venv/bin/python scripts/experiments/rq3_kc_discovery.py evaluate \
  --plan experiments/full_v1/rq3_kc_discovery_v1/plan.json \
  --selection experiments/full_v1/rq3_kc_discovery_v1/final_selection.json \
  --cohort final \
  --output /tmp/rq3_final_evaluation.json

.venv/bin/python -m pytest -q

.venv/bin/python scripts/final_release_manifest.py --verify
```

The retained RQ3 evaluator refuses to overwrite its frozen output; the `/tmp`
command is the independent replay form. Exact commands, model settings, seeds,
input hashes, and artifact hashes for every substantive experiment are recorded
in `reports/experiment_log.md`.

## Notebooks and paper

The tracked notebooks are read-only demonstrations; they do not make live model
calls or mutate the dataset:

```bash
.venv/bin/jupyter nbconvert --to notebook --execute \
  --output /tmp/pipeline_walkthrough.executed.ipynb \
  notebooks/pipeline_walkthrough.ipynb

GRAMMAR_KT_DATA_FOLDER=data/grammar_kt_full_v1 \
  .venv/bin/jupyter nbconvert --to notebook --execute \
  --output /tmp/final_dataset_results.executed.ipynb \
  --ExecutePreprocessor.timeout=600 \
  notebooks/final_dataset_results.ipynb

cd ACL
TZ=UTC SOURCE_DATE_EPOCH=1788069406 FORCE_SOURCE_DATE=1 \
  latexmk -g -pdf -interaction=nonstopmode -halt-on-error paper.tex
python tests/regression/run_tests.py
```

## Claim boundaries

- The empirical scope is single-main-clause English verbal morphosyntax over
  tense, aspect, voice, polarity, clause type, and central-modal identity; 675
  EGP records are legitimately outside that scope.
- Only complete mappings become exact GrammarCells. Partial and unresolved
  evidence is retained rather than silently completed.
- Automatic item validation has no human gold and is especially sensitive at
  determinacy boundaries. Cue-bounded imperative items are a labelled format
  limitation.
- K*, Q*, mastery, response probabilities, and sample-size findings are true
  only in declared synthetic worlds.
- Full column rank and many learner responses do not prove cognitive
  identifiability. RQ3 directly demonstrates a seen-Q equivalence class.
- The six-cell unseen-value cohort tests a particular perfect-progressive
  composition, not arbitrary unseen grammar or unseen latent skills.
- English-specific evidence does not establish cross-lingual validity.
