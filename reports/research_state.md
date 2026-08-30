# Research state

Last updated: 2026-08-30. The programme is complete under the revised
baseline-versus-experiment framing in `AGENTS.md`. The previous medium-scale
programme remains historical evidence; it is not the generator truth for the
full dataset.

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

The dataset is frozen. KC misspecification, KC discovery, linguistic
generalisation, oracle-only state recovery, compact simulator robustness, and
bounded collection design are complete. The declared synthetic experiment
queue is closed. Final synthesis, replay, notebook, release-manifest, and ACL
verification are also complete; none mutated the baseline.

## Repository audit result

- Active research branch: `agent/full-dataset-research-program`; its latest
  completed experimental checkpoint is pushed to the same remote branch.
- User-owned dirty files are preserved: modified `pipeline.txt`; untracked
  `AGENTS.md`, root `experiment_bank.md`, `ideas.txt`, `rqs.txt`,
  and `tmp/`.
- Final verification passes 272 Pytest contracts, exact Q*/event replay,
  independent headline-experiment replay, all three tracked notebooks, a
  machine-readable release root, and the deterministic 14-page named ACL
  preprint build using the retained UROP shell, with 71/71 author-list/BibTeX
  regressions and complete visual inspection.

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
- The pre-item generator-alternative audit's temporary structural-item path is
  development evidence only. It is not an input to the frozen K*/Q*/event
  release or any paper-facing result.

### Reusable Layer-B experiments

- `src/grammar_kt/{kc_candidates,kc_selection,kt,evaluate}.py`
- phase 3--6 candidate, selection, latent-world, KT, stability, and paired
  evaluation scripts/artifacts.

These define or evaluate `K_hat`; they are no longer part of baseline dataset
construction.

### Superseded as active final claims

- The outcome-selected pipeline in `scripts/run.py` and
  `scripts/finalize_full_dataset.py`.
- The old “programme complete” reports are archived under
  `reports/historical/medium_v1/`. The active final reports and ACL manuscript
  are full-v1 syntheses; medium-v1 evidence remains a labeled pilot.

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
- imperative, polar-question, and non-subject-WH operations when supported;
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
parsimony grounds, not predictive fit. The final item bank subsequently reran
support and geometry checks before K* and Q* passed the measurement gate.

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

## Full item-construction status

- The frozen N=3 campaign generated 225/225 valid candidates and independently
  accepted 102 (45.3%), covering 57/75 cells. Determinacy accounted for 117 of
  123 model-judged rejections and is the dominant full-scale measurement
  bottleneck; fidelity, grammaticality, simplicity, and world-knowledge checks
  passed every judged candidate.
- The preregistered two-draw unchanged-prompt rescue accepted 10/36 candidates
  and added nine cells, raising coverage to 66/75. The separately frozen
  explicit-construction intervention accepted 9/18 and added six cells, raising
  coverage to 72/75. Original and campaign evidence remain immutable and
  separately labelled.
- The frozen append-only correction passed one of three copied packages, adding
  the missing `mustn't` answer and raising coverage to 73/75. Both imperative
  copies again failed only determinacy because the judge found new polite and
  referential variants. This is a retained negative result: open full-sentence
  imperatives do not have a finite natural answer set under the current prompt.
- The two residual cells are the only structural support for
  `gkc_imperative`; dropping them would leave that frozen KC unmeasured. A final
  preregistered N=2 campaign therefore retains controlled production but bounds
  responses with unordered lexical chunks and an all-and-only-use contract.
  Negative cues omit `do not`, so learners still produce uncontracted
  DO-support. All four candidates passed unchanged independent validation,
  restoring 75/75 cell coverage. No further answer repair or prompt campaign is
  allowed.
- Outcome-free max-two curation froze 113 items: 37 cells have one item and 38
  have two, with no duplicate prompt. Max-one would retain 75 items; up-to-three
  would add only 13 further variants without new cell coverage. The imperative
  all-and-only cue constraint is explicitly labelled as a format-specific
  limitation.
- The final structural grammar split contains 54 `seen`, 15
  `unseen_combination`, and six `unseen_value` cells. Every unseen combination
  is pairwise-seen/full-tuple-unseen; perfect-progressive aspect defines the
  unseen-value cohort without creating an unseen-value-only generator KC.
- The frozen 113x18 Q* passes the pre-simulation gate: 269 edges, density
  0.1323, rank 18/18, all 75 cells measured, every KC supported by at least two
  items, and no identical or Jaccard>=.90 near-identical columns. Seven KCs have
  fewer than six items. The sole non-subject-WH cell creates two nested KC-pair
  geometries; these cannot be repaired by more variants of the same cell and
  are retained as an explicit source-inventory limitation.
