# Controlled-instrument structural scenario v1

Status: `FROZEN_STRUCTURE_ONLY_BEFORE_RESPONSES`

This is not a learner-facing item bank, platform dataset, or release candidate.
It is a deterministic structural scaffold for controlled simulator experiments
after the preregistered matched-bank campaign failed its own validity gates.

## Why this separate scenario exists

The completed three-round matched-bank campaign attempted 38 families. Only
five whole families passed all frozen gates, so the required 38-family,
152-item curated bank could not freeze. Rejected candidate content remains
rejected. Neither rejected nor accepted wording is copied into this scaffold.

The scaffold asks a narrower question:

> Given the already frozen 18-cell full-rank Q design, what behavior is induced
> by planted item-label, format-label, learner, error-information, and schedule
> effects in a content-free controlled measurement instrument?

It cannot answer whether a learner would understand an item, whether an answer
space is fair, or whether a platform would deploy the opportunity.

## Construction

The only structural source is the frozen outcome-free selection:

- 18 seen cells, two replicate labels, four format labels: 144 slots;
- one unseen-combination and one unseen-value cell, one replicate label and
  four format labels: eight non-updating probe slots;
- 38 families and 152 slots total;
- the selected Q row is copied exactly into every slot;
- the 18 distinct seen-cell rows retain rank 18.

`replicate_index` is a structural replicate label, not a claim that two valid
semantic variants exist. `format_label` is an experimental nuisance label, not
an instantiated task. Every row states that it has no prompt, target answer, or
accepted response space.

## Hard claim boundary

Permitted descriptions:

- controlled-instrument scaffold;
- structure-only scenario;
- content-free crossed format labels;
- synthetic response experiment over planted measurement nuisance.

Prohibited descriptions:

- validated item bank;
- realistic or platform-plausible dataset;
- learner-facing opportunity;
- deployable exercise;
- evidence that format effects have the planted human magnitude;
- replacement for the failed curated bank.

No artifact from this scenario is release-eligible. Its results, if later
authorized, must be segregated from curated-platform evidence and labelled as
controlled structural sensitivity analyses.

## Runner gate

The world runner accepts this schema only when all of the following hold:

1. the controlled scenario config and all content-addressed inputs verify;
2. `--controlled-scenario` is supplied at planning, response, analysis, and
   aggregation stages;
3. the plan status is the controlled-scenario status, not the curated status;
4. all 152 rows satisfy the dedicated schema and deterministic invariants;
5. the run manifest remains `release_eligible=false`.

The existing curated-bank path remains unchanged and rejects this scaffold.

## Adaptive-policy boundary

The adaptive schedule is an intentionally favourable controlled policy. It may
use the frozen instrument's declared KC/Q design map to organize item history,
but it may not read latent learner mastery, response probabilities, planted
effects, failed-KC attribution, or future outcomes. This oracle-aligned design
map would not ordinarily be trustworthy in a real log; it is available here
only because the controlled scenario asks what follows if a platform's skill
map equals the declared generator map. Adaptive-schedule findings must retain
that qualification and cannot be presented as evidence about a discovered or
human-valid skill map.

## Rebuild

```bash
.venv/bin/python \
  experiments/measurement_realism/design/controlled_instrument_v1/build_scaffold.py
```

The builder is idempotent only for byte-identical outputs and refuses to
overwrite drifted frozen artifacts.
