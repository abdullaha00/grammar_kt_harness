# Research map

The active system is organised around five questions rather than historical implementation stages.

| Scientific module | Question | Code | Method resources | Primary artifacts |
|---|---|---|---|---|
| Grammar Representation | What grammatical structures exist? | `grammar/source.py`, `normalisation.py`, `canonical.py` | `modules/grammar/` | source subset, raw/repeated mappings, canonical cells, source edges |
| Measurement | Under which structural conditions are they elicited? | `measurement/operations.py`, `opportunities.py` | `modules/measurement/opportunities/` | MeasurementOpportunities, operation derivations, opportunity fingerprint |
| Dataset Generation | How are opportunities presented naturally? | `generation/generators.py`, `items.py`, `validation.py` | `modules/generation/` | prompts/raw outputs, candidate/accepted/rejected items, reconstruction and quality reports |
| Knowledge Representation | Which KCs encode knowledge over opportunities? | `knowledge/candidates.py`, `selection.py`, `policy.py`, `qmatrix.py` | `modules/knowledge/` | candidates, activation vectors, selection trace, frozen policy, projections, Q-matrix |
| Evaluation | Does the representation transfer and predict? | `evaluation/simulation.py`, `kt.py` | `modules/evaluation/` | opportunity-keyed events, oracle evidence, frozen probes, predictions and metrics |

## Research-modular inputs by executable stage

“Modular” means a versioned scientific input that may be exchanged between
experimental conditions. Python implementations normally remain fixed unless a
new language or methodology requires genuinely different derivation logic.

| Stage | Intended modular inputs | Stable boundary |
|---|---|---|
| `source` | External snapshot/path, source hash/count, sample IDs and metadata, annotation units | Verification and Phase-1 field projection |
| `normalisation` | Phase-1/Phase-2 prompts and backend are experiment-configured; wrapper, rulebook, model instructions, and mapping schema are versionable research files currently loaded from standard module paths | Fresh-context routing, validation, evidence retention |
| `canonical` | Canonical grammar schema | Exact validation, deduplication, source edges |
| `measurement` | Opportunity-expansion config; versioned language-specific operation rules when needed | No surface, generator, KC, fold, or outcome inputs |
| `generation` | Generator configs, prompts, instructions, output schemas, backends, blind/quality evaluator configs | Fixed opportunity interface and blind-target validation |
| `knowledge_selection` | Candidate family, obligation policy, selector config, structural fold | Development-only deterministic selection and freeze |
| `knowledge` | Frozen selected policy or named predefined control | Structural projection through MeasurementOpportunity, never item text |
| `qmatrix` | Upstream accepted bank and frozen projection only; no independent policy knob | Mechanical matrix/edge materialisation |
| `simulation` | Oracle declaration, learner/learning parameters, protocol scale, seed, structural fold | Candidate-ontology independence and private/observable separation |
| `kt` | KT parameters, enabled techniques, calibration/bootstrap settings, structural fold | Observable pre-event fitting; no oracle state |

For a new language, the Grammar prompts, rulebook, mapping contract, and
canonical schema should be versioned as one coherent bundle. Measurement and
simulation activation rules must then be reviewed against that bundle rather
than inherited silently from English.

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
