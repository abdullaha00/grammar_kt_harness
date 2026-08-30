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
  canonical inventory. A publication-boundary audit found that the first
  public checkpoints still contained model-written `note` fields. Immutable
  private parsed results were retained unchanged; the public checkpoints were
  deterministically regenerated with a fixed redaction marker and technical
  error types only. Exact private input, prompt, model, stage, and structured
  mapping equality are now required on resume. This packaging correction made
  no new model call and changed no result, cell, relation, or rate.
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

## FULL-ITEM-001 — full-inventory N=3 generation and independent validation

- **Date:** 2026-08-29
- **Research question:** RQ1: does the retained best-of-three item method
  provide valid measurement opportunities for every full-v1 GrammarCell, and
  which validation criterion limits coverage at this scale?
- **Motivation:** The medium campaign suggested that most coverage gains occur
  by the third independent generation, but that result did not cover the
  75-cell full inventory or its expanded modal/aspect combinations.
- **Hypothesis:** Three independent candidates per cell will recover most of
  the inventory; any remaining gap will be dominated by response determinacy
  rather than target fidelity or grammaticality.
- **Methodology:** Froze all 225 generation calls before execution, made three
  independent calls for each of the 75 fixed cells, applied deterministic slot
  and answer checks, and sent every structurally valid candidate to the
  independently configured validator under a blinded identifier. Original
  candidate and judgment checkpoints are immutable; no repair, rescue,
  learner outcome, Q-matrix, or downstream score entered this run.
- **Manipulated variable:** Independent candidate draw (positions 1--3) within
  a fixed GrammarCell.
- **Held fixed:** Frozen cells and K* ordering gate, generation prompt,
  rulebook, item format, lexical policy, validation prompt/criteria, models,
  and reasoning efforts.
- **Exact commands:**

  ```bash
  .venv/bin/python scripts/build_dataset.py --stage generate-items --workers 8 --max-attempts 2
  .venv/bin/python scripts/build_dataset.py --stage validate-items --workers 8 --max-attempts 2
  ```
- **Models/settings:** Generation `gpt-5.6-sol`/medium; independent validation
  `gpt-5.6-terra`/medium; eight workers; at most two technical attempts;
  provider sampling seed unavailable.
- **Seeds:** No provider seed available. Candidate positions and identifiers
  were frozen deterministically.
- **Data:** All 75 full-v1 GrammarCells; 225 candidates and 225 terminal
  judgments at code revision `d7f067b411be167d408b80a6912c257320eda925`.
- **Results:** Generation recovered 225/225 valid payloads on their first
  technical attempt. Validation accepted 102/225 (45.33%), covering 57/75
  cells: 25 cells have one accepted candidate, 19 have two, 13 have three, and
  18 have none. Two candidates failed deterministic answer packaging; 223 were
  model-judged. Fidelity, grammaticality, non-target simplicity, and
  world-knowledge criteria passed 223/223. Determinacy passed only 106/223 and
  failed 117; the next largest failure count was pedagogical suitability at
  22. Naturalness, leakage, and extraneous-grammar failures numbered six, one,
  and three. Aggregate recorded call runtimes were 2,855.50 generation seconds
  and 3,451.42 validation seconds; three judge calls needed a second technical
  attempt.
- **Uncertainty/failure analysis:** The validator is automatic rather than
  human gold, and its strict determinacy interpretation rejects plausible
  exercises where the context leaves several modal or aspectual formulations
  open. The zero-coverage cohort is concentrated in modal identity,
  progressive/perfect-progressive aspect, and positive/negative imperatives.
  Naming only a lexical predicate generally does not select those forms.
- **Interpretation:** N=3 is insufficient for the complete full-v1 bank under
  the unchanged learner-facing prompt. The result confirms a systematic
  measurement-design failure, not a generator-KC failure: candidates almost
  always realize the requested target, but their visible prompts often do not
  make that target the uniquely licensed learner response.
- **Methodological consequence:** Curation remains blocked. Preserve all
  original output, run the separately frozen unchanged-prompt rescue below,
  and evaluate an explicit-construction instruction only for any still-
  uncovered determinacy-dominated cohort.
- **Artifact paths:** `data/grammar_kt_full_v1/provenance/items/` and private
  raw evidence under `runs/grammar_kt_full_v1_private/items/`.

## FULL-ITEM-002-PREREG — conditional full-bank item rescue

- **Date frozen:** 2026-08-29, before any rescue model call.
- **Research question:** Is the 18-cell N=3 gap principally finite candidate
  sampling, or does it require a small, explicit change to the learner-facing
  measurement instruction?
- **Hypothesis:** Two further unchanged-prompt independent draws will recover
  only part of the gap because the dominant ambiguity is construction-specific.
  For a residual determinacy-dominated cohort, allowing the instruction to name
  the complete target construction will materially improve cell coverage
  without reducing fidelity, grammaticality, or leakage quality.
- **Frozen methodology:** First, generate and independently validate exactly
  two additional unchanged-prompt candidates for all 18 cells with zero N=3
  acceptance. Freeze the complete cohort before the first call and do not stop
  a cell after an early acceptance. If gaps remain, freeze one second cohort
  before its first call: cells must still have zero acceptance and their prior
  evidence must show determinacy as the dominant recurring rejection reason.
  For that cohort generate exactly two candidates with the historical
  `determinacy_explicit_construction_prompt.txt`; this prompt may name the
  construction but may not reveal an inflected response, auxiliary chain, or
  accepted answer. Keep the validator and every other resource unchanged.
- **Manipulated variables:** Fresh candidate draw; then, only in the separately
  labelled second cohort, permission to name the target construction in the
  learner-facing instruction.
- **Held fixed:** GrammarCells, K*, original 225 rows, item format, rulebook,
  lexical policy, model/effort, validator, criteria, technical retry policy,
  and absence of learner/Q/KT evidence.
- **Primary outcomes:** Newly covered cells and accepted candidates by campaign;
  determinacy pass rate. Secondary safeguards are all other validation
  criteria, exact duplicate prompts, and deterministic packaging failures.
- **Decision rule:** Unchanged rescue and prompt-intervention results remain
  separately reported regardless of direction. Full-bank curation may proceed
  only if every cell has at least one independently accepted candidate. Any
  remaining gap after the frozen intervention is retained as a negative result
  and requires a new declared decision; it is never silently repaired.
- **Planned artifacts:** Immutable campaign plans, generation calls/candidates,
  validation calls/judgments, audits, and private raw evidence under the
  full-v1 item provenance directories.

### Execution result (post-freeze)

- **Exact commands:**

  ```bash
  .venv/bin/python scripts/build_dataset.py --stage rescue-items --workers 8 --max-attempts 2
  .venv/bin/python scripts/build_dataset.py --stage intervene-items --workers 8 --max-attempts 2
  ```
- **Models/settings:** Generation `gpt-5.6-sol`/medium and unchanged independent
  validation `gpt-5.6-terra`/medium; eight workers; at most two technical
  attempts; provider sampling seed unavailable. All 54 generation payloads
  completed, and only one of the 50 validator calls that passed deterministic
  prechecks required a second technical attempt.
- **Results:** The unchanged campaign generated 36/36 candidates, accepted
  10/36 (27.8%), and added nine cells, so coverage rose 57→66/75. Three
  candidates failed deterministic packaging checks; among 33 judged candidates,
  determinacy passed 10 and failed 23. The explicit-construction campaign then
  generated 18/18 candidates, accepted 9/18 (50.0%), and added six cells, so
  coverage rose 66→72/75. One candidate failed deterministic checks; among 17
  judged candidates, determinacy passed nine and failed eight. Aggregate model-
  call runtimes were 439.85 and 487.54 seconds for unchanged generation and
  validation, then 220.95 and 234.87 seconds for intervention generation and
  validation.
- **Failure analysis:** Fresh sampling alone recovered only half the original
  18-cell gap and retained the same determinacy bottleneck. Explicitly naming
  the requested construction doubled candidate acceptance while retaining
  perfect judged fidelity, grammaticality, naturalness, non-target simplicity,
  extraneous-grammar, and world-knowledge results. It did not guarantee
  determinacy: three cells remained uncovered. In one strongest residual
  candidate per cell, every required criterion except determinacy passed and
  the judge identified a finite omitted equivalent rather than an ambiguous
  grammatical target.
- **Interpretation:** The two campaigns distinguish sampling error from a
  systematic learner-facing measurement problem. Explicit construction is a
  useful narrow intervention for determinacy-dominated cells, but answer-package
  completeness remains a separate audit dimension.
- **Methodological consequence:** Do not make further generation calls. Preserve
  both campaigns as labelled evidence and apply only the separately
  preregistered, append-only correction in `FULL-ITEM-003-PREREG` before
  curation.
- **Artifacts:**
  `data/grammar_kt_full_v1/provenance/items/campaigns/unchanged_rescue/` and
  `data/grammar_kt_full_v1/provenance/items/campaigns/determinacy_intervention/`.

## FULL-ITEM-003-PREREG — frozen append-only answer-package correction

- **Date frozen:** 2026-08-29, after both declared generation campaigns and
  before any correction revalidation call.
- **Research question:** Can the final three zero-coverage cells be measured by
  already generated, target-faithful candidates once narrowly omitted natural
  equivalents are represented in the accepted-answer package?
- **Motivation:** The unchanged rescue added 10 accepted candidates and nine
  cells, taking coverage from 57/75 to 66/75. The separately labelled explicit-
  construction intervention added nine accepted candidates and six cells,
  taking coverage to 72/75. For one candidate in each remaining cell, the
  independent validator's only failed criterion named a finite equivalent form
  absent from `accepted_answers`; the prompt, target, grammar, naturalness,
  pedagogy, simplicity, leakage, extraneous-grammar, and world-knowledge
  criteria otherwise passed.
- **Hypothesis:** Appending only the validator-named equivalent forms will make
  all three copied packages determinate under unchanged independent validation,
  without modifying learner-facing prompts or target answers.
- **Frozen corrections:** Preserve every raw candidate and original judgment.
  Create provenance-linked copied candidates with new stable IDs and exactly
  these append-only changes:
  - `determinacy_intervention_gc_019f7fb10012b606_01`: append
    `The children mustn't enter the kitchen.`;
  - `determinacy_intervention_gc_04a854582c08aa84_02`: append
    `Don't touch it.`, `Do not touch it.`, `Don't touch that wall.`, and
    `Do not touch that wall.`;
  - `determinacy_intervention_gc_bb4f472f992ab76b_01`: append
    `Turn the light off.`.
- **Manipulated variable:** Accepted-answer enumeration in three copied item
  packages.
