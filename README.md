# Grammar–KT research harness

```text
Typed EGP resource
→ normalisation
→ canonicalisation
→ LLM item generation
→ independent item validation
→ FIXED accepted item bank
→ grammar fold
→ FIXED learner events
→ KC representation
→ item–KC projection
→ knowledge tracing
→ evaluation
```

This repository constructs and evaluates a small grammar-focused
language-learning dataset for knowledge-tracing research. Its central
experimental boundary is simple:

> Items and learner outcomes are fixed before candidate KC representations are
> compared. Candidate KCs never influence item generation or simulation.

Start with [`experiments/base.yaml`](experiments/base.yaml), follow each
referenced research file under [`modules/`](modules/), and then read
[`scripts/run.py`](scripts/run.py). The runner executes the method literally in
the order shown above; there is no workflow engine, registry, stage cache,
fingerprint, or reuse layer.

## Stages

| Stage | Input | Research-configurable files | Output |
|---|---|---|---|
| Typed resource | Selected EGP descriptor records | `modules/resource/egp/schema.yaml` | Typed EGP records |
| 1. Normalisation | Typed EGP descriptor | EGP Phase-1/Phase-2 prompts and rulebook; canonical schema; model settings in the experiment | `NormalisedMapping[]` |
| 2. Canonicalisation | Complete mappings only | `modules/canonical/schema.yaml` | Deduplicated `GrammarCell[]` with readable IDs and source IDs |
| 3. Item generation | GrammarCells | Generation prompt, English rulebook, design, format, lexicon, model settings | `CandidateItem[]` |
| 4. Item validation | Candidate items and intended cells | Independent judge prompt, explicit criteria, model settings | Fixed accepted bank, judgments, bank summary |
| 5. Grammar fold | GrammarCells | Frozen reference fold | Development, compositional-holdout and novel-feature-holdout assignments |
| 6. Simulation | Fixed accepted bank and grammar fold | Synthetic world | Fixed `BaseEvent[]` |
| 7. KC representation | Cells, fixed items and fold | Predefined policy, or candidates/obligations/selector | Frozen KC policy |
| 8. Projection | Fixed items, cells and frozen policy | None | One item–KC row per item and a Q-matrix |
| 9. Knowledge tracing | Fixed events and projection | KT protocol | Empirical, BKT and logistic predictions |
| 10. Evaluation | All final stage records | Evaluation protocol | Dataset, representation and KT results |

The grammar fold is not a temporal train/validation/test split. It asks whether
a GrammarCell is available to KC selection, a new combination of known feature
values, or contains a feature value unseen in development. Each learner event
also receives an ordinary temporal split for KT fitting and evaluation.

## Research modules

Every file retained under `modules/` changes a methodological choice.

| File | Scientific question controlled |
|---|---|
| `resource/egp/schema.yaml` | Which evidence fields does the selected EGP resource expose? |
| `resource/egp/normalisation/phase1.txt` | How is descriptor-only evidence mapped without examples? |
| `resource/egp/normalisation/phase1_self_check.txt` | What happens when Phase 1 adds an explicit evidence self-check? |
| `resource/egp/normalisation/phase2.txt` | When and how may examples refine a partial mapping? |
| `resource/egp/normalisation/rulebook.md` | Which EGP-to-English normalisation decisions and exclusions apply? |
| `canonical/schema.yaml` | What is the canonical six-dimensional grammar hypothesis? |
| `canonical/rationale.md` | Why does the pilot use this scope and representation? |
| `generation/prompt.txt` | How does the model turn a fixed cell into an exercise? |
| `generation/prompt_contextual.txt` | How does an explicit communicative-context intervention change generation? |
| `generation/rulebook.md` | Which English agreement, auxiliary, passive, negation and question rules apply? |
| `generation/design.yaml` | How many items and controlled variants are generated per cell? |
| `generation/formats/controlled_production.yaml` | What does the current learner task require? |
| `generation/lexicon.jsonl` | Which controlled English lexical frames constrain the pilot? |
| `validation/prompt.txt` | How is an item judged independently of generator reasoning? |
| `validation/criteria.yaml` | Which item-quality criteria are required for acceptance? |
| `folds/reference.yaml` | Which cells are development, compositional holdout, or novel-feature holdout? |
| `simulation/world.yaml` | What hidden synthetic population, difficulty, noise and learning assumptions generate outcomes? |
| `kc/policies/factorized.yaml` | What does the marked-feature factorized KC hypothesis assert? |
| `kc/policies/interactions.yaml` | Which explicit interactions augment the factorized hypothesis? |
| `kc/policies/full_cell.yaml` | What does the exact-cell KC baseline assert? |
| `kc/candidates.yaml` | Which feature and interaction hypotheses may selection consider? |
| `kc/obligations.yaml` | Which development distinctions must a selected policy preserve? |
| `kc/selector.yaml` | How are supported alternatives selected and pruned? |
| `kt/protocol.yaml` | Which KT techniques and scientifically meaningful parameters run? |
| `evaluation/protocol.yaml` | Which dataset, representation and KT metrics are primary or diagnostic? |

