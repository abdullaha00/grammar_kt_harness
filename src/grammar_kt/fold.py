"""Stage 5: apply the frozen grammar-level reference fold."""

from __future__ import annotations

from typing import Any

SPLITS = {"development", "compositional_holdout", "novel_feature_holdout"}


def apply_fold(
    cells: list[dict[str, Any]], fold_spec: dict[str, Any]
) -> list[dict[str, Any]]:
    declared = fold_spec["assignments"]
    cell_ids = {cell["cell_id"] for cell in cells}
    if set(declared) != cell_ids:
        raise ValueError("fold manifest must assign every and only canonical cell")
    rows = []
    for cell in cells:
        split = declared[cell["cell_id"]]["split"]
        if split not in SPLITS:
            raise ValueError(f"unknown grammar split: {split}")
        rows.append({"cell_id": cell["cell_id"], "grammar_split": split, "features": cell["features"]})

    development = [row for row in rows if row["grammar_split"] == "development"]
    seen = {(field, value) for row in development for field, value in row["features"].items()}
    for row in rows:
        unseen = {(field, value) for field, value in row["features"].items() if (field, value) not in seen}
        if row["grammar_split"] == "compositional_holdout" and unseen:
            raise ValueError(f"compositional holdout has unseen features: {row['cell_id']}")
        if row["grammar_split"] == "novel_feature_holdout" and not unseen:
            raise ValueError(f"novel-feature holdout lacks an unseen feature: {row['cell_id']}")
    return rows
