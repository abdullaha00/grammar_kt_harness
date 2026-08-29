# Phase 3 — learner-evidence KC selection

## Scope and hypotheses

Phase 3 built the second active KC stage:

```text
development CandidateKCs + development learner evidence + selection design
→ predictive/parsimony selection
→ frozen policy
```

It did not evaluate grammar-holdout transfer. The 16-cell bank is a structural
measurement bank without linguistic item text, and both worlds are controlled
synthetic probes rather than claims about human learners.

The preregistered expectations were:

- a factorized base should be sufficient in a factorized latent world;
- a supported perfect×negative candidate should help in a world containing that
  dependency;
- validation loss plus KC-count parsimony should reject unsupported complexity;
- selections should be stable across seeds when learner-event support is
  adequate;
- changing reserved outcomes or oracle fields must not change selection.

The interaction-recovery hypothesis was not reliably supported.

## Active method left in the pipeline

`src/grammar_kt/kc_selection.py` implements the paper-facing procedure directly:

1. reject any non-development item or grammar event;
2. reserve temporal test events from model selection;
3. preserve every structurally eligible feature-value marginal;
4. score each eligible operation/interaction addition with a fixed selector KT;
5. minimize validation log loss plus `lambda × selected KC count`;
6. add only a strict objective improvement;
7. backward-prune selected additions, never the feature marginals;
8. copy the selected activation rules into a plain frozen policy.

The primary selector KT is standardized observable PFA-style logistic
regression. Its inputs are learner success/attempt history and, for each KC,
current activation plus strictly prior successes/failures. It does not receive
simulator difficulty, latent mastery, response probability, cell/item identity,
or holdout grammar. Adding a candidate appends columns without altering the raw
columns of existing candidates. Standardization is fitted on training rows.

The active researcher declaration is `modules/kcs/selection.yaml`. The retained
Phase-3 setting is objective-only `lambda=0.0005`. This is a cautious operating
point, not an estimated human-cognitive constant.

`scripts/run.py` and `notebooks/pipeline_walkthrough.ipynb` now execute:

```text
make_kc_candidates(...)
→ select_kcs(candidate_inventory, development_events, selection_design)
→ frozen policy
→ project_kcs(...)
```

The old obligation selector and its fixture-specific candidate, obligation, and
selector YAML files were removed. Its core defect was that one conjunction could
replace both reusable marginals.

## Scientific design

The retained bank uses only rows with `canonical_split=development` from the
audited legacy structural artifact:

- 16 GrammarCells;
- 30 measurement-opportunity IDs;
- 48 raw candidates;
- 26 structurally selection-eligible candidates;
- nine protected feature candidates;
- nine possible primary additions: six pairwise interactions and three
  non-equivalent operations;
- 16 exact-development-cell candidates as the fine-grained extreme.

All legacy outcomes, KCs, operation evidence, post-training splits, and eight
holdout cells were excluded.

Two complete latent-world declarations were used:

- `phase3_factorized_v1`: nine canonical feature-value latent components;
- `phase3_perfect_negative_interaction_probe_v1`: the same world plus a
  low-initial, slow-learning `aspect=perfect × polarity=negative` dependency.

Difficulty adjustments were zero, and item order was counterbalanced by learner
and pass. For each world and each seed, 300 learners completed eight passes over
the same 30-item bank: 72,000 events per stream and 720,000 total events. Each
stream was gzip-retained and hashed before any representation comparison.

The primary model-selection split was temporal 60/20/20. Selection read only
train/validation rows; temporal test outcomes remained reserved until the policy
was frozen. Learner-level splitting was a sensitivity analysis. The first-seed
test predictions support learner-cluster paired bootstrap intervals.

Compared representations were:

| Representation | KCs | Role |
|---|---:|---|
| Factorized | 9 | protected reusable base |
| Full cell | 16 | exact-development-cell extreme |
| Manual true interaction | 10 | base plus perfect×negative probe |
| All eligible additions | 18 | deliberately dense diagnostic |
| Automated | data-dependent | active forward/prune selector |

