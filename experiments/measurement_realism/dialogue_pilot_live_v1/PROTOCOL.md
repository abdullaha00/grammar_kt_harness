# Live automated dialogue-continuum pilot protocol

## Evidential status

This directory is a separate, append-only execution layer for the previously
frozen zero-call plan in `../dialogue_pilot/`. It does not amend that plan and
does not authorize calls by itself. The `generate` and `critic` commands require
an explicit command guard after conversational approval from the root research
agent.

The study makes four independent `gpt-5.6-sol` generation calls at medium
reasoning effort, one per frozen GrammarCell family. It then makes 20 independent
`gpt-5.6-terra` critic calls at medium reasoning effort: one context for each of
four families crossed with five role lenses. Every critic call returns exactly
five opportunity judgments. Roles never receive another role's output.

Automated critic judgments are rubric-based stress tests. They are not learner,
teacher, expert, platform, or response-process evidence. They cannot by
themselves establish ecological validity, deployability, learner answerability,
or justify an extended dataset release.

## Frozen scientific boundary

- `data/grammar_kt_full_v1/` is read-only and must match its Git tree and frozen
  manifest throughout the study.
- The source plan, four cells, Q rows, five-format order, prompts, strict local
  schemas, model names, reasoning efforts, role lenses, and analyzer are hashed
  before the first call.
- Generation receives no learner outcomes, latent trajectories, KT results, or
  critic output.
- The learner critic sees only learner-visible interaction fields. Other role
  visibility is declared in `config.yaml`.
- The provider schemas constrain transport only. The original, richer source
  schemas and deterministic identity checks remain the scientific validators.
- Raw evidence, failures, and parsed responses are append-only. An incomplete
  evidence directory is never silently reused or replaced.
- Ecological/usability and measurement-precision dimensions remain separate;
  no average, weighted composite, or scalar realism score is computed.

## Commands

Preflight and freeze exact generation prompts without live calls:

```bash
.venv/bin/python scripts/experiments/measurement_realism_dialogue_live.py plan
```

After explicit root approval only:

```bash
.venv/bin/python scripts/experiments/measurement_realism_dialogue_live.py \
  generate --authorize-live-calls-after-root-approval --workers 4

.venv/bin/python scripts/experiments/measurement_realism_dialogue_live.py \
  critic --authorize-live-calls-after-root-approval --workers 4
```

Then run deterministic analysis, package the byte-exact call evidence, and
verify the complete study:

```bash
.venv/bin/python scripts/experiments/measurement_realism_dialogue_live.py analyse
.venv/bin/python scripts/experiments/measurement_realism_dialogue_live.py package
.venv/bin/python scripts/experiments/measurement_realism_dialogue_live.py verify
```

`plan` is idempotent only when every frozen byte is identical. Later stages
refuse changed inputs, incomplete evidence directories, identity drift, missing
opportunities, missing roles, or output replacement.

## Interpretation

The four GrammarCells are matched mechanism probes, not a representative sample
of English grammar. A format can improve interaction naturalness while worsening
answer determinacy or KC attribution. Open dialogue is allowed to fail its
measurement boundary; forcing a viable-looking result is explicitly prohibited.
Human and expert validation remains defined by the source pilot's future review
protocol.
