"""Select the declared EGP subset from the external source snapshot."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from .io import read_jsonl, repo_path, sha256_file, write_jsonl


PHASE1_FIELDS = ("egp_id", "supercategory", "subcategory", "guideword", "can_do")


def resolve_source_path(settings: dict[str, Any]) -> Path:
    direct_env = settings.get("source_path_env", "GRAMMAR_KT_EGP_SOURCE")
    if direct_env and os.environ.get(direct_env):
        return Path(os.environ[direct_env]).expanduser().resolve()
    configured = Path(settings["path"]).expanduser()
    if configured.is_absolute():
        return configured.resolve()
    root_env = settings.get("data_root_env", "GRAMMAR_KT_DATA_ROOT")
    data_root = os.environ.get(root_env) if root_env else None
    selected_root = Path(data_root or settings.get("data_root", "data/external"))
    return repo_path(selected_root / configured)


def phase1_record(record: dict[str, Any]) -> dict[str, Any]:
    """Project a source descriptor onto the fields visible during Phase 1."""

    if not record.get("egp_id"):
        raise ValueError("source descriptor requires egp_id")
    return {field: record.get(field) for field in PHASE1_FIELDS}


def select_records(
    source_path: str | Path,
    *,
    expected_sha256: str,
    expected_record_count: int,
    sample_ids_path: str | Path,
    expected_descriptor_count: int,
    sample_metadata_path: str | Path,
    annotation_units_path: str | Path,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    """Select and verify the declared EGP sample and annotation units."""

    # Verify and read the full external source snapshot.
    source = repo_path(source_path)
    if sha256_file(source) != expected_sha256:
        raise RuntimeError("external EGP source SHA-256 differs from experiments/base.yaml")
    ids = [line for line in repo_path(sample_ids_path).read_text(encoding="utf-8").splitlines() if line]
    records = read_jsonl(source)
    if len(records) != expected_record_count:
        raise RuntimeError(f"external source has {len(records)} records; expected {expected_record_count}")

    # Select the declared descriptor IDs in their declared order.
    by_id = {row["egp_id"]: row for row in records}
    missing = [value for value in ids if value not in by_id]
    if missing:
        raise RuntimeError(f"selected source IDs are absent: {missing[:5]}")
    selected = [by_id[value] for value in ids]
    if len(selected) != expected_descriptor_count:
        raise RuntimeError(f"selected {len(selected)} descriptors; expected {expected_descriptor_count}")

    # Validate the sample metadata and repeated annotation-unit design.
    metadata = read_jsonl(sample_metadata_path)
    units = read_jsonl(annotation_units_path)
    if [row["egp_id"] for row in metadata] != ids:
        raise RuntimeError("sample metadata order differs from the selected IDs")
    primary = [row for row in units if row["duplicate_of"] is None]
    if [row["egp_id"] for row in primary] != ids:
        raise RuntimeError("annotation units differ from the selected IDs")
    return selected, metadata, units


def run(run_dir: Path, settings: dict[str, Any]) -> dict[str, Any]:
    output = run_dir / "source"
    output.mkdir(parents=True, exist_ok=False)
    selected, metadata, units = select_records(
        resolve_source_path(settings),
        expected_sha256=settings["sha256"],
        expected_record_count=int(settings["records"]),
        sample_ids_path=settings["sample_ids"],
        expected_descriptor_count=int(settings["selected_descriptors"]),
        sample_metadata_path=settings["sample_metadata"],
        annotation_units_path=settings["annotation_units"],
    )
    # Isolate the five descriptor fields permitted as Phase-1 evidence.
    write_jsonl(output / "source_subset.jsonl", selected, sort_keys=False)
    write_jsonl(output / "phase1_records.jsonl", [phase1_record(row) for row in selected], sort_keys=False)
    write_jsonl(output / "sample_metadata.jsonl", metadata, sort_keys=False)
    write_jsonl(output / "annotation_units.jsonl", units, sort_keys=False)
    return {"descriptors": len(selected), "annotation_units": len(units)}
