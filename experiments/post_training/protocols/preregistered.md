# Preregistered diagnostic programme

This file was written before executing the experiments below. The programme is
deliberately diagnostic: it asks whether the current artifacts contain usable
post-training supervision before attempting SFT, preference optimization, or
reinforcement learning.

## Evidence boundary

The archived `runs/base` directory contains the 24-cell canonical inventory and
source edges, but it predates the current ontology-independent fixed item bank.
The external EGP snapshot required for a fresh source-to-KT run is not present.
Therefore the experiments use the archived canonical inventory as a declared
input and regenerate current deterministic items, KC projections, Q-matrix
diagnostics, and synthetic learner records. They do not reuse the archived
policy-specific item or simulation outputs and do not claim to be a fresh full
pipeline run.

## Experiment 1: record feasibility and near-miss preferences

**Hypothesis.** A shared latent grammar opportunity can yield at least 100
traceable post-training preference pairs and at least 500 SFT views without
inventing arbitrary bad responses. Hamming-one alternatives with identical
realization nuisance conditions will be fluent but wrong for exactly one
canonical dimension.

**Motivation.** This establishes whether the pipeline already contains enough
machine-checkable supervision to justify any later training.

**Independent variable.** Record view (controlled generation, exercise solving,
diagnosis, correction, grammaticality judgement, preference, verifier,
dialogue, or trajectory).

**Dependent variables.** Record count; canonical/KC/fold/format coverage;
deterministic pair validity; pair counts by differing dimension; duplication;
and response-only shortcut accuracy.

**Controls.** One canonical inventory, current realizer, fixed lexicon, fixed
item template, factorized KC policy, reference fold, seed 20260825, and exact
nuisance signature (frame, subject, WH role, and imperative subtype) within a
preference pair.

**Decision criterion.** Proceed to candidate-model diagnostics only if there
are at least 100 pairs, at least 10 for every observed error dimension, all
pairs pass deterministic validation, and a response-only character n-gram
classifier is no better than 0.65 grouped accuracy. The last threshold rejects
datasets where “bad” answers have an easy context-free style signature.

**Commands.**

```bash
.venv/bin/python experiments/post_training/scripts/build_records.py
.venv/bin/python experiments/post_training/scripts/evaluate_feasibility.py
```

## Experiment 2: zero-shot conditioning ablation

**Hypothesis.** Explicit realization constraints will have the highest exact
structural pass rate. Raw canonical structure may outperform a prose grammar
description, but this comparison is exploratory because model familiarity with
field names is unknown.

**Motivation.** Before fine-tuning, measure which existing representation adds
information in prompting and whether canonical conditioning is useful without
the full deterministic prompt.

**Independent variable.** (1) natural-language grammar description, (2) raw
canonical cell plus realization specification, or (3) canonical cell plus the
existing explicit realization constraints.

**Dependent variables.** Exact target-realization accuracy; one-sentence format
compliance; accuracy by canonical dimension/value; and error category inferred
when the output exactly matches another controlled realization.

**Controls.** The same 24 canonical opportunities (one deterministic item per
cell), lexical frames, subject conditions, model, batched call shape, and
evaluation code.

**Decision criterion.** A representation is worth exposing as model input if
it improves exact accuracy by at least 10 percentage points without reducing
format compliance. Any result remains provisional because there is one model,
one prompt version, and an unpinned service snapshot.

**Commands.**

```bash
.venv/bin/python experiments/post_training/scripts/run_model_diagnostics.py generation
.venv/bin/python experiments/post_training/scripts/evaluate_model_diagnostics.py
```

## Experiment 3: independent preference judgement and order sensitivity

**Hypothesis.** A model judge given the target cell and two fluent Hamming-one
candidates will select the deterministically valid response at least 90% of the
time. Reversing A/B order should change no more than 10% of decisions.

**Motivation.** Deterministic validity proves how pairs were constructed, but
an independent judge tests whether the distinction is legible to a general
instruction model and exposes positional bias.

**Independent variable.** Candidate order (seeded order versus exact reversal).

**Dependent variables.** Judge preference accuracy, error-dimension accuracy,
order consistency, and schema/coverage failures.

**Controls.** A stratified sample of 12 pairs per observed error dimension,
the same prompt and model, anonymized condition identity, and exact output
schema.

**Decision criterion.** If preference accuracy is below 0.90 or order
inconsistency exceeds 0.10, the pairs should not be used as soft pedagogical
preference labels. They may still be used for deterministic structural
verification.

**Commands.**

```bash
.venv/bin/python experiments/post_training/scripts/run_model_diagnostics.py preference
.venv/bin/python experiments/post_training/scripts/evaluate_model_diagnostics.py
```

## Explicitly deferred training experiments

Tiny SFT is conditional on Experiments 1–2 and on an available, versioned
training stack/checkpoint. Preference optimization is conditional on a useful
SFT baseline and validated hard pairs. Neither `torch`, `transformers`, `peft`,
nor `trl` is installed in the recorded environment, no local checkpoint or GPU
is available, and installing a stack or downloading a model would be a much
larger intervention than a diagnostic study. A failed attempt is therefore not
manufactured: training is recorded as **not run by design**.

Sequential RL is also not run. The current simulator updates mastery after an
item outcome but has no alternative tutor-action effects, delayed retention
outcome, or human-calibrated transition model. An action policy optimized in it
would learn the simulator's declared mechanics, not provide evidence of good
tutoring.
