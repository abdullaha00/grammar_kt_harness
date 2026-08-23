# Research map

The harness treats representation choices as experimental inputs while keeping the stage sequence fixed.

| Paper question | Main editable modules | Primary run evidence |
|---|---|---|
| RQ1 Normalisation reliability | `modules/normalisation/`, annotation-unit repeats | `normalisation/reliability.json`, `repeated_comparisons.jsonl` |
| RQ2 Canonical adequacy | `modules/canonical/grammar_schema.yaml` | `canonical/audit.json`, cells and source edges |
| RQ3 KC identifiability | candidate family, fold, lexicon | `kc_selection/diagnostics.jsonl`, equivalence classes |
| RQ4 KC granularity | candidate family, obligation policy, selector config | selection trace and frozen policy |
| RQ5 Representation level | cell and operation candidates, admissible realisations | activation/scope diagnostics and item projection |
| RQ6 Compositionality | fold, oracle, frozen-probe protocol, KC condition | compositional KT coverage and metrics |
| RQ7 Interaction necessity | declared interaction candidates and policy condition | paired fixed-probe comparisons |
| RQ8 Robustness | sample design, repeats, folds, seeds and future oracle worlds | cross-run comparisons and reuse metadata |

The reference condition uses `REFERENCE_FOLD_v0`, `STRUCTURAL_CANDIDATES_v0`, `MARKED_OPERATIONAL_v0`, and `STRUCTURAL_ORACLE_v0`. Changing any of those is a named scientific intervention, not an implementation tweak.

Component-specific guides are in [`docs/modules/`](modules/).
