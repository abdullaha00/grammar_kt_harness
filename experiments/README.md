# Experiment manifests

`current.yaml` is the reference experiment. A variant may inherit by short name or filename; nested mappings deep-merge and lists replace atomically.

```yaml
extends: current
experiment_id: phase1_variant
normalization:
  phase1_prompt: modules/stage_2_normalization/prompts/phase1_variant.txt
```

Before any stage runs, the harness writes:

- `experiment_manifest.json`: fully resolved values, inheritance chain, Git state, and hashes of every declared scientific file;
- `diff_from_parent.json`: explicit leaf-level `from`/`to` changes;
- `stage_status.json`: whether each available stage was `executed` or `reused`, plus reuse sources.

Examples in this repository:

- `run_one_demo.yaml`: isolates default single-unit demonstrations and points the otherwise external source path at a one-record local fixture;
- `phase1_demo.yaml`: one trivial Phase-1 wording intervention;
- `full_cell.yaml`: only `kc.policy` changes;
- `kt_bkt_only.yaml`: only the selected KT technique changes.

Run only a changed KT stage against content-identical frozen observable data:

```bash
python scripts/run_experiment.py kt_bkt_only --only kt
```

The runner recursively materializes identical dependencies from completed runs by fingerprint. If a required dependency has no identical completed stage, it stops instead of silently rerunning an unselected module. Use `--force` when a deliberate rerun is part of the experiment.
