# Final full-v1 methodology

This report defines the paper-facing method for `grammar_kt_full_v1`. Exact
commands, seeds, negative results, and artifact hashes are in
`reports/experiment_log.md`; the compact current state is
`reports/research_state.md`. The earlier outcome-selected medium-v1 method is
preserved at `reports/historical/medium_v1/final_methodology.md` and is pilot
evidence only.

## Scientific objects and causal order

The method keeps four objects distinct:

```text
SOURCE / LINGUISTIC REPRESENTATION
EGP descriptors -> canonical GrammarCells

SYNTHETIC GENERATOR TRUTH
declared K* -> deterministic Q*

OBSERVABLE DATA
fixed learner-facing items + response events

EXPERIMENTAL HYPOTHESES
K_hat + Q_hat supplied to or discovered by KT experiments
```

A GrammarCell says which linguistic construction an item instantiates. K* is
the latent skill inventory possessed by learners in one declared synthetic
world. K-hat is an experimental representation. Consequently:

```text
GrammarCell != K* != K_hat
```

K* and the item bank are fixed before learner simulation. Learner outcomes,
KT performance, discovered KCs, and holdout results cannot influence them.
After simulation, Layer-B experiments may perturb or hide K*/Q*, but they may
not mutate the frozen dataset.

## Layer A: dataset construction

### 1. Typed source boundary and linguistic scope

The consult-only source is a 1,222-record parsed English Grammar Profile (EGP)
snapshot with SHA-256
`e38c4f959f188150dae7b88f21e35d77828048772e222191818dc0c2488486cd`.
Every row is processed; there is no hand-picked final subset. The declared
empirical scope is single-main-clause English verbal morphosyntax over:

| Dimension | Scalar values entering exact cells |
|---|---|
| tense | present, past, NA |
| aspect | none, progressive, perfect, perfect-progressive |
| voice | active, passive |
| polarity | positive, negative |
| clause | declarative, polar question, subject-WH, non-subject-WH, imperative |
| modal | none and nine declared central modals |

NA is a licensed structural value, not missing evidence. Compatibility rules
are explicit; for example, central modals are tenseless in this schema and
imperatives are tenseless and modal-free. EGP descriptors outside this bounded
subdomain remain auditable `out_of_scope` rows rather than failed grammar.

### 2. Constrained two-phase normalisation

Phase 1 sees typed descriptor fields but no examples. It returns a status,
branches, explicit uncertain dimensions, and Phase-2 eligibility. Phase 2 is
called only for the frozen eligible cohort with a licensed example; it may
narrow named uncertainty but must preserve every Phase-1 branch and every
ineligible exact value. Deterministic validation enforces domains, status
invariants, compatibility rules, branch preservation, and resume-input
identity. No null/list value is silently completed.

The final disposition is 211 complete, 327 partial, nine unresolved, and 675
out of scope. Only complete scalar mappings canonicalise, yielding 75 unique
GrammarCells and 228 source-cell relations. A fresh, balanced 120-row Phase-1
repeat gives 93.3% status agreement, 95.8% eligibility agreement, and 38/38
exact cell-set agreement when both annotations are complete. The 79.0%
partial-branch agreement justifies retaining uncertainty rather than default
completion. These are model annotations, not expert gold.

### 3. Outcome-free generator ontology K*

The generator ontology is declared in
`modules/kcs/generator/{design.yaml,english_kcs.yaml,rationale.md}` and built by
generic activation machinery. The selected 18-KC reusable-operation hybrid
contains:

- present and past finite-form selection;
- shared perfect and progressive dependencies;
- canonical BE-passive and verbal negation;
- imperative, polar-question, and non-subject-WH operations; and
- one reusable KC for each central modal represented in the exact inventory.

Active, positive, declarative, simple, modal-free, and tenseless conditions are
reference conditions, not latent states. Perfect-progressive cells activate
the shared perfect and progressive KCs. A feature-only 19-KC control, a
hybrid-plus-chain 19-KC alternative, and a 75-KC exact-cell upper bound were
audited before item construction. The chain was rejected because its six-cell
column is strictly nested in both component skills and adds no independent
operation; exact cells have no reuse. This choice uses linguistic coherence,
reuse, support geometry, and parsimony—not response prediction.

### 4. Fixed measurement bank

Each GrammarCell receives three independent contextual controlled-production
candidates from `gpt-5.6-sol` at medium reasoning effort. Generation receives
the cell, English rulebook, task-format declaration, and common-language
instruction; it receives no learner, KC, regime, or KT evidence. A
deterministic answer/slot check precedes an independent `gpt-5.6-terra` medium
validator. Acceptance requires target fidelity, grammaticality, naturalness,
pedagogical suitability, determinacy, simple non-target language, no answer
leakage, no extraneous grammar, and no unnecessary world knowledge.

