# Source

**Purpose:** Extract the frozen 139-descriptor experiment subset from the full parsed EGP source.

**Inputs:** Hash-pinned external EGP JSONL, fixed sample IDs, sample metadata, and duplicate annotation units.

**Procedure:** Verify the external hash and select records in fixed ID order; project the five Phase-1 fields.

**Outputs:** `source_subset.jsonl`, `phase1_records.jsonl`, `sample_metadata.jsonl`, `annotation_units.jsonl`, and `manifest.json`.

**Command:** `python scripts/run_experiment.py experiments/current.yaml --to source`

**Configurable components:** External source path only; IDs and expected hash define the current reference subset.