## Outputs

A run retains the resolved experiment, seeds and model settings, final stage
records, and compact per-call LLM evidence:

```text
run/
├── resolved_experiment.yaml
├── run_settings.json
├── normalisation/
│   ├── mappings.jsonl
│   └── calls/.../{input.json,rendered_prompt.txt,raw_output.txt,parsed_result.json}
├── canonical/cells.jsonl
├── items/
│   ├── candidates.jsonl
│   ├── validation.jsonl
│   ├── accepted.jsonl
│   └── bank_summary.json
├── fold/assignments.jsonl
├── simulation/events.jsonl
├── kc/{frozen_policy.yaml,projection.jsonl,q_matrix.csv}
├── kt/predictions.jsonl
└── evaluation/results.json
```

The simulation oracle debug file is private explanatory evidence. It is never
passed to KC selection, projection, or KT.

## Running

`experiments/base.yaml` declares the live pilot models. The self-contained
`experiments/fixture.yaml` changes only the three model settings to
deterministic fixture responses, so the complete pipeline is also runnable
without a paid or networked call:

```bash
.venv/bin/python scripts/run.py fixture --output runs/readable_fixture
.venv/bin/python scripts/run_one.py normalisation
.venv/bin/python scripts/run_one.py generation
.venv/bin/python scripts/run_one.py validation
```

Run the four small modularity interventions with:

```bash
.venv/bin/python scripts/run_experiments.py --output runs/modularity_experiments
```

They check a normalisation-prompt intervention, a generation-prompt
intervention, factorized/full-cell/interaction KC policies on identical items
and events, and all three KT techniques on one event stream. These tiny fixture
experiments establish code-level modularity and inspectability, not scientific
superiority.

Run the scientific-contract tests with:

```bash
.venv/bin/python -m pytest -q
```

[`notebooks/walkthrough.ipynb`](notebooks/walkthrough.ipynb) is a compact,
executable view of the same real stage functions.

## Scope and claim boundaries

EGP is currently the only resource. The boundary permits a later resource to
provide its own typed schema and normalisation specification, but resource
merging, conflict resolution, adapters, and registries are intentionally out
of scope.

English generation is currently encoded in English prompts, an English
rulebook, the six English GrammarCell dimensions, and a small English lexicon.
A different language would need new resource normalisation, a new canonical
schema and constraints, language-specific generation guidance and lexical
evidence, revised fold semantics, and likely different simulation activations
and KC candidates.

The fixed synthetic world is a controlled data-generating process. Its hidden
dimensions are not claimed to be true human knowledge components, and its
outcomes do not establish pedagogical or cognitive validity. Fixture LLM
responses establish reproducible software behavior only; live annotation and
human review remain necessary for substantive dataset claims.
