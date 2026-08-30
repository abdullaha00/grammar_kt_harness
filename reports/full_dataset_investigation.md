# Full-v1 dataset and research investigation

Date: 2026-08-30

Dataset status: **frozen and replay-verified**

Research scope: controlled English grammar-KT methodology; no claim of human
cognitive truth or classroom validity

This report consolidates the investigation that produced
`data/grammar_kt_full_v1/` and the evidence derived from it. The former
medium-v1 investigation is preserved at
`reports/historical/medium_v1/full_dataset_investigation.md`.

## Executive findings

1. **A complete, auditable baseline exists.** All 1,222 source rows were
   processed. The bounded exact subset yields 75 canonical GrammarCells, 18
   declared generator KCs, 113 fixed items, a full-rank true Q-matrix, and
   283,000 public interactions plus a separate private oracle.
2. **The scientific layers are now clean.** GrammarCells describe linguistic
   constructions; K*/Q* define synthetic generator truth; items/responses are
   observations; K-hat/Q-hat are downstream hypotheses. No response was used to
   define the skills that generated it.
3. **Measurement, not response volume, is the main construction bottleneck.**
   Default N=3 generation produced structurally valid output for every cell,
   but independent validation covered only 57/75 because prompts often failed
   to make marked modal/aspect choices determinate. Declared rescue and narrow
   format interventions—not silent repair—were required.
4. **K* is structurally measurable but not uniformly supported.** Q* has rank
   18/18 and no equal or near-equal columns. Nevertheless, item support ranges
   2--49 and one non-subject-WH construction is nested inside present and
   negative evidence. Full rank is not a substitute for balanced support.
5. **Misspecification matters.** Under one common observable model, K* beats
   every frozen coarser and finer representation. Exact-cell KCs are especially
   poor on unseen grammatical combinations. Ten-percent Q-edge corruption is
   consistently harmful but smaller than severe granularity errors.
6. **Prediction does not identify ontology uniquely.** Observable-only KC
   discovery reaches an atomic/compositional equivalence class with very high
   structural overlap, but the two rules have identical Q on seen items. The
   perfect compositional candidate is reachable but cannot be uniquely selected
   without using held-out evidence or an external prior.
7. **Response prediction and state recovery tell related but distinct stories.**
   K* best recovers the weakest prerequisite state overall, but a coarse model
   reverses on the six unseen-value cells. A deliberately mismatched fixed BKT
   exposes states that correlate only .435 with terminal per-KC oracle mastery.
8. **The main RQ2 ordering is broad, not absolute.** It survives 12/13 compact
   simulator conditions across all three seeds. Unmodelled item difficulty is
   the exception: split-2 beats K* in one seed and changes its ordering relative
   to coarse in another.

## 1. Repository and evidence audit

The repository initially mixed two scientific layers. The historical medium
pipeline built grammar/items, simulated responses in candidate-specific latent
worlds, and used predictive KC selection as part of the apparent dataset
definition. That work remains useful pilot evidence for Phase-2 routing, N=3
generation, validation disagreement, semantic holdouts, and predictive
selection. It is not the full-v1 generator truth.

The active architecture is:

```text
LAYER A
resource -> mappings -> GrammarCells -> K* -> items -> Q* -> measurement gate
         -> fixed simulator -> public responses + private oracle -> frozen data

LAYER B
frozen data -> K_hat/Q_hat perturbation or discovery -> KT/state evaluation
            -> grammar generalisation -> simulator and collection sensitivity
```

Construction lives in `scripts/build_dataset.py`,
`scripts/build_true_q_matrix.py`, `scripts/investigate_baseline_simulator.py`,
and `scripts/freeze_baseline_dataset.py`. Downstream studies live under
`scripts/experiments/`. The baseline runner does not call KC discovery or KT
evaluation.

User-owned pre-existing working files were preserved throughout. Historical
datasets and reports were versioned rather than deleted. Research decisions and
negative results are append-only in `reports/experiment_log.md`.

