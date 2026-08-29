# Grammar-KT medium dataset v1

This versioned tree is the retained Phase-6 dataset. Its source,
normalization, and canonical artifacts are complete. Item construction first
attempts the frozen N=3 design for every cell and independently validates each
structurally valid candidate.

The 139 English Grammar Profile descriptors and their 2026-08-20 normalization
outputs are retained rather than regenerated. The outputs are translated to
the active field names and validated against the current resource and
GrammarCell schemas. The 44 complete mappings yield 24 unique GrammarCells and
48 source-to-cell relations. This exactly preserves the feature inventory and
source memberships of the retained structural run.

The pilot item rows reuse only the first-three prefix of the independently
generated, model-selected Phase-4 condition. Old hash cell IDs are translated
by exact six-feature tuple. The active deterministic answer-span check is then
reapplied before bank selection. No fold, learner outcome, simulation, KC, or
KT information enters generation, validation, or item selection.

Prepare or verify all retained artifacts without model calls:

```bash
.venv/bin/python scripts/run_full_dataset.py \
  --prepare-only \
  --output-dir data/grammar_kt_medium_v1
```

After the Phase-5 methodology checkpoint, generate and independently validate
the missing 16 cells (48 generation attempts) with the frozen active settings:

```bash
.venv/bin/python scripts/run_full_dataset.py \
  --generate-missing \
  --workers 4 \
  --generation-model gpt-5.6-sol \
  --validation-model gpt-5.6-terra \
  --reasoning-effort medium \
  --output-dir data/grammar_kt_medium_v1
```

The script checkpoints every candidate attempt and every judgment in the
dataset tree. A malformed output remains an explicit failed attempt; reruns
call only candidate positions and item judgments for which no record exists.
Downstream fold, learner-evidence, KC-selection, projection, KT, and evaluation
artifacts are added only after the item bank is fixed.

If and only if all default N=3 positions and validations are complete but one
or more cells have zero accepted items, run the preregistered coverage rescue:

```bash
.venv/bin/python scripts/run_full_dataset.py \
  --rescue-uncovered \
  --workers 4 \
  --generation-model gpt-5.6-sol \
  --validation-model gpt-5.6-terra \
  --reasoning-effort medium \
  --output-dir data/grammar_kt_medium_v1
```

Before making any call, this mode freezes the uncovered-cell cohort in
`items/rescue_plan.json`. It then generates and independently validates exactly
candidate positions 4 and 5 for every cohort cell, using the unchanged prompt,
rulebook, task design, models, and validation criteria. Rescue provenance is
explicit on each attempt, candidate, and judgment. The manifest reports
default and rescue counts separately, and interrupted reruns never recall a
retained position or terminal judgment.

If that unchanged-prompt rescue is complete but a cell remains uncovered and
every one of its prior terminal judgments failed determinacy, run the separately
preregistered determinacy intervention:

```bash
.venv/bin/python scripts/run_full_dataset.py \
  --determinacy-intervention \
  --workers 4 \
  --generation-model gpt-5.6-sol \
  --validation-model gpt-5.6-terra \
  --reasoning-effort medium \
  --output-dir data/grammar_kt_medium_v1
```

This mode freezes the post-rescue cohort in
`items/determinacy_intervention_plan.json` before any call, then attempts
exactly positions 6 and 7 for every frozen cell. Its researcher-facing prompt
is
`modules/items/generation/ablations/determinacy_explicit_construction_prompt.txt`:
the learner instruction may name the target construction but may not reveal an
inflected response. The rulebook, task format, generation design apart from the
declared position extent, models, validator prompt, and validation criteria are
unchanged. Attempts, candidates, and judgments have a distinct intervention
status; call evidence is stored under dedicated `determinacy_intervention/`
directories; and the manifest reports this cohort separately. Reruns recall
neither a retained position nor a terminal judgment.

After the all-item packaging audit, apply the separately preregistered six-row
answer-key correction and independently rejudge exactly those corrected
packages:

```bash
.venv/bin/python scripts/curate_item_packaging.py \
  --dataset-dir data/grammar_kt_medium_v1 \
  --workers 4 \
  --validation-model gpt-5.6-terra \
  --reasoning-effort medium
```

