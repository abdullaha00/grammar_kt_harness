# Phase 5 — medium-scale integrated validation

Date: 2026-08-27  
Status: complete

## Scope and hypotheses

Phase 5 validates the integrated Phase-4 method without changing its grammar
bank, items, folds, learner outcomes, or primary KT predictions. The retained
inputs are 24 canonical cells, 42 structural item identifiers, an 18/5/1
development/compositional/novel-value fold, four declared latent worlds, three
simulation seeds, and 240 learners per world/seed. This is a medium-scale
synthetic-method study, not human-learner or natural-language item evidence.

The interventions were deliberately staged:

1. at the active `lambda=0.0005`, rerun the selector on nested samples of 30,
   60, 120, and 240 learners in all four worlds;
2. at 240 learners, vary `lambda` over 0, .00025, .0005, .001, and .002 only in
   the factorized null world and interaction-heavy positive control;
3. reuse the retained primary-logistic predictions for factorized,
   all-supported-interaction, automated, and labelled exact-all-cell oracle
   representations;
4. compare representations with 5,000 event-weighted, paired learner-cluster
   bootstrap resamples on the reference seed.

The hypotheses were:

- **H5.1 / RQ20:** more independent learners will suppress chance additions in
  worlds without reusable interactions and stabilize planted-interaction
  recovery in the interaction-heavy world.
- **H5.2 / RQ1/RQ4:** an intermediate KC-count penalty will give a better
  recovery/parsimony tradeoff than no penalty or a strongly conservative one.
- **H5.3 / RQ3/RQ6:** selected interactions will improve fixed-logistic loss in
  the interaction-heavy world, but no representation will dominate every
  plausible world.
- **H5.4 / RQ5:** a predictive development result will not necessarily imply a
  resolved compositional-transfer result.

## Learner-event support (RQ20)

Every learner contributes 132 selection-train and 33
selection-validation development events. Repeated events do not increase the
18 independent development grammar cells or the 33 development item
identifiers.

| World | Learners | selected KC counts across seeds | addition counts | all-KC Jaccard | addition Jaccard |
|---|---:|---:|---:|---:|---:|
| factorized | 30 | 11, 10, 9 | 2, 1, 0 | .823 | .000 |
| factorized | 60 | 9, 9, 9 | 0, 0, 0 | 1.000 | 1.000 |
| factorized | 120 | 9, 9, 9 | 0, 0, 0 | 1.000 | 1.000 |
| factorized | 240 | 9, 9, 9 | 0, 0, 0 | 1.000 | 1.000 |
| interaction-heavy | 30 | 10, 11, 12 | 1, 2, 3 | .886 | .500 |
| interaction-heavy | 60 | 11, 12, 11 | 2, 3, 2 | .889 | .556 |
| interaction-heavy | 120 | 11, 11, 11 | 2, 2, 2 | .889 | .556 |
| interaction-heavy | 240 | 11, 12, 11 | 2, 3, 2 | .944 | .778 |
| cell-specific | 30 | 13, 10, 9 | 4, 1, 0 | .745 | .000 |
| cell-specific | 60 | 11, 9, 9 | 2, 0, 0 | .879 | .333 |
| cell-specific | 120 | 10, 9, 9 | 1, 0, 0 | .933 | .333 |
| cell-specific | 240 | 9, 9, 9 | 0, 0, 0 | 1.000 | 1.000 |
| mixed | 30 | 10, 10, 9 | 1, 1, 0 | .873 | .000 |
| mixed | 60 | 9, 11, 10 | 0, 2, 1 | .876 | .167 |
| mixed | 120 | 9, 10, 10 | 0, 1, 1 | .873 | .000 |
| mixed | 240 | 9, 9, 10 | 0, 0, 1 | .933 | .333 |

At 30 learners, the factorized null has chance additions in 2/3 seeds; these
disappear by 60 learners. Chance interaction/operation additions in the
cell-specific world decline more slowly and disappear only at 240. In the
interaction-heavy world, both structurally eligible planted interactions are
recovered together in 2/3 seeds at 30, 60, and 120 learners, and in 3/3 at 240.
One non-planted operation remains in one 240-learner seed. Thus 240 learners is
the smallest tested setting that recovers both eligible positive controls in
every seed while keeping both no-interaction controls clean.

The nine protected feature KCs inflate all-KC Jaccard, so addition-only
Jaccard is the more revealing stability measure. Even at 240 learners it is
.778 in the interaction world and .333 in the mixed world. Event volume cannot
fully resolve a structurally small hypothesis space: the two recovered
interactions have only two/three cell supports and four/five item supports.

