# Experiment log

Append new substantive experiments in chronological order. Fixture runs and
software tests must be labeled as such and must not be promoted to scientific
evidence.

## P1-AUDIT-001 — Active methodology and retained-evidence audit

- **Date:** 2026-08-27
- **Research question:** Which properties of the active pipeline currently
  prevent a controlled, interpretable comparison of KC representations?
- **Hypothesis:** The simplified pipeline preserves the fixed-item/fixed-event
  boundary, but the six-cell declarations, simulator, selector, KT inputs, and
  evaluation protocol are not yet adequate to identify KC granularity.
- **Exact intervention:** None. This was a read-only code/declaration/artifact
  audit followed by documentation. No KC method, data generator, model setting,
  or result was changed, and no large experiment was run.
- **Data/artifacts used:**
  - active `modules/`, `src/grammar_kt/`, `scripts/`, notebook, and tests;
  - `runs/research_pipeline_20260827/` and
    `runs/research_modularity_20260827/` fixture artifacts;
  - legacy `runs/base`, `runs/kc_interactions`, and `runs/kc_full_cell` artifacts;
  - tracked 24-cell structural evidence in
    `experiments/post_training_v1/data/pilot_v1/opportunities.jsonl`;
  - current ACL manuscript/evidence ledger.
- **Exact commands:**

  ```bash
  git status --short --branch
  .venv/bin/python -m pytest -q
  jq -s 'group_by(.grammar_split) | map({grammar_split:.[0].grammar_split, by_dataset_split:(group_by(.dataset_split) | map({split:.[0].dataset_split,n:length}))})' runs/research_pipeline_20260827/simulation/events.jsonl
  git diff --check
  ```

  File discovery and code evidence used `rg --files`, `rg -n`, `nl -ba`, and
  `jq` against the paths listed above; no network or live-model command was
  used.
- **Models:** None called. Retained pipeline artifacts use deterministic fixture
  responses and are treated only as wiring/schedule evidence.
- **Seeds:** No new stochastic run. The inspected retained simulator artifact
  declares seed `20260827`.
- **Result:**
  - the fixed item/outcome boundary is implemented and tested;
  - the active baseline uses a predefined factorized policy, not automated
    selection;
  - the only latent world is feature-factorized;
  - compositional events in the retained schedule are 72 train, 24 validation,
    and 0 test; novel-feature events are 48 train, 24 validation, and 24 test;
  - logistic KT consumes simulator-derived structural difficulty;
  - the obligation selector can replace marginal KCs with an interaction and
    ignores several declared fields;
  - the bootstrap compares KT techniques/event samples rather than KC
    representations/learners;
  - controlled-lexicon and CEFR wording concerns are removed in the current
    uncommitted working tree, but not experimentally evaluated;
  - final Phase 1 verification: `25 passed in 3.27s`; `git diff --check`
    passed.
- **Interpretation:** Current fixture KT numbers are technical integration checks,
  not evidence for factorized, interaction, full-cell, or selected KC quality.
  Structural candidate construction is the necessary next research phase.
- **Conclusion:** RQ9 is answered narrowly for the current protocol: it does not
  genuinely test pure compositional transfer. RQ1–RQ8 and RQ10–RQ20 remain open
  or only partially answered as recorded in `research_state.md`.
- **Whether methodology changed:** Scientific code did not change. The programme
  recommendation changed: reject the current obligation selector as the main
  method, treat current transfer metrics as non-evidence, and begin Phase 2 with
  development-derived structural candidates.
- **Output path:** `reports/pipeline_audit.md`

## Historical evidence not re-run in Phase 1

The following evidence is retained but is not logged as a new Phase 1
experiment:

- The older 139-descriptor base run reports 44 final complete mappings, 77
  partial, 16 out of scope, two unresolved, and 24 canonical cells. It belongs
  to a superseded architecture and its Phase-2 yield is only a scoped legacy
  result.
- The older factorized/interaction/full-cell runs used policy-specific item banks
  and learner events. Their cross-policy KT scores are inadmissible under the
  current fixed-bank comparison boundary.
- The post-training v1 pilot is a separate generation-supervision investigation.
  Its retained conclusion is that no trustworthy negative class emerged; it
  does not answer a KC-selection RQ.

## P2-CANDIDATES-001 — Development-only structural KC hypothesis space

- **Date:** 2026-08-27
- **Research questions:** RQ13, RQ14, RQ15, and the structural portion of RQ20.
- **Motivation:** Replace fixture-specific feature/interaction declarations with
  the first active, language-interface-general, inspectable half of automated KC
  selection while preserving the fixed-bank and holdout-leakage boundaries.
- **Hypotheses:** Schema-derived enumeration would remain manageable after
  support/equivalence marking; direct operation tags would mostly alias
  canonical values; explicit reference values would reduce artificial candidate
  growth; the four-cell fixture would not support reusable interactions.
- **Exact intervention:** Added an active candidate design and English-specific
  cell-deterministic operation declaration; implemented observed feature-value,
  supported feature-pair, exact-development-cell, support, and activation-
  equivalence construction; integrated it in the main runner; ran background
  and support-threshold sensitivity and a holdout-mutation negative control.
- **Dataset/artifact:**
  - four development cells/four fixed accepted items from the deterministic
    active fixture (software contract only);
  - structural-only development extraction from
    `experiments/post_training_v1/data/pilot_v1/opportunities.jsonl`, SHA-256
    `5635b69de038fa3d0532265c78695b8c7360d92a84df932791ab7446b3e9768e`:
    30 measurement opportunities, 16 development cells, from 42/24 overall.
  - No learner outcome, old KC, simulation, or predictive result was read.
- **Exact command:**

  ```bash
  .venv/bin/python scripts/run_candidate_analysis.py
  .venv/bin/python -m pytest -q
  git diff --check
  ```

  The whole-tree whitespace command reports only pre-existing trailing spaces
  in the user's modified `pipeline.txt`; targeted Phase 2 paths pass.
- **Models:** No live model. Fixture-backed normalisation/generation/validation
  uses deterministic canned responses solely to construct the contract bank.
- **Seeds:** None; structural enumeration is deterministic.
- **Result:**
  - all 42 legacy opportunity cells validate against the active schema with no
    ID/tuple conflicts; development is 30 opportunities/16 cells;
  - fixture: 22 raw candidates (5 feature, 10 operation, 3 pair, 4 full-cell),
    eight activation classes, seven support/equivalence-eligible, and zero
    eligible interactions;
  - medium structural run: 48 raw (9 feature, 10 operation, 13 pair, 16
    full-cell), 38 support-eligible, 33 activation classes, 15 duplicate excess,
    and 26 selection-eligible (9 feature, 3 operation, 6 pair, 8 full-cell);
  - item thresholds 1/2/3/5 retained 13/11/6/1 interactions, while cell
    thresholds 1/2/3/5 retained 13/6/1/0;
  - making every observed value explicit expanded the medium space from 48 to
    107 raw hypotheses and duplicate excess from 15 to 53; making present a
    reference reduced it to 41 raw/24 eligible versus 48/26 active;
  - direct negation/passive/imperative/inversion operations are feature aliases;
    perfect/progressive dependencies and finite-tense form add distinct columns;
    realisation-dependent operations are excluded;
  - fixture deterministic tag agreement is 4/4; legacy same-rule agreement is
    30/30 and explicitly not independent validation;
  - replacing all held-out feature/source content left the inventory unchanged,
    with equal digest
    `486614ecc9a1e3f8e044946923ffefe4e896ad6eecfd6d93df9227c9d80aafa3`;
  - final Phase 2 suite: `34 passed in 2.79s`; the executable notebook calls the
    active candidate function with live calls disabled.
- **Interpretation:** Candidate enumeration is manageable at this scale, but
  repeated item opportunities cannot substitute for cell support. Operation
  aliases are bank-specific, and structural evidence cannot decide whether
  present should be a reference value.
- **Conclusion:** RQ13 and RQ14 are answered for current structural evidence;
  RQ15 and RQ20 are partially answered. Use explicit reference values, a
  2-cell/3-item interaction guard, feature-first equivalence representatives,
  and only cell-deterministic operation rules for Phase 3.
- **Whether methodology changed:** Yes. The real runner now constructs and
  retains development-only candidates. Manual candidate lists and generator
  self-tags are no longer the active candidate-discovery method. The downstream
  predefined factorized policy remains provisional until Phase 3.
- **Output path:** `reports/phase2/analysis.md` and
  `reports/phase2/artifacts/`.

## P3-KC-SELECTION-001 — Development-only predictive/parsimony selection

- **Date:** 2026-08-27
- **Research questions:** RQ1, RQ2, RQ3, RQ4, RQ7, RQ19, and the
  learner-evidence portion of RQ20.
- **Motivation:** Replace the predefined active ontology with an automated
  selector and determine whether supported interactions can be recovered on a
  fixed development bank without reading grammar holdouts or reserved outcomes.
- **Hypothesis:** A protected factorized base plus forward additions selected by
  validation log loss and KC-count parsimony would reject interactions in a
  factorized world and recover the declared perfect×negative dependency in an
  interaction probe.
- **Exact intervention:** Implemented an observable PFA-style logistic selector,
  chronological and learner-level development partitions, a forward trace and
  backward pruning, a BKT selector control, and learner-cluster paired policy
  bootstrap. Simulated and froze five seeds in two worlds before scoring any KC
  representation. The response equation was refactored into an explicit helper
  without algebraic change, and a monotonicity test now protects that mastery
  raises and difficulty lowers response probability; item order was
  counterbalanced by learner and pass.
- **Dataset/artifact:** The Phase-2-audited 16-cell/30-opportunity development
  structure only. All legacy holdout rows, KCs, operations, splits, and learner
  outcomes were excluded. Each of ten new streams contains 300 learners × eight
  passes × 30 items = 72,000 events (720,000 total). Streams, private oracle
  checks, frozen policies, reference-seed predictions, and hashes are retained.
- **Exact command:**

  ```bash
  .venv/bin/python scripts/run_kc_selection_experiments.py
  ```

  A preceding `--quick` run is labelled software verification and is not
  promoted as scientific evidence.
