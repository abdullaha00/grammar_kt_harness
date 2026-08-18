"""Select the declared EGP subset from the external source snapshot."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .io import read_jsonl, sha256_file, write_jsonl


PHASE1_FIELDS = ("egp_id", "supercategory", "subcategory", "guideword", "can_do")


def select(config: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    source = Path(config["path"]).expanduser().resolve()
    if sha256_file(source) != config["sha256"]:
        raise RuntimeError("external EGP source SHA-256 differs from experiments/base.yaml")
    ids = [line for line in Path(config["sample_ids"]).read_text(encoding="utf-8").splitlines() if line]
    records = read_jsonl(source)
    if len(records) != int(config["records"]):
        raise RuntimeError(f"external source has {len(records)} records; expected {config['records']}")
    by_id = {row["egp_id"]: row for row in records}
    missing = [value for value in ids if value not in by_id]
    if missing:
        raise RuntimeError(f"selected source IDs are absent: {missing[:5]}")
    selected = [by_id[value] for value in ids]
    if len(selected) != int(config["selected_descriptors"]):
        raise RuntimeError(f"selected {len(selected)} descriptors; expected {config['selected_descriptors']}")
    metadata = read_jsonl(config["sample_metadata"])
    units = read_jsonl(config["annotation_units"])
    if [row["egp_id"] for row in metadata] != ids:
        raise RuntimeError("sample metadata order differs from the selected IDs")
    primary = [row for row in units if row["duplicate_of"] is None]
    if [row["egp_id"] for row in primary] != ids:
        raise RuntimeError("annotation units differ from the selected IDs")
    return selected, metadata, units


def run(run_dir: Path, config: dict[str, Any]) -> dict[str, Any]:
    output = run_dir / "source"
    output.mkdir(parents=True, exist_ok=False)
    selected, metadata, units = select(config)
    write_jsonl(output / "source_subset.jsonl", selected, sort_keys=False)
    write_jsonl(output / "phase1_records.jsonl", [
        {field: row.get(field) for field in PHASE1_FIELDS} for row in selected
    ], sort_keys=False)
    write_jsonl(output / "sample_metadata.jsonl", metadata, sort_keys=False)
    write_jsonl(output / "annotation_units.jsonl", units, sort_keys=False)
    return {"descriptors": len(selected), "annotation_units": len(units)}


def run_one(record: dict[str, Any]) -> dict[str, Any]:
    if not record.get("egp_id"):
        raise ValueError("source descriptor requires egp_id")
    return {field: record.get(field) for field in PHASE1_FIELDS}