**Decision.** Use at least 240 simulated learners per selection seed at this
bank size, retain multiple seeds, and report interaction frequencies rather
than presenting one selected inventory as certain. More repeated events from
the same few cells are not a substitute for broader structural support.

## Complexity-penalty sensitivity (RQ1, RQ4)

| `lambda` | factorized runs with false additions | factorized KC counts | interaction KC counts | runs recovering both planted interactions | notable extra selections |
|---:|---:|---:|---:|---:|---|
| 0 | 3/3 | 14, 14, 11 | 13, 15, 13 | 3/3 | 2--5 false additions/run in null; 1--4 extras in positive control |
| .00025 | 2/3 | 9, 10, 10 | 11, 13, 12 | 3/3 | two null false additions; up to two extras in positive control |
| **.0005** | **0/3** | **9, 9, 9** | **11, 12, 11** | **3/3** | one extra operation in one positive-control seed |
| .001 | 0/3 | 9, 9, 9 | 11, 11, 10 | 2/3 | one planted interaction missed in one seed |
| .002 | 0/3 | 9, 9, 9 | 9, 10, 10 | 0/3 | present×negative never recovered |

The unpenalized selector does not merely recover signal: it selects 12
irrelevant additions across the three factorized-null runs, with all-KC
Jaccard .660 and addition Jaccard .194. At `.00025`, both planted interactions
remain stable but null false positives persist. Penalties of `.001` and `.002`
are increasingly false-negative. The predeclared `.0005` operating point is
the only tested point with zero null additions and joint 3/3 planted recovery;
it was not chosen after observing this Phase-5 grid.

**Decision.** Retain objective-only `lambda=.0005`. It is an empirically useful
operating point in these controlled worlds, not a human-cognitive constant and
not guaranteed optimal at another bank scale. Keep the simple KC-count penalty;
the results do not motivate a more elaborate complexity formula.

## Fixed-logistic predictive comparison (RQ1--RQ6, RQ19)

Three-seed mean frozen-probe log loss is shown below. All methods receive the
same events; primary logistic excludes simulator difficulty and KC count.

| Latent world | factorized | all supported interactions | automated | exact-all-cell oracle | automated - factorized |
|---|---:|---:|---:|---:|---:|
| factorized | .578311 | .578334 | .578311 | .603004 | .000000 |
| interaction-heavy | .609353 | .607225 | **.607097** | .621903 | **-.002256** |
| cell-specific | .686715 | .686379 | .686715 | **.679439** | .000000 |
| mixed | .641559 | **.641273** | .641575 | .652886 | +.000016 |

The exact-all-cell result is explicitly oracle-labelled because it introduces
evaluation-cell KCs unavailable to development-only candidate discovery. It
wins only in the cell-specific world and is markedly worse in the other three,
including a three-seed compositional loss of .699977 versus .574894 in the
factorized world. It diagnoses the expected representation/world interaction;
it is not an admissible selected policy.

On the reference seed, 5,000 paired learner-cluster resamples give:

| World | regime | automated - factorized log loss | 95% interval | Brier delta | 95% interval |
|---|---|---:|---:|---:|---:|
| factorized | all test | .000000 | [.000000, .000000] | .000000 | [.000000, .000000] |
| interaction-heavy | all test | **-.002666** | **[-.004244, -.001103]** | **-.001127** | **[-.001795, -.000471]** |
| interaction-heavy | compositional | -.001438 | [-.005286, .002518] | -.000511 | [-.002075, .001082] |
| cell-specific | all test | .000000 | [.000000, .000000] | .000000 | [.000000, .000000] |
| mixed | all test | .000000 | [.000000, .000000] | .000000 | [.000000, .000000] |

The exact zeros occur because the reference-seed automated policy selected the
factorized inventory in those worlds, not because two separately fitted models
happened to tie. In the interaction-heavy world, automated selection produces
a small, cluster-robust all-test improvement. Its compositional point estimate
has the same sign, but the interval includes zero. Across three seeds the
automated compositional mean is .617641 versus .620270 for factorized; without
a multi-seed uncertainty design this remains suggestive, not established.

All-supported interactions also improve interaction-heavy all-test loss on the
reference seed (`delta=-.002443`, 95% interval `[-.003954, -.000959]`) but add
six interaction KCs rather than the automated policy's two or three additions.
Outside that positive-control world its intervals include zero. In the mixed
world, all-supported interactions have the best three-seed point estimate by
only .000286 log loss over factorized, while the automated selection is
seed-unstable and essentially tied. There is no world-independent predictive
winner.

