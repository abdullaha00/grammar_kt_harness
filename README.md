# Grammar–KT experimental harness

This repository is a small research laboratory for the fixed pipeline:

```text
source → normalisation → canonical → realisation → fixed item bank
       → fixed simulation → kc_selection → kc → Q-matrix → KT
```

The scientific methodology remains explicit and replaceable:

- `modules/` — prompts, rulebooks, policies, item families, lexicons, parameters, and tiny fixtures;
- `src/grammar_kt/` — Python that executes those choices;
- `scripts/` — researcher-facing run, sampling, inspection, comparison, and validation commands;
- `experiments/` — small combinations of scientific choices;
- `runs/` — generated observations and model evidence;
- `tests/` — software and boundary tests.

Start with the [research map](docs/research-map.md) and the concise
[component method guides](docs/modules/) to see which files correspond to each
paper question.

Q-matrix generation is implementation, not a separate scientific choice. Run metadata records the Git commit/dirty state, resolved experiment, seed, and external source SHA-256. There is no provenance stage, fingerprint graph, or automatic cache.

## Install and run

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e .
python scripts/run.py base
```

The baseline needs the external EGP source identity declared in
`experiments/base.yaml`. Set `GRAMMAR_KT_EGP_SOURCE` to the exact JSONL file, or
set `GRAMMAR_KT_DATA_ROOT` to its directory. The declared SHA-256 remains
mandatory. The configured models are invoked for normalisation and item
diagnostics; their evidence is retained under the relevant unit directory.

Run one example without constructing an experiment:

```bash
python scripts/run_one.py realisation --fixture lexical_present_question
python scripts/run_one.py kc_selection --fixture structural_selection
python scripts/run_one.py kc --fixture perfect_progressive --policy factorized
python scripts/run_one.py items --fixture valid_deterministic_item
python scripts/run_one.py simulation
python scripts/run_one.py kt --fixture frozen_compositional_probe
```

For a compact, executable tour with one fixed input and real call per pipeline
component, open [`notebooks/module_unit_examples.ipynb`](notebooks/module_unit_examples.ipynb).
The normalisation cell makes one call through the configured model backend.

`run_one.py` prints `BEFORE` and `AFTER`. It accepts a bundled
fixture or an explicit one-record JSON file; it never searches saved runs.
Normalisation uses the configured model and defaults to the first fixture:

```bash
python scripts/run_one.py normalisation --phase1-only
python scripts/run_one.py normalisation --egp-id EGP_ID
python scripts/run_one.py kc --input /tmp/opportunity.json
```

Use `--output /tmp/my-debug-run` to retain one-off evidence at a chosen location.

## KC selection and policy baselines

`kc_selection` is the development-only Phase-A structural selector. It builds
canonical and operation-evidence candidates, checks operation candidates over a
deterministic nuisance-realisation grid, collapses identical development
activation columns, covers salient facts and Hamming-one contrasts, and freezes
an ordinary KC policy before inspecting either holdout. Run the declared
structural condition with:

```bash
python scripts/run.py kc_selected_structural --from kc_selection
python scripts/compare.py base kc_selected_structural --stage kc_selection
```

Its inspectable outputs are `candidates.jsonl`, `activations.jsonl`,
`diagnostics.jsonl`, `selection_trace.jsonl`, `selected_policy.json`, and
`evaluation.json`. `kc.py` still performs deterministic policy application and
materialisation; it reads the frozen `selected_policy.json` without selecting
or inventing KCs.

The explicit fold manifest distinguishes `compositional_holdout` (only development-
seen salient facts in new combinations) from `novel_feature_holdout` (at least
one unseen fact). The fold is separate from realisations and items. All 24 cell assignments are explicit and exact-inventory
validation prevents new cells from silently defaulting into development.
Candidate discovery, support, equivalence classes, scope
checks, contrasts, and selection use development cells only. The current
factorized, interaction, and transductive full-cell policies remain explicit
baselines, and selection evaluation also constructs an honest full-cell policy
from development cells only.

`kc_factorized_dev_frozen` is a second inductive control. It starts from the
expert factorized hypothesis space but retains only rules activated by
development item opportunities, then freezes that reduced policy before
holdout application. Baseline prior-information categories remain explicit:
selected structural, factorized-development-frozen, and full-cell-development-
frozen are inductive; the current factorized policies are expert priors; and
full-cell-all is transductive.

KC selection deliberately does not read item-bank, simulation, Q-matrix, or KT
artifacts. The simulator now runs before selection, so selection and every
ontology variant reuse the same fixed learner-item outcomes by construction.

## Fixed item bank and KC projection

The item stage now runs before KC selection. It deterministically covers every
canonical cell, source-licensed imperative subtypes, WH roles, lexical versus
copular operator sources, and representative finite-agreement profiles. Item
existence, lexical conditions, prompts, answers, IDs, validation, and the saved
intrinsic bank SHA-256 contain neither fold assignments nor KC labels. A fold is
applied as a runtime view only when selection, simulation, materialisation, or
KT needs experimental roles.

Removing the old intrinsic `canonical_split` field intentionally migrates the
reference bank fingerprint from
`16a220cff3af8c87c2be1fbe13aab990146a38d91b3c0c5b20f64bfa8ae4fbb2` to
`ad5eed4498eb9fcb236a41ae8d0d2b8f3751e4c0cb30854e5b5a2eb1855bc02e`.
The 58 item IDs, RealizationSpecs, prompts, answers, frames, and lexical
conditions are unchanged. The new hash identifies the reusable
split-independent bank.

After a policy is frozen, `kc` applies it to every accepted concrete item
realization and writes `item_kc_projection.jsonl` and
`projected_kc_inventory.jsonl`. `qmatrix` mechanically converts that projection
to its edge list and matrix. Operation rules can therefore vary across two
items from the same cell while cell-scope rules remain invariant. To compare
ontologies on the exact parent data, run variants from `kc_selection`; both the
item bank and simulation are copied and their reuse is recorded:

```bash
python scripts/run.py kc_selected_structural --from kc_selection
python scripts/run.py kc_interactions --from kc_selection
python scripts/compare.py base kc_selected_structural --stage items
python scripts/compare.py base kc_selected_structural --stage qmatrix
```

`kc_full_cell_dev_frozen` is the honest exact-cell control compiled from
development cells only. Its held-out bank rows remain present with zero active
KCs, and all fixed events for those items remain present. KT reports ontology
coverage separately and uses a learner-global smoothed pre-event prior as the
same fallback for every technique on zero-KC events.

## Fixed structural simulation oracle

The simulation stage reads only accepted items, canonical cells, the declared
simulation config, and its seed. `STRUCTURAL_ORACLE_v0` deterministically maps
items to ten controlled data-generating dimensions: finite form, finite
agreement, perfect, progressive and passive dependencies, negation, operator
inversion, do-support, central modal structure, and imperative structure. These
are simulation primitives, not claimed human KCs. WH is absent because the
current fixed inventory has no observed WH item; subject- and non-subject-WH
realisation support is nevertheless covered by explicit regression fixtures.
Each oracle feature's activation rule is declared in the JSON config rather
than dispatched by a Python feature-name table.

For an item with active oracle set `A`, the pre-response score is the mean of
the logits of the learner's pre-event mastery over `A`, minus the item-ID-hashed
difficulty and `oracle_complexity_penalty × (|A|-1)`. The configured sigmoid,
floor, and span turn that score into a probability. Only oracle mastery is
updated after an outcome. Evaluated policies, Q columns, and candidate KC counts
are never inputs.

The public `base_events.jsonl` contains event, learner, item, canonical and
temporal split identities, timestamp, difficulty, and correctness—no KC or
oracle fields. Private `oracle_interactions.jsonl` and
`learner_parameters.oracle.jsonl` retain reproducibility evidence. After KC
materialisation, KT joins `base_events.jsonl` with
`kc/item_kc_projection.jsonl` and derives candidate-specific KC opportunity
indices in `kt/projected_interactions.jsonl`. The fixed event-stream SHA-256 is
persisted in `simulation/audit.json` and surfaced by `compare.py`.

## Development acquisition and frozen compositional probes

The ordinary two-pass chronological train/validation/test stream remains a
technical KT sanity benchmark. Phase D adds a separate stream under
`simulation/compositional/`: every learner acquires only development-cell items
over two shuffled passes, after which the oracle mastery state is frozen. Each
of the 17 compositional-holdout items and the one novel-feature item is then
probed once. Every probe probability and outcome reads the same frozen
post-development oracle state; probes never update that state, and keyed probe
draws make results independent of probe ordering.

For each candidate ontology, `kt/compositional/` projects KCs onto the fixed
acquisition and probe events. Empirical histories, BKT mastery, and logistic
features are learned from development acquisition only and frozen before every
probe. A probe is labelled fully development-supported, cold, or uncovered.
Cold KCs use a fixed training-independent prior; uncovered probes use the
learner-global smoothed development prior and remain in all-event metrics.
Metrics report log loss (primary), Brier score, AUC, accuracy, calibration,
coverage, and development-supported coverage separately for compositional and
novel-feature probes. `compare.py --stage compositional` verifies fixed probe
equality and computes paired learner-level bootstrap intervals; `inspect.py
probe EVENT_ID` shows the fixed-data, private-oracle, and candidate-model
boundaries explicitly.

This protocol measures transfer of learner evidence under one controlled,
factorized synthetic world. A higher score is not evidence that an ontology is
a cognitively correct model of human grammar learning.

## Predefined KC policy experiment example

1. Copy `modules/kc/policies/factorized.json` to `modules/kc/policies/new_policy.json` and edit its rules. KC policies can use `cell`, `operation`, `all`, and `any`; the oracle compiler additionally supplies `agreement_site` and `frame_type`. No Python change is needed for a policy using the KC primitives.
2. Test one case:

   ```bash
   python scripts/run_one.py kc --fixture perfect_progressive --policy new_policy
   ```

3. Declare only the intervention in `experiments/kc_new_policy.yaml`:

   ```yaml
   extends: base
   experiment: kc_new_policy

   kc_selection:
     mode: predefined
     policy: modules/kc/policies/new_policy.json
   ```

4. With `runs/base/` already present, explicitly reuse its pre-selection outputs and execute selection onward:

   ```bash
   python scripts/run.py kc_new_policy --from kc_selection
   python scripts/compare.py base kc_new_policy --stage kc_selection
   ```

   Runs created before fold/item decoupling must be regenerated from
   `realisation` or earlier; their intrinsic item records contain obsolete fold
   metadata and intentionally have the legacy bank hash.

`--from` is intentionally explicit. Before copying earlier stage outputs, it
compares the parent and child inputs for every reused stage, recursively hashing
referenced module configs. A mismatch refuses reuse with the affected stage and
hashes. This is a safety check, not hidden caching or a workflow DAG.

## Inspect, compare, validate

```bash
python scripts/inspect.py normalisation EGP_ID --run base
python scripts/inspect.py kc CELL_ID --run base
python scripts/inspect.py item ITEM_ID --run base
python scripts/inspect.py qmatrix ITEM_ID --run base
python scripts/inspect.py kt EVENT_ID --run base
python scripts/inspect.py probe COMP_PROBE_EVENT_ID --run base
python scripts/inspect.py trace ITEM_ID --run base

python scripts/compare.py base kc_full_cell
python scripts/compare.py base kc_full_cell --stage kc
python scripts/compare.py base kc_interactions --stage compositional
python scripts/validate.py base
```

Experiment variants inherit recursively and deep-merge mappings; lists replace atomically. For example, `experiments/kc_full_cell.yaml` changes only `kc_selection.policy`, while `experiments/kt_bkt_only.yaml` changes only `kt.techniques`. Run the latter with `--from kt` to consume the exact parent observable dataset without rerunning upstream stages.

Experiment execution accepts only short names from `experiments/*.yaml`. The
loader has one interface: `settings, parent = load_experiment("kc_full_cell")`.

Item generation makes one deterministic construction pass per grammatical/item
opportunity and retains its concrete realization evidence and coverage reason.
The simulator derives events per learner from every fixed accepted item and the
configured item passes, then derives train/validation boundaries from fractions.
Q-matrix integrity errors remain fatal; uncovered rows, redundancy, density,
support, scope, and wide rows are saved as scientific diagnostics so policy
variants can complete without changing the accepted bank or event stream.

The reference numbers in `reference/current/expected_counts.json` are operational/technical checks, not evidence of human learning, KC cognitive validity, or acquisition order.