- **Held fixed:** GrammarCell, K*, learner-facing prompt, target answer, item
  type, all existing accepted answers, generation provenance, validator prompt,
  criteria, validator model/effort, and retry policy. No learner, Q-matrix, KC-
  discovery, or KT evidence is permitted.
- **Primary outcome:** Independent acceptance of each corrected copy and final
  cell coverage. All validation criteria remain safeguards.
- **Decision rule:** Curation may use a corrected copy only if it passes the
  unchanged independent validator. A failed correction remains a negative
  result; no further answer, prompt, or target repair is allowed without a new
  declared decision. The correction plan and before-state hashes must be
  verified on every run, and raw evidence must remain immutable.
- **Planned exact command:**

  ```bash
  .venv/bin/python scripts/build_dataset.py --stage correct-items --workers 3 --max-attempts 2
  ```
- **Planned artifacts:** Frozen correction declaration, plan, corrected copied
  candidates, independent judgments, audit, and private raw validation evidence
  under `data/grammar_kt_full_v1/provenance/items/packaging_corrections/` and
  `runs/grammar_kt_full_v1_private/items/packaging_corrections/`.

### Execution result (post-freeze)

- **Exact command:**

  ```bash
  .venv/bin/python scripts/build_dataset.py --stage correct-items --workers 3 --max-attempts 2
  ```
- **Models/settings:** Independent validation `gpt-5.6-terra`/medium; three
  workers; two maximum technical attempts. All three calls completed on their
  first technical attempt; aggregate recorded call runtime was 34.37 seconds.
- **Results:** One of three copied packages passed all criteria. Adding
  `mustn't` repaired `gc_019f7fb10012b606`, raising bank coverage 72→73/75.
  The negative and positive imperative copies again failed only determinacy.
  For the negative imperative, the judge identified further valid polite and
  referential commands (`Please don't touch the wall`, `Don't touch the paint`).
  For the positive imperative, it identified polite variants before or after
  the command. All other 24 criterion decisions across the three copied items
  passed.
- **Negative result:** A finite answer-list expansion does not repair open full-
  sentence imperative production: after the exact validator-named equivalents
  were appended, another independently valid set remained. This is evidence of
  a task-format/response-space problem, not a missing finite package entry.
- **Methodological consequence:** Freeze this result and do not append another
  answer list. Curation remains blocked for the two imperative cells. Compare a
  constrained grammar-production format against exclusion/nonmeasurement, then
  preregister any final format intervention before new calls.
- **Artifacts:**
  `data/grammar_kt_full_v1/provenance/items/packaging_corrections/`; plan,
  corrected-candidate, and judgment file SHA-256 values are respectively
  `90a330d10fb70fdc975b07c7c2300cea5368c26c87cff9ecce5f9b1900ae4f31`,
  `944e24e9814d3a931da4e714ac7c26874a7d33132593b455fef907cbe863287a`,
  and `57c5bcc47d9f5219b042fc5925a945960127d36c52a9110ab5ad94da03d34e0d`.

## FULL-ITEM-004-PREREG — cue-bounded imperative production

- **Date frozen:** 2026-08-29, after the negative `FULL-ITEM-003` result and
  before any new generation or validation call.
- **Research question:** Can the two structurally necessary imperative cells be
  measured by narrowing the response space while retaining production of
  imperative word order and negative DO-support?
- **Motivation:** Seven independently generated open-production candidates per
  cell yielded zero accepted imperative items. The strongest candidate in each
  cell and its append-only copy passed every criterion except determinacy; the
  second judgment produced new valid polite/referential variants. This rules
  out another finite answer-list expansion. Excluding the cells would leave
  `gkc_imperative` with zero item support: the positive cell is imperative-only,
  the negative cell is imperative+negation, and declarative negatives provide
  the complementary negation-only measurement contrast.
- **Hypothesis:** An all-and-only unordered-cue contract will close the lexical
  and politeness response space. At least one of two independently generated
  candidates per cell will pass unchanged validation, yielding at least two
  imperative items and preserving the A-only/A+B/B-only Q* contrast.
- **Frozen methodology:** Freeze exactly two independent generation calls for
  each residual imperative cell before execution. Retain the existing
  `controlled_production` item format, common transparent model-selected
  lexical material, generation model/effort, rulebook, and independent
  validator. The separately labelled prompt variant must:
  - name positive or ordinary uncontracted negative imperative as appropriate;
  - show lexical chunks in deliberately non-target order;
  - require every chunk exactly once and forbid additions, omissions,
    substitutions, politeness markers, vocatives, pronouns, and adverbs;
  - place final punctuation outside the response slot and require initial
    capitalization;
  - for negative items, omit `do` and `not` from the cues and allow only the
    function words required for ordinary uncontracted DO-support.
- **Manipulated variable:** A cue-bounded response-space instruction applied
  only to the two residual imperative cells.
- **Held fixed:** GrammarCells, K*, all 282 prior candidate/correction rows and
  judgments, target item format, original prompts/evidence, generation backend,
  N=2 cohort size, validation prompt/criteria/backend, technical retries, and
  absence of learner/Q/K-hat/KT evidence.
- **Primary outcome:** Independently accepted candidates and newly covered
  imperative cells. Determinacy is the focal criterion; all eight other
  required criteria remain safeguards.
- **Decision rule:** Success requires at least one accepted candidate in each
  cell and at least two accepted imperative candidates overall. No post-call
  repair, answer expansion, early stopping, multiple choice, or further prompt
  campaign is allowed. On success, curate up to two items/cell and run the
  already frozen Q* gate; on failure, retain the negative result and explicitly
  rescope/version the baseline rather than changing K* silently.
- **Planned exact command:**

  ```bash
  .venv/bin/python scripts/build_dataset.py --stage constrain-imperatives --workers 4 --max-attempts 2
  ```
- **Planned artifacts:** Immutable plan, four calls/candidates, unchanged
  independent judgments, audit, coverage effect, and private raw evidence under
  a separately labelled full-v1 imperative-constraint campaign.

### Execution result (post-freeze)

- **Date executed:** 2026-08-30.
- **Exact commands:**

  ```bash
  .venv/bin/python scripts/build_dataset.py --stage constrain-imperatives --workers 4 --max-attempts 2
  .venv/bin/python scripts/build_dataset.py --stage curate-items
  ```
- **Models/settings:** Generation `gpt-5.6-sol`/medium and independent
  validation `gpt-5.6-terra`/medium; four workers; two maximum technical
  attempts. All eight calls completed on their first technical attempt.
  Aggregate recorded runtimes were 50.82 seconds for generation and 42.25
  seconds for validation.
- **Results:** All 4/4 cue-bounded candidates passed all nine required
  validation criteria, with two accepted items in each imperative cell. The
  decision rule passed, coverage rose 73→75/75, and no repair or early stopping
  occurred. Negative items require learners to supply uncontracted `Do not`;
  positive items retain base-verb imperative ordering. The resulting fixed
  max-two bank contains 113 unique-prompt items over all 75 cells: 37 cells have
  one item and 38 have two. The max-one counterfactual has 75 items; up-to-three
  adds only 13 items (126 total), no new cell coverage, and proportionally less
  lexical-type gain.
- **Interpretation:** The original open-production failure was a response-space
  problem. A narrow all-and-only cue contract resolved it without changing the
  GrammarCell, K*, target item format, validator, or downstream evidence. This
  format occurs only for imperative cells and is therefore a declared
  measurement-format confound/limitation.
- **Methodological consequence:** Freeze the 113-item max-two bank. It adds 38
  structurally identical cell variants for lexical/contextual diversity while
  avoiding the weak marginal value of a third variant. Proceed to semantic
  regimes and the preregistered Q* measurement gate; make no further item calls.
- **Artifacts:** `data/grammar_kt_full_v1/items/items.jsonl` and
  `data/grammar_kt_full_v1/provenance/items/`, including the separately labelled
  `campaigns/cue_bounded_imperative/` evidence.

## FULL-REGIME-Q-001-PREREG — semantic regimes and pre-simulation Q* gate

- **Date frozen:** 2026-08-29, before final-item regime assignment and Q*
  construction.
- **Research question:** Does the fixed full bank support all declared generator
  KCs and meaningful structural grammar holdouts without activation-equivalent
  or rank-deficient Q* columns?
- **Hypothesis:** The structural declaration will retain 54 `seen`, 15
  pairwise-seen/full-tuple-unseen `unseen_combination`, and six
  `unseen_value` cells after item curation. The max-two bank will preserve the
  18-KC full-rank geometry seen in the pre-item audit and give every KC at least
  two items.
- **Frozen methodology:** Apply
  `modules/simulation/grammar_regimes_full_v1.yaml` to the complete fixed cell
  and item inventories. The unseen-value search may withhold one schema value
  only when four to eight cells use it, no generator KC occurs solely in that
  cohort, and all KCs retain seen support. Select 15 exact unseen combinations
  only when every individual value and every lower-order dimension pair remains
  seen. Derive every Q* edge deterministically from the already frozen K*
  activation declarations; learner data, oracle truth, K-hat, and KT results
  are prohibited inputs.
- **Manipulated variable:** None; this is the mandatory structural quality gate
  on the fixed bank.
- **Held fixed:** 75 canonical cells, 18 declared generator KCs, curated item
  bank, regime design, activation rules, thresholds, and canonical order.
- **Required PASS conditions:** Every canonical cell measured; every item has at
  least one active KC; every K* has at least two items; Q* columns unique; and
  Q* has full column rank. Near-equivalent columns, pairs without two-sided
  contrasts, rare KCs, isolating opportunities, items/KC, cells/KC, KCs/item,
  and regime support remain mandatory reported diagnostics even when they are
  not hard rejection criteria.
- **Decision rule:** No learner simulation may proceed on a failed gate. If a
  weakness is modestly fixable with natural targeted measurement, preregister
  that intervention; otherwise retain and document it. Do not change K* or
  items in response to simulated outcomes.
- **Planned exact commands:**

  ```bash
  .venv/bin/python scripts/design_grammar_regimes.py --schema modules/grammar/canonical/schema.yaml --cells data/grammar_kt_full_v1/grammar/cells.jsonl --kcs data/grammar_kt_full_v1/kcs.jsonl --items data/grammar_kt_full_v1/items/items.jsonl --design modules/simulation/grammar_regimes_full_v1.yaml --assignments-output data/grammar_kt_full_v1/grammar/regime_assignments.jsonl --audit-output data/grammar_kt_full_v1/provenance/grammar_regimes/audit.json
  .venv/bin/python scripts/build_true_q_matrix.py --cells data/grammar_kt_full_v1/grammar/cells.jsonl --items data/grammar_kt_full_v1/items/items.jsonl --kcs data/grammar_kt_full_v1/kcs.jsonl --design modules/kcs/generator/design.yaml --regimes data/grammar_kt_full_v1/grammar/regime_assignments.jsonl --dense-q-matrix data/grammar_kt_full_v1/q_matrix.csv --sparse-q-matrix data/grammar_kt_full_v1/oracle/q_matrix_sparse.jsonl --audit data/grammar_kt_full_v1/provenance/measurement/audit.json --manifest data/grammar_kt_full_v1/provenance/measurement/manifest.json
  ```