- **Models:** No language model. Primary selector: standardized observable
  PFA-style logistic regression (`C=0.1`) with learner success/attempt history
  and per-KC activation/prior success/prior failure, but no item difficulty,
  latent mastery, response probability, item ID, or grammar holdout. Fixed
  multi-KC BKT is a sensitivity control.
- **Seeds:** simulation `20260827`–`20260831`; selector `20260827`; reference
  paired learner bootstrap 3,000 repeats with seed `20260827`.
- **Result:**
  - candidate pool: 48 raw candidates, 26 structurally selection-eligible;
    primary search starts with nine feature KCs and considers three operation
    plus six interaction additions; full-cell uses 16 exact development KCs;
  - the interaction manipulation was present: target-minus-other private oracle
    probability was approximately −0.0533 to −0.0553 across interaction seeds,
    versus +0.0197 to +0.0207 in factorized seeds;
  - the original `lambda=0.002` plus a second `0.0001` improvement gate selected
    exactly the nine-feature base in all ten runs (Jaccard 1.0), hence failed the
    intended recovery control;
  - mean reserved-test log loss for factorized/manual-interaction/full-cell was
    0.575207/0.575251/0.575219 in the factorized world and
    0.583075/0.582999/0.582822 in the interaction world; effects were tiny and
    seed-variable;
  - on reference-seed interaction data, manual interaction minus factorized log
    loss was −0.000369 with learner-bootstrap 95% interval
    [−0.000982, 0.000251], so the interval includes zero;
  - `C` values 0.1/1/10 and the learner-level internal split all retained only
    the feature base on the reference seeds; the BKT selector recovered the
    planted interaction on the interaction reference seed but selected none in
    the factorized reference seed;
  - residual ranking placed the planted interaction first in the interaction
    world but the ordinary penalized validation decision still rejected it;
    the restricted top-down extreme comparison preferred nine factorized KCs
    over 16 full cells after complexity cost;
  - the former obligation selector was removed from active code/config because
    its conjunction-replaces-marginals semantics are incoherent for an additive
    KC ontology.
- **Interpretation:** Structural support is adequate to expose the target, but
  the planted dependency has only a very small predictive effect under the
  observable scorer. The original double threshold was miscalibrated, and
  interaction recovery is also sensitive to the selector KT model. These are
  negative scientific results, not justification to tune against test loss.
- **Conclusion:** The active stage is genuinely automated and leakage-bounded,
  but RQ4 is only partially answered: useful interaction recovery is possible
  in a controlled case yet is not stable enough for a strong claim. RQ1–RQ3,
  RQ7, and RQ20 remain partial pending stronger worlds/folds and Phase 5.
- **Whether methodology changed:** Yes. The main runner now calls
  `make_kc_candidates → select_kcs → project_kcs`; a policy is frozen before
  holdout projection. The primary selector omits oracle difficulty and preserves
  all unary marginals. The double-threshold setting was subjected to a focused
  replay before changing the active penalty.
- **Output path:** `reports/phase3/artifacts/selection_study_v1/` and
  `reports/phase3/analysis.md`.

## P3-KC-SELECTION-002 — Parsimony-threshold stability replay

- **Date:** 2026-08-27
- **Research questions:** RQ4 and RQ20.
- **Motivation:** Determine whether failure of the planted-interaction recovery
  control came from the selector itself or from the original redundant
  complexity penalty plus minimum-gain threshold.
- **Hypothesis:** Removing the second threshold and reducing the per-KC penalty
  would improve recovery, but too small a penalty would admit null-world
  additions.
- **Exact intervention:** Replayed the already frozen ten Phase-3 event streams;
  no outcomes were regenerated. Compared the original `(lambda=0.002,
  minimum=0.0001)` with objective-only penalties 0.00025, 0.0005, and 0.001.
- **Dataset/artifact:** Exact retained event files from P3-KC-SELECTION-001.
- **Exact command:**

  ```bash
  .venv/bin/python scripts/run_phase3_penalty_stability.py
  ```
- **Models:** Same primary observable logistic selector as P3-KC-SELECTION-001;
  no model calls and no oracle inputs.
- **Seeds:** `20260827`–`20260831` in each of two worlds.
- **Result:**
  - objective-only 0.00025 admitted an addition in 2/5 factorized seeds (one
    finite-tense operation and one progressive×present interaction) and selected
    the planted interaction in 2/5 interaction seeds, plus finite tense in 1/5;
  - objective-only 0.0005 admitted no addition in all five factorized seeds,
    selected the planted interaction in 1/5 interaction seeds, and finite tense
    in another 1/5; its mean selected-minus-factorized interaction-world test
    log-loss delta was −0.000487;
  - objective-only 0.001 and the original double threshold selected no additions
    in either world;
  - no setting delivered both reliable planted-interaction recovery and complete
    cross-world addition stability.
- **Interpretation:** The second gain threshold was unnecessary, but removing it
  does not solve the deeper support/effect-size/credit-assignment problem.
  Penalty 0.00025 is permissive enough to create null-world false additions;
  0.001 is too conservative for the probe.
- **Conclusion:** Use objective-only `lambda=0.0005` as the cautious active
  Phase-3 setting, explicitly provisional. It has the cleanest observed
  null-world behavior, while the low 1/5 planted recovery prevents a claim of
  robust automated discovery.
- **Whether methodology changed:** Yes. Active `selection.yaml` now uses
  `complexity_penalty: 0.0005` and `minimum_improvement: 0.0`.
- **Output path:** `reports/phase3/artifacts/penalty_stability_v1/results.json`.

## P4-FOLD-001 — Outcome-free semantic grammar fold

- **Date:** 2026-08-27
- **Research questions:** RQ8 and the structural prerequisite for RQ5/RQ9.
- **Motivation:** Replace six-cell ordinal-ID assignments with a deterministic
  scalable split whose compositional and novel-value meanings are explicit.
- **Hypothesis:** Feature-tuple sampling can withhold exact combinations while
  keeping every constituent repeatedly measured in development; explicit
  novelty declarations can withhold a value completely.
- **Exact intervention:** Implemented `build_semantic_fold(schema, cells,
  accepted_items, design)`. Compared compositional fractions 0.20/0.30 and
  minimum constituent support 1/2; mutated all cell IDs and reversed input
  order as a negative control.
- **Dataset/artifact:** The Phase-2-audited 24 exact cells and 42 structural
  opportunity IDs. They are support units only, not item-quality evidence.
- **Exact command:**

  ```bash
  .venv/bin/python scripts/run_fold_analysis.py
  ```
- **Models:** None.
- **Seeds:** Semantic sampling seed `20260827`.
- **Result:** The active 0.20/minimum-2 design yields 18 development, five
  compositional, and one novel-value cell, with 33/8/1 structural items. Every
  compositional constituent has at least three development cells; 36/37 of its
  distinct value pairs occur in development. The 0.30 design yields 16/7/1
  cells and minimum constituent support two. Minimum 1 versus 2 changes no
  assignment. Feature-tuple assignments are ID/order invariant. Historical
  labels agree on 12/24 cells.
- **Interpretation:** The split now measures transfer to unseen tuples without
  confusing unseen individual values, while explicitly reporting that one
  compositional pair is also unseen.
- **Conclusion:** Use 0.20, minimum support two, and `modal=would` as the active
  structural fold for later phases.
- **Whether methodology changed:** Yes. The active runner uses the semantic
  builder; the old reference manifest remains only for regression/history.
- **Output path:** `reports/phase4/artifacts/fold/`.

## P4-NORMALISATION-001 — Phase-2 eligibility and transition safety replay

- **Date:** 2026-08-27
- **Research questions:** RQ12 and RQ17.
- **Motivation:** Test whether examples are routed only to resolvable
  uncertainty and whether Phase 2 can alter or lose Phase-1 branches.
- **Hypothesis:** Explicit eligibility will avoid most low-yield example calls;
  branch-preserving domain descent will reject unsafe transitions missed by the
  prior marginal check.
- **Exact intervention:** Added ordered `phase2_eligible` provenance to active
  mappings/prompts; require eligibility to name uncertain Phase-1 dimensions;
  require Phase 2 to preserve exact fields, narrow eligible domains, avoid
  cross-branch recombination, and cover every parent branch. Replayed retained
  transitions and six adversarial controls.
- **Dataset/artifact:** 139 primary descriptors and eight repeat annotations
  from `runs/base_seed_20260820`; retained outputs are replayed offline.
- **Exact command:**

  ```bash
  .venv/bin/python scripts/run_normalisation_audit.py
  ```
- **Models:** Retained legacy `gpt-5.6-sol`, medium reasoning; no new call,
  unpinned snapshot/decoding.
- **Seeds:** None recorded for legacy annotations.
- **Result:** Final mappings are 44 complete, 77 partial, 16 out of scope, and
  two unresolved. Only 2/80 Phase-2 calls became complete (2.5%), while only
  9/80 have nonempty explicit eligibility after adaptation, implying 71/80
  calls would be avoided. All 80 retained transitions pass the stronger
  contract. Eight repeats agree exactly. All six adversarial expectations pass.
- **Interpretation:** Phase 2 has low observed resolution yield; conservative
  routing improves cost and clarity. The repeat sample is too small/selected to
  establish general stability.
- **Conclusion:** Retain example-based Phase 2 only for explicitly eligible
  dimensions and enforce branch-preserving narrowing.
- **Whether methodology changed:** Yes, in active normalisation code, prompts,
  rulebook, and fixture responses.
- **Output path:** `reports/phase4/artifacts/normalisation/`.

## P4-ITEMS-001 — Blinded lexical/source and best-of-N item audit

- **Date:** 2026-08-27
- **Research questions:** RQ10, RQ11, RQ16, and initial RQ18 evidence.
- **Motivation:** Determine whether the active model-selected lexical policy,
  best-of-N generation, and source input produce a realistic fixed bank rather
  than treating prompt changes as self-evident improvements.
- **Hypothesis:** Model-selected simple language will cover difficult cells at
  least as safely as a six-entry lexicon; N=3 will capture most N=5 coverage;
  readable source evidence may help only on matched cells.
- **Exact intervention:** Fixed eight diverse cells, generated maximum-N once
  for model-selected and controlled-lexicon conditions (N=5) and for the three
  source-evidence cells (N=3), pooled and seed-blinded every structurally valid
  candidate, and independently judged all required criteria. Prefix results
  reuse calls exactly; selection keeps the earliest valid item and optionally
  the most token-distinct second item.
