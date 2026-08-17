"""Construct the fixed source subset without redistributing the full EGP source."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from shared.utils.io import ROOT, read_json, read_jsonl, repo_path, require_new_directory, sha256_file, utc_now, write_jsonl
from shared.utils.manifests import write_stage_manifest


PHASE1_FIELDS = ("egp_id", "supercategory", "subcategory", "guideword", "can_do")


def run_stage(run_dir: Path, config: dict[str, Any], experiment_manifest: Path, command: list[str]) -> None:
    started = utc_now()
    output = run_dir / "source"
    require_new_directory(output)
    source_path = repo_path(config["path"])
    if not source_path.is_file():
        raise FileNotFoundError(
            f"external EGP source missing: {source_path}; see data/external/README.md or use --source-path"
        )
    actual_hash = sha256_file(source_path)
    if actual_hash != config["sha256"]:
        raise RuntimeError(f"EGP source hash mismatch: expected {config['sha256']}, got {actual_hash}")

    ids_path = repo_path(config["sample_ids"])
    metadata_path = repo_path(config["sample_metadata"])
    units_path = repo_path(config["annotation_units"])
    ids = [line for line in ids_path.read_text(encoding="utf-8").splitlines() if line]
    if len(ids) != 139 or len(set(ids)) != 139:
        raise RuntimeError("current source config must contain 139 unique IDs")
    records = read_jsonl(source_path)
    if len(records) != config["records"]:
        raise RuntimeError(f"source record count mismatch: expected {config['records']}, got {len(records)}")
    by_id = {row.get("egp_id"): row for row in records}
    missing = [egp_id for egp_id in ids if egp_id not in by_id]
    if missing:
        raise RuntimeError(f"selected source IDs are missing: {missing[:5]}")
    selected = [by_id[egp_id] for egp_id in ids]
    schema_path = ROOT / "shared" / "schemas" / "source_record.schema.json"
    validator = Draft202012Validator(read_json(schema_path))
    schema_errors = [
        f"{row['egp_id']}: {error.message}"
        for row in selected
        for error in validator.iter_errors(row)
    ]
    if schema_errors:
        raise RuntimeError("source subset schema errors: " + "; ".join(schema_errors[:5]))

    metadata = read_jsonl(metadata_path)
    units = read_jsonl(units_path)
    if [row["egp_id"] for row in metadata] != ids:
        raise RuntimeError("sample metadata does not match fixed ID order")
    primary = [row for row in units if row["duplicate_of"] is None]
    duplicates = [row for row in units if row["duplicate_of"] is not None]
    if [row["egp_id"] for row in primary] != ids or len(units) != 147 or len(duplicates) != 8:
        raise RuntimeError("annotation-unit primary/duplicate contract mismatch")
    primary_by_unit = {row["unit_id"]: row for row in primary}
    for duplicate in duplicates:
        parent = primary_by_unit.get(duplicate["duplicate_of"])
        if parent is None or parent["egp_id"] != duplicate["egp_id"]:
            raise RuntimeError(f"invalid duplicate annotation unit: {duplicate['unit_id']}")

    subset_path = output / "source_subset.jsonl"
    phase1_path = output / "phase1_records.jsonl"
    output_metadata = output / "sample_metadata.jsonl"
    output_units = output / "annotation_units.jsonl"
    write_jsonl(subset_path, selected, sort_keys=False)
    write_jsonl(
        phase1_path,
        [{field: row.get(field) for field in PHASE1_FIELDS} for row in selected],
        sort_keys=False,
    )
    write_jsonl(output_metadata, metadata, sort_keys=False)
    write_jsonl(output_units, units, sort_keys=False)
    write_stage_manifest(
        output,
        module="source",
        version=config["version"],
        started_utc=started,
        command=command,
        inputs=[source_path],
        configs=[experiment_manifest, ids_path, metadata_path, units_path, schema_path],
        code=[Path(__file__)],
        outputs=[subset_path, phase1_path, output_metadata, output_units],
        details={
            "unique_source_descriptors": len(selected),
            "annotation_units": len(units),
            "duplicate_units": len(duplicates),
            "restricted_source_redistributed": False,
        },
    )