## 2. Full linguistic inventory

### Scope and census

The verified consult-only EGP snapshot contains 1,222 unique records. Every row
crosses the typed source boundary and is classified against a declared
single-main-clause English verbal-morphosyntax scope. The final outcome is:

| Outcome | Phase 1 | Final after eligible Phase 2 |
|---|---:|---:|
| Complete | 170 | 211 |
| Partial | 375 | 327 |
| Unresolved | 2 | 9 |
| Out of scope | 675 | 675 |

Of 106 eligible Phase-1 partials, 105 had licensed examples. Phase 2 completed
41, retained 57 partial, and made seven unresolved. Branches expanded from 124
to 137; they were never collapsed into an unsupported Cartesian product.

The 211 complete mappings yield 75 unique exact cells and 228 source-cell
relations. Remaining uncertainty concentrates in unspecified polarity,
clause, voice, aspect, and tense. Inspection found no high-yield failure group
that justified adding a seventh dimension or inventing defaults. The schema
therefore remained stable.

### Stability

A fresh category/CEFR-balanced repeat of 120 Phase-1 rows found:

- status agreement 112/120 (93.3%);
- Phase-2 eligibility agreement 115/120 (95.8%);
- exact complete-cell-set agreement 38/38 where both were complete; and
- partial branch-multiset agreement 64/81 (79.0%) where either result branched.

This supports the final exact inventory while demonstrating why partial model
annotations should remain explicit evidence instead of being treated as truth.

## 3. Generator-KC design

Four outcome-free principles were compared before learner generation:

| Ontology | KCs | Reuse | Structural result | Decision |
|---|---:|---|---|---|
| Feature-value | 19 | reusable | full rank | downstream atomic control |
| Reusable operations | 18 | reusable | full rank; 75 distinct rows | **K*** |
| Operations + perfect-progressive chain | 19 | reusable/nested | full rank; chain nested in both components | rejected as redundant |
| Exact cell | 75 | none across cells | identity-like upper bound | downstream fine control |

K* contains finite present/past, shared perfect/progressive, BE-passive,
negation, four clause operations, and modal-specific skills. Reference values
are conditions, not automatic KCs. Seventeen of 18 KCs recur across multiple
cells. The exact-cell ontology was not rejected because it later predicted
poorly; it was rejected as generator truth because it provides no reuse. The
chain was excluded because the cell inventory contains no chain-only evidence
or separate operation.

The declaration is explicit, deterministic, and English-specific. Generic
code receives activation predicates and contains no hidden `if tense == past`
branch. K* is ground truth only inside this synthetic experiment.

## 4. Measurement-bank investigation

### Default generation and validation

The full default campaign made three frozen calls for each of 75 cells:

| Quantity | Result |
|---|---:|
| Planned/completed candidate payloads | 225 / 225 |
| Independent accepts | 102 (45.3%) |
| Cells covered | 57 / 75 |
| Zero-coverage cells | 18 |

Every model-judged candidate passed target fidelity, grammaticality, simple
non-target language, and world-knowledge checks. Determinacy failed 117/223;
pedagogical suitability failed 22, naturalness six, extraneous grammar three,
answer leakage one. This distinguishes a measurement-contract failure from an
inability to form the target construction.

### Declared recovery path

The coverage path remained append-only:

| Campaign | New candidates | Accepted | Newly covered cells | Cumulative coverage |
|---|---:|---:|---:|---:|
| Default N=3 | 225 | 102 | 57 | 57 |
| Same-prompt rescue | 36 | 10 | 9 | 66 |
| Explicit-construction intervention | 18 | 9 | 6 | 72 |
| Frozen answer-package correction | 3 | 1 | 1 | 73 |
| Cue-bounded imperative | 4 | 4 | 2 | 75 |

