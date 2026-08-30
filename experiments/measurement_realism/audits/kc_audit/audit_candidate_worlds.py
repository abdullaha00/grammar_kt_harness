#!/usr/bin/env python3
"""Structural diagnostics for several declared, non-selected KC worlds.

These worlds are sensitivity hypotheses, not claims about human knowledge and
not proposals to mutate full-v1.  Worlds requiring semantic/function labels
cannot be projected from the current GrammarCell and are documented in the
companion report rather than fabricated here.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import statistics
from collections import Counter
from pathlib import Path
from typing import Callable

import numpy as np


Predicate = Callable[[dict[str, str]], bool]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--dataset", type=Path, default=Path("data/grammar_kt_full_v1")
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(
            "experiments/measurement_realism/audits/kc_audit/"
            "candidate_world_metrics.json"
        ),
    )
    return parser.parse_args()


def read_jsonl(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def do_support(features: dict[str, str]) -> bool:
    if features["clause"] == "imperative":
        return features["polarity"] == "negative"
    no_other_operator = (
        features["modal"] == "none"
        and features["aspect"] == "none"
        and features["voice"] == "active"
    )
    needs_operator = (
        features["polarity"] == "negative"
        or features["clause"] in {"polar_question", "non_subject_wh_question"}
    )
    return no_other_operator and needs_operator


def audit_world(
    world_id: str,
    matrix: np.ndarray,
    column_ids: list[str],
    rationale: str,
) -> dict:
    supports = matrix.sum(axis=0).astype(int).tolist()
    row_widths = matrix.sum(axis=1).astype(int).tolist()
    signatures = [tuple(matrix[:, index].astype(int)) for index in range(matrix.shape[1])]
    isolating = {
        column_ids[index]: int(
            sum(matrix[row_index, index] and row_widths[row_index] == 1 for row_index in range(matrix.shape[0]))
        )
        for index in range(matrix.shape[1])
    }
    pair_relations: Counter[str] = Counter()
    for left_index in range(matrix.shape[1]):
        left = set(np.flatnonzero(matrix[:, left_index]).tolist())
        for right_index in range(left_index + 1, matrix.shape[1]):
            right = set(np.flatnonzero(matrix[:, right_index]).tolist())
            if left <= right:
                pair_relations["left_nested_in_right"] += 1
            elif right <= left:
                pair_relations["right_nested_in_left"] += 1
            elif not left & right:
                pair_relations["disjoint"] += 1
            else:
                pair_relations["crossed"] += 1
    rank = int(np.linalg.matrix_rank(matrix))
    return {
        "world_id": world_id,
        "status": "structural sensitivity world only; not selected",
        "rationale": rationale,
        "kc_count": matrix.shape[1],
        "q_rank": rank,
        "full_column_rank": rank == matrix.shape[1],
        "q_edges": int(matrix.sum()),
        "q_density": round(float(matrix.mean()), 8),
        "unique_q_columns": len(set(signatures)),
        "distinct_q_rows": len({tuple(row.astype(int)) for row in matrix}),
        "item_support": {
            "minimum": min(supports),
            "median": statistics.median(supports),
            "maximum": max(supports),
        },
        "kcs_per_item_distribution": {
            str(key): value for key, value in sorted(Counter(row_widths).items())
        },
        "kcs_with_isolating_items": sum(value > 0 for value in isolating.values()),
        "isolating_items_by_kc": isolating,
        "pair_relation_distribution": dict(sorted(pair_relations.items())),
        "column_ids": column_ids,
    }


def main() -> None:
    args = parse_args()
    cells_path = args.dataset / "grammar/cells.jsonl"
    items_path = args.dataset / "items/items.jsonl"
    q_path = args.dataset / "q_matrix.csv"
    cells = read_jsonl(cells_path)
    items = read_jsonl(items_path)
    cells_by_id = {row["cell_id"]: row["features"] for row in cells}
    items_by_id = {row["item_id"]: row for row in items}
    with q_path.open(newline="", encoding="utf-8") as handle:
        q_rows = list(csv.DictReader(handle))
    v1_ids = [column for column in q_rows[0] if column != "item_id"]
    item_ids = [row["item_id"] for row in q_rows]
    features = [cells_by_id[items_by_id[item_id]["cell_id"]] for item_id in item_ids]
    v1 = np.asarray(
        [[int(row[kc_id]) for kc_id in v1_ids] for row in q_rows], dtype=float
    )

    worlds: list[tuple[str, np.ndarray, list[str], str]] = [
        (
            "frozen_v1_reference",
            v1,
            v1_ids,
            "The immutable 18-column reusable-operation hybrid.",
        )
    ]

    def replace_columns(
        removed: set[str], added: dict[str, Predicate]
    ) -> tuple[np.ndarray, list[str]]:
        retained_ids = [kc_id for kc_id in v1_ids if kc_id not in removed]
        retained_indices = [v1_ids.index(kc_id) for kc_id in retained_ids]
        columns = [v1[:, index] for index in retained_indices]
        ids = list(retained_ids)
        for kc_id, predicate in added.items():
            columns.append(np.asarray([predicate(row) for row in features], dtype=float))
            ids.append(kc_id)
        return np.column_stack(columns), ids

    clause_matrix, clause_ids = replace_columns(
        {"gkc_polar_question", "gkc_non_subject_wh_question"},
        {
            "gkc_operator_inversion": lambda row: row["clause"]
            in {"polar_question", "non_subject_wh_question"},
            "gkc_wh_fronting": lambda row: row["clause"]
            == "non_subject_wh_question",
        },
    )
    worlds.append(
        (
            "clause_compositional",
            clause_matrix,
            clause_ids,
            "Replace clause-type atoms with shared operator inversion and WH fronting.",
        )
    )

    chain = np.asarray(
        [row["aspect"] == "perfect_progressive" for row in features], dtype=float
    )
    worlds.append(
        (
            "v1_plus_perfect_progressive_chain",
            np.column_stack([v1, chain]),
            v1_ids + ["gkc_interaction_perfect_progressive_chain"],
            "Add the preregistered chain interaction without selecting it.",
        )
    )

    do_column = np.asarray([do_support(row) for row in features], dtype=float)
    worlds.append(
        (
            "v1_plus_do_support",
            np.column_stack([v1, do_column]),
            v1_ids + ["gkc_do_support"],
            "Add a realisation-context operation deterministically implied by cell combinations.",
        )
    )

    modal_ids = [kc_id for kc_id in v1_ids if kc_id.startswith("gkc_modal_")]
    shared_modal_matrix, shared_modal_ids = replace_columns(
        set(modal_ids),
        {"gkc_central_modal_shared": lambda row: row["modal"] != "none"},
    )
    worlds.append(
        (
            "shared_central_modal_only",
            shared_modal_matrix,
            shared_modal_ids,
            "Merge lemma-specific modal columns into one common modal-form factor.",
        )
    )
    shared_modal = np.asarray([row["modal"] != "none" for row in features], dtype=float)
    worlds.append(
        (
            "hierarchical_shared_modal_plus_lemma_children",
            np.column_stack([v1, shared_modal]),
            v1_ids + ["gkc_central_modal_shared"],
            "Add a shared modal parent above the mutually exclusive lemma children; linear dependence is expected for a flat binary Q.",
        )
    )

    reference = {
        "tense": {"NA"},
        "aspect": {"none"},
        "voice": {"active"},
        "polarity": {"positive"},
        "clause": {"declarative", "subject_wh_question"},
        "modal": {"none"},
    }
    dimension_order = ["tense", "aspect", "voice", "polarity", "clause", "modal"]
    feature_columns: list[np.ndarray] = []
    feature_ids: list[str] = []
    for dimension in dimension_order:
        for value in sorted({row[dimension] for row in features} - reference[dimension]):
            feature_ids.append(f"gkc_feature__{dimension}__{value}")
            feature_columns.append(
                np.asarray([row[dimension] == value for row in features], dtype=float)
            )
    feature_matrix = np.column_stack(feature_columns)
    worlds.append(
        (
            "feature_value_non_reference",
            feature_matrix,
            feature_ids,
            "One atomic column for every observed non-reference GrammarCell value.",
        )
    )

    result = {
        "audit_id": "full_v1_candidate_generator_worlds_structural_v1",
        "boundary": (
            "Deterministic projection over frozen items/cells only. These are "
            "diagnostics, not selected worlds or human cognitive claims."
        ),
        "input_sha256": {
            "cells": digest(cells_path),
            "items": digest(items_path),
            "q_matrix": digest(q_path),
        },
        "worlds": [audit_world(*world) for world in worlds],
        "unprojectable_but_scientifically_relevant_worlds": [
            {
                "world_id": "modal_function_and_form",
                "reason": "GrammarCell stores modal lemma but not pedagogical function such as ability, permission, epistemic possibility, obligation, or counterfactuality.",
            },
            {
                "world_id": "lexical_morphology_and_argument_structure",
                "reason": "GrammarCell omits lexical lemma, regularity, transitivity, subject person/number, and realised response burden.",
            },
            {
                "world_id": "prerequisite_or_transfer_hierarchy",
                "reason": "A binary flat Q does not encode prerequisite strengths or learning transfer; a hierarchy can be scientifically plausible even when parent and child columns are linearly dependent.",
            },
        ],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(args.output), "worlds": len(worlds)}, indent=2))


if __name__ == "__main__":
    main()