## FULL-REGIME-Q-001 — semantic regimes and pre-simulation Q* gate

- **Date executed:** 2026-08-30.
- **Methodology and held-fixed variables:** Exactly the preregistered procedure
  above, using the frozen 75 cells, 113 items, 18-KC declaration, semantic
  regime design, and deterministic activation projection. No learner events,
  discovered KCs, answers, item text, or holdout outcomes were read.
- **Results:** PASS. The assignment contains 54 `seen`, 15
  `unseen_combination`, and six `unseen_value` cells. All 15 unseen
  combinations are constituent-seen and pairwise-seen while their complete
  tuples are absent from seen grammar. Perfect-progressive aspect is the sole
  unseen value. Every generator KC remains represented in seen grammar.
  All 75 cells and 113 items are measured; Q* contains 269 edges, density
  0.1323, and rank 18/18. Every item has at least one active KC and every KC has
  at least two items. There are no identical or Jaccard>=.90 near-identical Q
  columns and no repeated canonical-cell activation rows.
- **Support and limitations:** Items/KC range from 2 to 49 and cells/KC from 1
  to 32. Seven KCs fall below the descriptive six-item rarity threshold;
  `gkc_non_subject_wh_question` has the minimum support (two items from its one
  canonical cell), followed by imperative (four items from two cells). Six
  composition KCs have no single-KC item, but Q* remains full rank. Of 153 KC
  pairs, 46 have A-only, B-only, and A+B evidence, 105 have two-sided evidence
  without co-occurrence, and two are nested: non-subject WH is contained within
  finite-present and negation in the only licensed canonical cell. Adding
  surface variants cannot alter those two cell-level contrasts; fixing them
  would require inventing new linguistic structures outside the frozen source
  inventory, so they are retained as an explicit limitation rather than an
  unnatural item intervention.
- **Interpretation:** The bank passes the mandatory measurement gate and is
  structurally distinguishable at the declared 18-KC level. Full rank does not
  imply uniform statistical power: rare and nested KCs require explicit
  uncertainty and recovery analysis downstream.
- **Reproducibility:** The dense Q artifact SHA-256 is
  `b6df582478f05976ceb200da6edc2b31fb305da64498e5ddb5f473a9459bf5bf`;
  sparse Q is
  `30b735a7d9698a965701fcf04ee5c831377c4b10e78fc2aba85fc75c953a0937`;
  and semantic Q* is
  `56e1984d7a4d98886429603f30839ea3b3d94fb289190e6d8928193c581e5cdd`.
  The exact construction commands are the two preregistered commands above;
  independent verification used the Q command with `--verify-only`.
- **Artifacts:** `data/grammar_kt_full_v1/grammar/regime_assignments.jsonl`,
  `data/grammar_kt_full_v1/provenance/grammar_regimes/audit.json`,
  `data/grammar_kt_full_v1/q_matrix.csv`,
  `data/grammar_kt_full_v1/oracle/q_matrix_sparse.jsonl`, and
  `data/grammar_kt_full_v1/provenance/measurement/`.

## FULL-SIM-001-PREREG — baseline simulator assumption and schedule audit

- **Date frozen:** 2026-08-29, before the full-v1 simulator pilot or learner
  dataset is generated.
- **Research question:** Which simple explicit response, learning, initial-
  mastery, noise, and acquisition assumptions produce an informative baseline
  without turning the simulator into a fitted model of human learners?
- **Hypothesis:** A weakest-link response rule and outcome-independent learning
  update give the clearest semantics for a required multi-KC item. One
  exhaustive seen-item occurrence followed by Q*-balanced top-up should avoid
  both missing rare-KC practice and excessive repetition of already common
  KCs. A target near 20 opportunities per seen KC should create visible but
  nonsaturated learning under a 0.02 fractional update.
- **Frozen analytical checks:** Compare minimum, product, arithmetic-mean, and
  mean-logit aggregation on monotonicity, permutation invariance, invariance to
  the number of equally mastered active KCs, and noncompensation for mastery
  `[.95,.05]`. Compare opportunity-based all-active updates with correct-only
  and incorrect-only alternatives, retaining the simplest defensible rule
  rather than whichever gives a preferred KT result. No KT model, K-hat,
  response-prediction score, or final learner outcome may enter this choice.
- **Frozen simulation pilot:** On final items/Q*/regimes, run 128 learners with
  targets 12/20/30, rates .01/.02, initial `Beta(2,2)`/`Beta(2,3)`, symmetric
  guess-slip .05/.10/.20, the four aggregators, and the three update rules in
  the script's compact staged design. Acquisition uses seen grammar only; one
  terminal all-bank probe never updates mastery. Select the lowest target that
  passes every gate under the declared baseline aggregation/update/noise
  condition. Repeat seeds `20260830` and `20260831` only if a selected metric is
  within .02 of a declared gate boundary.
- **Primary gates:** Every seen item has at least one acquisition occurrence;
  every seen KC reaches its target; initial seen median response probability
  .25--.60; terminal median .55--.80; median gain .10--.30; no more than 10%
  of terminal seen-KC states exceed .95; acquisition is seen-only; probes do
  not update. If no KC occurs exclusively in unseen-value grammar, the
  corresponding unchanged-state check is explicitly not applicable rather
  than a failure.
- **Provisional baseline condition:** Minimum aggregation;
  all-active opportunity learning at .02; independent learner×KC `Beta(2,2)`;
  fixed synthetic guess/slip .10/.10; no forgetting or item difficulty; one
  exhaustive coverage pass followed by Q*-balanced top-up; keyed occurrence
  order; one non-updating terminal all-bank probe; seed `20260829`; 1,000
  learners. The opportunity target remains provisional until the pilot gate.
- **Schedule negative control:** Five exhaustive passes are rejected as the
  default design before outcomes: with the 54-cell structural regime pilot and
  one item/cell they give only five opportunities to the rare non-subject-WH
  KC but 130 to negation. From mastery .5, 0.02 fractional learning yields
  about .548 after five, .666 after 20, and .964 after 130 opportunities.
- **Planned exact command:**

  ```bash
  .venv/bin/python scripts/investigate_baseline_simulator.py --items data/grammar_kt_full_v1/items/items.jsonl --kcs data/grammar_kt_full_v1/kcs.jsonl --q-matrix data/grammar_kt_full_v1/q_matrix.csv --regimes data/grammar_kt_full_v1/grammar/regime_assignments.jsonl --learners 128 --seed 20260829 --output reports/baseline/artifacts/full_simulator_v1/pilot_seed_20260829.json
  ```
- **Methodological consequence before execution:** Production scheduling now
  constructs one fixed occurrence multiset from items and Q*, gives every seen
  item one occurrence, tops up deficient KCs deterministically, and only then
  learner-key-orders the occurrences. Acquisition response draws are keyed by
  learner, item, and item-local exposure so target extensions preserve aligned
  draws. The final learner dataset remains blocked on item/Q/regime completion
  and this pilot.

## FULL-SIM-001 — baseline simulator assumption and schedule audit

- **Date executed:** 2026-08-30.
- **Exact command:**

  ```bash
  .venv/bin/python scripts/investigate_baseline_simulator.py --items data/grammar_kt_full_v1/items/items.jsonl --kcs data/grammar_kt_full_v1/kcs.jsonl --q-matrix data/grammar_kt_full_v1/q_matrix.csv --regimes data/grammar_kt_full_v1/grammar/regime_assignments.jsonl --learners 128 --seed 20260829 --output reports/baseline/artifacts/full_simulator_v1/pilot_seed_20260829.json
  ```
- **Frozen inputs/settings:** 113 fixed items, 18 generator KCs, 269 Q* edges,
  54/15/6 grammar regimes, 128 learners, seed 20260829, and the compact staged
  grid declared above. Twenty conditions generated 931,584 events in 91.12
  seconds. No K-hat, KT prediction, or KC-recovery evidence was accepted.
- **Analytical result:** Minimum was the only aggregation to satisfy all four
  declared semantic checks. Product failed equal-mastery row-count invariance;
  arithmetic mean and mean-logit failed the weakest-link/noncompensation check.
  Opportunity-based all-active learning remains the lowest-complexity update
  and does not condition learning on the simulated response.
- **Schedule result:** One or two exhaustive passes failed the minimum rare-KC
  opportunity gate. Q-balanced targets 12 and 20 passed; target 30 failed the
  gain and saturation gates. Under the preregistered lowest-passing rule,
  target 12 is selected. It gives 170 acquisition events per learner, covers
  every one of the 84 seen items, and gives each seen KC at least 12
  opportunities (median 12; maximum 84). Item exposure ranges from one to six.
- **Selected-condition metrics:** Initial median seen response probability
  0.3822; terminal 0.5936; median gain 0.1806; terminal seen-KC states above
  .95, 2.21%; acquisition response rate 0.4995; terminal-probe response rate
  0.5860. Acquisition was seen-only and probes were exactly non-updating. The
  unseen-value-only-KC check is not applicable because every K* also has seen
  support.
- **Stability decision:** No stochastic metric lies within .02 of a declared
  gate boundary (the closest is terminal probability, .0436 above its lower
  bound). The minimum-opportunity check is fixed by the deterministic schedule,
  so the preregistered extra-seed condition is not triggered.
- **Methodological consequence:** Freeze minimum aggregation, all-active
  opportunity learning at .02, independent `Beta(2,2)` learner-by-KC initial
  mastery, guess/slip .10/.10, no forgetting or item difficulty, target 12,
  one terminal all-bank probe, seed 20260829, and 1,000 learners. This produces
  283 observable rows per learner (283,000 total) while avoiding saturation.
- **Artifacts:**
  `reports/baseline/artifacts/full_simulator_v1/pilot_seed_20260829.json`;
  condition-grid SHA-256
  `a52288d68539981bdf05899b019470d01b5f049a5e56c624010ee12fcd38f567`.

## FULL-DATASET-FREEZE-001 — immutable full-v1 baseline

- **Date executed:** 2026-08-30, after K*, the item bank, Q*, regimes, and the
  simulator protocol were frozen and committed at `930d43f2`.
- **Research question:** Can the complete Layer-A inputs deterministically
  produce a dataset-neutral observable KT stream while retaining aligned
  simulator truth privately and preventing downstream information leakage?
- **Hypothesis:** The target-12 protocol will produce exactly 283 rows for each
  of 1,000 learners: 170 seen-only acquisition events and 113 non-updating
  all-bank probes. Streaming generation and exact keyed replay will agree.