- **Dataset/artifact:** Eight predeclared cells from the 24-cell structural
  inventory; three have recoverable guideword/can-do evidence. No legacy item,
  judgment, learner event, KC, or predictive outcome was reused.
- **Exact command:**

  ```bash
  .venv/bin/python scripts/run_item_audit.py --pilot --select-second --workers 4 --generation-model gpt-5.6-sol --validation-model gpt-5.6-terra --reasoning-effort medium --output-dir reports/phase4/artifacts/item_audit/live_pilot
  ```
- **Models:** `gpt-5.6-sol` generator and `gpt-5.6-terra` independent
  validator, both medium reasoning.
- **Seeds:** Blinding seed `20260827`; model sampling seed unavailable.
- **Result:** 89 attempts, 86 structurally valid outputs, 86 valid blinded
  judgments, and 56 accepted candidates. Model-selected N1/N3/N5 cover
  6/8, 8/8, 8/8 cells with end-to-end acceptance .750/.750/.675. Controlled
  lexicon covers 5/8, 5/8, 7/8 with .625/.542/.575. Source evidence covers
  2/3 then 3/3; on the same three cells at N=3, source and ordinary conditions
  each yield 6/8 accepted structurally valid candidates. Every model-selected
  cell has at least two accepted candidates by N=3. Determinacy participates in
  29/30 item rejections.
- **Interpretation:** Best-of-3 materially repairs cell coverage; N=5 adds no
  coverage. The controlled lexicon restricts rather than protects this bank.
  No source-evidence benefit is identifiable from three cells.
- **Conclusion:** Use common model-selected language, N=3, and up to two valid
  variants/cell for scale-up; do not use the six-entry lexicon or opaque source
  IDs in the active generator.
- **Whether methodology changed:** Yes, pending direct active-code integration
  after the repeat-validator audit.
- **Output path:** `reports/phase4/artifacts/item_audit/live_pilot/`.

## P4-VALIDATION-001 — Repeat and model-sensitivity validator audit

- **Date:** 2026-08-27
- **Research question:** RQ18.
- **Motivation:** Determine whether one blinded model judgment is stable and
  whether the nine criteria are empirically redundant before changing the
  acceptance method.
- **Hypothesis:** Determinacy will remain the principal discriminating
  criterion; some criteria may co-fail, but a small non-human study may not
  justify deletion or an ensemble.
- **Exact intervention:** Deterministically selected 24 valid-output items,
  enriched to 12 original accepts/12 rejects while covering conditions, cells,
  and observed failures. Rejudged neutral item content with a Terra repeat and
  Sol sensitivity model; computed per-criterion/overall agreement, Wilson
  intervals, kappa, and failure overlap. Reviewed six declared examples as an
  agent audit, explicitly not human validation.
- **Dataset/artifact:** Frozen P4-ITEMS-001 candidates/judgments and hashes.
- **Exact command:**

  ```bash
  .venv/bin/python scripts/run_validation_reliability.py --input-dir reports/phase4/artifacts/item_audit/live_pilot --output-dir reports/phase4/artifacts/validation_reliability --sample-size 24 --seed 20260827 --workers 4 --repeat-model gpt-5.6-terra --sensitivity-model gpt-5.6-sol --reasoning-effort medium
  ```
- **Models:** `gpt-5.6-terra` repeat and `gpt-5.6-sol` sensitivity, medium.
- **Seeds:** Stratified sampling seed `20260827`; model sampling seed
  unavailable.
- **Result:** Original/Terra-repeat acceptance agreement is 19/23=.826 (Wilson
  95% [.629,.930], kappa .652) with one malformed repeat; original/Sol is
  19/24=.792 ([.595,.908], kappa .583); repeat/Sol is 18/23=.783
  ([.581,.903], kappa .569). Determinacy agreement is .826 repeat/.792 Sol.
  Naturalness/pedagogy failure overlap is high (.875 Jaccard) but non-identical.
  Five all-pass criteria supply no negative-case redundancy evidence.
- **Interpretation:** Model validation is useful but materially uncertain. The
  enriched sample and lack of human gold cannot establish which disagreements
  are errors.
- **Conclusion:** Retain single independent per-criterion judgment and every
  criterion; do not add an ensemble. Add a narrow deterministic answer-span
  check and report the reliability limitation.
- **Whether methodology changed:** Yes for deterministic span checking; no for
  model count or criterion inventory.
- **Output path:** `reports/phase4/artifacts/validation_reliability/`.

## P4-WORLD-KT-001 — Frozen transfer across four latent structures

- **Date:** 2026-08-27
- **Research questions:** RQ5, RQ6, RQ7, RQ9, RQ19, and RQ20.
- **Motivation:** Test whether Phase-3 conclusions survive a semantic fold,
  genuine zero-exposure probes, multiple plausible latent granularities, and
  removal of simulator-derived KT inputs.
- **Hypothesis:** The selector will recover supported interactions in an
  interaction-heavy world and reject them in a factorized world; exact-cell
  KCs will help only in a matching cell world; mixed history will inflate
  apparent transfer.
- **Exact intervention:** Materialized four concise world declarations
  (factorized, interaction-heavy, cell-specific, mixed) generically over the
  schema/cells. For three seeds and 240 learners/world, generated frozen-probe
  and mixed streams, froze each before representation comparison, selected on
  development train/validation only, and compared factorized, all-supported,
  automated, and labelled oracle-all-cell policies with empirical/BKT/logistic.
  Audited oracle-difficulty, KC-count, regularization, BKT selector, activation
  duplicates, and probe update invariance.
- **Dataset/artifact:** 24 schema-valid cells/42 structural opportunity IDs,
  used only as a fixed measurement-bank structure; semantic split 18/5/1.
- **Exact command:**

  ```bash
  .venv/bin/python scripts/run_phase4_world_audit.py
  ```
- **Models:** Synthetic latent mastery worlds; empirical, fixed mean-credit BKT,
  and standardized no-oracle logistic. No language model.
- **Seeds:** `20260827`, `20260828`, `20260829`; reference paired bootstrap
  1,000 repeats with seed `20260827`.
- **Result:** Factorized and cell worlds select the nine-feature base 3/3;
  interaction-heavy selects both support-eligible planted interactions 3/3
  (11/12/11 KCs, Jaccard .944); mixed selects one planted interaction 1/3.
  Frozen mean automated-minus-factorized all-probe log loss is 0 in factorized,
  -.002256 in interaction-heavy, 0 in cell-specific, and +.000016 in mixed.
  Reference interaction-heavy paired delta is -.002666
  [-.004244,-.001103], but compositional-only is -.001438
  [-.005268,.002646]. Oracle-all-cell wins only the cell world. Frozen holdouts
  have zero same-cell exposure; mixed compositional/novel probes average
  8.843/4.836 prior exposures. Probe mutation is exactly invariant. Oracle
  difficulty/KC count change LL by <.00020; BKT/logistic selector Jaccard is
  .600--.846 and BKT overselects additions.
- **Interpretation:** Automated recovery is real under a stronger interaction
  manipulation but world-dependent. No representation dominates all plausible
  worlds, and overall predictive gain does not establish compositional gain.
- **Conclusion:** Adopt frozen probes, no-oracle/no-count logistic, and the
  conservative automated selector; expose cell-world failure and novel-value
  noncoverage as limitations. Use BKT and mixed history only as sensitivities.
- **Whether methodology changed:** Yes. The active runner now uses semantic
  folds/frozen probes and primary logistic excludes oracle difficulty/count.
- **Output path:** `reports/phase4/artifacts/world_kt/study_v1/`.

## P4-INTEGRATION-001 — Active Phase-4 methodology checkpoint

- **Date:** 2026-08-27
- **Research questions:** Integration contract for RQ8--RQ18.
- **Motivation:** Ensure the audited methods replace the fixture-era active
  path and that researcher declarations correspond to executable choices.
- **Hypothesis:** Best-of-three selection, semantic folds, frozen probes, and
  the automated selector can execute in one linear runner without weakening
  fixed-bank or leakage boundaries.
- **Exact intervention:** Integrated three independent candidates/cell,
  independent validation, a conservative answer-span precheck, and up-to-two
  deterministic bank selection; removed opaque source/tag/note fields; retained
  accepted and selected banks separately; audited active configuration and
  removed unused metric/history/learning prose fields while enforcing the
  declared all-required validation rule.
- **Dataset/artifact:** Deterministic six-row fixture for software verification;
  all scientific evidence remains in the preceding Phase-4 retained studies.
- **Exact commands:**

  ```bash
  .venv/bin/python -m pytest -q
  .venv/bin/python scripts/run.py --fixture --output runs/phase4_checkpoint_fixture
  .venv/bin/jupyter nbconvert --to notebook --execute --inplace notebooks/pipeline_walkthrough.ipynb --ExecutePreprocessor.timeout=180
  git diff --check -- . ':(exclude)pipeline.txt'
  ```
- **Models:** Deterministic fixture responses; no model call.
- **Seeds:** Fixture simulation/logistic/bootstrap seed `20260827`.
- **Result:** 82 tests pass; fixture output has six selected items and 624
  events; notebook executes without errors; scoped diff check is clean. The
  entire-tree whitespace check is excluded because of the pre-existing
  user-owned `pipeline.txt` trailing spaces.
- **Interpretation:** The current runner is an executable Phase-4 methodology,
  while the fixture remains contract evidence only.
- **Conclusion:** Phase 4 is complete and its findings are active. Proceed to
  support/stability validation rather than further fixture tuning.
- **Whether methodology changed:** Yes, throughout item, fold, simulation, KT,
  evaluation, and active configuration boundaries.
- **Output path:** `runs/phase4_checkpoint_fixture/` (ignored transient check),
  with retained scientific artifacts under `reports/phase4/artifacts/`.

## P5-INTEGRATED-VALIDATION-001 — Selector support, penalty, and paired effects

- **Date:** 2026-08-27
- **Research questions:** RQ1--RQ7, RQ19, and RQ20.
- **Motivation:** Determine whether the active selector is stable at medium
  learner support, whether λ=.0005 is a defensible predictive/parsimony point,
  and whether representation effects survive learner-cluster uncertainty.
