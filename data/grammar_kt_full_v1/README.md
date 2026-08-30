# Grammar-KT full dataset v1

This is the frozen Layer-A Grammar-KT baseline. It contains 75
canonical English GrammarCells, 18 declared synthetic
generator KCs, 113 fixed learner-facing items, a deterministic
true Q-matrix, and 283,000 observable response events from
1,000 simulated learners.

The scientific objects remain distinct:

```text
GrammarCell != generator K* != downstream discovered K-hat
```

K* and Q* are controlled truth only inside the declared synthetic world. They
are not claims about human cognitive decomposition. Automatic item validation
is not human pedagogical gold, simulator parameters are not human estimates,
and the English study does not establish cross-lingual empirical validity.

## Core artifacts

```text
grammar/cells.jsonl                     canonical linguistic structures
grammar/source_cell_relations.jsonl     auditable source-to-cell relations
kcs.jsonl                               frozen generator KC inventory K*
items/items.jsonl                       fixed learner-facing item bank
q_matrix.csv                            dense true item-to-KC mapping Q*
grammar/regime_assignments.jsonl        seen/generalisation regimes
interactions.jsonl.gz                   observable learner event stream
oracle/q_matrix_sparse.jsonl            sparse auditable Q* projection
oracle/learner_truth.jsonl.gz            private simulator trajectories
manifest.json                           hashes, counts, and reconstruction record
```

The structural grammar split contains 54 seen,
15 unseen-combination, and
6 unseen-value cells. Acquisition presents
seen items only. A terminal all-bank probe does not update mastery.

## Observable interactions

Every JSONL row has exactly:

```text
learner_id item_id sequence_index correct phase pass_index grammar_regime
```

`correct` is integer 0/1. During acquisition, `pass_index` is the item-local
exposure index. During probes, it is the probe-repeat index. The composite
`learner_id + sequence_index` is the stable event key. Ordinary KT does not
need `oracle/learner_truth.jsonl.gz`.

The private oracle has exactly:

```text
learner_id item_id sequence_index phase pass_index grammar_regime active_generator_kc_ids mastery_before aggregated_mastery_before response_probability response_draw correct updates_mastery mastery_after
```

It records active K*, mastery before/after, the weakest-link aggregate, true
response probability, and response draw. Keep it hidden from ordinary KT and
KC-discovery inputs; use it only for controlled evaluation.

## Frozen simulator

- simulation ID: `explicit_generator_kstar_baseline_v1`
- seed: `20260829`
- initial mastery: `Beta(2.0, 2.0)`
- response aggregation: minimum/weakest-link
- guess/slip: `0.1` / `0.1`
- learning: all active KCs, opportunity-based rate `0.02`
- forgetting and item difficulty: none
- acquisition target: at least `12` opportunities per seen KC
- pilot condition: `agg-minimum__update-all_active_opportunity__schedule-qbalanced-target-12__rate-0.020__beta-2.0-2.0__noise-0.10`

## Reconstruction and verification

The LLM-backed source, normalisation, item-generation, validation, rescue, and
packaging-correction evidence is retained under `provenance/`. Deterministic
construction from the frozen item/KC inputs is verified with:

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
```

Original stream-freeze invocation:

```text
/home/abdullah/grammar_kt_harness/.venv/bin/python scripts/freeze_baseline_dataset.py --dataset-dir data/grammar_kt_full_v1 --pilot reports/baseline/artifacts/full_simulator_v1/pilot_seed_20260829.json
```

Gzip uses an empty embedded filename, compression level 9, and `mtime=0`.
`manifest.json` records both compressed-byte hashes and uncompressed canonical
JSONL content hashes. Downstream experiments must treat this directory as
immutable and write their hypotheses and results elsewhere.
