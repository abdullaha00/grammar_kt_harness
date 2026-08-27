# Grammar–KT research harness

```text
Typed EGP resource
→ normalisation
→ canonicalisation
→ LLM item generation
→ independent item validation
→ grammar fold
→ ontology-independent simulation
→ KC representation
→ item–KC projection
→ knowledge tracing
→ evaluation
```

Open [`scripts/run.py`](scripts/run.py) first.

It names every active research declaration and passes the loaded objects
directly to the stage functions in methodological order. A researcher can see
the prompts, schemas, rulebooks, design, format, lexicon, fold, simulation
world, KC policy, KT protocol, and evaluation protocol without resolving an
experiment configuration.

> The repository deliberately avoids a generic experiment/configuration
> framework. Scientific declarations are loaded explicitly in the runner and
> passed directly to stage functions so that the executable code mirrors the
> methodology.

## Repository structure

```text
modules/          scientific declarations
src/grammar_kt/   scientific transformations
scripts/run.py    explicit baseline wiring and artifact writes
```

`modules/` has five scientific groups:

```text
modules/
├── grammar/       # typed EGP evidence, two-phase normalisation, GrammarCell schema
├── items/         # generation and independent validation declarations
├── simulation/    # grammar fold and synthetic world
├── kcs/           # predefined policies and development-only selection declarations
└── evaluation/    # KT and evaluation protocols
```

There is intentionally no experiment inheritance, deep merge, path resolver,
registry, workflow engine, stage cache, or `Pipeline` class. Small
interventions duplicate a short amount of wiring and replace the one scientific
object being changed.

## Scientific stages

| Stage | Direct inputs | Active declaration |
|---|---|---|
| Typed resource | selected EGP JSONL, resource schema | `modules/grammar/resource/egp/schema.yaml` |
| 1. Normalisation | typed records, two prompts, rulebook, canonical schema, model settings | `modules/grammar/resource/egp/normalisation/*` |
| 2. Canonicalisation | mappings, canonical schema | `modules/grammar/canonical/schema.yaml` |
| 3. Item generation | cells, prompt, rulebook, design, format, lexicon, model settings | `modules/items/generation/*` |
| 4. Item validation | candidates, intended cells, prompt, criteria, model settings | `modules/items/validation/*` |
| 5. Grammar fold | cells, fold specification | `modules/simulation/folds/reference.yaml` |
| 6. Simulation | accepted items, grammar fold, world | `modules/simulation/world.yaml` |
| 7. KC representation | predefined policy, or development records plus selection declarations | `modules/kcs/*` |
| 8. KC projection | accepted items, cells, frozen policy | mechanical transformation |
| 9. Knowledge tracing | fixed events, fixed projection, protocol | `modules/evaluation/kt/protocol.yaml` |
| 10. Evaluation | stage records, evaluation protocol | `modules/evaluation/protocol.yaml` |

The central experimental boundary is:

> Items and learner outcomes are fixed before candidate KC representations are
> compared. Candidate KCs never influence item generation or simulation.

The grammar fold is separate from the temporal KT split. The grammar fold asks
whether a GrammarCell is available during KC selection, recombines known
feature values, or contains a feature value unseen in development. Each learner
event also receives a chronological train/validation/test assignment for KT.

## Research declarations

