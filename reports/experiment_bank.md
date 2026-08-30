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

FULL-MASTERY-001 has completed frozen observable prediction, oracle-only
item-prerequisite-state evaluation, learner-paired uncertainty, and the
secondary fixed-BKT per-KC state check. Further state models are not automatic:
promote one only if it has a clearly comparable mastery semantics.

FULL-ROBUST-001 has completed the compact 13-condition, three-seed simulator
sensitivity study. The primary ordering survives every condition except a
seed-sensitive split-2 reversal under unmodelled item difficulty. Additional
severity grids are deferred unless a later claim depends on a threshold.

FULL-COLLECTION-001 has completed the bounded learner-count, opportunity,
max-one/max-two, and A-only/B-only/A+B anchor study, including factorized and
planted-interaction positive/negative controls. It establishes that response
volume cannot repair equivalent Q columns and that full rank alone need not
make a weak interaction practically recoverable.

## High-priority downstream experiments

None. The declared synthetic programme is closed. The six-cell unseen-value
limitation is already bounded by per-cell and leave-one-cell-out evidence;
resplitting this inventory cannot create a broader unseen-value construct.

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
- Further learner-count, opportunity, or anchor grids. Promote only if a new
  real-data design supplies parameter ranges that make a threshold actionable.
