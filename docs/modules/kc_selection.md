# KC-selection module

1. **Research question.** Which declared distinctions are supported, identifiable, contrast-preserving, and parsimonious on development evidence?
2. **Inputs.** Development cells/realisations from a fold, candidate-family config, obligation policy, selector config, and lexicon.
3. **Outputs.** Candidates, activations, diagnostics, trace, frozen policy, and post-freeze holdout evaluation.
4. **Assumptions.** Candidate search space, marked facts, nuisance invariance, interactions, support thresholds, and greedy objective.
5. **Researcher choice.** `candidate_families/structural_v0.json`, `obligations/marked_operational_v0.json`, fold, and selector config.
6. **Deterministic implementation.** Rule compilation, support/equivalence checks, backward selection, and policy materialisation.
7. **Without Python.** Add a named candidate family or obligation condition and reference it from the selector config.
8. **Inspect.** All `kc_selection/` artifacts, especially `diagnostics.jsonl`, `selection_trace.jsonl`, and `evaluation.json`.
9. **Example.** `python scripts/run_one.py kc_selection --fixture structural_selection`.
10. **Paper dependencies.** RQ3, RQ4, RQ5, RQ7 and RQ8.
