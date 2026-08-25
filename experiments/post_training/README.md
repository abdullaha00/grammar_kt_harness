# Historical post-training research area

> **Architecture boundary:** this study was produced at repository commit
> `f8e810e478d32c782649f5fa575a124e842d465c`, before the five-module
> refactor. Its retained records intentionally describe the former
> deterministic `RealizationSpec` pipeline. It is research evidence, not an
> active experiment or an API-compatibility target. Reproduce the record
> builder from a worktree at that commit; the active package must not import
> the archived deterministic realiser.

This directory contains an isolated, research-only investigation of whether
Grammar-KT's structured artifacts can supervise language-tutoring LMs. It does
not change the core pipeline or claim a production tutoring system.

Start with:

- [Main investigation and recommendation](report.md)
- [Focused literature review, including FEAT](literature/review.md)
- [Research-ready paper notes](paper_notes.md)
- [Preregistered diagnostic protocol](protocols/preregistered.md)

## Reproduce the historical deterministic feasibility experiment

The committed default output paths contain the retained study artifacts. To
verify them without overwriting the evidence, create a worktree at the recorded
pre-refactor commit and choose temporary paths:

```bash
git worktree add /tmp/grammar-kt-post-training \
  f8e810e478d32c782649f5fa575a124e842d465c
cd /tmp/grammar-kt-post-training
tmp_dir=$(mktemp -d)
.venv/bin/python experiments/post_training/scripts/build_records.py \
  --output "$tmp_dir/data"
.venv/bin/python experiments/post_training/scripts/evaluate_feasibility.py \
  --data "$tmp_dir/data" --output "$tmp_dir/results"
```

The retained artifact manifest is
[`data/feasibility_v0/manifest.json`](data/feasibility_v0/manifest.json) and the
retained evaluation is
[`results/feasibility_v0/summary.json`](results/feasibility_v0/summary.json).

## Reproduce the model diagnostics

These commands invoke a hosted model and therefore may cost money and cannot
reproduce an unpinned service snapshot bit-for-bit. The runner refuses to
overwrite an existing invocation directory. Use a new output directory via
`--output` if rerunning.

```bash
.venv/bin/python experiments/post_training/scripts/run_model_diagnostics.py \
  --output /tmp/grammar_kt_model_diagnostic generation
.venv/bin/python experiments/post_training/scripts/run_model_diagnostics.py \
  --output /tmp/grammar_kt_model_diagnostic preference
.venv/bin/python experiments/post_training/scripts/evaluate_model_diagnostics.py \
  --input /tmp/grammar_kt_model_diagnostic
```

The original prompts, schemas, events, raw JSON, stderr, invocation metadata,
scored output, and [model-run manifest](results/prompt_ablation_v0/manifest.json)
are retained under
[`results/prompt_ablation_v0`](results/prompt_ablation_v0/).

## Reproduce the FEAT release audit

```bash
.venv/bin/python experiments/post_training/scripts/audit_feat_release.py \
  --output /tmp/feat_release_audit.json
```

The script downloads two files pinned to the official repository commit and
checks their hashes. The retained result is
[`literature/feat_release_audit.json`](literature/feat_release_audit.json).

## Layout

```text
configs/       versioned experiment choices and decision criteria
data/          derived JSONL views and provenance manifest
literature/    literature synthesis and reproducible source-release audit
protocols/     hypotheses and decision rules written before execution
results/       retained summaries and raw model invocations
scripts/       transparent builders, runners, and evaluators
```

Claim boundary: the deterministic records use the historical `runs/base`
canonical inventory as a declared input and regenerate downstream artifacts at
the recorded pre-refactor commit. The external EGP snapshot is absent, so this
is not a fresh complete source-to-KT run. Dialogue and trajectory files are
schema demonstrations with weak/no policy labels, not recommended training
data.

The current-run boundary is reproducibly documented in
[`results/repository_audit_v0`](results/repository_audit_v0/).
