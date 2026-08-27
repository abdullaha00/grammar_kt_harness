# Research map

The active system is organised around five questions rather than historical implementation stages.

| Scientific module | Question | Code | Method resources | Primary artifacts |
|---|---|---|---|---|
| Grammar Representation | What grammatical structures exist? | `grammar/source.py`, `normalisation.py`, `canonical.py` | `modules/grammar/` | source subset, raw/repeated mappings, canonical cells, source edges |
| Measurement | Under which structural conditions are they elicited? | `measurement/operations.py`, `opportunities.py` | `modules/measurement/opportunities/` | MeasurementOpportunities, operation derivations, opportunity fingerprint |
| Dataset Generation | How are opportunities presented naturally? | `generation/generators.py`, `items.py`, `validation.py` | `modules/generation/` | prompts/raw outputs, candidate/accepted/rejected items, reconstruction and quality reports |
| Knowledge Representation | Which KCs encode knowledge over opportunities? | `knowledge/candidates.py`, `selection.py`, `policy.py`, `qmatrix.py` | `modules/knowledge/` | candidates, activation vectors, selection trace, frozen policy, projections, Q-matrix |
| Evaluation | Does the representation transfer and predict? | `evaluation/simulation.py`, `kt.py` | `modules/evaluation/` | opportunity-keyed events, oracle evidence, frozen probes, predictions and metrics |

## Scientific invariants

- Normalisation and Canonical are distinct transformations.
- `operations = f(GrammarCell, structural_conditions)`.
- Opportunity identity excludes surface wording, generator, KC policy, folds, and outcomes.
- Generator inputs exclude KC/fold information; target grammar is fixed first.
- Blind reconstruction never sees the intended target.
- KC selection uses development cells/opportunities, not generated sentences.
- The policy is frozen before holdout evaluation.
- Q-matrix construction does not re-evaluate policy rules.
- Simulation uses opportunity identity and never evaluated KCs.
- KT probes read frozen development state and cannot update it.

## Review surfaces

| Surface | Purpose | Correctness boundary |
|---|---|---|
| `notebooks/module_unit_examples.ipynb` | Primary sequential methodology walkthrough over five authentic EGP descriptors and retained real model evidence | Researcher orientation, audit, explanation, and smoke testing |
| `notebooks/research_audit.ipynb` | Manual audit of assumptions, contracts, leakage, failures, and metrics | Researcher judgement; never auto-certifies methodology |
| `tests/` | Exhaustive software and scientific-boundary regression | Detects implementation drift; does not replace linguistic validation |

## Named interventions

The fold, measurement policy, generator config, candidate family, obligation policy, KC selector, oracle, and KT model configuration are explicit research inputs. Changing one is a named experimental intervention, not a hidden implementation tweak.