- **Hypothesis:** More independent learners will reduce chance additions; an
  intermediate penalty will separate the factorized null from a strong
  interaction control; no representation will dominate every latent world.
- **Exact intervention:** Replayed frozen development events at nested
  30/60/120/240 learner sizes for four worlds × three seeds. At 240 learners,
  tested λ in `{0,.00025,.0005,.001,.002}` on factorized and interaction-heavy
  controls. Reused fixed primary-logistic predictions for four representations
  and made 5,000-repeat paired learner-cluster comparisons on the reference
  seed.
- **Dataset/artifact:** Phase-4 24-cell/42-structural-item bank, semantic 18/5/1
  fold, 12 frozen 240-learner event streams, and retained predictions.
- **Exact command:**

  ```bash
  .venv/bin/python scripts/run_phase5_integrated_validation.py
  ```
- **Models:** Observable standardized PFA-style logistic selector/primary KT;
  no language-model call, new item, event, simulation, or final-comparison KT
  fit.
- **Seeds:** simulation `20260827`--`20260829`; paired bootstrap `20260827`,
  5,000 repeats.
- **Result:** At 240 learners, λ=.0005 has zero factorized-null additions in
  3/3 and recovers both eligible planted interactions in 3/3, with one extra
  operation in one positive-control run. λ=0/.00025 false-add in 3/3 and 2/3;
  λ=.001/.002 jointly recover in 2/3 and 0/3. Both planted interactions are
  jointly recovered only 2/3 at 30/60/120 learners. Reference interaction-heavy
  automated-minus-factorized ΔLL is -.002666
  [-.004244,-.001103] and ΔBrier -.001127
  [-.001795,-.000471]; compositional ΔLL -.001438
  [-.005286,.002518] is inconclusive. Exact-all-cell wins only its matching
  cell world. Artifact mtime span was about 798.5 seconds; wall time was not
  separately instrumented.
- **Interpretation:** λ=.0005 is the best tested controlled operating point,
  not a cognitive constant. At least 240 learners/seed are needed here, while
  limited independent cell/item support still constrains inventory certainty.
- **Conclusion:** Retain the active forward/prune selector and λ=.0005; report
  multi-seed selection frequencies, world dependence, and unresolved
  compositional benefit.
- **Whether methodology changed:** The algorithm/configuration remains active;
  its provisional penalty becomes the Phase-6 frozen choice and the minimum
  recommended selection support becomes 240 learners/seed.
- **Output path:** `reports/phase5/artifacts/integrated_validation_v1/` (62 JSON
  artifacts, approximately 1.7 MB) and `reports/phase5/analysis.md`.

## P6-ITEM-N3-001 — Default full-bank generation and validation

- **Date:** 2026-08-27
- **Research questions:** RQ-F8--F14, RQ-F26--F28, RQ-F31, and RQ-F32.
- **Motivation:** Construct the fixed 24-cell learner-facing bank at the
  Phase-4-selected N=3 setting and determine whether pilot coverage scales.
- **Hypothesis:** N=3 will cover most or all 24 cells with at least one valid
  item while retaining a useful second variant for most cells; determinacy will
  remain the principal rejection reason.
- **Exact intervention:** Reused the frozen first-three model-selected pilot
  calls by exact feature tuple for eight cells; made exactly three independent
  generation calls for each of the other 16 cells; applied the deterministic
  answer-span check and one independent all-required-criteria judgment; selected
  earliest valid plus the most token-distant second valid item.
- **Dataset/artifact:** `data/grammar_kt_medium_v1/`: 139 descriptors, 44
  complete mappings, 24 exact cells. No fold, learner evidence, KC, or outcome
  entered item construction.
- **Exact command:**

  ```bash
  .venv/bin/python scripts/run_full_dataset.py --generate-missing --workers 4 --generation-model gpt-5.6-sol --validation-model gpt-5.6-terra --reasoning-effort medium --output-dir data/grammar_kt_medium_v1
  ```
- **Models:** `gpt-5.6-sol` generation and `gpt-5.6-terra` validation, medium
  reasoning; retained normalisation is earlier `gpt-5.6-sol`/medium evidence.
- **Seeds:** Model sampling seed unavailable; deterministic item ordering and
  IDs. No simulation seed involved.
- **Result:** Default N=1/2/3 covers 18/21/22 of 24 cells with 18/35/53 accepts
  from 24/48/72 attempts. N=3 has 71 structurally valid outputs, 53 validator
  accepts, and 43 selected items: 21 cells with two, one with one, two with
  zero. The full valid-output acceptance rate is 53/71=.7465; end-to-end is
  53/72=.7361. Rejected judgments implicate determinacy 17 times, pedagogy
  three, and naturalness two. New generation/validation concurrent call-time
  sums are 408.85/519.36 seconds with medians 7.56/10.83 seconds; these are not
  wall-clock or provider price. `cell_017` (negative past perfect progressive)
  and `cell_022` (affirmative past-perfect passive) have 0/3 accepts, all due
  to underdetermination of aspect/tense (one also contradicts the target).
- **Interpretation:** N=3 materially improves but does not guarantee realistic-
  scale coverage. The two failures are linguistically coherent hard cells, not
  call failures; the pilot's 8/8 coverage should not have been generalized.
- **Conclusion:** Retain N=3 as the default evidence. Invoke only the
  preregistered, separately labelled two-candidate rescue for the two uncovered
  cells with no prompt tuning, then reassess coverage.
- **Whether methodology changed:** No default-method change. A conditional
  failure-driven rescue experiment is triggered exactly as preregistered.
- **Output path:** `data/grammar_kt_medium_v1/items/` and raw call evidence
  beneath its `generation_evidence/` and `validation_evidence/` directories.

## P6-ITEM-RESCUE-001 — Predeclared unchanged-method coverage rescue

- **Date:** 2026-08-27
- **Research question:** RQ-F33.
- **Motivation:** Default N=3 left two structurally difficult cells without an
  accepted item. Test whether two additional independent draws alone resolve
  the gap before changing the generation method.
- **Hypothesis:** With the prompt, rulebook, models, and validation criteria
  unchanged, two further draws may supply temporally explicit contexts that
  determine the target forms.
- **Exact intervention:** Froze the two-cell zero-coverage cohort after all
  default positions and judgments were terminal, then generated and validated
  exactly candidate positions 4 and 5 for those cells. Rescue provenance and
  call evidence are separate from the default N=3 evidence.
- **Dataset/artifact:** The frozen default bank from `P6-ITEM-N3-001`; rescue
  plan `data/grammar_kt_medium_v1/items/rescue_plan.json`.
- **Exact command:**

  ```bash
  .venv/bin/python scripts/run_full_dataset.py --rescue-uncovered --workers 4 --generation-model gpt-5.6-sol --validation-model gpt-5.6-terra --reasoning-effort medium --output-dir data/grammar_kt_medium_v1
  ```
- **Models:** `gpt-5.6-sol` generation and `gpt-5.6-terra` validation, medium
  reasoning.
- **Seeds:** Model sampling seed unavailable; fixed candidate positions 4/5.
- **Result:** All four calls returned structurally valid candidates, and one of
  four was accepted. `cell_022` gained one accepted past-perfect passive item;
  `cell_017` remained uncovered after 0/5 accepted negative past-perfect-
  progressive items. Its two rescue candidates again failed only determinacy
  because simple-perfect, simple-past, or past-progressive alternatives remain
  grammatical. Rescue generation/validation concurrent call-time sums were
  54.84/52.21 seconds; these are not wall time or provider price.
- **Interpretation:** Additional sampling can recover an occasional hard cell,
  but it does not repair systematic construction ambiguity. The five
  `cell_017` failures motivate a separately declared prompt intervention rather
  than another blind batch.
- **Conclusion:** Preserve N=3 and unchanged-method rescue results as negative
  evidence. Test an explicit learner-facing grammatical-form cue only for the
  persistent uncovered cohort, with separate provenance; do not relabel it as
  default generation evidence.
- **Whether methodology changed:** Not yet. The result triggers a focused
  failure-driven experiment.
- **Output path:** `data/grammar_kt_medium_v1/items/`, including
  `generation_evidence/rescue/` and `validation_evidence/rescue/`.

## P6-ITEM-DETERMINACY-001 — Explicit-construction prompt intervention

- **Date:** 2026-08-27
- **Research question:** RQ-F35.
- **Motivation:** `cell_017` remained uncovered after five structurally valid
  candidates because an ordinary context could not uniquely require negative
  past-perfect-progressive aspect.
- **Hypothesis:** Permitting the learner-facing instruction to name the target
  grammatical construction will determine the response without displaying its
  inflected answer.
- **Exact intervention:** Before the first call, froze the one-cell cohort and
  positions 6/7. Changed only the generation prompt to allow an explicit
  construction label; retained the cell, rulebook, format, lexical design,
  generator, validator, and all validation criteria. Independently generated
  and judged both positions regardless of the first outcome.
- **Dataset/artifact:** Post-rescue fixed-bank candidate/judgment records and
  `data/grammar_kt_medium_v1/items/determinacy_intervention_plan.json`.
- **Exact command:**

  ```bash
  .venv/bin/python scripts/run_full_dataset.py --determinacy-intervention --workers 4 --generation-model gpt-5.6-sol --validation-model gpt-5.6-terra --reasoning-effort medium --output-dir data/grammar_kt_medium_v1
  ```
- **Models:** `gpt-5.6-sol` generation and `gpt-5.6-terra` validation, medium
  reasoning.
- **Seeds:** Model sampling seed unavailable; fixed candidate positions 6/7.
- **Result:** Both calls were structurally valid and both passed determinacy;
  one of two passed every required criterion. Position 6 failed naturalness
  because its full target repeated a subject already printed before the slot.
  Position 7 was accepted, giving complete 24/24 cell coverage. Final totals
  are 78 attempts, 77 structurally valid candidates, 55 validator accepts, and
  45 selected items. The prompt intervention generation/validation call-time
  sums were 27.64/25.13 seconds; these are not wall time or provider price.
- **Interpretation:** Explicit construction cues repair a systematic aspect-
  determinacy problem, but do not eliminate response-slot contract errors.
  The cue is a conditional instructional intervention, not evidence that
  unchanged contextual generation succeeds on every structure.
