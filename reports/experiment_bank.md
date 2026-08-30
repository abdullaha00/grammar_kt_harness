# Experiment bank

This file contains unexecuted or explicitly deferred ideas. Executed evidence
belongs in `reports/experiment_log.md`. Priority begins only after
`grammar_kt_full_v1` is frozen.

## Completed work moved to the experiment log

Layer A is closed: FULL-LING-001, FULL-KC-001, the four item campaigns and
curation, FULL-REGIME-Q-001, FULL-SIM-001, and FULL-DATASET-FREEZE-001 all have
retained evidence and decisions in `reports/experiment_log.md`.

FULL-RQ2-001 has also completed the primary six-point granularity comparison
and preregistered 10% false-positive, false-negative, and mixed Q corruption.
Further Q rates are not automatic; promote them only if a conclusion depends
on the shape of the corruption curve.

FULL-RQ3-001 has completed the blind candidate selection, name-free activation
matching, predictive-equivalence analysis, and positive/negative controls. It
found a high-overlap seen-Q equivalence class rather than unique ontology
recovery; further selector tuning is not an automatic follow-up.

FULL-RQ4-001 has completed learner-paired, cell-macro, per-cell, and
leave-one-cell-out analysis for all 54/15/6 grammar cells, plus the exact-item
novelty negative control. Further grammar resplitting is not warranted by the
current inventory.

## High-priority downstream experiments

- Oracle-only prerequisite/mastery recovery for the fixed RQ2 hypotheses.
- Compact multi-seed robustness capable of changing RQ2 rankings: guess/slip,
  aggregation, learner heterogeneity, forgetting, item difficulty, and update
  rule. BKT remains secondary because its mean/full-credit semantics mismatch
  the generator.
- One planted two-KC union-versus-intersection micro-control. The real-bank RQ4
  spurious-intersection test is complete; K* contains no separate true
  interaction KC, so a real-bank missing-true-interaction ablation is not
  applicable.
- Bounded collection-design evidence after headline RQs: learner-count nested
  resampling; opportunity targets 6/12/24; max-one versus max-two bank; and a
  two-KC A-only/B-only/A+B anchor microstudy at matched response volume.
- Grammar-holdout-size resampling only if the six-cell unseen-value conclusion
  remains sensitive in leave-one-cell-out analysis.

## Deferred unless primary RQs expose a need

- Neural KT architectures: add only if simpler BKT/PFA models cannot answer a
  primary question.
- Adaptive teaching policies and prediction-versus-teaching trade-offs.
- Dropout and policy-bias simulations.
- Post-training generation models.
- Further LLM item generation or more than two selected variants/cell; the
  frozen bank already answers the baseline construction question.
- Large Q-noise, simulator, or KT hyperparameter Cartesian grids.
- Universal human sample-size thresholds derived from synthetic learners.