## P3-KC-SELECTION-001 results

The private manipulation check confirmed a detectable data-generating change.
Across interaction seeds, the mean target-minus-other response probability was
between −0.0533 and −0.0553. The same contrast was +0.0197 to +0.0207 in the
factorized world. These oracle values were never supplied to the selector.

### Original active threshold

The original `lambda=0.002` plus a second `minimum_improvement=0.0001`
selected exactly the nine-feature base in all five seeds of both worlds.
Within-world pairwise selection Jaccard was therefore 1.0, but this apparent
stability concealed a false negative: the planted interaction was recovered in
0/5 interaction seeds.

Five-seed reserved-test means were:

| World | Representation | Log loss mean | Log loss SD | Brier mean |
|---|---|---:|---:|---:|
| Factorized | Factorized/automated | 0.575207 | 0.002520 | 0.192187 |
| Factorized | Manual interaction | 0.575251 | 0.002499 | 0.192196 |
| Factorized | Full cell | 0.575219 | 0.002510 | 0.192210 |
| Interaction probe | Factorized/automated | 0.583075 | 0.002429 | 0.196020 |
| Interaction probe | Manual interaction | 0.582999 | 0.002360 | 0.195946 |
| Interaction probe | Full cell | 0.582822 | 0.002607 | 0.195863 |

The manual-interaction minus factorized mean log-loss delta was +0.000044 in
the factorized world and −0.000076 in the interaction world. Signs varied by
seed. On the reference interaction seed, the learner-cluster paired delta was
−0.000369 with 95% interval [−0.000982, 0.000251]. The interval includes zero.

These values do not establish a predictive winner. The dense all-eligible
diagnostic sometimes scored better on test, especially in the interaction
world, but it was not selected by the development objective and is not evidence
for retaining nine extra KCs.

### Split, selector-model, and regularization sensitivity

- Chronological and learner-level internal selection both retained only the
  nine-feature base on both reference seeds.
- Logistic `C` in `{0.1, 1, 10}` did not change the reference-seed selected
  inventory.
- BKT selected no addition in the factorized reference seed and selected the
  planted interaction in the interaction reference seed. Logistic did not.
- The BKT-selected interaction scored better than factorized under the primary
  logistic on that reference test, but fixed BKT itself had much worse absolute
  test loss. This demonstrates selector-model sensitivity rather than validating
  BKT as the primary scorer.

### Residual guidance and top-down diagnostic

Train-residual contrast ranked the planted interaction first in the interaction
world, so residuals can focus proposals. The unchanged penalized validation step
still rejected it. With only nine eligible additions, shortlisting does not save
enough computation to justify another active method.

The restricted reverse-direction diagnostic compared the exact-cell and
factorized extremes rather than installing a clustering framework. At the
original penalty, factorized had the better validation objective in both worlds.
Top-down merging was not retained.

## P3-KC-SELECTION-002 penalty replay

The original design applied two thresholds: the KC-count penalty and a second
minimum objective improvement. The second threshold was redundant, so the ten
frozen event streams were replayed without resimulation.

| Objective setting | Factorized-world additions | Interaction-world additions |
|---|---|---|
| original 0.002 + 0.0001 gate | none in 5/5 | none in 5/5 |
| objective-only 0.00025 | additions in 2/5 | planted interaction 2/5; finite tense 1/5 |
| objective-only 0.0005 | none in 5/5 | planted interaction 1/5; finite tense 1/5 |
| objective-only 0.001 | none in 5/5 | none in 5/5 |

At `0.00025`, null-world false additions and planted recovery were equally
frequent. At `0.0005`, the factorized null control was clean, but recovery was
only 1/5. At `0.001`, recovery vanished. No setting achieved both stable
recovery and stable rejection of irrelevant additions.