- **Conclusion:** Keep model-selected contextual N=3 as the default and report
  rescue/intervention evidence separately. Permit the explicit-construction
  prompt only after repeated determinacy-only zero coverage; freeze the cohort
  and cap it at two calls.
- **Whether methodology changed:** Yes. The final item method adds this narrow,
  explicitly triggered fallback and records its distinct provenance.
- **Output path:** `data/grammar_kt_medium_v1/items/`, including
  `generation_evidence/determinacy_intervention/` and
  `validation_evidence/determinacy_intervention/`.

## P6-DOWNSTREAM-001 — Final fixed-bank KC selection and KT evaluation

> **Superseded evidence boundary (2026-08-27):** this first downstream run used
> the 45-item pre-curation bank.  Its artifacts are retained under
> `data/grammar_kt_medium_v1/superseded_pre_curation/2026-08-27_f36_packaging_correction/`.
> The active dataset and paper use `P6-DOWNSTREAM-CURATED-001` below.

- **Date:** 2026-08-27
- **Research questions:** RQ-F6/F7 and RQ-F15--F25.
- **Motivation:** Apply the frozen Phase-5 methodology to the completed live
  item bank and retain a realistic-scale learner dataset, selected KC policy,
  Q-matrices, predictions, and paired representation evidence.
- **Hypothesis:** The mixed-world evidence may support a small number of
  reusable interactions, but the automated policy need not outperform every
  richer representation or establish compositional benefit.
- **Exact intervention:** Built the outcome-free semantic 18/5/1 fold; derived
  candidates from the 18 development cells and 33 development items only;
  generated a single 1,000-learner mixed-world stream with development-only
  acquisition and non-updating all-bank probes; selected on development
  train/validation; froze factorized, all-supported, automated, and labelled
  exact-all-cell oracle policies; projected the same 45 items; ran empirical,
  fixed BKT, and no-oracle logistic KT; and made 5,000 learner-paired logistic
  comparisons.
- **Dataset/artifact:** `data/grammar_kt_medium_v1`, fixed at 24 cells and 45
  selected items before the fold or learner evidence was constructed.
- **Exact command:**

  ```bash
  .venv/bin/python scripts/finalize_full_dataset.py --dataset-dir data/grammar_kt_medium_v1 --learners 1000 --seed 20260827 --bootstrap-repeats 5000
  ```
- **Models:** Declared synthetic mixed latent world; empirical, mean-credit
  BKT, and standardized observable PFA-style logistic KT. No language model.
- **Seeds:** simulation/selector/bootstrap `20260827`; 5,000 bootstrap repeats.
- **Result:** The dataset contains 210,000 events, of which 165,000 development
  train/validation events enter selection; all policies share those events.
  Candidate counts are 55 raw (9 feature, 10 operation, 18 interaction, 18
  development full-cell), 38 activation classes, 42 support-eligible, and 28
  selection-eligible. The selector retains 10 KCs: nine feature marginals plus
  `aspect=perfect × polarity=negative` (two cells/four items). Primary logistic
  test log loss is .644029 factorized, .643627 all-supported, .643798 automated,
  and .657535 oracle-cell. Automated-minus-factorized paired delta is -.000232
  with 95% interval [-.000488,.000028]; compositional delta is -.000318
  [-.000930,.000311]. All-supported-minus-factorized is -.000402
  [-.000738,-.000071] overall and -.000939 [-.001573,-.000307]
  compositionally, but uses 16 rather than 10 KCs. Exact-cell transfer is
  substantially worse.
- **Interpretation:** The active selector finds a planted mixed-world
  interaction and improves the predictive/parsimony objective on its reserved
  development validation stream, but its frozen-test effect is small and its
  interval crosses zero. The richer all-supported representation has the best
  point estimate and a nonzero paired interval in this seed, so the final
  evidence does not support claiming that automated selection is the most
  predictive representation at every scale/world. The oracle-cell failure is
  evidence for reuse, not proof that the factorized ontology is cognitively
  correct.
- **Conclusion:** Retain the automated policy as the main interpretable,
  parsimonious method and all-supported interactions as an important stronger-
  prediction comparison. Report the mixed-world predictive result as
  inconclusive for automation and test inventory stability across seeds before
  final claims.
- **Whether methodology changed:** No algorithmic change. The final selected
  policy and fixed dataset are now materialized; claims are narrowed to match
  the paired evidence.
- **Output path:** `data/grammar_kt_medium_v1/{fold,simulation,kc,kt,evaluation}`
  and `data/grammar_kt_medium_v1/finalization_manifest.json`.

## P6-ITEM-QUAL-001 — All-item independent agent audit

- **Date:** 2026-08-27
- **Research questions:** RQ-F27, RQ-F28, and failure-driven RQ-F36.
- **Motivation:** Aggregate model-validator acceptance and lexical diversity do
  not reveal response-slot packaging errors, repeated worksheet templates, or
  inconsistent decisions near tense/aspect boundaries.
- **Hypothesis:** Exhaustive qualitative inspection will expose a small number
  of deterministic item-contract defects and broader model-judgment/realism
  limitations that summary rates miss.
- **Exact intervention:** An independent agent inspected every one of 45
  selected items and all 22 structurally valid rejected candidates against the
  visible prompt, complete target, slot-only accepted answers, intended cell,
  and retained judgments. It made no model call and no artifact change. This is
  an interactive qualitative audit, so there is no executable command; the
  complete scope, item-ID classifications, criteria, and findings are retained
  in the output artifact.
- **Dataset/artifact:** The `P6-ITEM-DETERMINACY-001` fixed bank and raw
  candidate/judgment files.
- **Models:** Agent qualitative review; explicitly not human/expert validation.
- **Seeds:** None.
- **Result:** Thirty-one selected items had no material item-level concern,
  nine were judgment-sensitive, and five require deterministic packaging or
  complete-reference correction. Four slot-only accepted sets repeat terminal
  punctuation printed after the blank; two complete target references omit
  visible clause material (one overlaps). No selected target was clearly
  ungrammatical or wrong-cell. Of 22 rejections, 15 were well supported and
  seven were plausibly inconsistent/repairable. Prompt uniqueness is 45/45,
  yet 34 prompts use a “Complete…” stem; common names, domestic contexts, and
  predicates recur.
- **Interpretation:** Model acceptance is not sufficient quality assurance.
  The deterministic precheck missed suffix punctuation and complete-reference
  reconstruction, while validator decisions remain unstable around marked
  tense/aspect and optional paraphrases. Surface lexical diversity overstates
  pedagogical/contextual diversity.
- **Conclusion:** Freeze exact corrections that do not alter prompts or grammar,
  strengthen the suffix check, independently revalidate corrected records, and
  regenerate downstream evidence. Do not silently revise borderline elicitation
  semantics or claim human quality.
- **Whether methodology changed:** The result triggers F36 and a narrow
  post-generation packaging-correction/revalidation stage.
- **Output path:** `reports/phase6/artifacts/qualitative_item_audit.md`.

## P6-ITEM-CURATION-001 — Frozen packaging correction and independent revalidation

- **Date:** 2026-08-27
- **Research question:** Failure-driven RQ-F36.
- **Motivation:** The exhaustive audit found six exact answer/reference packaging
  defects.  They had to be corrected without silently rewriting prompts,
  grammar targets, or the immutable raw model evidence.
- **Hypothesis:** Correcting only the frozen fields and independently
  revalidating all six records would repair the response contract while
  revealing whether prior validator decisions were stable to the corrected
  representation.
- **Exact intervention:** Froze the six item IDs and field-level edits before
  any call (plan SHA-256
  `bbed7be77c2d326bd7133308ea22d637bed5de8d44cd4bb470a2421c4ebe0dc5`),
  preserved the raw candidates and judgments byte-for-byte, rejudged the six
  corrected records once with the original validator settings, rebuilt the
  active accepted/selected bank, and recoverably archived all pre-curation
  downstream artifacts.
- **Dataset/artifact:** `data/grammar_kt_medium_v1/items/packaging_correction_plan.json`;
  raw candidate SHA-256 `0317d2b0cf36ea24b5ff55775374e03034e233b41208d1ecebd83f658537d88a`,
  raw judgment SHA-256 `0d3aa8ef46df1ed49a50cc1c61fd53d4de2d67764b012f621f558b6a70b758a9`.
- **Exact command:**

  ```bash
  .venv/bin/python scripts/curate_item_packaging.py --dataset-dir data/grammar_kt_medium_v1 --workers 4 --validation-model gpt-5.6-terra --reasoning-effort medium
  ```
- **Models:** `gpt-5.6-terra`, medium reasoning, one independent judgment per
  corrected record.
- **Seeds:** Model sampling seed unavailable; frozen plan and deterministic
  bank ranking.
- **Result:** Four corrected records were accepted and two were rejected.
  `candidate_cell_017_06` flipped false→true after its complete-target repair;
  `candidate_cell_005_01` and `candidate_cell_018_01` flipped true→false on
  determinacy, while the other three retained acceptance.  The active bank has
  54 accepts and 44 selected items over 24/24 cells.  The suffix-punctuation
  precheck is now active and counts two raw precheck failures.
- **Interpretation:** The packaging fixes are reproducible, but the two
  accept→reject flips on criteria unrelated to punctuation are direct evidence
  that a single model judgment is unstable at marginal determinacy cases.
- **Conclusion:** Retain the curated 44-item bank, the immutable raw evidence,
  both validation layers, and the instability limitation.  All downstream
  learner/KC evidence must be regenerated from the curated bank.
- **Whether methodology changed:** Yes.  Deterministic slot reconstruction and
  frozen correction/revalidation are now explicit quality-control stages.
- **Output path:** `data/grammar_kt_medium_v1/items/{curated_candidates.jsonl,packaging_correction_validation.jsonl,curated_validation.jsonl,validator_accepted.jsonl,selected_bank.jsonl,packaging_correction_manifest.json}`.

## P6-DOWNSTREAM-CURATED-001 — Curated-bank KC selection and KT evaluation

- **Date:** 2026-08-27
- **Research questions:** RQ-F6/F7 and RQ-F15--F25.
- **Motivation:** Replace every pre-curation fold, learner stream, policy,
  projection, prediction, and evaluation with evidence derived from the final
  corrected bank.