- **Manipulated variable:** None; this is the one-time production execution of
  the already selected baseline protocol.
- **Held fixed:** 75 GrammarCells, 18 K*, 113 items, 269 Q* edges, 54/15/6
  regimes, target 12, minimum aggregation, all-active rate .02, `Beta(2,2)`,
  guess/slip .10/.10, no forgetting/item difficulty, 1,000 learners, and seed
  20260829.
- **Exact commands:**

  ```bash
  .venv/bin/python scripts/freeze_baseline_dataset.py --dataset-dir data/grammar_kt_full_v1 --pilot reports/baseline/artifacts/full_simulator_v1/pilot_seed_20260829.json
  .venv/bin/python scripts/freeze_baseline_dataset.py --dataset-dir data/grammar_kt_full_v1 --pilot reports/baseline/artifacts/full_simulator_v1/pilot_seed_20260829.json --verify-only
  ```
- **Results:** PASS. The public stream contains 283,000 rows from 1,000
  learners: 170,000 acquisition and 113,000 probe events. Every learner has
  identical structural opportunity counts, every seen item occurs at least
  once, and every seen KC receives at least 12 opportunities. Acquisition has
  84,438 correct responses (49.67%); probes have 65,986 (58.40%). Probe rows do
  not update mastery. Public rows expose only learner, item, sequence, outcome,
  phase, pass index, and grammar regime; K* activations, mastery, probabilities,
  and draws occur only in the private oracle.
- **Verification:** Both the generation command's internal exact replay and a
  separate `--verify-only` invocation passed. The verifier reconstructed
  regimes and Q* from frozen declarations, checked the selected pilot and all
  input hashes, replayed all 283,000 keyed events, linked public/private rows,
  validated mastery transitions and probabilities, and checked all 88 retained
  artifact hashes. The freeze plan predates learner output and records git
  revision `930d43f27d3053a5a5a8046432848c25aadb2f55`.
- **Hashes:** observable gzip
  `9272ca86a647e3b13c9ce52b5381dde215f7ef448e4a19a41a22495fa99ef97f`
  (canonical content
  `9b5eb37cf398132453e2247b70cacf9266ccf9a817fe1230a1812efa0d06cdd9`);
  private oracle gzip
  `956ed53f370d5494d379072954c0821d4098f11e51e2629b33d8ee0b8b844601`
  (canonical content
  `46f5da111ae4f8e411c2fc262644d8a8acb31c8408dd87642e5d725cfaa88a10`);
  artifact-inventory semantic hash
  `78008283ae56bad84199145495ad76c9c4897031f4e9bc0861fbb964b2338387`.
- **Interpretation:** RQ1's construction object now exists at full declared
  scope and is independently replay-verifiable. It is a controlled synthetic
  benchmark, not evidence that K* or simulator parameters describe humans.
- **Methodological consequence:** Layer A is closed. Treat
  `data/grammar_kt_full_v1/` as immutable; all KC misspecification, discovery,
  KT, robustness, and generalisation work must write outside it and may use the
  oracle only for explicitly labelled evaluation.
- **Artifacts:** `data/grammar_kt_full_v1/{README.md,manifest.json,
  interactions.jsonl.gz}`, `data/grammar_kt_full_v1/oracle/learner_truth.jsonl.gz`,
  and `data/grammar_kt_full_v1/provenance/simulation/`.

## FULL-RQ2-001 — preregistered KC granularity and Q-noise study

- **Date frozen/executed:** Plan and all 15 Q-hypothesis projections were
  frozen on 2026-08-30 before the first outcome load; an N=20 development run
  checked execution, then the unchanged plan ran on all 1,000 learners.
- **Research question:** How does observable KT prediction change when the
  supplied K-hat/Q-hat is coarser, finer, or edge-corrupted relative to the
  known generator K*/Q*?
- **Hypotheses:** Moderate merging may remain competitive, but increasing
  structural splitting should dilute histories; 10% Q corruption should hurt,
  with false negatives expected to be most damaging under weakest-link
  generation. No U-shaped curve was assumed.
- **Manipulated variables:** Six outcome-free granularity representations:
  all-merged (1 KC), linguistic-family union merge (6), K* (18), deterministic
  context split-2, split-4, and exact cell (75); plus false-positive,
  false-negative, and mixed Q corruption at a total 27-edge Hamming budget for
  seeds 20260830--20260832. Mixed corruption removes 14 and adds 13 edges.
  Deletions preserve at least one edge/item and one item/KC.
- **Held fixed:** The exact 283,000 full-v1 event rows, acquisition/probe
  schedule, public fields, learner histories, model, seed, and evaluation rows.
  Every representation uses all 170,000 acquisition rows for fitting and the
  same 113,000 terminal non-updating probes for evaluation (event-key SHA-256
  `e6432a583c8bb6b451b9b3bf07e069ad800c95e87b801958610e612907b0250b`).
  No private oracle was read.
- **Model/settings:** Standardized observable history logistic/PFA-like model,
  Beta(1,1) history prior, overall and active-KC prior success rates, active
  opportunity history, KC count/indicators, C=1, max 500 iterations, seed
  20260830. All 15 fits converged. Primary metric is probe log loss; Brier,
  ECE, AUC, and accuracy are secondary. Uncertainty is a 2,000-repeat paired
  percentile bootstrap over whole learners; deltas are candidate minus K*.
  Empirical/BKT sensitivity was explicitly reserved for the robustness study.
- **Exact commands:**

  ```bash
  .venv/bin/python scripts/experiments/rq2_kc_misspecification.py --stage plan
  .venv/bin/python scripts/experiments/rq2_kc_misspecification.py --stage run --learner-limit 20
  .venv/bin/python scripts/experiments/rq2_kc_misspecification.py --stage run
  ```
- **Granularity result:** K* has the lowest all-probe log loss, 0.670627.
  Split-2 costs +0.003165 (95% CI [.002744,.003581]); split-4 +0.005868
  ([.005281,.006473]); linguistic-family coarse +0.008132
  ([.007450,.008779]); all-merged +0.010225 ([.009380,.011029]); exact-cell
  +0.015039 ([.014108,.015990]). Thus this frozen grid is descriptively
  U-shaped, with K* at the minimum and monotone increases away from it on each
  coarser/finer side. It is a discrete asymmetric pattern, not a claim of a
  universal smooth curve. These are predictive consequences in the declared
  world, not evidence that K* is human cognitive truth.
- **Grammar-regime result:** Exact-cell sparsity is especially costly on unseen
  combination (+0.037609, [.033761,.041513]) and unseen value (+0.028627,
  [.025120,.032174]). Split-2, all-merged, and family-coarse unseen-value
  intervals cross zero; those specific contrasts are unresolved. Unseen-value
  comprises six perfect-progressive cells and is not a novel latent-KC test.
- **Q-noise result:** Every 10% corruption replicate has a supported positive
  overall cost. Mean delta log loss is +0.001685 for false positives (seed
  range .001265--.001970), +0.002644 for false negatives
  (.001791--.004004), and +0.002294 for mixed corruption
  (.001757--.002641). False negatives tend to be larger, but three structural
  seeds and the visible range do not support a precise universal ordering.
- **Failure/limitations:** The split children are controlled context buckets,
  not proposed human subskills. Learner bootstrap represents learner sampling,
  not uncertainty over simulator worlds or Q-corruption structures. K* has no
  atomic planted interaction KC, so missing-true-interaction is not applicable;
  union versus added-intersection controls remain a separate experiment.
- **Methodological consequence:** RQ2 has a supported baseline answer: both
  coarsening and refinement can measurably hurt prediction, finer exact-cell
  ontologies generalise particularly poorly, and modest Q errors have smaller
  but reliable costs. The next tests must ask whether observable selection can
  identify K* uniquely and whether these rankings survive alternative learner
  worlds/models.
- **Artifacts/hashes:**
  `reports/full_v1_artifacts/rq2_misspecification_v1/`; plan
  `e1945fb1078e883f2c420c3b8adbee4b0772359facaa4321ba616277ff7ddb6d`,
  projection bundle
  `4b793fc6a44a14b975db41f272abfcc0d9df7c3f8effa6b1109f0711c3885661`,
  final result
  `46230a37cd7e6e5cf64d1f9a41e9ae24c26c07c81c1605c889f2026181842050`.

## FULL-RQ3-001 — observable-only KC discovery and name-free recovery

- **Date frozen/executed:** 2026-08-30. The plan was written before the pilot
  or final selection. An N=120 development cohort exercised the unchanged
  procedure; final evidence uses all 1,000 learners.
- **Research question:** Can canonical item structure and observed learner
  responses recover an appropriate KC representation when generator K*/Q* is
  hidden, and does predictive selection identify the generator ontology
  uniquely?
- **Hypothesis:** Truth-like reusable operations should be reachable and beat
  coarse/fine or spurious controls, but hypotheses with identical activation on
  seen items may remain observationally indistinguishable.
- **Manipulated variable:** An outcome-independent 181-candidate space spanning
  18 atomic features, 18 reusable operations, eight coarse KCs, 54 exact-cell
  KCs, 35 structural splits, 19 supported interactions, and 18 deterministic
  hash distractors. Seven whole policies and a protected-feature forward
  selector were compared. The selector evaluated 22 eligible operation or
  interaction additions.
- **Held fixed:** Full-v1 items/cells, the same 170,000 seen acquisition rows,
  stable learner-disjoint 800/200 fit/validation groups, observable PFA-like
  model, C=.1, complexity penalty .0005/KC, and seed 20260830. Selection could
  read item/cell structure and seen acquisition outcomes only; it skipped all
  113,000 probe outcomes before outcome access and could not read generator
  KCs, Q*, or private learner truth. Truth was loaded only after the frozen
  selection artifact for evaluation.
- **Exact commands:**

  ```bash
  .venv/bin/python scripts/experiments/rq3_kc_discovery.py plan --output experiments/full_v1/rq3_kc_discovery_v1/plan.json
  .venv/bin/python scripts/experiments/rq3_kc_discovery.py select --plan experiments/full_v1/rq3_kc_discovery_v1/plan.json --cohort pilot --output experiments/full_v1/rq3_kc_discovery_v1/pilot_selection.json
  .venv/bin/python scripts/experiments/rq3_kc_discovery.py evaluate --plan experiments/full_v1/rq3_kc_discovery_v1/plan.json --selection experiments/full_v1/rq3_kc_discovery_v1/pilot_selection.json --cohort pilot --output experiments/full_v1/rq3_kc_discovery_v1/pilot_evaluation.json
  .venv/bin/python scripts/experiments/rq3_kc_discovery.py select --plan experiments/full_v1/rq3_kc_discovery_v1/plan.json --cohort final --output experiments/full_v1/rq3_kc_discovery_v1/final_selection.json
  .venv/bin/python scripts/experiments/rq3_kc_discovery.py evaluate --plan experiments/full_v1/rq3_kc_discovery_v1/plan.json --selection experiments/full_v1/rq3_kc_discovery_v1/final_selection.json --cohort final --output experiments/full_v1/rq3_kc_discovery_v1/final_evaluation.json
  ```