| File | Scientific choice |
|---|---|
| `grammar/resource/egp/schema.yaml` | EGP evidence fields at the typed-resource boundary |
| `grammar/resource/egp/normalisation/phase1.txt` | descriptor-only normalisation |
| `grammar/resource/egp/normalisation/phase1_self_check.txt` | explicit Phase-1 self-check intervention |
| `grammar/resource/egp/normalisation/phase2.txt` | example-eligible refinement |
| `grammar/resource/egp/normalisation/rulebook.md` | EGP-to-English mapping rules and exclusions |
| `grammar/canonical/schema.yaml` | six-dimensional GrammarCell hypothesis |
| `grammar/canonical/rationale.md` | scope and representation rationale |
| `items/generation/prompt.txt` | baseline item-generation task |
| `items/generation/prompt_contextual.txt` | contextual generation intervention |
| `items/generation/rulebook.md` | English realization rules |
| `items/generation/design.yaml` | variants and balancing choices |
| `items/generation/formats/controlled_production.yaml` | learner-facing item contract |
| `items/generation/lexicon.jsonl` | controlled lexical material |
| `items/validation/prompt.txt` | independent judging task |
| `items/validation/criteria.yaml` | acceptance criteria |
| `simulation/folds/reference.yaml` | frozen grammar-level split |
| `simulation/world.yaml` | synthetic population, difficulty, response, and learning assumptions |
| `kcs/policies/factorized.yaml` | factorized KC hypothesis |
| `kcs/policies/interactions.yaml` | interaction-augmented hypothesis |
| `kcs/policies/full_cell.yaml` | exact-cell hypothesis |
| `kcs/candidates.yaml` | development-only selectable candidate space |
| `kcs/obligations.yaml` | distinctions selected policies must preserve |
| `kcs/selector.yaml` | deterministic selection rule |
| `evaluation/kt/protocol.yaml` | empirical, BKT, and logistic KT settings |
| `evaluation/protocol.yaml` | dataset, representation, and KT metrics |

All paths in this table are relative to `modules/`.

## Outputs

The runner writes each artifact immediately after the stage that creates it:

```text
run/
├── run_settings.json
├── normalisation/
│   ├── mappings.jsonl
│   └── calls/.../{input.json,rendered_prompt.txt,raw_output.txt,parsed_result.json,model_settings.json}
├── canonical/cells.jsonl
├── items/
│   ├── candidates.jsonl
│   ├── validation.jsonl
│   ├── accepted.jsonl
│   └── bank_summary.json
├── fold/assignments.jsonl
├── simulation/{events.jsonl,oracle_debug.json}
├── kc/{frozen_policy.yaml,projection.jsonl,q_matrix.csv}
├── kt/predictions.jsonl
└── evaluation/results.json
```

The simulation oracle is private explanatory evidence. It is never passed to
KC selection, projection, or KT.

## Running

The baseline runner uses the live models declared near the top of
`scripts/run.py`:

```bash
.venv/bin/python scripts/run.py --output runs/baseline
```

Deterministic fixture responses exercise the same stage functions without paid
or networked model calls:

```bash
.venv/bin/python scripts/run.py --fixture --output runs/fixture
.venv/bin/python scripts/run_one.py normalisation
.venv/bin/python scripts/run_one.py generation
.venv/bin/python scripts/run_one.py validation
```

Run the small modularity interventions with:

```bash
.venv/bin/python scripts/run_experiments.py --output runs/modularity_experiments
```

They compare the baseline and self-check normalisation prompts, compare the
baseline and contextual generation prompts on fixed cells, apply factorized,
full-cell, and interaction policies to identical accepted items and events,
and run empirical, BKT, and logistic KT on the same event stream and
projection. The checks use direct Python record equality; they make no
scientific-superiority claim.

Run the scientific-contract tests with:

```bash
.venv/bin/python -m pytest -q
```

[`notebooks/pipeline_walkthrough.ipynb`](notebooks/pipeline_walkthrough.ipynb)
is an executable, fixture-backed walkthrough. It loads and displays each
scientific declaration directly before passing it to the relevant stage.

## Scope and claim boundaries

EGP is the only resource. Resource adapters, resource registries,
cross-language dispatch, and conflict-merging frameworks are intentionally out
of scope.

English generation is encoded by the English prompts, rulebook, six
GrammarCell dimensions, and controlled lexicon. Supporting another language
would require new scientific declarations rather than a generic dispatch
layer.

The synthetic world is a controlled data-generating process. Its hidden
dimensions are not claimed to be true human knowledge components, and its
outcomes do not establish pedagogical or cognitive validity. Fixture responses
establish reproducible software behavior only; live annotation and human review
remain necessary for substantive dataset claims.
