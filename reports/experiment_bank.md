# Experiment bank

This file contains unexecuted or explicitly deferred ideas. Executed evidence
belongs in `reports/experiment_log.md`. Priority begins only after
`grammar_kt_full_v1` is frozen.

## Baseline-construction decisions in progress

- FULL-LING-001: full 1,222-row normalisation/canonicalisation census.
- FULL-KC-001: outcome-free generator-KC structural and recovery pilot.
- FULL-ITEM-001: item-count/diversity marginal-value pilot on the full cells.
- FULL-Q-001: mandatory K*/Q* support, rank, equivalence, and contrast audit.
- FULL-SIM-001: response aggregation and learning-update baseline pilot.
- FULL-SCHEDULE-001: acquisition passes, learner count, and probe-scale pilot.

## High-priority downstream experiments

- RQ2 granularity curve: coarse merges → K* → controlled splits.
- RQ2 Q* false-positive, false-negative, and mixed edge corruption.
- RQ2 missing/spurious interaction controls.
- RQ3 blind KC discovery with activation-based optimal matching to K*/Q*.
- RQ3 predictive equivalence versus structural recovery.
- RQ4 seen, constituent-seen, pairwise-seen, and unseen-value evaluation.
- Guess, slip, and compact guess×slip robustness.
- Learner/KC heterogeneity, forgetting, and item-difficulty nuisance.
- Response-aggregation sensitivity.
- Response prediction versus latent-mastery recovery.
- Learner-count and opportunities-per-learner curves.
- Items-per-KC and structural-diversity-versus-volume comparisons.
- KC co-occurrence and anchor-item identifiability.
- Grammar-holdout-size stability.

## Deferred unless primary RQs expose a need

- Neural KT architectures: add only if simpler BKT/PFA models cannot answer a
  primary question.
- Adaptive teaching policies and prediction-versus-teaching trade-offs.
- Dropout and policy-bias simulations.
- Post-training generation models.
