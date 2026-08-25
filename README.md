# Grammar–KT research harness

This repository studies grammar knowledge representations through five scientific modules:

```text
Grammar Representation → Measurement → Dataset Generation
                       → Knowledge Representation → Evaluation
```

The active method fixes grammatical structure before asking a constrained LLM to choose natural lexical content and surface wording. The historical deterministic English realiser is retained only under [`archived_code/`](archived_code/) for reproducibility; active code does not import it.

## 1. Grammar Representation

**What grammatical structures exist?**

`Source → Normalisation → Canonical GrammarCells`

- Source verifies the declared EGP snapshot by SHA-256, selects explicit descriptors, restricts Phase-1 fields, and retains repeated annotation units and provenance.
- Normalisation keeps descriptor-only Phase 1 separate from eligible example-assisted Phase 2, uses fresh model contexts, validates/retries outputs, retains raw evidence, and reports repeated-normalisation reliability.
- Canonical validates exact six-field GrammarCells, derives stable `CELL_…` IDs, deduplicates cells, retains source→cell edges, and excludes partial mappings from exact cells.

## 2. Measurement

**Under which controlled structural conditions are cells elicited?**

`GrammarCell + structural conditions → operations → MeasurementOpportunity`

A `MeasurementOpportunity` has a stable `OPP_…` identity and contains only generator-invariant evidence:

```json
{
  "measurement_opportunity_id": "OPP_…",
  "canonical_cell_id": "CELL_…",
  "cell": {
    "tense": "past",
    "aspect": "none",
    "voice": "active",
    "polarity": "negative",
    "clause": "declarative",
    "modal": "none"
  },
  "structural_conditions": {
    "predicate_class": "lexical_transitive",
    "subject_person": 3,
    "subject_number": "singular",
    "wh_role": null,
    "imperative_subtype": null
  },
  "expected_operations": ["do_support", "negation"],
  "source_descriptor_ids": ["…"],
  "coverage_reasons": ["canonical_cell_baseline"]
}
```

Operations are derived by [`measurement/operations.py`](src/grammar_kt/measurement/operations.py) from the cell and structural conditions. The module has no lexicon and cannot generate English.

## 3. Dataset Generation

**How are opportunities presented naturally to learners?**

One public slot, `generate_items(opportunities, generator_config, ...)`, supports:

- `llm_standalone_v0` — the main constrained LLM condition;
- `llm_dialogue_v0` — the same opportunity presented in dialogue;
- deterministic fixture transports for tests and notebooks, not as the production methodology.

Both formats return the same item schema. They retain the same `measurement_opportunity_id` and `canonical_cell_id` but receive different content-derived `ITEM_…` IDs.

Validation has two independent layers:

1. hard schema/reference/leakage checks;
2. blind grammatical reconstruction from visible item content and learner response, without the intended target.

GrammarCell and operation exact-match are reported separately from naturalness, ambiguity, pedagogy, world-knowledge, lexical-level, and dialogue-quality diagnostics. All prompts, raw outputs, parsed outputs, attempts, rejections, and accepted candidates are retained.

## 4. Knowledge Representation

**Which KCs encode learner knowledge over opportunities?**

`candidate discovery → deterministic selection → frozen policy → application → Q-matrix`

Candidate discovery and selection receive development GrammarCells and MeasurementOpportunities only. Generated wording, item-bank outcomes, simulation, Q-matrix, and KT evidence are excluded. The selector retains explicit obligations, activation-equivalence collapsing, deterministic greedy selection, backward pruning, and a written-before-holdout frozen policy.

Policy rules use the small structural language `cell`, `operation`, `agreement_site`, `predicate_class`, `all`, and `any`. The same frozen policy applies to standalone and dialogue items without generator branches. The Q-matrix mechanically converts accepted item IDs and frozen projections into edges and diagnostics.

## 5. Evaluation

**Does the representation transfer and predict under controlled evidence?**