- **Selection result:** The automated procedure retained its 18-feature base
  after testing every eligible addition. Atomic features obtain validation log
  loss .679686 and objective .688686; all interactions have nearly identical
  raw loss (.679683) but worse penalized objective (.698183); coarse KCs have
  .685129/.689129; hash distractors .686588/.695588. Atomic features,
  compositional operations, and both automated projections share one exact
  seen-Q signature. Their tiny separately fitted loss difference (4e-9) is
  numerical, not evidence. The pilot selected coarse narrowly, while N=1,000
  selected the atomic/compositional equivalence class.
- **Structural result after selection:** The public compositional policy is a
  candidate-space ceiling and exactly matches all 18 generator activations
  (Jaccard and aligned Q-edge F1 1.0). This proves reachability, not blind
  recovery. Atomic/automated-atomic recover 16/18 exactly, with padded Jaccard
  .970854 and F1 .965385; their two aspect columns fail to compose onto the six
  unseen perfect-progressive cells. Coarse KCs recover five exact plus three
  merges (Jaccard .371913, F1 .750929); exact-cell fine gives Jaccard .084184
  and F1 .186969; the hash negative control recovers zero exact (Jaccard
  .202342, F1 .359259).
- **Predictive result:** On frozen non-updating probes, compositional log loss
  is .669606 and atomic .669979: learner-paired delta +.000374, 95% bootstrap
  CI [.000228,.000517]. Seen loss is identical (.668208); the difference is
  concentrated in unseen values (.676281 versus .680974). Relative to the
  compositional ceiling, coarse costs +.005864, fine +.006657, and hash
  distractors +.013238. Added interactions cost +.000206 with CI
  [-.000069,.000478], so that contrast is inconclusive.
- **Failure analysis:** Seen response evidence cannot distinguish semantic
  rules whose Q columns agree on every seen item. The held-out cells reveal
  that the rules differ, but their outcomes cannot legitimately break the
  selection tie. The N=120 pilot also shows that finite-sample policy choice
  can be unstable. Consequently predictive fit alone is insufficient evidence
  for unique cognitive KC truth in this controlled positive case.
- **Methodological consequence:** RQ3 is answered negatively for unique
  recovery but positively for recovering a high-overlap equivalence class.
  Report all seen-Q-equivalent hypotheses and separate structural reachability
  from selection evidence. RQ4 must retain the atomic/compositional ambiguity
  and quantify cell-level holdout sensitivity.
- **Artifacts/hashes:** `experiments/full_v1/rq3_kc_discovery_v1/`; plan
  SHA-256 `2746b39d46ebdfa47d4f95d52a26946ea90e874b01a13a3f74bcdbcba1a50394`;
  final selection
  `d60ff9898448d68312b7fea346666640fdd75aad7bb6408e64b50b91fb1d22ee`;
  final evaluation
  `52e4ff8cba3932010d54fa3af653d64553d3e042d901ab5ac5f9d308bf12f0cd`.

## FULL-RQ4-001 — linguistic generalisation and exact-item novelty control

- **Date frozen/executed:** 2026-08-30. The six representations, grammar
  cohorts, cell-level estimands, learner bootstrap, and 30-cell item-novelty
  partition were frozen before RQ4 outcome analysis.
- **Research question:** How do reusable, merged, split, exact-cell, and
  interaction-augmented KC hypotheses generalise from seen grammar to
  pairwise-seen/full-tuple-unseen combinations and genuinely unseen aspect
  values? Is the apparent gap merely exact item novelty?
- **Hypotheses:** Reusable K* should transfer better than exact-cell KCs to new
  combinations; RQ3 atomic and compositional projections should remain
  indistinguishable wherever their Q columns agree; same-cell item replacement
  should be a negative control because the baseline simulator has no
  item-memory or item-difficulty variable.
- **Manipulated variable:** Six already frozen representations under one common
  fitting protocol: compositional K* ceiling, RQ3 atomic, family-union coarse,
  structural split-2, exact-cell fine, and compositional plus supported
  conjunctive/intersection candidates. The separate novelty control withholds
  one SHA-ranked item from each of 30 exactly-two-item seen cells and replaces
  its 54 schedule occurrences with the same-cell counterpart.
- **Held fixed:** Full-v1's 1,000 learners, 170,000 seen acquisition events,
  non-updating terminal probes, item/cell/regime declarations, all model
  settings, and seed. Every baseline representation reads the same rows. The
  novelty schedule retains 170 acquisitions/learner and exactly preserves all
  18 K* opportunity counts. No probe outcome enters fitting or selection; no
  learner oracle is read.
- **Primary metrics/statistics:** Event-weighted and cell-macro log loss/Brier,
  full per-cell results, leave-one-cell-out cell-macro sensitivity, and a
  2,000-repeat learner-paired percentile bootstrap for candidate-minus-K* by
  regime (seed 20260830). The 15 combination cells are all pairwise-seen and
  full-tuple-unseen; there is no constituent-only stratum.
- **Exact commands:**

  ```bash
  .venv/bin/python scripts/experiments/rq4_grammar_generalisation.py --stage plan --dataset data/grammar_kt_full_v1 --output experiments/full_v1/rq4_generalisation_v1
  .venv/bin/python scripts/experiments/rq4_grammar_generalisation.py --stage run --dataset data/grammar_kt_full_v1 --output experiments/full_v1/rq4_generalisation_v1
  ```
- **Reference result:** K* event-weighted log loss is .669161 seen, .672036 on
  unseen combinations, and .681181 on unseen values; corresponding cell-macro
  values are .669783, .670637, and .681882. The six-cell unseen-value cohort is
  sensitive to composition: per-cell loss ranges .666512--.691208 and its six
  leave-one-cell-out macro estimates range .680016--.684955.
- **Representation result:** Exact-cell costs +.008209 seen
  ([.007486,.008906]), +.037609 on combinations
  ([.033761,.041513]), and +.028627 on unseen values
  ([.025120,.032174]). Split-2 costs +.002234 seen and +.008806 on
  combinations; family-union coarse costs +.008940 and +.009185, respectively;
  all four intervals exclude zero. Their unseen-value point differences are
  small and intervals cross zero. Compositional plus spurious intersections
  costs +.001415 seen, +.001196 on combinations, and +.006954 on unseen values,
  with all intervals above zero. Thus union/merge and
  intersection/conjunction are not interchangeable perturbations.
- **RQ3 equivalence result:** Atomic and compositional predictions differ by at
  most 1.2e-7 on seen and combination rows. Atomic-minus-compositional on
  unseen values is -.003236 with CI [-.007943,.001272], so it is inconclusive;
  its point direction differs from the RQ3 protocol. Holdout outcomes may expose
  the ambiguity but cannot legitimately select among seen-Q-equivalent rules.
- **Exact-item negative control:** The new stream contains 170,000 acquisition
  and 30,000 probe rows. All 30,000 held-out-item outcomes exactly match their
  paired baseline seen probes (correct rate .5897), because same-Q replacements
  preserve outcome-independent mastery updates and probe response draws are
  keyed to the held-out item. K* loss is .668028 versus .668343 on matched
  baseline rows, compared with .672036 on unseen combinations and .681181 on
  unseen values. Prediction differences reflect the refitted public histories;
  the identical outcomes are the causal negative-control result.
- **Failure/limitations:** Six unseen-value cells all concern
  perfect-progressive composition, not arbitrary novel grammar or a novel
  latent KC. Learner bootstrap does not capture grammar-cell sampling. The
  exact-item control is guaranteed by a simulator with no lexical memory or
  difficulty and says nothing about human transfer between surface variants.
- **Methodological consequence:** RQ4 supports reusable compositional
  representations over exact-cell memorisation for full-tuple recombination,
  while the strongest unseen-value comparison remains limited and cannot break
  the RQ3 equivalence class. Preserve per-cell/leave-one-cell-out evidence and
  do not interpret item novelty beyond the declared negative control.
- **Artifacts/hashes:** `experiments/full_v1/rq4_generalisation_v1/`; plan
  `0f7a2d423f3761f196ddb4c16dd76aa18a3a0eac2ad114c14aa27342f0813515`;
  results `a25f43833e620f40294c350259673dadfaaf3f38356339cd6b4cef42be4ec144`;
  novelty interactions
  `7403ab24b07633ea04304793706f924548630ee8616da7ef4c73fb373a2ad3f8`.

## FULL-MASTERY-001 — oracle-only prerequisite-state recovery

- **Date frozen/executed:** 2026-08-30. Observable predictions were written
  before the private oracle was opened. The learner-paired bootstrap and the
  fixed-BKT analysis are explicitly labelled post-plan and secondary checks;
  neither altered the primary estimand or predictions.
- **Research question:** Do representations with similar response-prediction
  scores recover the frozen simulator's latent state equally well, and does the
  RQ2 predictive ordering agree with recovery of the item state that actually
  governs a response?
- **Hypothesis:** The true K*/Q* projection should best recover the minimum
  pre-response mastery of an item's active generator KCs overall; coarsening
  should blur prerequisites and fine partitions should lose reusable evidence.
- **Manipulated variable:** Five already-frozen RQ2 hypotheses: K*,
  linguistic-family coarse, structural split-2, split-4, and exact-cell. The
  same observable PFA-like fits used their public acquisition histories. A
  fixed BKT (`initial=.35`, `learn=.12`, `guess=.18`, `slip=.10`) was added as
  a secondary deliberately misspecified state model.
- **Held fixed:** All 1,000 learners, 170,000 acquisition rows, 113,000 terminal
  probes, RQ2 projections, fitting settings, seed 20260830, and public/private
  event keys. The primary estimate is the observable response prediction
  inverse-linked through the known baseline guess/slip transformation,
  `(p-.10)/.80`; the oracle target is `aggregated_mastery_before`, the minimum
  mastery of active K*. It is an item prerequisite state, not individual-KC or
  human mastery. No inverse-linked value required clipping.
- **Exact commands:**

  ```bash
  .venv/bin/python scripts/experiments/full_v1_mastery_recovery.py --stage plan
  .venv/bin/python scripts/experiments/full_v1_mastery_recovery.py --stage run
  .venv/bin/python scripts/experiments/full_v1_mastery_recovery_bootstrap.py --stage plan
  .venv/bin/python scripts/experiments/full_v1_mastery_recovery_bootstrap.py --stage run
  .venv/bin/python scripts/experiments/full_v1_bkt_state_recovery.py --stage plan
  .venv/bin/python scripts/experiments/full_v1_bkt_state_recovery.py --stage run
  ```