- **Hypothesis:** The frozen Phase-5 selector should remain structurally valid;
  small predictive intervals may change because one item left the bank.
- **Exact intervention:** Rebuilt the semantic fold and development-only
  candidates from 44 items, simulated one 1,000-learner mixed-world stream,
  selected/froze policies, projected the identical bank, ran empirical/BKT/
  no-oracle logistic KT, and performed 5,000 learner-cluster paired bootstrap
  comparisons.
- **Dataset/artifact:** Curated `data/grammar_kt_medium_v1`, 24 cells and 44
  items fixed before fold construction or simulation.
- **Exact command:**

  ```bash
  .venv/bin/python scripts/finalize_full_dataset.py --dataset-dir data/grammar_kt_medium_v1 --learners 1000 --seed 20260827 --bootstrap-repeats 5000
  ```
- **Models:** Declared `phase4_mixed_v1` synthetic world; empirical,
  mean-credit BKT, and standardized observable PFA-style logistic KT.  No
  language-model call.
- **Seeds:** Simulation/selector/bootstrap `20260827`; 5,000 bootstrap repeats.
- **Result:** The final dataset has 204,000 events; exactly 160,000 development
  train/validation events enter selection.  The fold contains 18/5/1 cells and
  32/10/2 items.  Candidate counts remain 55 raw, 38 activation classes, 42
  support-eligible, and 28 selection-eligible.  The automated policy again
  contains nine marginals plus perfect×negative.  Logistic test log loss is
  .643731 factorized, .643334 all-supported, .643356 automated, and .657507
  exact-all-cell.  Automated-minus-factorized is -.000375 with learner 95%
  interval [-.000631,-.000109] overall, -.000450
  [-.000758,-.000141] on development, -.000234
  [-.000836,.000375] compositionally, and +.000119
  [-.000099,.000352] on the single novel-value cell.  All-supported minus
  factorized is -.000397 [-.000782,-.000026] overall and -.001168
  [-.002042,-.000246] compositionally.
- **Interpretation:** Curated-bank automation has a small paired overall
  advantage over marginals in this one declared mixed stream, but its
  compositional and novel-value effects remain inconclusive.  All supported
  interactions have the stronger compositional estimate at six extra KCs;
  exact-cell memorisation transfers poorly.
- **Conclusion:** Keep the 10-KC automated policy as the parsimonious active
  representation and all-supported as the stronger-prediction sensitivity.
  Do not claim established compositional or novel-feature benefit.
- **Whether methodology changed:** No selector change; the evidence and paper
  numbers replace the superseded 45-item run.
- **Output path:** `data/grammar_kt_medium_v1/{fold,simulation,kc,kt,evaluation}`
  and `data/grammar_kt_medium_v1/finalization_manifest.json`.

## P6-SELECTION-STABILITY-001 — Full-bank support and seed stability

- **Date:** 2026-08-27
- **Research questions:** RQ-F19, RQ-F25, and RQ20.
- **Motivation:** The final policy was selected from one synthetic stream; the
  programme required inventory stability across repeated event seeds and
  learner supports before paper-facing claims.
- **Hypothesis:** At the Phase-5-supported 1,000-learner scale the selected
  interaction will be stable, while smaller nested samples may expose a noisy
  support region.
- **Exact intervention:** With the curated bank, fold, candidates, world, and
  selector fixed, selected on nested 60/120/240/500/1,000 learner prefixes of
  seed 20260827 and on full 1,000-learner streams for seeds 20260827--20260831.
  This is nine unique conditions, not a Cartesian grid.  Only development
  train/validation events entered any selection.
- **Dataset/artifact:** Final curated candidate inventory and semantic fold;
  five retained compressed event streams plus nine policies/traces.
- **Exact command:**

  ```bash
  .venv/bin/python scripts/run_phase6_selection_stability.py
  ```
- **Models:** Declared mixed synthetic world and fixed observable-logistic
  selector; no language model.
- **Seeds:** 20260827, 20260828, 20260829, 20260830, 20260831.
- **Result:** All five 1,000-learner seeds selected the identical 10-KC
  inventory (all-selected and addition Jaccard 1.0), including
  perfect×negative.  Nested 60/240/500/1,000 conditions also matched.  The
  120-learner condition instead selected present×passive, giving selected-set
  Jaccard .818 with the reference.  Across all nine conditions the reference
  interaction frequency is 8/9.  Holdout and reserved-test events supplied to
  selection are both zero.
- **Interpretation:** Synthetic stream noise is negligible at 1,000 learners
  under the declared world, but the non-monotone 120-learner swap confirms that
  low-support selection is not reliable.  This is not generation-model,
  validator, human, or cross-language stability.
- **Conclusion:** Final policy stability is established only within the fixed
  mixed simulator at 1,000 learners.  Retain the ≥240 learner working rule and
  report the anomalous 120-learner result rather than smoothing it away.
- **Whether methodology changed:** No.
- **Output path:** `reports/phase6/artifacts/selection_stability_v1/` and the
  compact dataset copy `data/grammar_kt_medium_v1/kc/selection_stability.json`.

## P6-FULL-ANALYSIS-001 — Deterministic paper-facing dataset analysis

- **Date:** 2026-08-27
- **Research questions:** RQ-F1--F36.
- **Motivation:** Consolidate source, normalization, canonical, item, fold,
  candidate, policy, KT, paired, qualitative, and stability evidence without
  making new model calls or resimulating learners.
- **Hypothesis:** A single artifact-driven analysis can support every
  quantitative paper table while keeping unresolved RQs explicit.
- **Exact intervention:** Read only retained final artifacts, generated
  traceable CSV/Markdown tables and a compact JSON summary, and attached the
  exact RQ evidence index.
- **Dataset/artifact:** Final curated `data/grammar_kt_medium_v1` plus its
  dataset-local stability result.
- **Exact command:**

  ```bash
  .venv/bin/python scripts/analyze_full_dataset.py --dataset-dir data/grammar_kt_medium_v1 --output-dir reports/phase6/artifacts/full_dataset_analysis
  ```
- **Models:** None.
- **Seeds:** Reads the retained seeds above; makes no stochastic computation.
- **Result:** Produced 19 paper-facing CSV tables, `tables.md`, and
  `summary.json`; reconciled 139 descriptors, 24 cells, 78 attempts, 77
  candidate payloads/judgments, 54 accepts, 44 selected items, 204,000 learner
  events, four KC policies, 12 paired comparisons, and the nine-condition
  stability study.
- **Interpretation:** Paper numbers can now be traced to one final artifact
  graph.  Normalisation repeatability, human item quality, and natural learner
  validity remain outside the evidence.
- **Conclusion:** Use these outputs as the quantitative source of truth for the
  Phase-6 report and ACL manuscript.
- **Whether methodology changed:** No.
- **Output path:** `reports/phase6/artifacts/full_dataset_analysis/`.

## P7-CONSOLIDATION-001 — Final active-path, language-boundary, and paper verification

- **Date:** 2026-08-27
- **Research questions:** RQ-F29 and final reproducibility/claim consistency.
- **Motivation:** Ensure the repository and manuscript describe the supported
  final method rather than leaving English fixture assumptions, rejected
  policies, stale paths, or pre-curation numbers in the active interface.
- **Hypothesis:** The generic KC/simulation interface can remain simple while
  moving English/manual fixture material out of active declarations, and the
  complete final package can pass code, notebook, artifact, and rendered-paper
  verification.
- **Exact intervention:** Removed hard-coded passive/question difficulty
  branches from generic simulation; validate declared latent activations against
  the schema; enforce the declared selection metric/complexity labels; moved
  ID-specific folds/manual policies and historical generator-tag rules to
  fixtures; extended the alternate schema through active selection/freezing;
  modernized the linear runner and executed notebook; rewrote the README,
  methodology and RQ ledger; updated the ACL paper exclusively from final
  curated evidence; rendered and visually inspected every PDF page; tightened
  appendix floats after QA.
- **Dataset/artifact:** Final curated `data/grammar_kt_medium_v1` and all Phase
  2--6 retained reports/artifacts.
- **Exact commands:**

  ```bash
  .venv/bin/python -m pytest -q
  .venv/bin/jupyter nbconvert --to notebook --execute --inplace --ExecutePreprocessor.timeout=600 notebooks/pipeline_walkthrough.ipynb
  .venv/bin/python scripts/run.py --fixture --output <new-temporary-run-directory>
  .venv/bin/python scripts/finalize_full_dataset.py --dataset-dir data/grammar_kt_medium_v1 --learners 1000 --seed 20260827 --bootstrap-repeats 5000
  .venv/bin/python scripts/run_phase6_selection_stability.py --recompute
  .venv/bin/python scripts/run_phase6_selection_stability.py
  cd ACL && latexmk -pdf -interaction=nonstopmode -halt-on-error paper.tex
  .venv/bin/python ACL/tests/regression/run_tests.py
  git diff --check -- . ':(exclude)pipeline.txt'
  ```
- **Models:** No live model calls. The notebook/runner use deterministic fixture
  responses; the paper consumes retained evidence.
- **Seeds:** Fixture declarations use 20260827. No new stochastic scientific
  result is produced.
- **Result:** 107/107 Pytest contracts and 71/71 ACL regressions pass. The
  fixture runner completes with six items/624 events; the offline notebook
  completes with six items/eight learners/208 events. The alternate
  `mood`/`person` test runs candidate construction→selection→freezing→projection.
  The finalizer reproduces all 204,000 events, policies, metrics, and paired
  intervals exactly under the cleaned code; forced regeneration of all five
  stability streams preserves the 5/5 identical full-support inventories.
  The ACL PDF builds in 11 pages with embedded fonts, no overfull/undefined/error
  warning, and no observed render defect. Scoped diff check is clean; the only
  unfiltered finding is preserved pre-existing whitespace in user-owned
  `pipeline.txt`.
- **Interpretation:** The active method is structurally schema-driven after the
  language/resource declarations, while the empirical evidence remains English
  only. Code, data, reports, and paper now share one final artifact graph.
- **Conclusion:** Phase 7 is complete. Further scientifically decisive work
  requires external human/expert validation or real learner responses rather
  than additional in-harness tuning.
- **Whether methodology changed:** Yes at the interface/documentation level;
  no post-hoc change to the frozen candidate design, selector, dataset, or
  quantitative result.