The correction added a validator-named accepted equivalent but did not alter
the visible prompt or overwrite raw output. Open sentence-level imperatives
still failed after correction because natural polite/referential alternatives
could not be finitely enumerated. The final all-and-only lexical-chunk contract
is a narrow, labelled format intervention. It fixes determinacy at the cost of
format comparability and must not be generalized as a universal item design.

### Curation scale

Max-one gives 75 items; outcome-free max-two gives 113; up-to-three gives 126.
The second item adds contextual replication to 38 cells. Thirteen third items
add no cells and relatively little new lexical surface. The max-two bank was
therefore frozen before Q* and simulation. All 113 prompts are unique, but
surface uniqueness is not equated with measurement independence.

## 5. Q* and identifiability gate

The final pre-simulation audit passes every hard condition:

| Diagnostic | Full-v1 |
|---|---:|
| Cells measured | 75 / 75 |
| Items / KCs / Q edges | 113 / 18 / 269 |
| Q density | .1323 |
| Column rank | 18 / 18 |
| Equal / near-equal columns | 0 / 0 |
| Distinct cell activation rows | 75 |
| Items per KC | 2--49 (median 7.5) |
| Cells per KC | 1--32 |

Forty-six KC pairs have complete A-only/B-only/A+B contrasts; another 105 have
two-sided contrast without observed co-occurrence. Two pairs remain nested
because the source inventory licenses non-subject WH only with present and
negative. More text variants cannot change cell-level activation geometry, so
inventing unnatural cells was rejected. The release reports this limitation
rather than claiming that rank proves recovery.

The semantic regime design yields:

- 54 seen cells;
- 15 unseen combinations whose values and all lower-order pairs are seen but
  whose complete tuple is absent; and
- six unseen-value perfect-progressive cells.

The full-v1 split is materially stronger than medium-v1's 18/5/1 fold, while
the six-cell unseen-value family remains narrow.

## 6. Simulator decision and release scale

The frozen pre-response simulator pilot tested aggregation semantics, update
rules, response noise, initial mastery, learning rate, and opportunity targets.
Minimum aggregation alone satisfied the declared interpretation that every
active KC is required. Product changes when an equally mastered prerequisite
is duplicated; arithmetic/logit means compensate for a weak prerequisite.
All-active opportunity learning was chosen because it is simple and does not
condition simulated acquisition on the random correctness draw.

Target 12 is the lowest schedule passing every information/saturation gate. It
produces 170 seen-only acquisitions per learner, covers every seen item, gives
each seen KC at least 12 opportunities, and then presents 113 frozen probes.
The 128-learner pilot's median response probability changes from .3822 to
.5936, with median gain .1806 and only 2.21% terminal seen-KC states above .95.

The production release contains:

| Quantity | Count |
|---|---:|
| Learners | 1,000 |
| Acquisition events | 170,000 |
| Non-updating probes | 113,000 |
| Total public events | 283,000 |
| Acquisition / probe correct | 84,438 / 65,986 |

Exact replay reconstructs every response probability, draw, transition, Q
edge, and public/private join. Public rows contain no latent state. The
baseline is intentionally simpler than a human-learning model; its deviations
are experimental variables downstream.

## 7. RQ2: misspecification and Q noise

The primary PFA-like model is fitted on all acquisition rows and evaluated on
the same 113,000 probes for every representation. Candidate-minus-K* log-loss
deltas are:

| Representation | KCs | All-probe loss | Delta [95% learner-paired interval] |
|---|---:|---:|---:|
| K* | 18 | .670627 | reference |
| Split-2 | 35 | .673792 | +.003165 [.002744,.003581] |
| Split-4 | 66 | .676495 | +.005868 [.005281,.006473] |
| Family union | 6 | .678759 | +.008132 [.007450,.008779] |
| All merged | 1 | .680852 | +.010225 [.009380,.011029] |
| Exact cell | 75 | .685666 | +.015039 [.014108,.015990] |