The default campaign produced 225/225 valid candidates and accepted 102
(45.3%), covering 57/75 cells. Determinacy failed for 117/223 model-judged
candidates and is the primary bottleneck. A preregistered two-draw unchanged-
prompt rescue covered nine more cells; a separately labelled explicit-
construction intervention covered six. One append-only accepted-answer
correction covered another. Open full-sentence imperative prompts remained a
negative result, so a final frozen cue-bounded, all-and-only lexical-chunk
format covered the two imperative cells with four accepted candidates. Raw
evidence is immutable and every correction/intervention is separately marked.

Outcome-free max-two curation selects 113 unique-prompt items over all 75
cells: 37 cells have one item and 38 have two. Max-one supplies 75 items; a
third variant would add only 13 items and no cell coverage. The final bank
choice improves contextual replication without confusing surface variants
with new grammatical structures. Automatic validation and cue-bounded
imperatives remain limitations requiring future human review.

### 5. Semantic grammar regimes and deterministic Q*

The fixed structural rule assigns 54 cells to `seen`, 15 to
`unseen_combination`, and six to `unseen_value`. All combination cells contain
only seen constituent values and seen lower-order value pairs, but their full
six-tuples are absent from seen grammar. Perfect-progressive is the withheld
aspect value; all 18 KCs still have seen support, so this is novel linguistic
composition rather than a novel latent-KC test.

For item i and generator KC k:

```text
Q*[i,k] = 1 iff k's frozen activation rule holds for item i's GrammarCell.
```

No response data enter projection. The 113-by-18 Q* has 269 edges, density
.1323, rank 18/18, no identical columns, no Jaccard-at-least-.90 column pairs,
and 75 distinct cell-activation rows. Items per KC range 2--49 and cells per KC
1--32. Forty-six KC pairs have A-only, B-only, and A+B evidence; 105 have
two-sided evidence without co-occurrence. Non-subject WH is structurally nested
inside finite-present and negation in its sole licensed source cell. Full rank
does not remove rare-KC or finite-sample uncertainty.

### 6. Baseline simulator

The simulator consumes only fixed items, K*, Q*, the protocol, and seed. The
scientific assumptions are:

- independent learner-by-KC initial mastery `Beta(2,2)`;
- minimum/weakest-link aggregation across active KCs;
- response probability `0.10 + 0.80 * minimum_mastery`;
- outcome-independent fractional learning
  `m_after = m_before + .02 * (1 - m_before)` for every active KC;
- no forgetting, item difficulty, prerequisites, or transfer;
- a seen-only Q*-balanced acquisition schedule with target 12; and
- one terminal non-updating probe of every item.

Minimum aggregation was selected before learner generation because it alone
passed monotonicity, permutation, equal-mastery row-count invariance, and
weakest-link/noncompensation checks. Product fails row-count invariance;
arithmetic and logit means compensate for a weak prerequisite. Opportunity-
based all-active learning is the simplest rule that does not make simulated
learning depend on the response draw. A 128-learner frozen pilot selected the
lowest schedule target passing prespecified information and saturation gates:
12, not 20 or 30.

Each of 1,000 learners receives 170 acquisition events and 113 probes, producing
283,000 public rows. Public fields are learner ID, item ID, sequence index,
correctness, phase, pass index, and grammar regime. K* activations, mastery
before/after, response probability, and random draw live only in the separate
oracle. Event draws are keyed, probes never update state, and an independent
exact replay verifies all public/private transitions.

### 7. Frozen release

`data/grammar_kt_full_v1/` is immutable. Its manifest records code revision,
commands, configuration and input hashes, deterministic gzip settings, counts,
and a recursive artifact inventory. The public interaction gzip hash is
`9272ca86a647e3b13c9ce52b5381dde215f7ef448e4a19a41a22495fa99ef97f`;
the private oracle hash is
`956ed53f370d5494d379072954c0821d4098f11e51e2629b33d8ee0b8b844601`.
The baseline can be verified without rerunning LLM calls.

## Layer B: downstream experiments

### Common response-prediction protocol

Pure representation comparisons reuse the same 170,000 acquisition rows and
113,000 terminal probes. The primary model is a standardized observable
PFA-like logistic regression using strictly prior successes and opportunities
on active hypothesis KCs, with no item identity, oracle field, latent state, or
probe outcome. Log loss and Brier score are primary; calibration, AUC, and
accuracy are secondary. Paired uncertainty resamples whole learners while
retaining all their events. A fixed BKT and empirical estimator are secondary
sensitivity models because their semantics do not match every generator world.