Novel-value probes contain only one cell/one item (240 events per seed) and
`modal=would` has no factorized projection coverage. Their metrics are retained
but cannot adjudicate KC granularity. This is a structural limitation of a
development-derived ontology, not evidence that novel grammatical values are
already learned.

## Method recommendation

Keep the active bottom-up forward/prune selector with:

- all structurally eligible feature-value marginals protected;
- only supported, activation-nonredundant operations/interactions eligible as
  additions;
- development-only chronological train/validation evidence;
- observable nested PFA-style logistic scoring;
- validation log loss plus `.0005 × KC count`;
- backward pruning and freezing before grammar-holdout projection.

This recommendation is conditional and conservative. It is supported because
the same procedure rejects additions in both no-interaction controls, recovers
both eligible planted interactions in all three 240-learner positive-control
seeds, and yields a paired predictive improvement when those interactions are
actually present. It does not recover cell-specific latent state because exact
cells are intentionally excluded from additions, and it gives mixed evidence
in the mixed world. Therefore the paper should describe an adaptive,
interpretable predictive/parsimony procedure—not claim discovery of a unique or
universally correct cognitive ontology.

Residual shortlisting and top-down merging remain rejected: Phase 3 found no
predictive justification, and Phase 5 supplies no new evidence for restoring
them. A world-specific manual “true interaction” policy is also not a fair main
baseline because it reads the synthetic data-generating declaration. The
all-supported policy is the non-oracle interaction-rich comparison.

## RQ answers

- **RQ1 — KC granularity:** partially answered. Adaptive factorized-plus-
  selected interactions gives the best prediction/parsimony tradeoff in the
  interaction-heavy control and collapses to factorized in clean controls; no
  representation dominates across worlds.
- **RQ2 — feature sufficiency:** answered conditionally. Feature KCs suffice in
  the factorized world, but not in the interaction-heavy world. They do not
  express exact-cell latent state.
- **RQ3 — useful interactions:** partially answered. Perfect×negative and
  present×negative are recoverable and predictive when deliberately planted.
  This is no evidence that human English learners have those dependencies.
- **RQ4 — automated recovery:** answered for the controlled hypothesis. At 240
  learners and `.0005`, both eligible planted interactions are recovered 3/3
  with no false additions in the factorized null; one extra operation appears
  in one positive-control run.
- **RQ5 — compositional transfer:** partially answered and inconclusive. The
  point estimate favors automation in the interaction world, but the paired
  interval crosses zero.
- **RQ6 — latent-world robustness:** answered for the four declared synthetic
  worlds. Rankings depend strongly on latent structure; no universal winner is
  supported.
- **RQ7 — KT sensitivity:** Phase-4 answer retained. Logistic regularization is
  stable, but BKT changes selected inventories and its multi-KC full-credit
  updates confound representation size; primary selection remains logistic.
- **RQ19 — paired comparison:** answered. Event-identical, event-weighted
  learner-cluster bootstrap with 5,000 repeats is the final primary procedure.
- **RQ20 — evidence support:** partially answered. At this bank size, 240
  learners outperform smaller tested samples for controlled recovery, but
  structural support remains only two/three cells and needs broader item-bank
  evidence in Phase 6.

## Reproducibility and artifacts

Exact command:

```bash
.venv/bin/python scripts/run_phase5_integrated_validation.py
```

No model was called, no item or learner event was regenerated, and no KT model
was refit for the final representation comparison. Simulation seeds are
`20260827`--`20260829`; paired-bootstrap seed is `20260827` with 5,000 repeats.
The script hashes all 12 retained frozen event streams and writes every newly
fit policy separately before aggregation.

Important outputs:

- `reports/phase5/artifacts/integrated_validation_v1/results.json`
- `reports/phase5/artifacts/integrated_validation_v1/summary.json`
- `reports/phase5/artifacts/integrated_validation_v1/selections/learner_support/`
- `reports/phase5/artifacts/integrated_validation_v1/selections/lambda_sensitivity/`

Verification:

```bash
.venv/bin/python -m pytest -q tests/test_phase5_integrated_validation.py
git diff --check -- scripts/run_phase5_integrated_validation.py \
  tests/test_phase5_integrated_validation.py reports/phase5
```

The focused test result is four passing tests, including exact paired coverage,
whole-learner resampling, sign convention, nested learner sampling, and
determinism. The targeted whitespace check passes.