The active choice is therefore objective-only `lambda=0.0005`: it is the
cleanest conservative point observed, while its low recovery rate is documented
as a limitation. It must be revisited with stronger worlds, better folds, more
accepted items per cell, and Phase-5 support studies.

## RQ answers at this checkpoint

- **RQ1 — granularity:** partially answered. Nine feature KCs were the most
  stable parsimonious representation in this diagnostic, but full-cell and
  interaction effects were too small and variable for a final ranking.
- **RQ2 — feature sufficiency:** partially answered. Features were sufficient
  in the factorized world and usually selected in the probe, but the probe
  contains real residual structure that factorized histories do not fully
  capture.
- **RQ3 — useful interactions:** partially answered. Perfect×negative was the
  only deliberately planted interaction and had small, seed-variable predictive
  benefit; no empirical-English interaction claim follows.
- **RQ4 — automated recovery:** partially answered and largely negative. The
  selector can recover the planted interaction, but only 1/5 seeds at the
  retained null-safe penalty.
- **RQ7 — selector-model sensitivity:** partially answered. BKT/logistic differed
  on the planted reference seed; logistic regularization and the two internal
  split schemes did not change that inventory.
- **RQ19 — paired comparison:** answered methodologically. Use event-identical,
  learner-cluster, event-weighted bootstrap deltas with candidate-minus-reference
  sign; use 5,000 repeats for final paper comparisons.
- **RQ20 — support:** partially answered. Two cells/four items produced thousands
  of event activations, yet recovery remained unstable; repeated events cannot
  compensate fully for only two independent grammar cells and a small effect.

## Negative results and limitations

- Fixed-width mean-active-KC history summaries failed a controlled toy because
  adding a KC altered existing predictors; they were rejected before the
  scientific run in favor of nested per-KC histories.
- The original double threshold failed the planted recovery control.
- Residual shortlisting did not improve the retained selection.
- The restricted top-down direction added no evidence beyond the two extremes.
- No grammar holdout was used, so Phase 3 supplies no compositional-transfer
  result.
- Worlds are synthetic and the bank has structural IDs rather than validated
  learner-facing item text.
- PFA fits more coefficients when more KCs are present, and every active KC gets
  full response credit. Phase 4 must audit dimensionality and shared-credit
  confounding.
- There is no human learner or cross-language evidence.

## Reproducibility and verification

Commands:

```bash
.venv/bin/python scripts/run_kc_selection_experiments.py
.venv/bin/python scripts/run_phase3_penalty_stability.py
.venv/bin/python scripts/run.py --fixture --output /tmp/grammar_kt_phase3_checkpoint_<timestamp>
.venv/bin/python -m pytest -q
git diff --check -- . ':(exclude)pipeline.txt'
```

Seeds are `20260827`–`20260831`; no language model was called. The primary run
uses 3,000 bootstrap repeats on the reference seed. Final Phase-3 verification
is 51 passing tests. The targeted whitespace check passes; whole-tree
`git diff --check` continues to report only the pre-existing whitespace in the
user-modified `pipeline.txt`.

Important artifacts:

- `reports/phase3/artifacts/selection_study_v1/study_design.json`
- `reports/phase3/artifacts/selection_study_v1/results.json`
- `reports/phase3/artifacts/selection_study_v1/events/*.jsonl.gz`
- `reports/phase3/artifacts/selection_study_v1/selections/*.json`
- `reports/phase3/artifacts/selection_study_v1/predictions/*.jsonl.gz`
- `reports/phase3/artifacts/penalty_stability_v1/results.json`
- `reports/phase3/artifacts/quick_verification/` (software verification only)

## Phase-4 handoff

Replace the ordinal fold and mixed-history schedule before interpreting
generalization. Add four readable worlds; audit no-oracle KT, representation
dimensionality, BKT shared credit, source/normalization transitions, best-of-N
generation, and validator reliability. Reuse the same active candidate and
selection components rather than building a parallel selector.
