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


def _kc_id(field: str, value: str) -> str:
    names = {
        ("tense", "present"): "kc_present",
        ("tense", "past"): "kc_past",
        ("aspect", "progressive"): "kc_progressive",
        ("voice", "passive"): "kc_passive",
        ("polarity", "negative"): "kc_negation",
        ("clause", "polar_question"): "kc_polar_question",
        ("modal", "should"): "kc_modal_should",
    }
    return names.get((field, value), f"kc_{field}_{value}")


def _discover_candidates(
    development_cells: list[dict[str, Any]], candidate_space: dict[str, Any]
) -> list[dict[str, Any]]:
    candidates = []
    allowed = candidate_space["families"]["feature_value"]["allowed"]
    for field, value in allowed:
        if any(cell["features"][field] == value for cell in development_cells):
            candidates.append(
                {
                    "id": _kc_id(field, value),
                    "definition": f"Represent {field}={value}.",
                    "activation": {"cell": {field: value}},
                    "conditions": [[field, value]],
                    "represents": [f"{field}={value}"],
                }
            )
    for declaration in candidate_space["families"]["interactions"]["allowed"]:
        conditions = declaration["conditions"]
        cell_condition = {field: value for field, value in conditions}
        if any(
            _cell_matches(cell["features"], cell_condition)
            for cell in development_cells
        ):
            candidates.append(
                {
                    "id": declaration["id"],
                    "definition": "Represent the interaction "
                    + " and ".join(f"{field}={value}" for field, value in conditions)
                    + ".",
                    "activation": {"cell": cell_condition},
                    "conditions": conditions,
                    "represents": [f"{field}={value}" for field, value in conditions],
                }
            )
    return candidates


def _select_candidates(
    candidates: list[dict[str, Any]], obligations: set[str], selector: dict[str, Any]
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    selected = []
    covered: set[str] = set()
    trace = []
    while covered != obligations:
        ranked = []
        for candidate in candidates:
            if candidate in selected:
                continue
            new = set(candidate["represents"]) & obligations - covered
            if new:
                ranked.append(
                    (
                        -len(new),
                        len(candidate["conditions"]),
                        candidate["id"],
                        candidate,
                        new,
                    )
                )
        if not ranked:
            raise ValueError(
                "candidate space cannot cover obligations: "
                f"{sorted(obligations - covered)}"
            )
        _count, _complexity, _name, chosen, newly_covered = sorted(
            ranked, key=lambda row: row[:3]
        )[0]
        selected.append(chosen)
        covered.update(newly_covered)
        trace.append(
            {
                "step": len(trace) + 1,
                "selected": chosen["id"],
                "new_obligations": sorted(newly_covered),
            }
        )

    if selector["backward_prune"]:
        for candidate in list(reversed(selected)):
            remaining = [row for row in selected if row is not candidate]
            remaining_coverage = (
                set().union(*(set(row["represents"]) for row in remaining))
                if remaining
                else set()
            )
            if obligations <= remaining_coverage:
                selected = remaining
                trace.append({"step": len(trace) + 1, "pruned": candidate["id"]})
    return selected, trace


def select_kcs(
    cells: list[dict[str, Any]],
    items: list[dict[str, Any]],
    fold: list[dict[str, Any]],
    candidate_space: dict[str, Any],
    obligation_policy: dict[str, Any],
    selector: dict[str, Any],
) -> dict[str, Any]:
    """Select and freeze a KC policy from development grammar records only."""

    development_ids = {
        row["cell_id"]
        for row in fold
        if row["grammar_split"] == "development"
    }
    # Held-out cells are excluded before candidate discovery so that selection
    # cannot use their grammatical content or generated wording.
    development_cells = [cell for cell in cells if cell["cell_id"] in development_ids]
    development_items = [item for item in items if item["cell_id"] in development_ids]
    obligations = {
        f"{field}={value}"
        for row in obligation_policy["required"]
        for field, value in [row["condition"]]
        if any(cell["features"][field] == value for cell in development_cells)
    }
    candidates = _discover_candidates(development_cells, candidate_space)
    selected, trace = _select_candidates(candidates, obligations, selector)
    kcs = [
        {"id": row["id"], "definition": row["definition"], "activation": row["activation"]}
        for row in selected
    ]
    return {
        "policy_id": "development_selected",
        "description": (
            "Deterministic policy selected on development grammar records "
            "and then frozen."
        ),
        "kcs": kcs,
        "selection_metadata": {
            "mode": "selected",
            "development_cell_ids": sorted(development_ids),
            "development_item_ids": sorted(item["item_id"] for item in development_items),
            "holdout_content_read": False,
            "outcomes_read": False,
            "obligations": sorted(obligations),
            "trace": trace,
        },
    }


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
