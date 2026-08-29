# Research state

Last updated: 2026-08-29. The programme has been reopened under the revised
baseline-versus-experiment framing in `AGENTS.md`. The previous medium-scale
programme remains historical evidence; it is not the generator truth for the
new full dataset.

## Active scientific framing

The project now separates four objects throughout:

```text
SOURCE / LINGUISTIC REPRESENTATION
EGP descriptors → canonical GrammarCells

SYNTHETIC GENERATOR TRUTH
fixed K* + deterministic Q*

OBSERVABLE DATA
fixed items + learner responses

DOWNSTREAM HYPOTHESES
K_hat + Q_hat supplied to or discovered by KT experiments
```

`GrammarCell != K* != K_hat`. In particular, learner outcomes may not define
the KCs that generated those outcomes.

## Active construction pipeline

```text
verified 1,222-row EGP snapshot
→ all-row descriptor-only Phase 1
→ frozen eligibility cohort
→ branch-preserving Phase 2
→ exact six-dimensional English GrammarCells
→ declared reusable-operation generator KCs K*
→ N=3 independent item candidates/cell
→ deterministic checks + independent validation + explicit curation
→ fixed item bank
→ deterministic Q*
→ mandatory support/rank/equivalence audit
→ simple K*/Q*-consuming learner simulator
→ observable interactions + separate oracle trajectories
→ immutable `data/grammar_kt_full_v1/`
```

Only after that dataset is frozen will KC misspecification, KC discovery, KT
robustness, sample complexity, and grammatical-generalisation experiments
become the active queue.

## Repository audit result

- Active research branch: `agent/full-dataset-research-program`, based on
  `c2e1d21e`.
- The previous branch is synchronized with its remote and ten commits ahead of
  `origin/main`.
- User-owned dirty files are preserved: modified `pipeline.txt`; untracked
  `AGENTS.md`, root `experiment_bank.md`, `ideas.txt`, `rqs.txt`,
  `notebooks/final_dataset.ipynb`, and `tmp/`.
- Initial verification passes: 112 Pytest contracts, both tracked notebooks,
  the fixture runner, the ACL build, and 71 ACL regression checks.

## Artifact classification

### Active/reusable Layer-A methodology

- `modules/grammar/` and `src/grammar_kt/{normalise,canonicalise}.py`
- `modules/items/` and
  `src/grammar_kt/{generate,validate_items}.py`
- model-effort result in `modules/model_backends.yaml`
- new full runner `scripts/build_dataset.py`
- new K* declaration under `modules/kcs/generator/`
- new generic K*/Q* code in
  `src/grammar_kt/{generator_kcs,measurement}.py`

### Historical evidence

- `data/grammar_kt_medium_v1/`: 139 descriptors, 24 cells, 44 curated items,
  1,000 learners, and 204,000 events.
- Phase 2--7 reports/artifacts and the backend-effort audit.
- `runs/base/kc/kc_inventory.jsonl`: earlier nine-KC hybrid structural design.

### Reusable Layer-B experiments

- `src/grammar_kt/{kc_candidates,kc_selection,kt,evaluate}.py`
- phase 3--6 candidate, selection, latent-world, KT, stability, and paired
  evaluation scripts/artifacts.

These define or evaluate `K_hat`; they are no longer part of baseline dataset
construction.

### Superseded as active final claims

- The outcome-selected pipeline in `scripts/run.py` and
  `scripts/finalize_full_dataset.py`.
- The old “programme complete” conclusions in the existing final reports and
  ACL manuscript. They remain retained until full-v1 evidence supports their
  replacements.

## Full linguistic scope and completed census

- Consult-only source:
  `/home/abdullah/urop-aug/sources/parsed_final/egp_entries.jsonl`
- Verified SHA-256:
  `e38c4f959f188150dae7b88f21e35d77828048772e222191818dc0c2488486cd`
- 1,222 unique descriptors; 1,218 marked usable by the extractor and four with
  empty can-do/example evidence.
- Scope decision: process all 1,222 rows, then classify them against the
  existing explicit boundary: single-main-clause English verbal morphosyntax
  over tense, aspect, voice, polarity, clause type, and central-modal identity.
- The frozen all-row Phase-1 census completed without a technical failure:
  170 complete, 375 partial, two unresolved, and 675 out-of-scope mappings.
- Of 106 Phase-2-eligible partials, 105 had licensed examples and were called;
  41 became complete, 57 remained partial, and seven became unresolved. The
  final census is therefore 211 complete, 327 partial, nine unresolved, and
  675 out-of-scope descriptors.
