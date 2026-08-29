"""Stages 7–8: freeze a KC hypothesis, then mechanically project fixed items."""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Any


def _cell_matches(features: dict[str, str], conditions: dict[str, Any]) -> bool:
    for field, expected in conditions.items():
        actual = features[field]
        if isinstance(expected, list) and actual not in expected:
            return False
        if isinstance(expected, dict) and actual == expected["not"]:
            return False
        if not isinstance(expected, (list, dict)) and actual != expected:
            return False
    return True


def activation_matches(features: dict[str, str], activation: dict[str, Any]) -> bool:
    """Evaluate the deliberately small activation language: cell, all, and any."""

    if "cell" in activation:
        return _cell_matches(features, activation["cell"])
    if "all" in activation:
        return all(activation_matches(features, part) for part in activation["all"])
    if "any" in activation:
        return any(activation_matches(features, part) for part in activation["any"])
    raise ValueError(f"unknown KC activation primitive: {activation}")


def project_kcs(
    items: list[dict[str, Any]], cells: list[dict[str, Any]], policy: dict[str, Any]
) -> list[dict[str, Any]]:
    """Apply a frozen policy mechanically, producing one row per accepted item."""

    cells_by_id = {cell["cell_id"]: cell for cell in cells}
    rows = []
    for item in items:
        if item["cell_id"] not in cells_by_id:
            raise ValueError(
                f"KC projection refers to unknown GrammarCell: {item['item_id']}"
            )
        features = cells_by_id[item["cell_id"]]["features"]
        if policy.get("kind") == "full_cell":
            kc_ids = [policy["kc_id_pattern"].format(cell_id=item["cell_id"])]
        else:
            kc_ids = [
                row["id"]
                for row in policy["kcs"]
                if activation_matches(features, row["activation"])
            ]
        rows.append({"item_id": item["item_id"], "kc_ids": kc_ids})
    return rows


def write_q_matrix(path: str | Path, projection: list[dict[str, Any]]) -> None:
    kc_ids = sorted({kc_id for row in projection for kc_id in row["kc_ids"]})
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["item_id", *kc_ids])
        for row in projection:
            writer.writerow(
                [
                    row["item_id"],
                    *(int(kc_id in row["kc_ids"]) for kc_id in kc_ids),
                ]
            )
