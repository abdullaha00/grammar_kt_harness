# Fixture-backed scientific checks

The refactor evidence run is reproducible without a paid API call:

```bash
.venv/bin/python scripts/run_scientific_checks.py --force
```

The retained config, command manifest, raw generator/evaluator evidence, and full result are under [`reference/five_module_refactor/`](../reference/five_module_refactor/). The run uses seed 77 and deterministic fixture transports.

## Results

- **A — operation dependence:** the same present positive polar-question GrammarCell requires `do_support + operator_inversion` with `lexical_transitive`, but only `operator_inversion` with `copular`.
- **B — generator invariance:** `OPP_11EED1F1B3C2162B` yields standalone `ITEM_8F5F8890C12BE6D3` and dialogue `ITEM_9F6BD302F468198F`; both retain the same cell and `do_support + negation` operations.
- **C — validation:** both valid format fixtures obtain GrammarCell and operation exact-match rates of 1.0. A positive-past response for the intended negative-past opportunity is rejected with cell, operation, and agreement-site mismatches. Two repeated structural and quality diagnostics agree exactly in this fixture run.
- **D — simulation invariance:** both format conditions have difficulty `0.38323484`, outcomes `[0, 1]`, and opportunity-outcome fingerprint `3f7bcc8664d3837a8078fd9681b1b7160f563e0a5cae3ef9554a232c201a090e`.
- **E — KC invariance:** both formats project to `KC_FINITE_PAST + KC_NEGATION`; their Q-matrix rows are identical despite different item IDs. Structural selection is development-only and yields frozen-policy fingerprint `FROZEN_E7030EEA0562E8CF` in the selection fixture.
- **F — KT sanity:** the probe reads a frozen two-attempt/two-correct development state, produces the same 0.75 empirical prediction for both probe orders, and does not update candidate state.

## Claim boundary

These results establish software behavior and controlled fixture invariants. They do not establish dataset validity, human evaluator reliability, cognitive KC validity, or empirical transfer. Those claims require live generation, blinded linguistic/human review, and preregistered learner-data experiments.