The prespecified six-point curve is descriptively U-shaped: K* is its minimum,
and cost rises monotonically away from K* on each coarser/finer side. This
discrete asymmetric pattern is not a universal smooth law; it shows the
consequences of matching or mismatching the declared world, not human ontology
optimality. Exact-cell sparsity costs +.037609 on unseen combinations and
+.028627 on unseen values.

At an equal 27-edge budget, false-positive, false-negative, and mixed Q noise
increase mean loss by .001685, .002644, and .002294 across three structures.
Every instance harms performance. The limited structural seed range does not
establish that false negatives are universally worse.

## 8. RQ3: discovery and identifiability

The blinded candidate space contains 181 hypotheses. Selection uses only seen
acquisition evidence in learner-disjoint fit/validation groups. K*, Q*, oracle,
and all probe outcomes remain unopened until the selection artifact is frozen.

At 1,000 learners, the selector retains its 18-feature base. Atomic features,
compositional operations, and their automated projections have the exact same
seen-Q signature; their separately fitted validation losses differ only at
floating-point scale. Post-selection truth comparison finds:

| Hypothesis | Exact KCs | Padded activation Jaccard | Aligned Q-edge F1 |
|---|---:|---:|---:|
| Compositional candidate ceiling | 18 / 18 | 1.000000 | 1.000000 |
| Atomic / selected equivalence class | 16 / 18 | .970854 | .965385 |
| Family coarse | 5 exact + 3 merges | .371913 | .750929 |
| Exact-cell fine | -- | .084184 | .186969 |
| Hash distractor | 0 / 18 | .202342 | .359259 |

Compositional probe loss is .669606 versus atomic .669979, delta +.000374
[.000228,.000517]. Seen loss is identical; all difference occurs on withheld
perfect-progressive cells where atomic rules do not extrapolate component
activation. Those outcomes cannot legitimately be used to resolve the
selection tie. The N=120 pilot selects coarse, reinforcing that small-sample
policy choice is unstable.

The supported RQ3 answer is therefore deliberately two-part: the method
recovers a high-overlap, truth-containing equivalence class, but unique
generator ontology recovery is rejected. Predictive KT fit alone is
insufficient evidence for cognitive truth even in a positive synthetic case.

## 9. RQ4: linguistic generalisation

K* reference losses are:

| Regime | Cells | Probe events | Event-weighted / cell-macro log loss |
|---|---:|---:|---:|
| Seen | 54 | 84,000 | .669161 / .669783 |
| Pairwise-seen combination | 15 | 20,000 | .672036 / .670637 |
| Unseen value | 6 | 9,000 | .681181 / .681882 |

Relative to K*, exact-cell costs +.008209 seen, +.037609 combination, and
+.028627 unseen value; all intervals exclude zero. Split-2 and family-union
also have supported combination costs (+.008806 and +.009185). Adding
unsupported conjunctive/intersection KCs harms all three regimes, demonstrating
that a union merge is not an interaction.

Atomic and compositional predictions are numerical-equivalent on seen and
combination rows. Their unseen-value difference is -.003236 with interval
[-.007943,.001272] and changes point direction under the RQ3 fitting protocol.
It is inconclusive. The unseen-value result is also composition-sensitive:
per-cell K* loss ranges .666512--.691208 and leave-one-cell-out macro estimates
.680016--.684955.

The exact-item negative control retains the same 170 acquisition opportunities
and K* counts while withholding one item from each of 30 two-item seen cells.
All 30,000 paired probe outcomes are exactly identical to baseline. This is the
expected consequence of no item memory/difficulty and same-Q opportunity
updates; it does not imply human surface-form transfer.

## 10. Mastery recovery

The public-only PFA predictions were frozen before opening oracle state. Their
known guess/slip inverse link estimates the weakest active prerequisite state:

| Representation | All-probe RMSE | Correlation | Seen / combination / unseen-value RMSE |
|---|---:|---:|---:|
| K* | .123738 | .569746 | .122352 / .130717 / .120623 |
| Family coarse | .146300 | .267969 | .146723 / .156074 / .116960 |
| Split-2 | .132752 | .465799 | .128427 / .153555 / .122187 |
| Split-4 | .140428 | .383038 | .132906 / .169750 / .136738 |
| Exact cell | .163828 | .291646 | .144619 / .218837 / .188047 |

Every overall candidate-minus-K* RMSE interval excludes zero. The coarse
unseen-value delta is nevertheless -.003663 [-.005740,-.001507], a supported
local reversal. State recovery therefore agrees with RQ2 overall but not
uniformly across narrow regimes.

Fixed BKT is evaluated separately because its exposed state is per KC rather
than an item minimum. Unique terminal learner-KC RMSE is .300804, correlation
.434973, and bias +.094505. Its posterior-plus-learning and full-credit update
do not match the generator. Similar response scores cannot be assumed to imply
equivalent or correctly interpreted learner states.

## 11. Simulator robustness

The compact robustness design materializes 13 conditions over three common
seeds and 500 learners (39 worlds). It fits K*, family-coarse, and split-2 with
the primary observable model and retains empirical/BKT only as secondary
sensitivities.

Baseline mean log-loss costs are +.007924 coarse and +.003241 split-2. K* beats
both candidates in every seed for 12/13 conditions, including noise .00--.20,
product/mean aggregation, learner guess/slip and learning-rate heterogeneity,
mild forgetting, correlated starting mastery, and correct-only updates.

Unmodelled item difficulty is the exception. At logit SD .60, coarse remains
worse in every seed, while split-2's mean cost +.004138 spans -.000413 to
+.009955. Split-2 wins one seed and falls below coarse in another. The fine
partition can accidentally absorb stable item nuisance. This is a genuine
warning: representation recovery and item effects are confounded when items
are not crossed or modelled.

Fixed BKT shows further reversals, but its mean/full-credit semantics are
deliberately mismatched and were prohibited from driving the conclusion. All
worlds are one-factor synthetic controls; three seeds and one severity per
nuisance are not a universal robustness envelope.

## 12. Collection design

The frozen bounded study contains four deliberately small interventions. It
uses outcome-free nested cohorts and reads only acquisition outcomes for
selection. Unpenalized predictive validation selects K* in all 21 learner
cohorts: five repetitions each at N=60, 120, 240, and 500, and the complete
N=1,000 cohort. At N=1,000, family union, split-2, and exact-cell cost +.005242,
+.002567, and +.004878 log loss; all learner-paired intervals exclude zero.
This is stability inside the simulator, not a human sample-size prescription.
A fixed `.0005 * number_of_KCs` penalty instead selects family union in 18/21
cohorts. The penalty has changed the estimand; parsimony is not empirical proof
of generator truth.

Opportunity targets 6, 12, and 24 give K* mean all-bank probe losses .681757,
.672104, and .636837 across three seeds. Absolute prediction improves, while
the gap to family union grows from +.005437 to +.010070 and the exact-cell gap
from +.007523 to +.032110. More practice strengthens reusable-state evidence.
It also makes exact-cell combination prediction worse (.703218 to .720349):
isolated seen-cell histories become more confident but do not transfer. Three
unequal schedule lengths do not establish a diminishing-return threshold.

Max-one versus max-two curation separates replication from geometry. The bank
grows from 75 to 113 items, minimum/median KC support grows from 1/5 to 2/7.5,
but both projections contain the same 75 Q rows, rank 18, and no identical KC
columns. The additional 38 items improve within-cell support and contextual
replication; they add no new activation contrast.