The structural oracle is independent of evaluated KCs. Latent difficulty and keyed outcome randomness use `measurement_opportunity_id`, so paired surface generators share controlled difficulty and outcomes. Folds remain runtime metadata and are absent from opportunity IDs, prompts, and item IDs.

KT retains observable histories, pre-event features, empirical/BKT/logistic baselines, development-only state accumulation, frozen compositional probes, cold-KC handling, zero-KC fallback, and probe-order invariance. Cross-format acquisition/probe conditions need no special KC logic.

## Active layout

```text
src/grammar_kt/
├── grammar/       # source, normalisation, canonical cells
├── measurement/   # operations and MeasurementOpportunities
├── generation/    # item schema, LLM generators, validation
├── knowledge/     # candidates, selection, policy, Q-matrix
├── evaluation/    # simulation and KT
├── backend.py
├── folds.py
├── records.py
├── config.py
├── io.py
└── runner.py

modules/
├── grammar/
├── measurement/
├── generation/
├── knowledge/
├── evaluation/
└── folds/
```

Code and methodological resources mirror one another; for example:

```text
src/grammar_kt/knowledge/selection.py
modules/knowledge/selection/
```

## Running the harness

Create/install the environment according to `pyproject.toml`, then:

```bash
.venv/bin/python scripts/run.py base
.venv/bin/python scripts/run.py dialogue
```

The external EGP snapshot is intentionally not committed. Configure it with `GRAMMAR_KT_EGP_SOURCE` or `GRAMMAR_KT_DATA_ROOT`; the declared SHA-256 and record count are checked before use.

Generator conditions are minimal interventions:

```yaml
extends: base
experiment: dialogue

generation:
  generator: modules/generation/generators/llm_dialogue_v0.yaml
```

Run individual fixture-backed transformations without a paid model call:

```bash
.venv/bin/python scripts/run_one.py measurement
.venv/bin/python scripts/run_one.py generation
.venv/bin/python scripts/run_one.py generation --dialogue
.venv/bin/python scripts/run_one.py validation
.venv/bin/python scripts/run_one.py selection
.venv/bin/python scripts/run_one.py simulation
.venv/bin/python scripts/run_one.py kt
```

Use `--live` on model-dependent `run_one.py` examples only when a real backend call is intended.

Run and retain the small A–F scientific checks:

```bash
.venv/bin/python scripts/run_scientific_checks.py --force
```

## Research notebooks and automated tests

- [`module_unit_examples.ipynb`](notebooks/module_unit_examples.ipynb) is the compact executable five-module tour.
- [`research_audit.ipynb`](notebooks/research_audit.ipynb) audits configuration, contracts, assumptions, leakage boundaries, examples, failures, and metrics for every box.
- [`tests/`](tests/) checks software and scientific boundaries; tests do not establish linguistic or cognitive validity.

Both notebooks execute with deterministic fixture transports. The smoke test executes every code cell in order, so public scientific-interface drift fails the suite.

```bash
.venv/bin/python -m pytest -q
.venv/bin/python scripts/validate.py runs/base
```

## Reproducibility and claim boundaries

Completed runs retain the exact command, resolved experiment config, git state, seed, source hash, stage input signatures, opportunity-bank fingerprint, generator identity and evidence, validation counts/evidence, simulation fingerprints, frozen-policy fingerprint, and representative artifacts.

Keep three claims distinct:

- **software correctness** — schemas, tests, reference checks, and deterministic invariants;
- **dataset validity** — blind reconstruction, quality diagnostics, and human review;
- **research evidence** — experimental results and their methodological interpretation.

See [`docs/research-map.md`](docs/research-map.md), [`docs/refactor-report.md`](docs/refactor-report.md), [`docs/scientific-checks.md`](docs/scientific-checks.md), and [`archived_code/deterministic_realiser_v0/README.md`](archived_code/deterministic_realiser_v0/README.md).