- The baseline simulator decision is weakest-link/minimum response aggregation,
  all-active opportunity learning, independent Beta(2,2) initial mastery,
  fixed synthetic guess/slip 0.10/0.10, no forgetting or item difficulty, and
  terminal non-updating probes. The final-bank pilot selected the preregistered
  lowest passing target of 12 opportunities per seen KC: one exhaustive
  seen-item occurrence followed by deterministic Q*-balanced top-up. It gives
  170 acquisition and 113 probe rows per learner, median probability gain
  0.181, and only 2.21% terminal KC saturation above .95. No extra pilot seed
  was required by the frozen boundary rule.

## Frozen full-v1 dataset

- `data/grammar_kt_full_v1/` is complete and immutable at 75 GrammarCells, 18
  generator KCs, 113 items, 269 Q* edges, 1,000 learners, and 283,000 events.
- Each learner has 170 seen-only acquisition rows and 113 terminal all-bank
  probes. The observable stream contains no K*, mastery, probability, draw, or
  update fields; aligned private truth is retained separately under `oracle/`.
- Generation and an independent `--verify-only` execution both replayed every
  keyed event and validated all public/private, Q*, mastery, probability,
  schedule, and artifact-hash contracts.
- Observable gzip SHA-256:
  `9272ca86a647e3b13c9ce52b5381dde215f7ef448e4a19a41a22495fa99ef97f`;
  private-oracle gzip:
  `956ed53f370d5494d379072954c0821d4098f11e51e2629b33d8ee0b8b844601`.
- The manifest records the pre-response code revision `930d43f2`, exact
  command, input hashes, deterministic gzip settings, and an 88-file recursive
  inventory. Automatic validation remains a declared non-human limitation.

## Established full-v1 downstream evidence

- In the preregistered 15-condition RQ2 study, K* gives the best overall
  observable-logistic probe log loss (0.670627). Costs increase for structural
  split-2 (+.003165), split-4 (+.005868), linguistic-family coarse (+.008132),
  all-merged (+.010225), and exact-cell (+.015039); every learner-paired 95%
  interval excludes zero. This is a monotone predictive granularity result on
  the tested grid, not a cognitive-truth claim.
- Exact-cell hypotheses generalise especially poorly to unseen combinations
  (+.037609 log loss) and unseen values (+.028627). Some lower-dimensional
  unseen-value contrasts remain unresolved, so RQ4 needs explicit structural
  recovery and cell-sensitivity evidence rather than only pooled events.
- All nine preregistered 10% Q-corruption structures degrade prediction. Mean
  costs are +.001685 false-positive, +.002644 false-negative, and +.002294
  mixed; seed spread prevents a strong ordering claim. The shared 113,000 probe
  rows and observable-only boundary were verified.
- The frozen observable-only RQ3 selector evaluated 181 structural candidates
  and all 22 eligible forward additions on 170,000 seen acquisition rows. It
  retained the 18-feature base; the atomic-feature and compositional-operation
  projections are exactly Q-equivalent on seen items, so the selected object is
  an equivalence class rather than a uniquely recovered ontology. The N=120
  development cohort selected the coarse policy, whereas N=1,000 selected this
  equivalence class, which also exposes sample instability at pilot scale.
- Post-selection truth evaluation confirms that the candidate space contains a
  perfect structural ceiling (18/18 exact KCs, activation Jaccard and aligned
  Q-edge F1 both 1.0), but that ceiling is reachability evidence only. The
  selected atomic projection recovers 16/18 exactly (padded Jaccard .970854,
  F1 .965385) because it cannot infer the compositional activation of perfect
  and progressive operations on the six unseen-value cells. Its all-probe log
  loss is .000374 worse than the compositional ceiling (95% learner-paired CI
  [.000228,.000517]); the difference is entirely concentrated in unseen-value
  probes. Prediction on seen evidence therefore does not uniquely identify K*.
- The RQ3 negative control behaves as intended: hash distractors recover 0/18
  KCs (Jaccard .202342, F1 .359259) and cost .013238 probe log loss. Added
  interactions do not produce a supported gain over the compositional policy
  (delta +.000206, 95% CI [-.000069,.000478]). Selection never read Q*, K*,
  oracle state, or probe outcomes; truth entered only after frozen selection.
- RQ4 confirms reusable transfer on the 15 pairwise-seen/full-tuple-unseen
  cells. Under one common observable model, K* log loss is .669161 seen,
  .672036 on unseen combinations, and .681181 on unseen values. Exact-cell KCs
  cost +.037609 on combinations (95% learner-paired CI
  [.033761,.041513]) and +.028627 on unseen values
  ([.025120,.032174]); split-2 and family-union merges also have supported
  combination costs. Spurious conjunctive/intersection additions harm all
  three regimes, so a union merge and an intersection are empirically and
  conceptually distinct perturbations.
- Atomic and compositional hypotheses remain effectively identical on seen and
  combination probes (maximum probability difference 1.2e-7). Their nominal
  unseen-value difference is inconclusive (atomic-minus-compositional
  -.003236, [-.007943,.001272]) and changes direction under the distinct RQ3
  fitting protocol. It cannot resolve the seen-Q equivalence class. The six
  unseen-value cells are visibly cell-sensitive: K* per-cell log loss ranges
  .666512--.691208 and leave-one-cell-out macro values .680016--.684955.