### RQ2: controlled K*/Q* misspecification

Six deterministic granularities span all-merged, linguistic-family union,
K*, structural split-2, split-4, and exact-cell hypotheses. Separate controls
add false-positive, false-negative, or mixed Q edges at a 27-edge (about 10%)
budget over three structural seeds. Inputs and projections are frozen before
outcome access; the identical event stream is used throughout.

### RQ3: observable-only KC discovery

Discovery receives canonical item structure and seen acquisition outcomes but
cannot read K*, Q*, oracle state, or any probe outcome. Its 181-candidate space
contains atomic features, reusable operations, coarse unions, structural
splits, supported intersections, exact cells, and deterministic hash
distractors. Learner-disjoint fit/validation cohorts score whole policies and a
protected-feature forward selector using validation log loss plus
`.0005 * #KCs`. The selected artifact is frozen before K*/Q* is opened.

Structural evaluation is name-free: optimal activation-column matching reports
exact recovery, Q-edge precision/recall/F1, Jaccard similarity, merges, splits,
missing KCs, and spurious KCs. Predictive equivalence is evaluated separately.
The compositional operation policy is an explicit candidate-space ceiling, not
evidence that the blind selector discovered it.

### RQ4: linguistic generalisation

The same predeclared representations are evaluated by seen,
pairwise-seen/full-tuple-unseen combination, and unseen-value regimes. Results
include event-weighted, cell-macro, per-cell, leave-one-cell-out, and
whole-learner paired estimates. Holdout outcomes cannot select the policy. A
separate negative control withholds one item in 30 two-item seen cells,
replaces every acquisition occurrence with its same-cell counterpart, and
preserves every K* opportunity count. This isolates exact item novelty under a
simulator with no item memory or item difficulty.

### Mastery recovery

Observable predictions for the frozen RQ2 representations are written before
the oracle is opened. Under the known baseline response link, `(p-.10)/.80`
estimates the item-level minimum prerequisite state and is compared with
oracle `aggregated_mastery_before`. This is deliberately not called individual
KC mastery. A secondary fixed-BKT analysis exposes terminal per-KC states and
compares them with oracle KC mastery to demonstrate the consequences of update
and aggregation mismatch.

### Robustness and collection design

The final robustness study uses compact predeclared worlds rather than a broad
hyperparameter search. It varies guess/slip, aggregation, learner noise and
learning-rate heterogeneity, forgetting, item difficulty, correlated initial
mastery, and correctness-conditioned updates over fixed seeds, comparing K*,
coarse, and split-2 representations with PFA primary and empirical/BKT
secondary. The collection-design study separately varies learner count,
opportunities per seen KC, max-one versus max-two measurement, and the balance
of A-only/B-only/A+B anchor items in a planted two-KC control. Exact conditions
and final results are recorded in the experiment ledger. These interventions
separate response volume, repeated contexts, and new Q rows. Selection uses
outcome-free learner cohorts and acquisition outcomes only. A fixed KC-count
penalty is reported as a distinct estimand, not as evidence of ontology truth;
microstudy OR/union and A+B-only intersection rules remain explicitly
different.

## Language boundary and software contract

EGP parsing, the six English dimensions, English KC declarations, and item
prompts are language/resource-specific. Generator-KC records, activation
projection, Q audit, schedule construction, simulation, merge/split/noise
transformations, KT fitting, and evaluation are schema-driven. A non-English-
named toy schema (`mood`, `person`) executes cells -> K* -> Q* -> schedule ->
observable interactions without English branches. This establishes software
abstraction only; no cross-lingual empirical validity is claimed.

## Reconstruction commands

The complete append-only construction sequence is recorded in the experiment
ledger. Deterministic release verification is:

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

The frozen source-dependent LLM outputs need not be regenerated for any
downstream simulator or KT experiment. This is essential: changing learner
assumptions must never trigger item regeneration or redefine K*.
`reports/final_release_manifest.json` supplies the final byte-hash root for the
baseline, paper-facing experiments, reports, notebooks, and ACL build; it is
verified with `scripts/final_release_manifest.py --verify`.

## Claim boundary

The release establishes an auditable controlled benchmark under declared
English and synthetic assumptions. It does not establish that K* is a human
cognitive ontology, that automatic judgments are human pedagogical validation,
that simulator parameters estimate learner behaviour, that synthetic sample
thresholds transfer to a real study, or that one English instantiation provides
cross-lingual evidence.