- **Primary result:** On all 113,000 probes K* gives RMSE .123738, MAE
  .100560, Pearson correlation .569746, and mean estimate-minus-oracle bias
  -.025206. Coarse, split-2, split-4, and exact-cell RMSEs are .146300,
  .132752, .140428, and .163828. The ordering is not identical in every pair,
  but every candidate is worse than K* overall.
- **Paired uncertainty:** A post-plan 2,000-repeat whole-learner bootstrap gives
  candidate-minus-K* RMSE differences +.022562 for coarse (95% interval
  [.021715,.023348]), +.009013 split-2 ([.008596,.009421]), +.016689 split-4
  ([.016130,.017191]), and +.040090 exact-cell ([.039248,.040925]). Thus the
  overall K* advantage is stable to learner resampling.
- **Regime result and negative finding:** K* RMSE is .122352 seen, .130717 on
  unseen combinations, and .120623 on unseen values. Exact-cell is especially
  poor on combinations (.218837) and unseen values (.188047). Coarse is worse
  on seen and combinations, but *better* on the six-cell unseen-value cohort:
  candidate-minus-K* RMSE -.003663, interval [-.005740,-.001507]. Split-2's
  unseen-value RMSE cost is +.001564 ([.000812,.002371]), while its MAE interval
  crosses zero. This local reversal prevents a claim that true granularity is
  uniformly optimal under sparse out-of-regime support.
- **Secondary BKT result:** The exposed terminal fixed-BKT states are evaluated
  against per-KC oracle mastery on 269,000 active-KC probe pairs. RMSE is
  .291195, correlation .355418, and expected absolute ten-bin calibration gap
  .225853. On the 18,000 unique terminal learner-KC states, RMSE is .300804,
  correlation .434973, bias +.094505, and bin gap .240860. This is an expected
  model-generator mismatch: BKT conditions learning on correctness and applies
  full item credit, while the generator updates every active KC by opportunity
  and aggregates responses by the minimum. It demonstrates that a model can
  expose a plausible-looking state whose semantics do not match generator
  mastery.
- **Failure/limitations:** The inverse link uses declared generator guess/slip
  and therefore is oracle-assisted evaluation even though model fitting is
  public-only. Its item-level minimum target is not directly comparable with
  BKT's per-KC target. Bootstrap intervals quantify learner sampling only, and
  the unseen-value reversal concerns six perfect-progressive cells. None of
  these values estimate human mastery.
- **Methodological consequence:** Predictive and item-state recovery evidence
  both favor K* overall, but response prediction alone still does not imply
  correct latent-state semantics or unique cognitive ontology. Report the
  unseen-value coarse reversal and keep model-specific state meanings explicit.
- **Artifacts/hashes:** `reports/full_v1_artifacts/mastery_recovery_v1/`;
  primary plan
  `703005079cfed1f679d75b7e7ac73c70c24fa9dd07a84a14379c397318d567d3`,
  observable predictions
  `9fba28d564f31c1b9ee552f15bf2e23a8c65b3c12817cd30f3e6f6f6fc33df93`,
  primary result
  `3055096d70232dd53b37010f5eb22d59d47c763b7df950b33ecbb0093a2824c6`,
  bootstrap result
  `684bda7d9ae25758f9ad5b56c4328fe9ac5bd5258ddcf1cb59dd4d546277d651`,
  and secondary BKT result
  `b6099901212302c47cbb353848fffbe099ffe2b780918c80bca01155bd96f07e`.

## FULL-ROBUST-001 — compact simulator-sensitivity study

- **Date frozen/executed:** 2026-08-30. The 13 conditions, three seeds,
  representations, primary/secondary models, common-random-number scheme, and
  reversal rules were written before any sensitivity response was generated.
- **Research question:** Which simple simulator assumptions carry the RQ2
  conclusion that K* predicts better than a family merge or structural
  split-2, and which plausible nuisance factors can reverse that ordering?
- **Hypothesis:** K* should remain best under response noise, alternative
  aggregation, learner heterogeneity, mild forgetting, correlated starting
  mastery, and correctness-dependent updating. Unmodelled item difficulty is
  the strongest candidate for rank instability because none of the compared
  observable models contains item identity.
- **Manipulated variables:** Baseline minimum aggregation with guess/slip
  .10/.10; noise .00/.00, .20/.10, .10/.20, and .20/.20; product and arithmetic
  mean aggregation; learner-specific guess/slip in [0,.20]; forgetting .002 per
  acquisition gap; item logit difficulty SD .60; learner learning rate in
  [.005,.035]; an undirected .50 global-versus-independent `Beta(2,2)` starting-
  mastery mixture; and correct-only active-KC updating. Each sensitivity
  changes one assumption except the declared compact noise design.
- **Held fixed:** The full 113-item bank, 18-KC K*, Q*, regimes, target-12
  schedule, 500 learners/world, seeds 20260829--20260831, and K*/family-
  coarse/split-2 projections. Within a seed, keyed initial, learner, item,
  event, and response latents are common across conditions. Events are
  transient; neither frozen baseline interactions nor its private oracle is
  read. Every representation/model receives identical observable rows inside
  a world.
- **Models/settings:** The primary model is the unchanged observable PFA-like
  logistic fit on acquisition and evaluated on all terminal probes (C=1,
  standardized, 500 iterations, seed 20260830). All 117 fits converged.
  Prior-smoothed empirical history and fixed mean/full-credit BKT are secondary
  sensitivities. BKT is prohibited from driving conclusions because its
  response aggregation and correctness-conditioned full-credit update
  deliberately mismatch the generator.
- **Exact commands:**

  ```bash
  .venv/bin/python scripts/experiments/simulator_robustness.py --stage plan
  .venv/bin/python scripts/experiments/simulator_robustness.py --stage run
  ```
- **Scale:** 13 conditions x 3 seeds = 39 transient worlds, each with 500
  learners and 141,500 events; 117 primary fits and 234 secondary evaluations.
  The 500-learner baseline seed exactly matches the corresponding first half of
  the frozen observable stream, and all common-draw hashes match.
- **Baseline result:** Mean candidate-minus-K* primary log loss is +.007924 for
  family-coarse (seed range +.007568--+.008306) and +.003241 for split-2
  (+.003001--+.003575). Corresponding Brier costs are +.003845 and +.001584.
- **Robustness result:** K* beats both candidates in every seed for 12/13
  conditions. Coarse log-loss costs remain positive in all 39 worlds. Split-2
  costs remain positive in 38/39 worlds. Noise-free data amplify the mean K*
  advantage (coarse +.016363; split-2 +.005969); .20/.20 noise attenuates it
  (+.003082; +.001506). Product, compensatory mean, learner noise/rate
  heterogeneity, forgetting, correlated initial mastery, and correct-only
  updates do not change the primary winner.
- **Important exception:** With unmodelled item logit difficulty SD .60,
  split-2 mean cost remains +.004138 but spans -.000413 to +.009955 across
  seeds. It beats K* on seed 20260830 and falls behind coarse on seed 20260831.
  Thus the headline ranking is robust to the other compact assumptions but not
  invariant to item-specific nuisance structure. This motivates measuring or
  modelling item difficulty in any real collection.
- **Secondary-model result:** Empirical and especially BKT rankings vary more;
  fixed BKT often prefers split-2 under its mismatched credit semantics. These
  are retained model-sensitivity results, not evidence against the primary
  conclusion. They reinforce the mastery study's warning that KT model and
  generator state semantics must be aligned.
- **Failure/limitations:** Three structural seeds characterize direction and
  visible range, not a population interval. The correlated condition is an
  undirected marginal-preserving mixture, not a prerequisite model. Only one
  severity per heterogeneity, forgetting, and difficulty assumption is tested;
  no interaction grid was run. The worlds are not human parameter estimates.
- **Methodological consequence:** The RQ2 K* advantage is not an artefact of
  fixed moderate guess/slip, minimum aggregation alone, independent initial
  mastery, homogeneous learning, no forgetting, or opportunity-only updates.
  It is vulnerable to omitted item difficulty, so paper claims must be
  conditional and future learner studies should include crossed item evidence.
- **Artifacts/hashes:** `experiments/full_v1/simulator_robustness_v1/`; plan
  `66403c074fe7dbdfa3bd859225d7998a34524e8a2332e1286adecdc6a77636dc`,
  projection bundle
  `2292ff0a2d99f1d853a02ff651b0f4f3ce539a17112c47200d5f1ecd0814eb62`,
  result
  `f9a01e718588e6fbb69994d111f62bee2384333d94526bdaa456f8806d052d6a`,
  and seed comparison table
  `4c5a8e6044ffb68fe62c0c4cb3a9a052fd4c09705528706ba4a7d2778d4cf866`.

## FULL-COLLECTION-001 — bounded collection-design study

- **Date frozen/executed:** 2026-08-30. Learner-count cohorts, opportunity
  targets, max-item variants, microstudy worlds, anchors, representations,
  seeds, metrics, and interpretation boundaries were materialized in
  `study_plan.json` before results were produced.
- **Research question:** Under the declared synthetic conditions, how do
  learner count, opportunities per seen KC, within-cell replication, and
  A-only/B-only/A+B measurement contrasts affect predictive representation
  selection and structural identifiability?
- **Motivation:** The headline experiments establish representation effects on
  one fixed bank and sample. They do not by themselves distinguish response
  volume from Q-matrix structure or show what the second item per cell adds.
- **Hypotheses:** More learners should stabilize unpenalized predictive
  comparison; more opportunities should improve prediction; a second item per
  cell should improve support but not necessarily Q geometry; repeated A+B
  rows should not distinguish A and B, whereas linguistically valid anchors
  should restore rank and expose a union merge. A planted A+B interaction is a
  positive control and a spurious interaction in the factorized world is a
  negative control.
- **Manipulated variables:** (A) nested learner cohorts N=60, 120, 240, 500,
  and 1,000; (B) acquisition targets 6, 12, and 24 opportunities per seen KC;
  (C) max-one versus max-two curated items per GrammarCell; and (D) all-A+B,
  sparse-anchor, and balanced-anchor two-KC microbanks in factorized and
  planted-interaction worlds at N=100, 300, and 1,000.
- **Held fixed:** Full-v1 inputs and event rows are immutable. Learner cohorts
  are outcome-free hash selections; learner-count selection uses acquisition
  outcomes and skips every probe before outcome access. Opportunity worlds
  keep the 113-item bank, K*, Q*, response/update rules, and 500 learners.
  Max-one/max-two is an outcome-free structural projection. Microstudy designs
  keep 60 acquisition rows plus three terminal probes per learner and common
  seeds 20260829--20260831 within each comparison. No oracle state enters a
  selector.