- A downstream exact-item-novelty negative control withheld one item in each of
  30 two-item seen cells while replacing its 54 acquisition occurrences with
  the same-cell counterpart. It preserved every K* opportunity and produced
  exactly the same 30,000 probe outcomes as the paired baseline rows. This is a
  consequence of the declared simulator's lack of item memory/difficulty and
  correctness-independent same-Q updates, not evidence about human item
  novelty.
- Oracle-only evaluation of the frozen observable fits agrees with the RQ2
  headline ordering overall: K* item-prerequisite-state RMSE is .123738 versus
  .146300 coarse, .132752 split-2, .140428 split-4, and .163828 exact-cell.
  Every candidate-minus-K* overall RMSE interval from 2,000 paired learner
  resamples excludes zero. This target is the minimum active-KC mastery that
  governs the item response, not individual-KC or human mastery.
- The mastery result is not uniform across regimes. Coarse is worse on seen and
  unseen-combination probes but improves RMSE by .003663 on the six
  unseen-value cells (95% interval [-.005740,-.001507]). This retained local
  reversal limits the headline claim to the declared overall distribution and
  reinforces the six-cell holdout caveat.
- A deliberately misspecified fixed BKT poorly tracks per-KC oracle state:
  terminal active-KC-pair RMSE .291195 and correlation .355418; unique
  learner-KC RMSE .300804 and correlation .434973. Its correctness-conditioned,
  full-credit update does not match opportunity-based all-active learning or
  minimum aggregation. Predictive adequacy and state semantics must therefore
  be reported separately.
- The compact robustness study runs 39 worlds (13 conditions x three seeds) at
  500 learners with 117 converged primary fits. K* beats family-coarse and
  split-2 in every seed for 12/13 conditions. Baseline mean log-loss costs are
  +.007924 coarse and +.003241 split-2; noise, product/mean aggregation,
  learner noise/rate heterogeneity, mild forgetting, correlated initial
  mastery, and correct-only learning preserve the winner.
- Unmodelled item logit difficulty (SD .60) is the exception. Split-2's mean
  cost is still +.004138 but its three-seed range is -.000413--+.009955: it
  beats K* in one seed and falls below coarse in another. The RQ2 conclusion is
  therefore broad within the compact study but explicitly conditional on item
  nuisance control. Fixed BKT produces further reversals under its known
  aggregation/update mismatch and remains secondary.
- The bounded collection-design study makes four distinctions explicit. Raw
  validation selects K* in all 21 nested learner cohorts from N=60 to 1,000,
  whereas a fixed KC-count penalty selects family union in 18/21, so a penalty
  changes the estimand. Targets 6/12/24 improve absolute prediction and widen
  K*'s advantage; they do not establish a human threshold. Max-two raises KC
  support over max-one but adds zero Q rows or rank. In the two-KC control,
  A+B-only repetitions remain exactly unidentifiable through N=1,000; anchors
  restore rank and expose union merging, yet the planted-interaction omission
  costs only +.000506 at N=1,000 balanced. Full rank therefore need not imply
  practically unique predictive recovery.

## Current unresolved research questions

No declared synthetic experiment remains unexecuted. The unresolved questions
require evidence outside this programme: expert/human item validation, real
learner dynamics, unseen-value structures beyond perfect-progressive, and
empirical cross-lingual replication.

## Important active paths

- Full dataset target: `data/grammar_kt_full_v1/`
- Restricted full evidence: `runs/grammar_kt_full_v1_private/`
- Full runner: `scripts/build_dataset.py`
- K* declarations: `modules/kcs/generator/`
- K*/Q* code: `src/grammar_kt/generator_kcs.py`,
  `src/grammar_kt/measurement.py`
- Persistent experiment ledger: `reports/experiment_log.md`
- Active experiment queue: `reports/experiment_bank.md`
- Frozen RQ3 artifacts: `experiments/full_v1/rq3_kc_discovery_v1/`
- Frozen RQ4 artifacts: `experiments/full_v1/rq4_generalisation_v1/`
- Mastery artifacts: `reports/full_v1_artifacts/mastery_recovery_v1/`
- Robustness artifacts: `experiments/full_v1/simulator_robustness_v1/`
- Collection-design artifacts: `experiments/full_v1/collection_design_v1/`
- Release root: `reports/final_release_manifest.json`
- Standalone dataset visualization: `reports/final_dataset_visualization.html`
- Executable dataset viewer: `notebooks/final_dataset.ipynb`
- Executable results notebook: `notebooks/final_dataset_results.ipynb`
- Manuscript: `ACL/paper.pdf` (named full-v1 ACL preprint using the retained
  `report_versions/UROP/` presentation shell)
- Historical medium dataset: `data/grammar_kt_medium_v1/`

## Current next action

Preserve `grammar_kt_full_v1` immutably. Any human-validation, real-learner, or
cross-lingual study should be versioned as a new programme rather than changing
this baseline or post-hoc extending its final claims.