- **Output path:** `README.md`, `reports/{final_methodology.md,final_rq_ledger.md,final_verification.md}`,
  `scripts/run.py`, `notebooks/pipeline_walkthrough.ipynb`, and `ACL/paper.pdf`.

## BACKEND-THINKING-001 — Per-stage medium/high/xhigh effort audit

- **Date:** 2026-08-28
- **Research question:** RQ21: which backend reasoning effort should each
  model-backed module use?
- **Motivation:** The active runner applied one untested global `medium` effort
  to normalisation, generation, and validation even though these tasks have
  different inference and safety profiles.
- **Hypothesis:** The lowest setting within five quality points of the best
  admissible setting will normally suffice; deeper effort may help constrained
  normalisation more than generation or binary validation.
- **Exact intervention:** Froze a challenge-enriched 24-descriptor Phase-1
  normalisation cohort, nine fixed-input Phase-2 transitions, a 36-item
  boundary validation cohort plus 12 authored safety negatives, and all 24
  final GrammarCells at N=3. Interleaved fresh medium/high/xhigh calls, used two
  repeats for normalisation/validation and one generation block, froze one
  common medium validator before judging generation, retained token/latency
  evidence, and obtained two condition-blind research-agent reviews plus
  disagreement-only adjudication. Selection used a five-point paired cluster-
  bootstrap margin, completeness/critical gates, and a one-cell generation-
  coverage tolerance.
- **Dataset/artifact:** `data/grammar_kt_medium_v1` cells and curated challenge
  items; frozen cohorts and every call/review/result under
  `reports/backend_thinking/artifacts/live_v1/`.
- **Exact commands:**

  ```bash
  .venv/bin/python scripts/run_backend_thinking_audit.py --stage prepare --output-dir reports/backend_thinking/artifacts/live_v1
  .venv/bin/python scripts/run_backend_thinking_audit.py --stage normalisation --output-dir reports/backend_thinking/artifacts/live_v1 --workers 4
  .venv/bin/python scripts/run_backend_thinking_audit.py --stage validation --output-dir reports/backend_thinking/artifacts/live_v1 --workers 4
  .venv/bin/python scripts/run_backend_thinking_audit.py --stage generation --output-dir reports/backend_thinking/artifacts/live_v1 --workers 4
  .venv/bin/python scripts/run_backend_thinking_audit.py --stage generation --output-dir reports/backend_thinking/artifacts/live_v1 --workers 4 --judge-effort medium
  .venv/bin/python scripts/run_backend_thinking_audit.py --stage analyze --output-dir reports/backend_thinking/artifacts/live_v1
  .venv/bin/python scripts/analyze_backend_thinking_reviews.py --output-dir reports/backend_thinking/artifacts/live_v1 --bootstrap-replicates 10000
  ```
- **Models/settings:** `gpt-5.6-sol` for normalisation/generation and
  `gpt-5.6-terra` for validation/common judging; efforts medium, high, xhigh;
  Codex CLI 0.150.1; four workers. The 918 stage evaluations contained 905 live
  model calls and 13 deterministic precheck decisions; CLI reported 3,351,258
  tokens. There were no nonzero CLI return codes and one malformed judge JSON.
- **Seeds:** 20260828 for interleaving, blinding, and 10,000 paired cluster-
  bootstrap resamples. Provider sampling seed unavailable.
- **Result:** All 198 normalisation calls were contract/transition valid.
  Adjudicated quality medium/high/xhigh was 89.4/92.4/92.4%, critical mappings
  3/2/2, and structural repeat agreement 78.8/87.9/81.8%; high-minus-xhigh was
  0.0 points, 95% CI [-4.55,+4.55]. Validation quality was
  69.4/58.3/56.9%; every effort rejected all 24 repeated authored safety
  controls, but confirmed critical false accepts were 2/3/2. Medium-minus-high
  was +11.11 points [0.00,+22.22] and medium-minus-xhigh +12.50
  [+1.39,+23.61]. All 216 generation payloads were valid; common-judge
  acceptance was 70.8/77.8/74.6% and N=3 coverage 21/23/23 cells. Blind
  position-1 quality tied at 87.5%, with critical defects 2/3/3; paired
  generation intervals crossed zero. Strict zero-critical/completeness/
  coverage gates yielded no confirmatory winner in any module.
- **Interpretation:** More thinking is not monotonically better. High improves
  normalisation relative to medium and dominates xhigh operationally on
  stability/cost. Validation degrades with added effort on this cohort.
  Generation high offers more coverage but not independently confirmed quality
  and has more safety defects; retain the lower-risk current setting.
- **Conclusion:** Active future settings are Sol/high normalisation,
  Sol/medium generation, and Terra/medium validation. These are explicitly
  operational fallbacks under an inconclusive strict rule, not universal or
  human-validated superiority claims. The already retained dataset remains
  unchanged with its original all-medium provenance.
- **Whether methodology changed:** Yes. Replaced the runner's shared hard-coded
  effort with the small per-stage `modules/model_backends.yaml` declaration and
  independent routing/provenance tests. No dataset, KC, learner-event, or paper
  result was regenerated.
- **Output path:** `reports/backend_thinking/analysis.md`,
  `reports/backend_thinking/artifacts/live_v1/`,
  `modules/model_backends.yaml`, `scripts/run_backend_thinking_audit.py`, and
  `scripts/analyze_backend_thinking_reviews.py`.

## FULL-AUDIT-001 — revised-framing repository and evidence audit

- **Date:** 2026-08-29
- **Research question:** What existing artifacts remain valid under the strict
  `GrammarCell != K* != K_hat` distinction, and what blocks a full baseline?
- **Motivation:** The retained repository called an outcome-selected,
  medium-scale experimental pipeline complete, while the revised programme
  requires an explicit pre-simulation generator ontology and full source
  census.
- **Hypothesis:** Linguistic/item/KT components and historical evidence would
  remain reusable, but the baseline ordering and dataset package would require
  a new K*/Q*/simulator boundary.
- **Methodology:** Read-only inspection of git state/branches, every active
  source module/config/script family, persistent reports, medium artifacts,
  ignored historical runs, notebooks, tests, manuscript, and the locally
  available full source. Three independent audits covered linguistic scope,
  generator-KC design, and code/reproducibility architecture.
- **Manipulated variable:** None; evidence audit.
- **Held fixed:** Repository revision `c2e1d21e`, existing working tree, and
  retained artifacts.
- **Exact commands:** `git status --short --branch`; `rg --files`; targeted
  `sed`/`rg`/hash/count inspections; `.venv/bin/python -m pytest -q`; tracked
  notebook execution checks; ACL force-build and regression checks.
- **Models/settings:** No live research-model calls. Parallel audit agents used
  the active Codex environment for independent critique.
- **Seeds:** None.
- **Data:** Repository at `c2e1d21e`; exact 1,222-row EGP snapshot with SHA-256
  `e38c4f...c2488486cd`.
- **Results:** The old pipeline simulates an implicit world before selecting
  KCs from outcomes; those KCs are `K_hat`, not K*. The medium dataset has 139
  descriptors, 24 cells, 44 items, and 204,000 events but no top-level K*, true
  Q*, or revised interaction schema. The full source is available and exact,
  but the documented runner is stale, fixture-hardcoded, sequential, and not
  resumable. Existing normalisation, item, KT, paired-evaluation, and historical
  experiment evidence remain reusable in their proper layers. All 112 initial
  Pytest contracts pass; notebooks and the ACL package remain executable.
- **Uncertainty/failure analysis:** Live model aliases are mutable/unseeded;
  the source is consult-only; old final reports and paper embody the superseded
  framing. Dirty user-authored files must remain untouched.
- **Interpretation:** The programme is not complete under the revised RQs. The
  minimal scientific repair is a full stage-separated linguistic census,
  declared K*, deterministic Q* audit, and K*/Q*-consuming simulator before any
  downstream experiment.
- **Methodological consequence:** Reopened the programme on
  `agent/full-dataset-research-program`; classified the medium work as pilot
  evidence; began `scripts/build_dataset.py`, `modules/kcs/generator/`, and
  generic generator/Q audit modules.
- **Artifact paths:** `reports/research_state.md`,
  `reports/full_v1_protocols/`, and the new full-v1 construction code/config.

## FULL-KC-001-PILOT — outcome-free generator-KC alternatives on the retained bank

- **Date:** 2026-08-29
- **Research question:** Which declared generator ontology is linguistically
  reusable, parsimonious, and structurally measurable before any learner is
  simulated?
- **Motivation:** The revised programme requires `K*` to be fixed independently
  of the response evidence it will generate. The retained medium bank provides
  a cheap structural pilot but cannot select `K*` by predictive KT fit.
- **Hypothesis:** The declared reusable-operation hybrid will retain full Q
  column rank and useful pair contrasts with fewer latent dimensions than a
  feature control; the perfect-progressive chain will add nested complexity,
  while exact-cell KCs will provide no reuse.
- **Methodology:** Projected the same 44 fixed medium-bank items mechanically
  onto four inventories: the operation hybrid, hybrid plus the preregistered
  perfect-progressive-chain interaction, observed non-reference feature values,
  and one KC per exact cell. Compared support, rank, identical/near-identical Q
  columns, pair contrasts, and reuse. The script copies only cell IDs/features
  and item-to-cell references; it has no event, outcome, selector, or KT input.
- **Manipulated variable:** Generator-KC construction principle.
- **Held fixed:** The 24 retained canonical cells, 44 curated items, canonical
  schema, generator support thresholds, and deterministic Q projection.
- **Exact command:**

  ```bash
  .venv/bin/python scripts/investigate_generator_kcs.py \
    --cells data/grammar_kt_medium_v1/canonical/cells.jsonl \
    --items data/grammar_kt_medium_v1/items/selected_bank.jsonl \
    --output reports/full_v1_artifacts/kc/generator_alternatives_medium.json
  ```
- **Models/settings:** None; deterministic structural analysis.
- **Seeds:** None.
- **Data:** Historical `grammar_kt_medium_v1` cells and fixed item bank.
- **Results:** The hybrid used 9 KCs, had rank 9, 99 Q edges, 24 distinct
  cell-activation rows, no identical or near-identical columns, and two-sided
  contrasts for all 36 KC pairs. The feature control used 10 KCs and also had
  full rank. Adding the chain produced 10 full-rank KCs, but its 5 items/3
  cells were strictly nested within both component skills: each comparison had
  8 component-only, 5 co-occurring, and 0 chain-only items. The 24 exact-cell
  KCs had no cross-cell reuse and one fell below the two-item support gate.