The script verifies the frozen plan and raw artifact hashes before any call.
It never changes `items/candidates.jsonl` or `items/validation.jsonl`; corrected
rows, correction-only judgments, and call evidence are retained separately.
It moves old-bank derivatives into the dated `superseded_pre_curation/`
archive, then deterministically rebuilds the accepted pool, selected bank,
summary, and item manifest. The downstream finalizer must be rerun afterward.

Once `manifest.json` records `fixed_item_bank_complete`, finalize the frozen
bank with the Phase-5-active KC selection declaration and the retained mixed
learner world:

```bash
.venv/bin/python scripts/finalize_full_dataset.py \
  --dataset-dir data/grammar_kt_medium_v1 \
  --learners 1000 \
  --seed 20260827 \
  --bootstrap-repeats 5000
```

The finalizer refuses an incomplete bank before writing any downstream
artifact. It evaluates factorized, all-supported-interaction, automated, and
labelled oracle-all-cell representations on the identical frozen event stream.
Large event, private-oracle, and prediction row artifacts are retained as
deterministic gzip files; policies, projections, Q-matrices, summaries, and
evaluation results remain plain-text inspectable files.

Measure support and seed stability without changing the fixed bank or
candidate inventory:

```bash
.venv/bin/python scripts/run_phase6_selection_stability.py
```

This staged study selects on nested 60/120/240/500/1,000-learner prefixes of
seed 20260827 and on five full 1,000-learner streams (20260827--20260831).  Its
compact result is retained at `kc/selection_stability.json`; the event streams,
policies, traces, and integrity manifests remain under
`reports/phase6/artifacts/selection_stability_v1/`.

Regenerate all paper-facing tables deterministically, with no model call or
learner resimulation:

```bash
.venv/bin/python scripts/analyze_full_dataset.py \
  --dataset-dir data/grammar_kt_medium_v1 \
  --output-dir reports/phase6/artifacts/full_dataset_analysis
```

## Final retained scale

| Object | Count |
|---|---:|
| Source descriptors | 139 |
| Complete / partial / unresolved / out-of-scope mappings | 44 / 77 / 2 / 16 |
| Canonical GrammarCells | 24 |
| Generation attempts / payloads | 78 / 77 |
| Curated validator accepts / selected items | 54 / 44 |
| Development / compositional / novel-value cells | 18 / 5 / 1 |
| Development / compositional / novel-value items | 32 / 10 / 2 |
| Synthetic learners / events | 1,000 / 204,000 |
| Raw / activation-class / selection-eligible KC candidates | 55 / 38 / 28 |
| Automatically selected KCs | 10 (nine marginals + one interaction) |

## Artifact schema and roles

```text
source/descriptors.jsonl                 typed EGP source records
normalisation/mappings.jsonl             complete/partial/unresolved mappings
canonical/cells.jsonl                    exact canonical feature tuples
canonical/source_cell_relations.jsonl    many-to-many source→cell evidence
items/candidates.jsonl                   immutable raw generated payloads
items/validation.jsonl                   immutable original judgments
items/curated_{candidates,validation}.jsonl
                                         active packaging-corrected evidence
items/selected_bank.jsonl                fixed learner-facing measurement bank
fold/assignments.jsonl                   outcome-free semantic grammar regimes
simulation/events.jsonl.gz               fixed observable learner history
simulation/oracle_debug.json.gz          private simulator diagnostics only
kc/candidate_inventory.json              support/equivalence candidate artifact
kc/selection_trace.json                  development-only selector trajectory
kc/policies/*.yaml                       frozen comparison policies
kc/projections/*.jsonl, q_matrices/*.csv item–KC mappings
kt/*/predictions.jsonl.gz                online KT predictions
evaluation/*/results.json                metrics by technique and regime
evaluation/paired_logistic.json           learner-cluster paired intervals
finalization_manifest.json               final scale, methods, seeds, commands
```

Rows use stable string IDs only for reference.  Scientific fold decisions and
KC activation are made from canonical feature tuples, not ordinal ID values.
The same learner-event file is reused across every KC representation.

## Evidence and limitations

The selected policy is identical across all five retained 1,000-learner mixed-
world seeds.  One 120-learner prefix swaps its interaction, so stability is not
claimed at low support.  The final item bank is model-generated and model-
judged; an independent agent audit is not human or expert validation.  Learner
responses are synthetic, the empirical grammar study is English-only, and the
alternate-schema tests establish an interface contract rather than cross-
lingual validity.  See `reports/full_dataset_investigation.md` for the complete
RQ-by-RQ analysis and claim boundaries.
