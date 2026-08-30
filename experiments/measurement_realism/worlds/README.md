# Measurement-realism worlds

Status: the production curated-bank path remains unexecuted because its
measurement gate failed. A separate, explicitly non-release controlled
instrument scenario has been executed: 27 response runs, 18 preregistered
Q-balanced A--D analyses, three structured-error analyses, and a frozen
cross-world aggregate. The controlled instrument contains structure and format
labels but no learner-facing prompts or answer spaces. It is sensitivity
evidence, not a platform-plausible dataset. Fixture rows remain contract tests
and are not scientific evidence.

The frozen study plan is in `controlled_instrument_v1/study_plan.json`; the
append-only authorization/execution disclosure is in
`controlled_instrument_v1/execution_authorization.json`. The latter does not
retroactively alter the preregistration. Aggregate results are under
`controlled_instrument_v1/aggregate/`.

The executable design is frozen in
`../design/scenario_config_v1.yaml`. It content-addresses the original proposal
and the 20-cell selection before any confirmatory responses can be generated.
The runner then requires a second frozen `study_plan.json` that hashes the
curated bank, its schema, the implementation, and the final acquisition budget.
Any changed byte makes the response stage fail closed.

## Curated-bank contract

The future bank must contain exactly 152 hard-gate-passing items:

- 144 acquisition items: 18 seen cells x 4 formats x 2 semantic variants;
- 8 non-updating probes: 2 held-out cells x 4 formats x 1 variant;
- identical Q* within each matched cell/variant family;
- exact cell-level seen-Q rank 18.

The current selected bank gives an acquisition budget of 188 events per learner
under `exhaustive_then_q_balanced`: 144 exhaustive exposures plus 44 top-ups to
reach at least 12 opportunities for every generator KC. The proposal's value of
184 was an illustrative earlier rank witness, not the selected bank. The final
budget is calculated from the curated bank and frozen in the run plan before
responses.

## Implemented controls

`scripts/experiments/measurement_realism_worlds.py` directly implements:

- six keyed common-random-number worlds, including exact clean-zero response
  equivalence;
- seen-item effects orthogonal to intercept, format, and Q*, with separate
  explicitly non-estimable held-out probe sensitivity effects;
- an experimental Q*-balanced benchmark plus equal-budget curriculum,
  mixed-practice, and adaptive alternatives that use only GrammarCell/item
  metadata and observable histories (not generator K*/Q* or mastery), with
  recorded propensities;
- disjoint observable and learner-oracle streams;
- binary, linked, 80%-linked, and within-item-shuffled error streams;
- observable-distribution and design-linked exposure diagnostics;
- causal-history A--D bounded-logistic models with learner-disjoint
  train/dev/test partitions, train-only scaling, dev-only regularization
  selection, and learner-paired intervals;
- an error-history comparison that holds model D fixed across all four error
  streams;
- seen-probe primary metrics with unseen-combination and unseen-value results
  reported separately, plus three-seed/cross-world aggregation of the four
  preregistered contrasts.

The planted `failed_kc` field is a post-outcome, deficit-proportional diagnostic
attribution. It is not represented as a unique causal explanation of an error:
slip, format, item, and other measurement nuisance may also produce failure.

## Production curated-bank commands

Validate the frozen inputs:

```bash
.venv/bin/python scripts/experiments/measurement_realism_worlds.py \
  --stage validate-config
```

Create a visibly non-linguistic fixture for contract inspection:

```bash
.venv/bin/python scripts/experiments/measurement_realism_worlds.py \
  --stage make-fixture \
  --bank /tmp/measurement_realism_fixture.jsonl
```

After a curated run exists, validate and freeze its confirmatory plan:

```bash
.venv/bin/python scripts/experiments/measurement_realism_worlds.py \
  --stage validate-bank \
  --bank experiments/measurement_realism/design/bank_protocol/runs/RUN_ID/bank/items.jsonl

.venv/bin/python scripts/experiments/measurement_realism_worlds.py \
  --stage plan \
  --bank experiments/measurement_realism/design/bank_protocol/runs/RUN_ID/bank/items.jsonl
```

Only then can `--stage run` create a non-overwritable response directory. A
planned run always uses the preregistered 500 learners; reduced learner counts
are accepted only by the in-memory fixture/testing API.

Response generation and fitted analysis are deliberately separate immutable
stages. After a response run completes:

```bash
.venv/bin/python scripts/experiments/measurement_realism_worlds.py \
  --stage analyze \
  --world clean_zero --seed 20260829 --policy q_balanced_lab
```

After all preregistered response runs and all Q-balanced model analyses exist,
the aggregate stage computes seed-specific, mean/range, learner-paired, and
cross-world difference-in-differences evidence:

```bash
.venv/bin/python scripts/experiments/measurement_realism_worlds.py \
  --stage aggregate
```

Focused verification:

```bash
.venv/bin/pytest -q tests/test_measurement_realism_worlds.py
```

## Executed controlled-instrument commands

The non-release path uses the isolated controlled config and requires the
explicit mode flag on every scientific stage:

```bash
.venv/bin/python scripts/experiments/measurement_realism_worlds.py \
  --stage validate-plan --controlled-scenario \
  --config experiments/measurement_realism/design/controlled_instrument_v1/scenario_config.yaml \
  --output-dir experiments/measurement_realism/worlds/controlled_instrument_v1

.venv/bin/python scripts/experiments/measurement_realism_worlds.py \
  --stage aggregate --controlled-scenario \
  --config experiments/measurement_realism/design/controlled_instrument_v1/scenario_config.yaml \
  --output-dir experiments/measurement_realism/worlds/controlled_instrument_v1
```

The three alternative-policy model fits are an append-only derived analysis,
not part of the original confirmatory analysis matrix. Their timing disclosure,
fixed estimands, input hashes, and commands are frozen in
`controlled_instrument_v1/policy_recovery_v1/plan.json` before those fits.