- **Models/settings:** The unchanged observable PFA-like logistic model is fit
  with C=1, standardized predictors, at most 500 iterations, and deterministic
  seed 20260830. Learner-count selection compares raw validation log loss and a
  predeclared illustrative `log_loss + .0005 * number_of_KCs` criterion. The
  latter changes the estimand and is not treated as recovery truth. All 282
  fits converged.
- **Exact commands:**

  ```bash
  .venv/bin/python scripts/experiments/collection_design.py --stage plan \
    --dataset data/grammar_kt_full_v1 \
    --output experiments/full_v1/collection_design_v1
  .venv/bin/python scripts/experiments/collection_design.py --stage run \
    --dataset data/grammar_kt_full_v1 \
    --output experiments/full_v1/collection_design_v1
  .venv/bin/python -m pytest tests/test_collection_design.py -q
  ```
- **Learner-count result:** Unpenalized validation prediction selects K* in all
  21 cohorts: 5/5 repetitions at each of N=60, 120, 240, and 500, and the one
  full N=1,000 cohort. At N=1,000, candidate-minus-K* log-loss costs are
  +.005242 for family union (95% learner-paired interval
  [.004056,.006489]), +.002567 split-2 ([.001762,.003378]), and +.004878
  exact-cell ([.003741,.006055]). This does not establish an N=60 human sample
  requirement: the effects are properties of this simulator and fixed item
  bank. The fixed KC-count penalty selects K* only 3/21 times and selects the
  family union 18/21 times, showing that complexity penalties encode a
  preference rather than consistently reveal generator truth.
- **Opportunity result:** Mean K* all-bank probe log loss across three seeds is
  .681757, .672104, and .636837 at targets 6, 12, and 24, with realized
  acquisition lengths 106, 170, and 311. Family-union costs grow
  +.005437, +.007885, +.010070; split-2 costs +.002712, +.003027, +.003680;
  exact-cell costs +.007523, +.014301, +.032110. More practice improves
  absolute K* prediction and amplifies the representation contrast. The
  unequal schedule lengths and three targets do not support a formal
  diminishing-return threshold. Exact-cell unseen-combination loss worsens
  (.703218, .709853, .720349) because increasingly confident isolated seen-cell
  histories do not transfer to new tuples.
- **Bank-variant result:** Max-one gives 75 items and max-two gives 113. KC
  support increases from min/median/max 1/5/32 to 2/7.5/49, but both banks
  have 75 distinct Q rows, rank 18, and no identical KC columns. The 38 second
  variants therefore add within-cell replication and context support, not a
  new structural contrast. The simulator has no lexical-memory nuisance, so
  this cannot quantify human lexical diversity.
- **Anchor and interaction result:** With A+B-only items, factorized A/B and
  planted A/B/I Q columns are identical and union, spurious-interaction, and
  missing-interaction representations tie exactly at N=100, 300, and 1,000.
  Sparse and balanced anchors restore rank two in the factorized world and rank
  three in the planted world. At N=1,000, union-minus-true log loss is +.004775
  sparse and +.003194 balanced in the factorized world, and +.009495 sparse
  and +.010952 balanced when the interaction is planted. Thus response volume
  cannot repair structural equivalence, while anchors make a union merge
  detectably wrong.
- **Negative and positive controls:** The spurious-interaction negative
  control is approximately null at N=1,000 (factorized sparse -.000007,
  balanced +.000092). The planted-interaction positive control is weak despite
  full Q rank: omitting I costs only +.000060 under sparse anchors and +.000506
  under balanced anchors at N=1,000; the balanced three-seed range is
  [.000313,.000621], while N=100 crosses zero. Structural full rank is
  necessary here but does not guarantee practically unique predictive
  recovery. Union is explicitly OR support; interaction I is A+B-only
  intersection.
- **Failure/limitations:** Only one synthetic response/update family, compact
  sample sizes, three opportunity seeds, and an artificial two-KC microstudy
  are tested. Cohorts share learners and are not independent replications.
  The illustrative penalty is not calibrated to a generative prior. Result
  JSON converts integer `q_row_multiplicity` keys to strings on reload, so the
  byte SHA below is authoritative; the documented in-memory semantic hash
  requires restoring integer keys. None of the counts transfers directly to
  human learners.
- **Interpretation and methodological consequence:** Collect structural
  contrasts before collecting more repetitions of the same Q row; cross items
  and learners to model item nuisance; treat within-cell variants as support,
  not structural diversity; and report the selection criterion because a KC
  penalty changes the target. Even a full-rank Q may leave a small interaction
  effect predictively difficult to recover, so rank audits must be paired with
  effect-size and uncertainty evidence.
- **Artifacts/hashes:** `experiments/full_v1/collection_design_v1/`; plan byte
  SHA-256
  `5049a7f4cd61579ee68034e33e2cec1b6588eb09efe83490607e464ffb10242d`,
  results byte SHA-256
  `5ef059f18025ec6f5fc88bfeaccfebb536be29fab8ff32767059ebd40f931533`,
  projections
  `25b03ac893ee9a0323e9e713f3ba93fb0686d6a149e31b70cbe2c500b16e8c1b`,
  microstudy design
  `f6a6d1a2133fea3175c4dae9d2dd8cc8c63ce7f3bceea17e16b15e74b36e571e`,
  and runner
  `8e3261702dcda46ee24a9f7408da7948455a5c065a8c7a6ff454c08a319ee9d0`.
  The append-only `integrity_verification.json` records and tests the declared
  integer-key restoration needed to validate the pre-serialization semantic
  digest; `results.json` remains byte-identical.

## MR-AUDIT-KC-001 — full-v1 platform audit and outcome-blind KC stress test

- **Date frozen/executed:** 2026-08-30.
- **Research question:** Does the frozen bank plausibly function as a
  learner-facing platform instrument, and does repeated outcome-blind KC
  construction support one uniquely natural generator ontology?
- **Limitation motivating the experiment:** Full-v1's original validator
  primarily established linguistic instantiation and determinacy for stored
  text. It did not establish learner comprehension, response-space fairness,
  deployability, or psychological uniqueness of K*.
- **Exact intervention:** None to full-v1. A strict 113-item census and a second
  fixed-call learner/teacher/platform-product/measurement audit were applied to
  frozen items. A separate KC audit measured support, isolates, nesting, and
  pedagogical interpretation. Three independent induction calls received
  frozen GrammarCells, support information, and a predicate grammar, but no
  learner outcomes, K*, or Q* labels; proposals were canonicalised by cell
  activation before comparison with K*.
- **Models/settings:** Four-role audit and KC induction used
  `gpt-5.6-terra`, medium reasoning. The role audit made 16 batched calls and
  retained 452 judgments; KC induction made three independent calls. Prompts,
  exact inputs, raw and parsed outputs, settings, and byte hashes are frozen.
  The strict audit and structural analyses are deterministic. No judgment is
  human or expert gold.
- **Primary audit result:** Strict labels are 70 usable, 15 minor repair, 15
  technically valid but pedagogically artificial, 10 material answer-space
  failures, and three rewrite/withhold. Exact cross-audit agreement is 70/113;
  60/113 are usable in both mappings; 53/113 are in the union requiring
  action; 18/113 are in the critical answer-space/withhold union. Live roles
  disagree on 56/113.
- **KC result:** Only 16/113 rows isolate one KC and six KCs lack an isolating
  row. The three inductions yield 17/18/18 unique activation signatures with
  ranks 17/18/17. Nine signatures occur in every run, the union has 30,
  pairwise activation Jaccard is `.400`, `.440`, and `.458`, and 5/4/7
  signatures exactly match K*.
- **Interpretation:** Original validator acceptance, Q full rank, learner
  evidence, and platform validity are different claims. K* remains useful as a
  declared synthetic coordinate system but is not a uniquely recovered human
  ontology. Role disagreements and critical items must remain item-level
  evidence rather than one realism score.
- **Exact reconstruction/verification commands:**

  ```bash
  .venv/bin/python scripts/experiments/analyze_platform_audits.py \
    --json-output /tmp/platform_audit_synthesis.json \
    --report-output /tmp/platform_plausibility_audit.md
  .venv/bin/python -m pytest -q \
    tests/test_measurement_realism_kc_induction.py
  ```
- **Artifacts:** `experiments/measurement_realism/audits/`,
  `experiments/measurement_realism/kc_induction_v1/`,
  `reports/platform_plausibility_audit.md`, and
  `reports/kc_methodology_audit.md`. Frozen KC proposal bundle SHA-256:
  `180b99ffbf54488a88d6d1ceafeb408d40b6be019dfc636ffa3582bdfcec1f46`;
  raw proposals:
  `15fc31a384cee666c7261ebf56ef8c23207bdc20a40e78ab6b09542426f70c5c`.

## MR-MATCHED-BANK-001 — preregistered crossed learner-facing bank

- **Date frozen/executed:** 2026-08-30.
- **Research question:** Can matched educational formats preserve a common
  GrammarCell/Q row while passing answerability, linguistic, measurement, and
  platform-product gates strongly enough to support a platform-plausible
  extension?
- **Pre-outcome design:** Rank feasibility required 18 distinct seen cell-Q
  rows for 18 KCs. The frozen target crossed 18 seen cells with constrained
  cloze, dialogue completion, multiple choice, and sentence transformation,
  with two semantic variants; one unseen-combination and one unseen-value cell
  supplied eight non-updating probe slots. Total target: 38 families/152 slots.
  Cell selection SHA-256:
  `8f8fa56e710982c92426f154482d062cffebfb32d29f19c7fe96f4208a4b479b`.
- **Models/settings:** Generation used `gpt-5.6-sol`, medium reasoning;
  independent solvers and linguistic/measurement/platform critics used
  `gpt-5.6-terra`, medium reasoning. Deterministic checks preceded solver and
  critic gates. The corrected scientific campaign completed 178 calls, 106
  candidates, 712 solver attempts, and 90 role judgments with zero technical
  failures. Two earlier attempts remain explicitly labelled infrastructure
  failures; their outputs were not silently repaired.
- **Result:** The three round funnels were `38→31→12→3`,
  `35→32→12→2`, and `33→26→6→0` from generated family to
  deterministic pass to solver pass to critic pass. Only 5/38 whole families
  (20/152 slots) passed. They cover 4/20 cells, 6/18 KCs, seen-Q rank 3, and
  all-regime rank 4. Of 30 critic-reached candidates, measurement accepted 9,
  linguistic 29, and product 24; 23 decisions were mixed. Dialogue completion
  was the weakest solver format.
