"""Load and apply experimental grammar folds without changing intrinsic content."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .io import ROOT, read_json, repo_path


DEFAULT_FOLD = ROOT / "modules" / "folds" / "reference_v0.json"
SPLITS = ("development", "compositional_holdout", "novel_feature_holdout")


def load_fold(path: str | Path | None = None) -> dict[str, Any]:
    manifest = read_json(repo_path(path or DEFAULT_FOLD))
    required = {
        "fold_id",
        "development_cell_ids",
        "compositional_holdout_cell_ids",
        "novel_feature_holdout_cell_ids",
    }
    if not isinstance(manifest, dict) or not required <= set(manifest):
        raise ValueError(f"fold manifest lacks fields: {sorted(required - set(manifest or {}))}")
    groups = [set(manifest[f"{split}_cell_ids"]) for split in SPLITS]
    overlaps = (groups[0] & groups[1]) | (groups[0] & groups[2]) | (groups[1] & groups[2])
    if overlaps:
        raise ValueError(f"fold assignments overlap: {sorted(overlaps)}")
    if not isinstance(manifest["fold_id"], str) or not manifest["fold_id"]:
        raise ValueError("fold_id must be a non-empty string")
    return manifest


def assignment_for_cells(
    cells: list[dict[str, Any]], manifest: dict[str, Any]
) -> dict[str, str]:
    cell_ids = {row["canonical_cell_id"] for row in cells}
    declared = {
        cell_id: split
        for split in SPLITS
        for cell_id in manifest[f"{split}_cell_ids"]
    }
    unknown = set(declared) - cell_ids
    if unknown and manifest.get("require_all_declared_cells", False):
        raise RuntimeError(f"declared fold cells are absent: {sorted(unknown)}")
    if manifest.get("require_exact_inventory", False) and set(declared) != cell_ids:
        raise RuntimeError(
            "fold must exactly cover the canonical inventory: "
            f"unassigned={sorted(cell_ids - set(declared))}, "
            f"absent={sorted(set(declared) - cell_ids)}"
        )
    return {
        cell_id: declared.get(cell_id, "development")
        for cell_id in sorted(cell_ids)
    }


def fold_rows(
    cells: list[dict[str, Any]], manifest: dict[str, Any]
) -> list[dict[str, str | None]]:
    assignment = assignment_for_cells(cells, manifest)
    return [
        {
            "canonical_cell_id": cell_id,
            "split": split,
            "holdout_kind": None if split == "development" else split,
        }
        for cell_id, split in assignment.items()
    ]


def annotate_items(
    items: list[dict[str, Any]], assignment: dict[str, str]
) -> list[dict[str, Any]]:
    """Return runtime views with fold metadata; do not mutate intrinsic bank rows."""

    unknown = sorted(
        {row["canonical_cell_id"] for row in items} - set(assignment)
    )
    if unknown:
        raise RuntimeError(f"items refer to cells absent from the fold: {unknown}")
    return [
        {**row, "canonical_split": assignment[row["canonical_cell_id"]]}
        for row in items
    ]


def fold_path(settings: dict[str, Any]) -> Path:
    return repo_path(settings.get("fold_manifest", DEFAULT_FOLD))
