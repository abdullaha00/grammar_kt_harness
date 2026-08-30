#!/usr/bin/env python3
"""Reproducible structural audit of the frozen full-v1 generator KCs.

This script is deliberately read-only with respect to ``grammar_kt_full_v1``.
It reports properties of the declared K*/Q* and simple, explicitly heuristic
properties of the learner-facing prompts.  The heuristics are diagnostics, not
human linguistic or pedagogical judgments.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import numpy as np


EXPLICIT_CUE_PATTERNS: dict[str, tuple[str, ...]] = {
    "gkc_aspect_perfect": (r"\bperfect\b",),
    "gkc_aspect_progressive": (r"\bprogressive\b", r"\bcontinuous\b"),
    "gkc_be_passive": (r"\bpassive\b",),
    "gkc_finite_past": (r"\bpast\b",),
    "gkc_finite_present": (r"\bpresent\b",),
    "gkc_imperative": (r"\bimperative\b",),
    "gkc_negation": (
        r"\bnegative\b",
        r"\bnot\b",
        r"\b(?:cannot|can't|couldn't|doesn't|don't|hadn't|hasn't|isn't|mustn't|shouldn't|wasn't|weren't|won't|wouldn't)\b",
    ),
    # These are task-type cues rather than necessarily answer leakage.  They
    # are retained to show how tightly clause KCs are tied to prompt wording.
    "gkc_non_subject_wh_question": (r"\bask\b", r"\bquestion\b", r"\bwhat\b", r"\bwhich\b"),
    "gkc_polar_question": (r"\bask\b", r"\bquestion\b", r"\bwhether\b"),
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--dataset",
        type=Path,
        default=Path("data/grammar_kt_full_v1"),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(
            "experiments/measurement_realism/audits/kc_audit/structural_metrics.json"
        ),
    )
    return parser.parse_args()


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def distribution(values: list[Any]) -> dict[str, int]:
    return {
        str(key): count
        for key, count in sorted(Counter(values).items(), key=lambda pair: str(pair[0]))
    }


def campaign(item: dict[str, Any]) -> str:
    metadata = item.get("generation_metadata") or {}
    return metadata.get("campaign", "default_campaign")


def cue_patterns(kc_id: str) -> tuple[str, ...]:
    if kc_id.startswith("gkc_modal_"):
        return (rf"\b{re.escape(kc_id.removeprefix('gkc_modal_'))}\b",)
    return EXPLICIT_CUE_PATTERNS.get(kc_id, ())


def prompt_has_explicit_cue(prompt: str, kc_id: str) -> bool:
    return any(
        re.search(pattern, prompt, flags=re.IGNORECASE)
        for pattern in cue_patterns(kc_id)
    )


def prompt_style(prompt: str) -> str:
    lowered = prompt.lower()
    if "all and only" in lowered or "rearrange" in lowered:
        return "bounded_chunk_reordering"
    if re.search(
        r"\b(?:negative|positive|active|passive|declarative|imperative|perfect|progressive|continuous)\b",
        lowered,
    ):
        return "explicit_metalanguage_production"
    if "ask " in lowered or "question" in lowered or "whether" in lowered:
        return "question_formation"
    if "complete" in lowered or "___" in prompt or "[____" in prompt:
        return "completion_or_cloze"
    return "other_controlled_production"


def finite_operator_family(features: dict[str, str]) -> str:
    """Coarse realisation context implied by a cell, not an added KC claim."""
    if features["modal"] != "none":
        return f"central_modal:{features['modal']}"
    if features["aspect"] in {"perfect", "perfect_progressive"}:
        return "perfect_HAVE"
    if features["aspect"] == "progressive" or features["voice"] == "passive":
        return "BE"
    if (
        features["polarity"] == "negative"
        or features["clause"] in {"polar_question", "non_subject_wh_question"}
    ):
        return "DO_support"
    if features["clause"] == "imperative":
        return "uninflected_lexical_verb"
    return "finite_lexical_main_verb"


def main() -> None:
    args = parse_args()
    dataset = args.dataset
    paths = {
        "cells": dataset / "grammar/cells.jsonl",
        "kcs": dataset / "kcs.jsonl",
        "items": dataset / "items/items.jsonl",
        "q_matrix": dataset / "q_matrix.csv",
        "kc_construction": dataset / "provenance/kcs/construction.json",
        "measurement_audit": dataset / "provenance/measurement/audit.json",
    }
    cells = read_jsonl(paths["cells"])
    kcs = read_jsonl(paths["kcs"])
    items = read_jsonl(paths["items"])
    cells_by_id = {cell["cell_id"]: cell for cell in cells}
    items_by_id = {item["item_id"]: item for item in items}
    kcs_by_id = {kc["id"]: kc for kc in kcs}

    with paths["q_matrix"].open(newline="", encoding="utf-8") as handle:
        q_rows = list(csv.DictReader(handle))
    if not q_rows:
        raise ValueError("empty Q-matrix")
    kc_ids = [column for column in q_rows[0] if column != "item_id"]
    if set(kc_ids) != set(kcs_by_id):
        raise ValueError("K*/Q* column mismatch")
    if set(row["item_id"] for row in q_rows) != set(items_by_id):
        raise ValueError("item/Q* row mismatch")

    matrix = np.asarray(
        [[int(row[kc_id]) for kc_id in kc_ids] for row in q_rows], dtype=float
    )
    item_ids_in_q_order = [row["item_id"] for row in q_rows]
    active_item_indices = {
        kc_id: set(np.flatnonzero(matrix[:, index]).tolist())
        for index, kc_id in enumerate(kc_ids)
    }
    active_cell_ids = {
        kc_id: {
            items_by_id[item_ids_in_q_order[index]]["cell_id"]
            for index in indices
        }
        for kc_id, indices in active_item_indices.items()
    }

    singular_values = np.linalg.svd(matrix, compute_uv=False)
    normalized_matrix = matrix / np.linalg.norm(matrix, axis=0, keepdims=True)
    normalized_singular_values = np.linalg.svd(normalized_matrix, compute_uv=False)

    pair_metrics: list[dict[str, Any]] = []
    for left_index, left_id in enumerate(kc_ids):
        left = active_item_indices[left_id]
        for right_id in kc_ids[left_index + 1 :]:
            right = active_item_indices[right_id]
            intersection = left & right
            union = left | right
            if left <= right:
                relation = "left_nested_in_right"
            elif right <= left:
                relation = "right_nested_in_left"
            elif not intersection:
                relation = "disjoint"
            else:
                relation = "crossed"
            pair_metrics.append(
                {
                    "left_kc_id": left_id,
                    "right_kc_id": right_id,
                    "left_only_items": len(left - right),
                    "right_only_items": len(right - left),
                    "cooccurring_items": len(intersection),
                    "jaccard": round(len(intersection) / len(union), 6),
                    "relation": relation,
                    "a_only_b_only_and_a_plus_b": bool(
                        left - right and right - left and intersection
                    ),
                }
            )

    per_kc: list[dict[str, Any]] = []
    for column_index, kc_id in enumerate(kc_ids):
        kc = kcs_by_id[kc_id]
        indices = sorted(active_item_indices[kc_id])
        active_items = [items_by_id[item_ids_in_q_order[index]] for index in indices]
        cell_ids = sorted(active_cell_ids[kc_id])
        active_cells = [cells_by_id[cell_id] for cell_id in cell_ids]
        isolating_indices = [
            index for index in indices if int(matrix[index].sum()) == 1
        ]
        cooccurring = Counter()
        for index in indices:
            for other_index, other_id in enumerate(kc_ids):
                if other_id != kc_id and matrix[index, other_index]:
                    cooccurring[other_id] += 1
        nested_in = []
        contains = []
        for other_id in kc_ids:
            if other_id == kc_id:
                continue
            own = active_item_indices[kc_id]
            other = active_item_indices[other_id]
            if own < other:
                nested_in.append(other_id)
            if other < own:
                contains.append(other_id)
        explicit_count = sum(
            prompt_has_explicit_cue(item["prompt"], kc_id) for item in active_items
        )
        per_kc.append(
            {
                "kc_id": kc_id,
                "name": kc["name"],
                "family": kc["family"],
                "activation_rule": kc["activation_rule"],
                "item_support": len(indices),
                "cell_support_from_q": len(cell_ids),
                "declared_cell_support": kc["cell_support"],
                "isolating_item_count": len(isolating_indices),
                "isolating_item_ids": [
                    item_ids_in_q_order[index] for index in isolating_indices
                ],
                "q_width_distribution": distribution(
                    [int(matrix[index].sum()) for index in indices]
                ),
                "cooccurring_kcs": dict(sorted(cooccurring.items())),
                "nested_in_kcs": sorted(nested_in),
                "contains_nested_kcs": sorted(contains),
                "campaign_distribution": distribution(
                    [campaign(item) for item in active_items]
                ),
                "format_distribution": distribution(
                    [item["format"] for item in active_items]
                ),
                "surface_prompt_style_distribution": distribution(
                    [prompt_style(item["prompt"]) for item in active_items]
                ),
                "explicit_prompt_cue_patterns": list(cue_patterns(kc_id)),
                "items_with_explicit_prompt_cue": explicit_count,
                "explicit_prompt_cue_fraction": round(
                    explicit_count / len(active_items), 6
                ),
                "active_cell_feature_values": {
                    dimension: sorted(
                        {cell["features"][dimension] for cell in active_cells}
                    )
                    for dimension in cells[0]["features"]
                },
                "finite_operator_family_by_cell": distribution(
                    [finite_operator_family(cell["features"]) for cell in active_cells]
                ),
                "finite_operator_family_by_item": distribution(
                    [
                        finite_operator_family(
                            cells_by_id[item["cell_id"]]["features"]
                        )
                        for item in active_items
                    ]
                ),
                "active_cell_ids_sha256": hashlib.sha256(
                    "\n".join(cell_ids).encode("utf-8")
                ).hexdigest(),
                "q_column_sha256": hashlib.sha256(
                    bytes(int(value) for value in matrix[:, column_index])
                ).hexdigest(),
            }
        )

    q_row_widths = matrix.sum(axis=1).astype(int).tolist()
    construction = json.loads(paths["kc_construction"].read_text(encoding="utf-8"))
    measurement = json.loads(paths["measurement_audit"].read_text(encoding="utf-8"))
    output = {
        "audit_id": "full_v1_generator_kc_structural_audit_v1",
        "scope": (
            "Deterministic K*/Q*/prompt diagnostics plus transparent regex "
            "heuristics. No learner outcomes or oracle trajectories are read."
        ),
        "judgment_boundary": (
            "This JSON contains computed diagnostics only. Any linguistic or "
            "pedagogical interpretation in the companion report is non-human "
            "Codex analysis, not expert or learner evidence."
        ),
        "dataset": str(dataset),
        "input_sha256": {name: sha256(path) for name, path in paths.items()},
        "frozen_provenance_cross_checks": {
            "construction_generator_kc_count": construction["metadata"][
                "generator_kc_count"
            ],
            "construction_outcomes_read": construction["metadata"][
                "learner_outcomes_read"
            ],
            "measurement_status": measurement["status"],
            "measurement_q_rank": measurement["counts"]["q_rank"],
        },
        "counts": {
            "canonical_cells": len(cells),
            "items": len(items),
            "generator_kcs": len(kc_ids),
            "q_edges": int(matrix.sum()),
            "q_row_width_distribution": distribution(q_row_widths),
            "items_with_one_kc": sum(width == 1 for width in q_row_widths),
            "items_with_multiple_kcs": sum(width > 1 for width in q_row_widths),
            "all_item_format_distribution": distribution(
                [item["format"] for item in items]
            ),
            "all_surface_prompt_style_distribution": distribution(
                [prompt_style(item["prompt"]) for item in items]
            ),
            "all_campaign_distribution": distribution(
                [campaign(item) for item in items]
            ),
        },
        "linear_algebra": {
            "rank": int(np.linalg.matrix_rank(matrix)),
            "raw_singular_values": [round(float(value), 8) for value in singular_values],
            "raw_condition_number": round(
                float(singular_values[0] / singular_values[-1]), 8
            ),
            "column_normalized_singular_values": [
                round(float(value), 8) for value in normalized_singular_values
            ],
            "column_normalized_condition_number": round(
                float(normalized_singular_values[0] / normalized_singular_values[-1]),
                8,
            ),
            "interpretation_limit": (
                "Full rank and finite condition numbers show algebraic column "
                "independence on this bank; they do not establish cognitive "
                "independence, content validity, or pedagogical transfer."
            ),
        },
        "pair_relation_distribution": distribution(
            [pair["relation"] for pair in pair_metrics]
        ),
        "pairs_without_two_sided_contrast": [
            pair
            for pair in pair_metrics
            if not pair["left_only_items"] or not pair["right_only_items"]
        ],
        "pairs_with_a_only_b_only_and_a_plus_b": sum(
            pair["a_only_b_only_and_a_plus_b"] for pair in pair_metrics
        ),
        "per_kc": per_kc,
        "pair_metrics": pair_metrics,
        "heuristic_notes": {
            "explicit_prompt_cue": (
                "Case-insensitive regex over prompt text. For modal KCs it is "
                "the literal modal lemma; for clause KCs it includes task-type "
                "language such as ask/question. A hit is neither automatically "
                "bad nor proof of answer leakage."
            ),
            "surface_prompt_style": (
                "Priority-ordered lexical heuristic. It exposes variation hidden "
                "under the single controlled_production format label."
            ),
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps({"output": str(args.output), "counts": output["counts"]}, indent=2))


if __name__ == "__main__":
    main()
