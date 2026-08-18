# Research harness design

## Four visible parts per module

Every `contract.yaml` declares INPUT, CONFIGURATION / SCIENTIFIC CHOICES, PROCEDURE, and OUTPUT. JSON Schemas type the stable records currently required. Stage entry/exit validation and the runner’s dependency graph enforce the boundaries; modules do not discover arbitrary run state.

Behavior-defining files are colocated: model prompts are standalone versioned text, rulebooks are plain files, backend settings are YAML, and deterministic policies/parameters are JSON. Python loads and substitutes declared placeholders; it does not hide substantial scientific instructions in string literals.

## Strict dataflow

- Source selects only the declared source records.
- Normalization reads source records and annotation units only.
- Canonical reads final mappings and carries source-edge notes forward once.
- Realization reads canonical cells and explicit source edges only.
- KC reads canonical cells and realization output; it cannot see item yield or KT.
- Items read realization and frozen KC projection; they cannot reopen raw EGP or normalization.
- Q-matrix reads accepted items and frozen KC activation; it performs no manual labeling or reinterpretation.
- Simulation reads accepted items and Q structure; its KC identifiers are exactly the declared Q columns.
- KT reads observable interactions only. Oracle state is excluded from its signature and manifest.
- Provenance reads declared interfaces and their manifests, but no simulator oracle or KT predictions.

## Model invocation evidence

Every model unit has a self-contained directory:

```text
units/<unit_id>/
  input.json
  rendered_prompt.txt
  invocation.json
  raw_output.txt
  parsed_output.json
  validation.json
  attempts/attempt_01/...
```

`invocation.json` records backend, model, reasoning/options, timeout, exact command, isolation flags, prompt/schema/instruction hashes, declared rule/config hashes, transport events, stderr, and raw-output hash. Raw output is retained before parsing.

## Controlled intervention and causal comparison

Inheritance changes only named leaves. The resolved configuration and its direct-parent diff are frozen in the run before execution. `compare_runs.py` reports semantic record changes and separately reports changed input, scientific-resource, configuration, and implementation hashes, allowing a researcher to distinguish an intervention from downstream consequences.

## Reuse

Reuse is content-addressed and stage-local. Identity includes only declared boundary files, the stage’s resolved scientific configuration/resources, and relevant implementation files. Reuse never regenerates an unchanged upstream stage and never treats stochastic output as requiring byte equality across different inputs. Symlinks keep reused evidence immutable; `stage_status.json` identifies its source run.

## Claim boundary

The harness preserves operational behavior, not a redesigned scientific methodology. KC granularity, difficulty, prerequisite order, simulator parameters, and profile-conditioned rates remain declared inputs. No KC count claims latent dimensionality; no automated item check claims human validation; no synthetic trajectory claims human learning.