- **Uncertainty/failure analysis:** This is medium-bank pilot geometry, not the
  full-inventory freeze and not evidence about human cognitive structure. Full
  support can change after the linguistic census and item-bank construction.
  Q full rank establishes linear distinguishability, not reliable statistical
  recovery under finite noisy responses.
- **Interpretation:** Retain the operation hybrid as the working `K*`. The
  feature-only and exact-cell representations remain downstream controls. The
  chain lacks a parsimony justification at this scale and remains excluded by
  default; its full-bank structural result will be reported before the freeze.
- **Methodological consequence:** Added an outcome-free, reproducible
  generator-ontology pilot and an explicit K*/Q*-consuming baseline simulator.
  No learner responses were generated and no ontology was selected by KT fit.
- **Artifact paths:**
  `reports/full_v1_artifacts/kc/generator_alternatives_medium.json`,
  `scripts/investigate_generator_kcs.py`, and
  `modules/kcs/generator/`.

## FULL-LING-001 — full-source normalisation, canonicalisation, and repeat audit

- **Date:** 2026-08-29
- **Research question:** RQ1: can the complete available grammar resource be
  dispositioned reproducibly into an explicit declared canonical scope rather
  than a purposive medium sample?
- **Motivation:** The retained 139-descriptor pilot did not establish source
  coverage and omitted most modal values and WH structure. The revised
  baseline requires every source row to receive an auditable disposition.
- **Hypothesis:** The existing six-dimensional single-main-clause verbal-
  morphosyntax schema will support a meaningful exact subset without schema
  expansion, while explicit partial/out-of-scope results will absorb genuinely
  underspecified or unrelated descriptors.
- **Methodology:** Verified the consult-only 1,222-row EGP snapshot by hash;
  sent every typed descriptor through descriptor-only Phase 1; froze the
  declared example-licensed Phase-2 cohort; retained every branch and result;
  canonicalised only mappings declared complete; and independently repeated a
  category/CEFR-balanced 120-row Phase-1 cohort. The repeat comparison is
  source-ID paired and ignores branch order. Raw descriptors, prompts, model
  outputs, and notes remain in ignored private evidence.
- **Manipulated variable:** Phase-2 example assistance for its frozen eligible
  cohort; fresh annotation instance for the repeat audit.
- **Held fixed:** Source hash, typed boundary, schema, rulebook, prompts,
  backend, effort, and canonicalisation rules.
- **Exact commands:**

  ```bash
  .venv/bin/python scripts/build_dataset.py --stage prepare-source --source /home/abdullah/urop-aug/sources/parsed_final/egp_entries.jsonl
  .venv/bin/python scripts/build_dataset.py --stage normalise-phase1 --source /home/abdullah/urop-aug/sources/parsed_final/egp_entries.jsonl --workers 8 --max-attempts 2
  .venv/bin/python scripts/build_dataset.py --stage normalise-phase2 --source /home/abdullah/urop-aug/sources/parsed_final/egp_entries.jsonl --workers 8 --max-attempts 2
  .venv/bin/python scripts/build_dataset.py --stage canonicalise
  .venv/bin/python scripts/run_full_normalisation_stability.py --stage run --typed-source runs/grammar_kt_full_v1_private/source/descriptors.jsonl --primary-phase1 data/grammar_kt_full_v1/provenance/normalisation/phase1_mappings.jsonl --workers 8 --max-attempts 2
  .venv/bin/python scripts/audit_full_normalisation.py --source runs/grammar_kt_full_v1_private/source/descriptors.jsonl --phase1 data/grammar_kt_full_v1/provenance/normalisation/phase1_mappings.jsonl --phase2 data/grammar_kt_full_v1/provenance/normalisation/phase2_mappings.jsonl --phase1-attempts data/grammar_kt_full_v1/provenance/normalisation/phase1_attempts.jsonl --phase2-attempts data/grammar_kt_full_v1/provenance/normalisation/phase2_attempts.jsonl --cells data/grammar_kt_full_v1/grammar/cells.jsonl --relations data/grammar_kt_full_v1/grammar/source_cell_relations.jsonl --repeat-mappings data/grammar_kt_full_v1/provenance/normalisation/stability/repeat_mappings.jsonl --allow-incomplete --output data/grammar_kt_full_v1/provenance/normalisation/full_audit.json
  ```
- **Models/settings:** `gpt-5.6-sol`, high reasoning; eight parallel workers;
  two maximum technical attempts. Provider sampling seed and token count were
  unavailable. All 1,447 calls used one attempt and returned valid contracts;
  aggregate call runtimes were 18,402.58 seconds for Phase 1, 1,531.30 seconds
  for Phase 2, and 1,827.04 seconds for repeats.
- **Seeds:** Deterministic cohort seed `20260829`; provider seed unavailable.
- **Data:** All 1,222 source rows, SHA-256
  `e38c4f959f188150dae7b88f21e35d77828048772e222191818dc0c2488486cd`.
- **Results:** Phase 1 produced 170 complete, 375 partial, two unresolved, and
  675 out-of-scope mappings. Of 106 eligible partials, 105 had licensed
  examples; Phase 2 resolved 41/105 (39.05%) to complete, retained 57 partial,
  and made seven unresolved, with 124→137 branches. The final census is 211
  complete, 327 partial, nine unresolved, and 675 out-of-scope descriptors.
  Canonicalisation produced 75 exact cells and 228 source-cell relations with
  exact feature/support agreement and no schema violation. On the balanced
  repeat, result agreement was 112/120 (93.3%), eligibility agreement 115/120
  (95.8%), and exact complete-cell-set agreement 38/38 (100%). Partial/uncertain
  branch-multiset agreement was lower: 64/81 (79.0%) among rows with branches.
- **Uncertainty/failure analysis:** Automatic normalisation is not human gold;
  model sampling is not provider-seeded. Remaining uncertainty clusters in
  unspecified polarity and combinations of voice/aspect/clause/tense. One
  Phase-1-eligible row lacked an example and was not silently called. A
  duplicate branch remains inside a partial mapping and does not enter the
  canonical inventory.
- **Interpretation:** The declared schema represents a defensible exact
  verbal-morphosyntax subset of the full source without adding dimensions for
  coverage alone. Perfect agreement for jointly complete rows supports the
  canonical inventory; weaker partial agreement supports the conservative
  completeness gate.
- **Methodological consequence:** Freeze the 75-cell inventory and keep all
  non-complete dispositions as provenance, not measurement cells. No schema
  expansion or default filling was adopted.
- **Artifact paths:** `data/grammar_kt_full_v1/grammar/` and
  `data/grammar_kt_full_v1/provenance/normalisation/`.

## FULL-KC-001-FULL-PREITEM — generator ontology decision on all exact cells

- **Date:** 2026-08-29
- **Research question:** RQ1/RQ2: which outcome-free ontology is a parsimonious,
  reusable, structurally distinguishable generator truth on the full exact
  grammar inventory?
- **Motivation:** The medium structural pilot needed confirmation after the
  full inventory introduced nine additional modal identities and WH structure.
- **Hypothesis:** The reusable-operation hybrid will remain full-rank; an
  explicit perfect-progressive-chain interaction will be measurable only as a
  nested skill and exact-cell KCs will remain non-reusable.
- **Methodology:** Projected one structural pseudo-item per fixed GrammarCell
  onto the hybrid, hybrid-plus-chain, non-reference feature-value control, and
  exact-cell diagnostic. Compared rank, activation rows, support, isolation,
  equivalence, pair geometry, and reuse. No item text, learner outcome,
  simulator state, selector, or KT metric was accepted.
- **Manipulated variable:** Generator-KC construction principle.
- **Held fixed:** All 75 exact cells, schema, declarations, deterministic
  activation projection, and support/rank audit implementation.
- **Exact commands:**

  ```bash
  .venv/bin/python scripts/build_dataset.py --stage construct-k-star
  .venv/bin/python scripts/investigate_generator_kcs.py --cells data/grammar_kt_full_v1/grammar/cells.jsonl --items /tmp/grammar_kt_full_v1_structural_items.jsonl --output reports/full_v1_artifacts/kc/generator_alternatives_full_cells_preitem.json
  ```
- **Models/settings:** None; deterministic structural analysis.
- **Seeds:** None.
- **Data:** 75 frozen full-v1 GrammarCells; one declared structural row per
  cell solely for pre-item geometry.
- **Results:** The hybrid has 18 KCs, rank 18, 75 distinct activation rows, no
  identical or near-identical columns, 151/153 two-sided KC-pair contrasts,
  and 17/18 KCs reused across cells. The feature control has 19 full-rank KCs.
  Hybrid-plus-chain has 19 full-rank KCs, but the added chain is supported by
  only the six perfect-progressive cells and is strictly nested inside both
  component KCs. Exact-cell uses 75 KCs and has zero cross-cell reuse. All
  alternatives fail only the two-item support gate because this pre-item audit
  deliberately uses one pseudo-item/cell.
- **Uncertainty/failure analysis:** Full bank acceptance may leave rare cells
  with fewer than two valid items, so final support must be rerun on curated
  items. Rank is a structural diagnostic, not proof of finite-sample or human
  cognitive identifiability. The single non-subject-WH cell is nested within
  present and negation in this inventory.
- **Interpretation:** The chain adds a nonseparable latent state without an
  independent linguistic operation or item contrast. The feature control adds
  an atomic perfect-progressive value where the hybrid gives a compositional
  account. Exact-cell KCs violate reuse.
- **Methodological consequence:** Freeze the 18-KC hybrid before item calls;
  exclude the chain on linguistic parsimony, not outcome fit. Reopen K* only if
  the final measurement audit exposes a genuine structural failure, never
  because of learner-response performance.
- **Artifact paths:** `data/grammar_kt_full_v1/kcs.jsonl`,
  `data/grammar_kt_full_v1/provenance/kcs/construction.json`, and
  `reports/full_v1_artifacts/kc/generator_alternatives_full_cells_preitem.json`.
