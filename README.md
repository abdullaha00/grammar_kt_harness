# Grammar–KT experimental harness

This repository is a small research laboratory for the fixed pipeline:

```text
source → normalisation → canonical → realisation → KC selection
       → items → deterministic Q-matrix → simulation → KT
```

The scientific methodology remains explicit and replaceable:

- `modules/` — prompts, rulebooks, policies, item families, lexicons, parameters, and tiny fixtures;
- `src/grammar_kt/` — Python that executes those choices;
- `scripts/` — the five researcher-facing commands;
- `experiments/` — small combinations of scientific choices;
- `runs/` — generated observations and model evidence;
- `tests/` — software and boundary tests.

Q-matrix generation is implementation, not a separate scientific choice. Run metadata records the Git commit/dirty state, resolved experiment, seed, and external source SHA-256. There is no provenance stage, fingerprint graph, or automatic cache.

## Install and run

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e .
python scripts/run.py base
```

The baseline needs the external EGP source declared in `experiments/base.yaml` and invokes the configured models for normalisation and item diagnostics. Model evidence is retained under the relevant unit directory as `input.json`, `rendered_prompt.txt`, `invocation.json`, `raw_output.txt`, `parsed_output.json`, and `validation.json`.

Run one example without constructing an experiment:

```bash
python scripts/run_one.py realisation --fixture lexical_present_question
python scripts/run_one.py kc --fixture perfect_progressive --policy factorized
python scripts/run_one.py items --fixture valid_deterministic_item
python scripts/run_one.py simulation
```

For a compact, executable tour with one fixed input and real call per pipeline
component, open [`notebooks/module_unit_examples.ipynb`](notebooks/module_unit_examples.ipynb).
The normalisation cell makes one call through the configured model backend.

Each command prints `BEFORE` and `AFTER`. `run_one.py` accepts a bundled
fixture or an explicit one-record JSON file; it never searches saved runs.
Normalisation uses the configured model and defaults to the first fixture:

```bash
python scripts/run_one.py normalisation --phase1-only
python scripts/run_one.py normalisation --egp-id EGP_ID --experiment base
python scripts/run_one.py kc --input /tmp/opportunity.json
```

Use `--output /tmp/my-debug-run` to retain one-off evidence at a chosen location.

## KC experiment example

1. Copy `modules/kc/policies/factorized.json` to `modules/kc/policies/new_policy.json` and edit its rules. Supported rule primitives are `cell`, `operation`, and `all`; no Python change is needed for a policy using those primitives.
2. Test one case:

   ```bash
   python scripts/run_one.py kc --fixture perfect_progressive --policy new_policy
   ```

3. Declare only the intervention in `experiments/kc_new_policy.yaml`:

   ```yaml
   extends: base
   experiment: kc_new_policy

   kc:
     policy: modules/kc/policies/new_policy.json
   ```

4. With `runs/base/` already present, explicitly reuse its pre-KC outputs and execute KC onward:

   ```bash
   python scripts/run.py kc_new_policy --from kc
   python scripts/compare.py base kc_new_policy --stage kc
   ```

`--from` is intentionally explicit. It copies earlier stage outputs from the parent run and records that fact in `metadata.json`; it does not infer reuse from hashes.

## Inspect, compare, validate

```bash
python scripts/inspect.py normalisation EGP_ID --run base
python scripts/inspect.py kc CELL_ID --run base
python scripts/inspect.py item ITEM_ID --run base
python scripts/inspect.py qmatrix ITEM_ID --run base
python scripts/inspect.py kt EVENT_ID --run base
python scripts/inspect.py trace ITEM_ID --run base

python scripts/compare.py base kc_full_cell
python scripts/compare.py base kc_full_cell --stage kc
python scripts/validate.py base
```

Experiment variants inherit recursively and deep-merge mappings; lists replace atomically. For example, `experiments/kc_full_cell.yaml` changes only `kc.policy`, while `experiments/kt_bkt_only.yaml` changes only `kt.techniques`. Run the latter with `--from kt` to consume the exact parent observable dataset without rerunning upstream stages.

Item generation makes one deterministic construction pass per KC and retains
the selected opportunity, replicate, split, and lexical search offset. The
simulator derives events per learner from the accepted item count and configured
item passes, then derives train/validation boundaries from fractions. Q-matrix
integrity errors remain fatal; redundancy, density, support, and wide rows are
saved as scientific diagnostics so policy variants can complete.

The reference numbers in `reference/current/expected_counts.json` are operational/technical checks, not evidence of human learning, KC cognitive validity, or acquisition order.