- **Conclusion and methodology change:** The preregistered freeze gate failed.
  No learner-facing bank was frozen, the 20 slots are not a partial release,
  and `data/grammar_kt_measurement_v1/` must not be created. This is a retained
  negative result showing that linguistic validity cannot substitute for
  response-space and measurement validity.
- **Exact verification command:**

  ```bash
  .venv/bin/python \
    scripts/experiments/analyze_measurement_realism_bank_failure.py verify
  ```
- **Artifacts/hashes:** Corrected run under
  `experiments/measurement_realism/design/bank_protocol/runs/matched_bank_v0_2_20260830/`;
  call-evidence bundle
  `a8a59bf265ce209994bf2cc244c979729ee5f2abbadf4e1c04f442bdb635d982`;
  failure analysis
  `1761db11853163421cd83cb9b4410f00ec887a2e0f574e1578c474eba203b7c3`.

## MR-CONTROLLED-001 — nuisance, heterogeneity, and structured-error worlds

- **Date frozen/executed:** 2026-08-30. The scenario plan was frozen before
  responses. The final synthesis corrects one generic sign gloss append-only;
  it does not rewrite the frozen aggregate.
- **Research question:** Can omitted measurement nuisance masquerade as KC
  granularity, does an observed nuisance covariate recover the shared
  representation, and what diagnostic information is lost by binary outcomes?
- **Claim boundary:** The preregistered matched bank had failed. This experiment
  therefore uses a content-free 38-family/152-slot structural instrument with
  categorical format labels but no prompt, target, accepted answers, or
  response space. It is a **controlled scenario**, not a platform-valid item
  bank, and carries `release_eligible=false`.
- **Worlds/scale:** Six separate worlds vary no nuisance, format SD `.35`,
  strong-format positive-control SD `.70`, item SD `.50`, item plus format,
  and combined item/format/ability/learning/noise heterogeneity. Seeds are
  `20260829`--`20260831`; each run has 500 learners, 188 acquisition and 152
  non-updating probe events per learner (170,000 rows). Eighteen Q-balanced and
  nine alternative-policy response runs total 4,590,000 rows. Worlds are
  plausible sensitivity magnitudes, not estimates from humans.
- **Models:** A = shared K* without nuisance; B = false format-split KCs; C =
  shared K* plus observed format contrasts; D = C plus an aligned seen-item
  residual basis. Bounded logistic models use learner-disjoint fitting,
  acquisition-only causal histories, train-only standardisation, seen-probe
  primary evaluation, and learner-paired bootstrap intervals conditional on a
  frozen fit/seed. D is an exact-span positive control, not a general item
  model or unseen-item solution.
- **Format result:** Format difference-in-differences
  `(B-A)_strong-(B-A)_zero` has mean `-.031551` (seed range
  `[-.033431,-.029013]`), with all conditional intervals excluding zero.
  Negative means planted format nuisance increases B's relative advantage over
  A. C-B in the strong-format world averages `-.005317`
  (`[-.006034,-.004652]`), again excluding zero in every seed. Mean A/B/C loss
  is `.663597/.638965/.633648`; in the zero-format control A/B is
  `.657219/.664138`.
- **Item/heterogeneity boundaries:** D-C is `-.013099` item-only and
  `-.012609` item-plus-format, with every interval excluding zero, because D
  exactly spans the planted seen-item effect. Item-only B-A is small/mixed
  (`+.001195`, `+.000847`, `-.001328`) with every interval crossing zero.
  Combined-heterogeneous C-B is also mixed and every interval crosses zero;
  explicit format adjustment is not a universal remedy.
- **Structured-error result:** Binary/linked/80%-linked/within-item-shuffled
  mean log loss is `.636359/.635493/.635833/.636987`; failed-KC top-1 is
  `.420781/1.000/.883728/.462525`; secondary terminal evidence RMSE is
  `.228727/.144357/.158804/.165519`. Linked-minus-binary loss deltas are only
  `-.001336`, `-.000897`, and `-.000368`, with the third interval crossing
  zero. Failed KC is sampled post-outcome in proportion to mastery deficit; it
  is not a single causal human error. The shuffled RMSE improvement exposes
  bias in treating that secondary metric alone as diagnostic proof.
- **Exact verification commands:**

  ```bash
  .venv/bin/python scripts/experiments/measurement_realism_worlds.py \
    --stage validate-plan --controlled-scenario \
    --config experiments/measurement_realism/design/controlled_instrument_v1/scenario_config.yaml \
    --output-dir experiments/measurement_realism/worlds/controlled_instrument_v1
  .venv/bin/python -m pytest -q \
    tests/test_controlled_instrument_scenario.py \
    tests/test_measurement_realism_worlds.py
  .venv/bin/python \
    experiments/measurement_realism/worlds/controlled_instrument_v1/synthesis/build_synthesis.py \
    --check
  ```
- **Artifacts/hashes:** Study plan
  `e3d50e10001b7dff8042b002aba04b595bb8d95e496bd66beebae08e4d678667`;
  aggregate results
  `06da0a0c2e297124234ad433caa0fd0d6f7924d5b13b707f4fed8ded9a81bfaf`;
  verified synthesis results
  `55ac72dfdaf739597451e5766edb399690b780bbfa9499474c9142cf919e844a`.

## MR-POLICY-001 — exploratory schedule-conditioned recovery

- **Date frozen/executed:** 2026-08-30. The A--D fit plan was frozen after
  response generation and inspection of descriptive schedule diagnostics; it
  is explicitly post-response exploratory rather than preregistered
  confirmatory evidence.
- **Research question:** Do laboratory, curriculum, mixed-practice, and simple
  adaptive assignment policies generate different observable histories and
  fitted-state recovery under the combined heterogeneous controlled world?
- **Held fixed:** All policies use 188 acquisition events per learner. Lab,
  curriculum, and mixed reorder the same occurrence multiset; because learning
  is unconditional and order-independent, their terminal oracle mastery and
  probe accuracy are identical by construction. Adaptive assignment uses only
  observable cell-level correctness, exposure, spacing, and keyed exploration;
  it changes exposure and terminal state. It reads no latent mastery, future
  outcomes, or planted nuisance.
- **Result:** Item-exposure Gini for lab/curriculum/mixed/adaptive is
  `.162530/.162530/.162530/.080298`; median repetition gap is
  `93.67/31.00/92.00/26.67`. Model-D log loss is
  `.636359/.639779/.636341/.639477`; item-state RMSE is
  `.129724/.139472/.130748/.141659`. Curriculum-minus-lab loss averages
  `+.003420`, mixed-minus-lab `-.000018`, and adaptive-minus-lab `+.003118`.
  The transparent terminal-evidence RMSE is
  `.228727/.229618/.229042/.237280`.
- **Interpretation:** These are history morphology, selection, and model-fit
  results, not educational-policy value. Logged propensities are design
  diagnostics, not a complete off-policy estimator; adaptive differences mix
  selection and changed practice.
- **Exact verification command:**

  ```bash
  .venv/bin/python \
    scripts/experiments/measurement_realism_policy_recovery.py verify
  ```
- **Artifacts/hashes:** Plan
  `5a47ca244c57001ae353e4cc673754cac3df071631347fb79b1853ce3ad0f3e7`;
  results
  `29702c895ae9ba34cd0e1313514b23694572d3ca60b9629923b4713c5340a5c6`.

## MR-DIALOGUE-001 — ecology--precision continuum pilot

- **Date frozen/executed:** 2026-08-30.
- **Research question:** As a controlled grammar opportunity moves from cloze
  toward open dialogue, how do automated naturalness, answer determinacy,
  incidental grammar, response-family size, shortcuts, and KC attribution
  change?
- **Design/models:** Four matched GrammarCell families each instantiate five
  openness levels. Generation used `gpt-5.6-sol`, medium reasoning; critique
  used `gpt-5.6-terra`, medium reasoning. Twenty critic calls yield five
  independent role judgments for each of 20 opportunities (100 judgments).
  Exact prompts, settings, raw/parsed outputs, and byte hashes are frozen.
- **Result:** Cloze receives 17/20 naturalness, 17/20 determinate, and 17/20
  clear-KC judgments, with 1/20 shortcuts and mean plausible-response-family
  lower bound 1.30. Open dialogue receives 20/20 naturalness, 0/20 determinate
  (16 bounded, three materially ambiguous, one N/A), 4/20 clear-KC, 13/20
  shortcuts, and response-family mean 4.55. Open-minus-cloze changes are
  `+1.00` determinacy risk, `+.70` KC-attribution risk, `+3.25` response
  families, `+1.50` incidental grammar, and `+.60` shortcuts, while
  naturalness risk falls `.15`. Dialogue completion is not a universal middle
  point: 14/20 shortcuts and 3/20 clear KC attributions.
- **Interpretation:** The pilot supports an ecological-naturalness versus
  scoring/KC-precision tradeoff under its automated rubric; it does not rank
  task formats universally. It has four families, no learner responses, and no
  human/expert validation. Surface error text was not scaled because the
  release-valid instrument prerequisite failed.
- **Exact verification command:**

  ```bash
  .venv/bin/python \
    scripts/experiments/measurement_realism_dialogue_live.py verify
  ```
- **Artifacts/hashes:** `experiments/measurement_realism/dialogue_pilot_live_v1/`;
  analysis
  `5d2538e7866855782f92fe0c946bfcfb714463ae60f8879f01135f2459e797ef`;
  call bundle
  `eaee2637f978b3a2286647b6a035d5bc6bc0da422c4c3575d72a14ba21c38ccb`;
  package manifest
  `8ad84e3200d4997041bccc92e46da2d46c08645c19fa6da6e78104dd0efa4f8e`.

## MR-RELEASE-001 — extension decision and claim boundary

- **Date:** 2026-08-30.
- **Decision:** **NO_NEW_DATASET_RELEASE**. There is no new dataset release,
  `data/grammar_kt_measurement_v1/` must remain absent, and full-v1 remains the
  immutable reference.
- **Evidence:** The matched learner-facing bank failed its complete-family,
  cell/KC coverage, held-out, rank, solver-answerability, and independent
  measurement gates. The content-free substitute explicitly lacks prompts,
  answers, response spaces, and platform-valid formats, so it is retained only
  as a controlled scenario. Automated item, KC, and dialogue audits cannot
  supply release validity without human/expert evidence.
- **Retained output:** Negative construction evidence, compact controlled-world
  aggregates, policy/error/dialogue analyses, reconstruction commands, reports,
  notebook, and manuscript. No partial bank or synthetic surface-error log is
  promoted.
- **Verification boundary:**

  ```bash
  .venv/bin/python \
    scripts/experiments/verify_measurement_realism_programme.py preflight
  .venv/bin/python \
    scripts/experiments/verify_measurement_realism_programme.py verify
  ```
