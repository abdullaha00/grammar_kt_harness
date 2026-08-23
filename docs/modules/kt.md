# KT module

1. **Research question.** How predictive is each frozen KC representation on identical outcomes, especially unseen combinations?
2. **Inputs.** Observable fixed events, frozen item-KC projection, fold, and KT parameters.
3. **Outputs.** Projected histories, empirical/BKT/logistic predictions, coverage, metrics, and frozen candidate states.
4. **Assumptions.** Smoothing priors, BKT parameters, logistic features, zero-KC fallback, cold-KC prior, and bootstrap design.
5. **Researcher choice.** Techniques and parameter config; the Phase-D non-updating probe protocol is explicit.
6. **Deterministic implementation.** Opportunity counting, state fitting/freezing, prediction, metrics, and paired learner bootstrap.
7. **Without Python.** Change technique lists or KT config; compare representations without changing fixed events.
8. **Inspect.** `kt/metrics.json` and all `kt/compositional/` support, prediction, state, and metric artifacts.
9. **Example.** `python scripts/run_one.py kt --fixture frozen_compositional_probe`.
10. **Paper dependencies.** RQ4–RQ8, with RQ6 as the central Phase-D use.