- Complete mappings yield 75 exact canonical GrammarCells and 228 immutable
  source-cell relations. No schema constraint failed and no schema expansion
  is justified by the observed failure groups; remaining uncertainty is
  concentrated in unspecified polarity, clause, voice, aspect, and tense.
- A balanced fresh 120-descriptor Phase-1 repeat obtained 93.3% result
  agreement and 95.8% Phase-2-eligibility agreement. All 38 descriptors judged
  complete in both runs had exactly the same canonical cell set. Lower
  agreement in partial branch multisets (79.0% among mappings with any branch)
  supports retaining explicit uncertainty rather than default completion.
- Raw source text and rendered prompts remain restricted under ignored
  `runs/`; only source identity and derived artifacts enter the publishable
  dataset tree.

The previous 139 rows were a purposive sample and omit both WH clause values
and every central modal except `would`; they cannot establish final linguistic
coverage.

## Generator-KC decision before item construction

The frozen outcome-free generator inventory uses the reusable-operation
hybrid:

- present and past finite-form selection;
- shared perfect and progressive dependencies;
- canonical BE-passive;
- verbal negation;
- imperative, polar-question, subject-WH, and non-subject-WH operations when
  supported;
- one specific KC for each observed central modal.

Reference active/positive/declarative/simple/modal-free/tenseless conditions
are not separate latent KCs. Perfect-progressive activates both shared aspect
operations instead of an atomic feature KC.

On the 75-cell full inventory, this declaration yields 18 KCs, full column
rank, 75 distinct cell-activation rows, and no identical or near-identical
columns. Seventeen KCs recur across cells. The feature-only control needs 19
KCs; the exact-cell diagnostic needs 75 non-reusable KCs. Adding a
perfect-progressive-chain KC also retains full rank, but its six cells are
strictly nested inside both component operations and it adds no linguistic
operation absent from the compositional declaration. It is excluded on
parsimony grounds, not predictive fit. The final item bank will rerun support
and geometry checks before K* and Q* pass their measurement gate.

## Established evidence retained from the medium programme

- Explicit Phase-2 eligibility and branch-preserving transitions are safer
  than unrestricted example use.
- N=3 captures most observed item-coverage gains; fallbacks must be separately
  labelled.
- Determinacy is the main automatic-validation bottleneck.
- Raw generation/validation evidence and declared packaging corrections must
  remain immutable.
- Frozen non-updating probes are required for genuine grammar-transfer
  evaluation.
- Q-column equivalence and structural support matter independently of learner
  count.
- Outcome-selected interactions can improve prediction in worlds where they
  are planted, but this is downstream discovery evidence, not generator-KC
  construction evidence.
- Predictive representation rankings depend strongly on the declared latent
  world.
- Learner-paired bootstrap evaluation and no-oracle observable logistic KT are
  retained downstream tools.
- Operational model settings are Sol/high normalisation, Sol/medium generation,
  and Terra/medium validation; all strict critical-error gates remained
  inconclusive.

## Current unresolved construction questions

1. Full-bank candidate acceptance, zero-coverage cells, and whether a declared
   narrow rescue is needed.
2. Full-bank items per KC, Q rank, near-equivalence, and rare-KC support.
3. Full grammar-regime split with materially larger unseen-combination and
   unseen-value cohorts.
4. Baseline multi-KC response aggregation and learning update after the
   preregistered simulator pilot.
5. Final item count, learner count, acquisition schedule, and probe schedule.
6. Automatic item validation remains non-human evidence.

## Important active paths

- Full dataset target: `data/grammar_kt_full_v1/`
- Restricted full evidence: `runs/grammar_kt_full_v1_private/`
- Full runner: `scripts/build_dataset.py`
- K* declarations: `modules/kcs/generator/`
- K*/Q* code: `src/grammar_kt/generator_kcs.py`,
  `src/grammar_kt/measurement.py`
- Persistent experiment ledger: `reports/experiment_log.md`
- Active experiment queue: `reports/experiment_bank.md`
- Historical medium dataset: `data/grammar_kt_medium_v1/`

## Current next action

Generate the frozen N=3 candidate plan for all 75 GrammarCells, apply
deterministic checks and independent validation, inspect any zero-coverage
cells before a declared rescue, curate the full bank, and run the mandatory
K*/Q* support and identifiability audit before any learner simulation.