The two-KC control gives the sharpest design result. When every item is A+B,
A/B columns (and planted interaction I) are identical: every tested
representation ties exactly even at N=1,000. Sparse or balanced A-only/B-only
anchors restore full rank and make the OR/union merge detectably worse. At
N=1,000 union costs +.003194 in the factorized balanced bank and +.010952 in
the planted balanced bank. Yet omitting the planted intersection costs only
+.000506 (three-seed range [.000313,.000621]) with balanced anchors, while the
spurious-intersection negative control remains near zero. Thus structural rank
is necessary but does not guarantee practically unique predictive recovery of
a weak interaction.

## 13. Implications for future real learner collection

The current evidence supports design principles, not numeric human power
claims:

- retain item-to-GrammarCell provenance independently of the KC hypothesis;
- measure stable item effects or cross items over learners, because nuisance
  difficulty can mimic finer KCs;
- collect structurally distinct A-only, B-only, and A+B opportunities where
  linguistically natural; repeated responses cannot break equivalent Q
  columns;
- evaluate effect size after rank is restored, because a full-rank bank can
  still leave an interaction only weakly recoverable;
- obtain multiple independently reviewed contexts for rare KCs rather than
  relying on surface paraphrases of one cell; count these separately as
  replication and as distinct Q rows;
- keep acquisition separate from non-updating grammar probes;
- preregister Q/KC selection evidence and hide grammar holdouts until policy
  freeze;
- estimate guess, slip, learning heterogeneity, forgetting, and item
  difficulty from pilot learners instead of borrowing the synthetic settings;
  and
- include qualified human review of normalisation and item determinacy before
  deployment.

Under the declared synthetic conditions, inference becomes unreliable when
structural contrast is absent, a weak interaction has too little predictive
effect even after rank is restored, exact-cell histories do not transfer, a
complexity penalty changes the selection target, or unmodelled item variation
aligns with a split. None of these observations says that a human study
requires an exact learner count.

## 14. Limitations and negative results

- The six-dimensional scope excludes 675 legitimate EGP records; full source
  processing is not the same as full English grammar coverage.
- Normalisation and validation are automatic. Repeat evidence is useful but no
  expert or learner gold standard exists.
- Cue-bounded imperatives are a measurement-format confound. Open natural
  imperative production remained unresolved under the finite-answer contract.
- K* is a designed synthetic truth. Independent `Beta(2,2)` mastery, fixed
  noise, minimum aggregation, and .02 updates are not human estimates.
- Q* rank and unique columns do not prove statistical or cognitive
  identifiability; RQ3 demonstrates an exact seen-Q equivalence class.
- The unseen-value cohort is six perfect-progressive cells and introduces no
  unseen generator KC.
- Learner bootstrap captures sampling of synthetic learners, not uncertainty
  over grammar resources, item generation, simulator worlds, or people.
- The robustness study is compact and one-factor-at-a-time. Item difficulty is
  a demonstrated confound; prerequisites and policy bias remain future work.
- The alternate `mood`/`person` test proves an interface contract, not
  cross-lingual empirical validity.

## 15. Artifact map

| Object | Path |
|---|---|
| Frozen dataset and README | `data/grammar_kt_full_v1/` |
| K* declaration | `modules/kcs/generator/` |
| Measurement audit | `data/grammar_kt_full_v1/provenance/measurement/audit.json` |
| Simulator pilot | `reports/baseline/artifacts/full_simulator_v1/` |
| RQ2 | `reports/full_v1_artifacts/rq2_misspecification_v1/` |
| RQ3 | `experiments/full_v1/rq3_kc_discovery_v1/` |
| RQ4 | `experiments/full_v1/rq4_generalisation_v1/` |
| Mastery recovery | `reports/full_v1_artifacts/mastery_recovery_v1/` |
| Simulator robustness | `experiments/full_v1/simulator_robustness_v1/` |
| Exact experiment ledger | `reports/experiment_log.md` |

The final verification report records tests, notebook execution, artifact
replay, paper compilation, and clean-diff checks after all evidence is frozen.
