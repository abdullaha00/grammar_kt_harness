#!/usr/bin/env python3
"""Select and audit the matched-format GrammarCell cohorts.

The selector reads only frozen linguistic/measurement artifacts and the
outcome-free full-v1 item audit.  It never reads interactions, learner truth,
response probabilities, or downstream model results.

The full cohort is a minimum-size (18-row) exact basis for the 18 frozen KCs.
The pilot is a minimum-cardinality 12-cell *coverage* set.  It deliberately
has only rank 12 and must not be used for KC identifiability claims.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import itertools
import json
from collections import Counter, defaultdict
from fractions import Fraction
from pathlib import Path
from typing import Any, Iterable, Sequence

import numpy as np


DISPOSITION_ORDER = {
    "usable_as_stored": 0,
    "minor_ui_or_context_change": 1,
    "technically_valid_but_artificial": 2,
    "answer_space_problem": 3,
    "rewrite_or_withhold": 4,
}
STATUS_ORDER = {"pass": 0, "concern": 1, "uncertain": 2, "fail": 3}

# These templates make the common-operation block exactly identifiable and
# retain direct contrasts rather than merely maximizing source support.
CORE_TEMPLATES: tuple[tuple[str, dict[str, str], str], ...] = (
    (
        "finite_past_anchor",
        {
            "tense": "past",
            "aspect": "none",
            "voice": "active",
            "polarity": "positive",
            "clause": "declarative",
            "modal": "none",
        },
        "One-KC past anchor; reference row for the past aspect contrasts.",
    ),
    (
        "finite_present_anchor",
        {
            "tense": "present",
            "aspect": "none",
            "voice": "active",
            "polarity": "positive",
            "clause": "declarative",
            "modal": "none",
        },
        "One-KC present anchor.",
    ),
    (
        "past_perfect_contrast",
        {
            "tense": "past",
            "aspect": "perfect",
            "voice": "active",
            "polarity": "positive",
            "clause": "declarative",
            "modal": "none",
        },
        "Differs from the past anchor by perfect activation.",
    ),
    (
        "past_progressive_contrast",
        {
            "tense": "past",
            "aspect": "progressive",
            "voice": "active",
            "polarity": "positive",
            "clause": "declarative",
            "modal": "none",
        },
        "Differs from the past anchor by progressive activation.",
    ),
    (
        "past_progressive_passive_contrast",
        {
            "tense": "past",
            "aspect": "progressive",
            "voice": "passive",
            "polarity": "positive",
            "clause": "declarative",
            "modal": "none",
        },
        "Differs from the active past-progressive row by passive activation; "
        "also compresses past/progressive/passive coverage in the pilot.",
    ),
    (
        "complex_negation_contrast",
        {
            "tense": "past",
            "aspect": "perfect",
            "voice": "passive",
            "polarity": "negative",
            "clause": "declarative",
            "modal": "none",
        },
        "Four-KC complex row; with the aspect and voice contrasts it identifies "
        "negation without excluding complex measurement.",
    ),
    (
        "present_perfect_polar_contrast",
        {
            "tense": "present",
            "aspect": "perfect",
            "voice": "active",
            "polarity": "positive",
            "clause": "polar_question",
            "modal": "none",
        },
        "Adds a non-modal polar-question contrast in a present-perfect context.",
    ),
)

EXPECTED_MODAL_CELL_IDS = {
    "gkc_modal_can": "gc_edcc8d38860ff41d",
    "gkc_modal_could": "gc_9b8833161ce61d83",
    "gkc_modal_may": "gc_325e05b06bb38886",
    "gkc_modal_might": "gc_90b9229122fa55d6",
    "gkc_modal_must": "gc_4a4c9d34c1b5bce4",
    "gkc_modal_shall": "gc_f86ecd83135f0b52",
    "gkc_modal_should": "gc_809d40d141731b61",
    "gkc_modal_will": "gc_16d9f6e33f0517ec",
    "gkc_modal_would": "gc_e7fef77abc10b5ba",
}
EXPECTED_IMPERATIVE_CELL_ID = "gc_bb4f472f992ab76b"
EXPECTED_WH_CELL_ID = "gc_4634bf1b005f7724"
EXPECTED_UNSEEN_COMBINATION_CELL_ID = "gc_e730dbce7b036961"
EXPECTED_UNSEEN_VALUE_CELL_ID = "gc_483f3ac117f331a7"


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def exact_rank(matrix: Sequence[Sequence[int]]) -> int:
    work = [[Fraction(value) for value in row] for row in matrix]
    if not work:
        return 0
    row_count = len(work)
    column_count = len(work[0])
    pivot_row = 0
    for column in range(column_count):
        pivot = next(
            (row for row in range(pivot_row, row_count) if work[row][column]),
            None,
        )
        if pivot is None:
            continue
        work[pivot_row], work[pivot] = work[pivot], work[pivot_row]
        pivot_value = work[pivot_row][column]
        work[pivot_row] = [value / pivot_value for value in work[pivot_row]]
        for row in range(row_count):
            if row == pivot_row or not work[row][column]:
                continue
            factor = work[row][column]
            work[row] = [
                value - factor * pivot_entry
                for value, pivot_entry in zip(work[row], work[pivot_row])
            ]
        pivot_row += 1
        if pivot_row == row_count:
            break
    return pivot_row


def exact_determinant(matrix: Sequence[Sequence[int]]) -> Fraction:
    if not matrix or len(matrix) != len(matrix[0]):
        raise ValueError("determinant requires a non-empty square matrix")
    work = [[Fraction(value) for value in row] for row in matrix]
    determinant = Fraction(1)
    size = len(work)
    for column in range(size):
        pivot = next(
            (row for row in range(column, size) if work[row][column]), None
        )
        if pivot is None:
            return Fraction(0)
        if pivot != column:
            work[column], work[pivot] = work[pivot], work[column]
            determinant *= -1
        pivot_value = work[column][column]
        determinant *= pivot_value
        for row in range(column + 1, size):
            if not work[row][column]:
                continue
            factor = work[row][column] / pivot_value
            for offset in range(column, size):
                work[row][offset] -= factor * work[column][offset]
    return determinant


def exact_inverse(matrix: Sequence[Sequence[int]]) -> list[list[Fraction]]:
    if not matrix or len(matrix) != len(matrix[0]):
        raise ValueError("inverse requires a non-empty square matrix")
    size = len(matrix)
    work = [
        [Fraction(value) for value in row]
        + [Fraction(int(row_index == column)) for column in range(size)]
        for row_index, row in enumerate(matrix)
    ]
    for column in range(size):
        pivot = next(
            (row for row in range(column, size) if work[row][column]), None
        )
        if pivot is None:
            raise ValueError("matrix is singular")
        work[column], work[pivot] = work[pivot], work[column]
        pivot_value = work[column][column]
        work[column] = [value / pivot_value for value in work[column]]
        for row in range(size):
            if row == column or not work[row][column]:
                continue
            factor = work[row][column]
            work[row] = [
                value - factor * pivot_entry
                for value, pivot_entry in zip(work[row], work[column])
            ]
    return [row[size:] for row in work]


def fraction_json(value: Fraction) -> int | str:
    return value.numerator if value.denominator == 1 else str(value)


def representative_key(item: dict[str, Any], audit: dict[str, Any]) -> tuple[Any, ...]:
    judgment = audit["audit"]
    return (
        DISPOSITION_ORDER[judgment["primary_disposition"]],
        STATUS_ORDER[judgment["platform_overall"]],
        STATUS_ORDER[judgment["learner_overall"]],
        STATUS_ORDER[judgment["answer_determinacy"]],
        STATUS_ORDER[judgment["measurement_purity"]],
        STATUS_ORDER[judgment["response_space_fairness"]],
        STATUS_ORDER[judgment["task_comprehensibility"]],
        STATUS_ORDER[judgment["lexical_context_accessibility"]],
        len(item["prompt"].split()),
        item["item_id"],
    )


def select_representatives(
    items: list[dict[str, Any]], audits: dict[str, dict[str, Any]]
) -> dict[str, dict[str, Any]]:
    by_cell: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in items:
        by_cell[item["cell_id"]].append(item)
    return {
        cell_id: min(cell_items, key=lambda item: representative_key(item, audits[item["item_id"]]))
        for cell_id, cell_items in by_cell.items()
    }


def find_exact_cell(
    cells: dict[str, dict[str, Any]],
    regimes: dict[str, str],
    features: dict[str, str],
) -> str:
    matches = sorted(
        cell_id
        for cell_id, cell in cells.items()
        if regimes[cell_id] == "seen" and cell["features"] == features
    )
    if len(matches) != 1:
        raise ValueError(f"expected one seen cell for {features}, found {matches}")
    return matches[0]


def pair_geometry(matrix: Sequence[Sequence[int]], kc_ids: Sequence[str]) -> dict[str, Any]:
    counts: Counter[str] = Counter()
    examples: dict[str, list[list[str]]] = defaultdict(list)
    for left, right in itertools.combinations(range(len(kc_ids)), 2):
        patterns = {(row[left], row[right]) for row in matrix}
        if {(1, 0), (0, 1), (1, 1)} <= patterns:
            category = "crossed"
        elif (1, 1) not in patterns:
            category = "disjoint"
        elif (1, 0) not in patterns and (0, 1) not in patterns:
            category = "equal"
        elif (1, 0) not in patterns or (0, 1) not in patterns:
            category = "nested"
        else:
            category = "other"
        counts[category] += 1
        if len(examples[category]) < 8:
            examples[category].append([kc_ids[left], kc_ids[right]])
    return {"counts": dict(sorted(counts.items())), "examples": dict(sorted(examples.items()))}


def minimum_set_cover_size(row_masks: Iterable[int], target_mask: int) -> int:
    best: dict[int, int] = {0: 0}
    for row_mask in sorted(set(row_masks)):
        additions: dict[int, int] = {}
        for covered, count in list(best.items()):
            combined = covered | row_mask
            candidate = count + 1
            if candidate < min(best.get(combined, 10**9), additions.get(combined, 10**9)):
                additions[combined] = candidate
        for covered, count in additions.items():
            best[covered] = min(best.get(covered, 10**9), count)
    if target_mask not in best:
        raise ValueError("seen cells do not cover every KC")
    return best[target_mask]


def selected_metrics(
    records: list[dict[str, Any]], kc_ids: list[str]
) -> dict[str, Any]:
    matrix = [record["q_row"] for record in records]
    array = np.asarray(matrix, dtype=float)
    support = array.sum(axis=0).astype(int)
    norms = np.linalg.norm(array, axis=0)
    column_normalised = array / norms
    anchors = {
        kc_ids[record["q_row"].index(1)]: record["cell_id"]
        for record in records
        if sum(record["q_row"]) == 1
    }
    equal_columns = [
        [kc_ids[left], kc_ids[right]]
        for left, right in itertools.combinations(range(len(kc_ids)), 2)
        if all(row[left] == row[right] for row in matrix)
    ]
    feature_counts = {
        dimension: dict(
            sorted(Counter(record["features"][dimension] for record in records).items())
        )
        for dimension in ("tense", "aspect", "voice", "polarity", "clause", "modal")
    }
    return {
        "cell_count": len(records),
        "kc_count": len(kc_ids),
        "exact_rank": exact_rank(matrix),
        "raw_condition_number_2": float(np.linalg.cond(array)),
        "column_normalised_condition_number_2": float(np.linalg.cond(column_normalised)),
        "all_kcs_covered": bool(np.all(support > 0)),
        "selected_cell_support_by_kc": dict(zip(kc_ids, support.tolist())),
        "q_cardinality_counts": {
            str(width): count
            for width, count in sorted(Counter(sum(row) for row in matrix).items())
        },
        "q_isolating_cell_by_kc": dict(sorted(anchors.items())),
        "q_isolating_cell_count": len(anchors),
        "equal_activation_column_pairs": equal_columns,
        "pair_geometry": pair_geometry(matrix, kc_ids),
        "feature_value_counts": feature_counts,
        "representative_item_dispositions": dict(
            sorted(Counter(record["item_audit"]["primary_disposition"] for record in records).items())
        ),
        "representative_platform_overall": dict(
            sorted(Counter(record["item_audit"]["platform_overall"] for record in records).items())
        ),
        "representative_learner_overall": dict(
            sorted(Counter(record["item_audit"]["learner_overall"] for record in records).items())
        ),
        "source_support": {
            "min": min(record["source_support_count"] for record in records),
            "max": max(record["source_support_count"] for record in records),
            "sum": sum(record["source_support_count"] for record in records),
        },
    }


def write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, records: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record, sort_keys=True) + "\n")


def write_q_csv(path: Path, records: list[dict[str, Any]], kc_ids: list[str]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(["cell_id", "reference_item_id", *kc_ids])
        for record in records:
            writer.writerow([record["cell_id"], record["reference_item_id"], *record["q_row"]])


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--repo-root", type=Path, default=Path(__file__).resolve().parents[4]
    )
    parser.add_argument(
        "--output-dir", type=Path, default=Path(__file__).resolve().parent
    )
    args = parser.parse_args()
    root = args.repo_root.resolve()
    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    dataset = root / "data/grammar_kt_full_v1"
    item_audit_path = (
        root
        / "experiments/measurement_realism/audits/item_audit/item_level_audit.jsonl"
    )
    paths = {
        "dataset_manifest": dataset / "manifest.json",
        "cells": dataset / "grammar/cells.jsonl",
        "regimes": dataset / "grammar/regime_assignments.jsonl",
        "items": dataset / "items/items.jsonl",
        "kcs": dataset / "kcs.jsonl",
        "q_matrix": dataset / "q_matrix.csv",
        "item_audit": item_audit_path,
        "selector": Path(__file__).resolve(),
    }

    manifest = json.loads(paths["dataset_manifest"].read_text(encoding="utf-8"))
    manifest_paths = {
        "cells": "grammar/cells.jsonl",
        "regimes": "grammar/regime_assignments.jsonl",
        "items": "items/items.jsonl",
        "kcs": "kcs.jsonl",
        "q_matrix": "q_matrix.csv",
    }
    frozen_hash_matches = {
        key: sha256(paths[key]) == manifest["artifact_inventory"][relative]["sha256"]
        for key, relative in manifest_paths.items()
    }
    if not all(frozen_hash_matches.values()):
        raise ValueError(f"full-v1 input hash mismatch: {frozen_hash_matches}")

    cells = {row["cell_id"]: row for row in read_jsonl(paths["cells"])}
    regimes = {
        row["cell_id"]: row["grammar_regime"] for row in read_jsonl(paths["regimes"])
    }
    items = read_jsonl(paths["items"])
    item_by_id = {row["item_id"]: row for row in items}
    audits = {row["item_id"]: row for row in read_jsonl(paths["item_audit"])}
    kcs = read_jsonl(paths["kcs"])
    kc_by_id = {row["id"]: row for row in kcs}
    representatives = select_representatives(items, audits)

    with paths["q_matrix"].open(encoding="utf-8", newline="") as handle:
        q_reader = csv.DictReader(handle)
        if not q_reader.fieldnames:
            raise ValueError("Q matrix has no header")
        kc_ids = q_reader.fieldnames[1:]
        q_by_item = {
            row["item_id"]: [int(row[kc_id]) for kc_id in kc_ids]
            for row in q_reader
        }
    if kc_ids != [row["id"] for row in kcs]:
        raise ValueError("Q columns do not match frozen KC order")
    if set(q_by_item) != set(item_by_id):
        raise ValueError("Q/item ID mismatch")
    if set(audits) != set(item_by_id):
        raise ValueError("item-audit/frozen-item ID mismatch")

    items_by_cell: dict[str, list[str]] = defaultdict(list)
    for item in items:
        items_by_cell[item["cell_id"]].append(item["item_id"])
    q_by_cell: dict[str, list[int]] = {}
    for cell_id, item_ids in items_by_cell.items():
        rows = {tuple(q_by_item[item_id]) for item_id in item_ids}
        if len(rows) != 1:
            raise ValueError(f"cell has inconsistent Q rows: {cell_id}")
        q_by_cell[cell_id] = list(next(iter(rows)))

    modal_kcs = [kc_id for kc_id in kc_ids if kc_id.startswith("gkc_modal_")]
    modal_selections: list[tuple[str, str, str]] = []
    for kc_id in modal_kcs:
        kc_index = kc_ids.index(kc_id)
        candidates = [
            cell_id
            for cell_id, row in q_by_cell.items()
            if regimes[cell_id] == "seen" and row[kc_index] == 1
        ]

        def modal_key(cell_id: str) -> tuple[Any, ...]:
            item = representatives[cell_id]
            judgment = audits[item["item_id"]]["audit"]
            width = sum(q_by_cell[cell_id])
            return (
                DISPOSITION_ORDER[judgment["primary_disposition"]],
                0 if width == 1 else 1,
                -len(cells[cell_id]["source_ids"]),
                width,
                representative_key(item, audits[item["item_id"]]),
                cell_id,
            )

        cell_id = min(candidates, key=modal_key)
        if cell_id != EXPECTED_MODAL_CELL_IDS[kc_id]:
            raise ValueError(
                f"modal selection drift for {kc_id}: {cell_id} != "
                f"{EXPECTED_MODAL_CELL_IDS[kc_id]}"
            )
        modal_selections.append(
            (
                f"modal_{kc_id.removeprefix('gkc_modal_')}",
                cell_id,
                "Seen cell chosen outcome-free: audited usable first; then a "
                "Q-isolating modal anchor when available; otherwise greatest "
                "EGP source support, narrower Q row, and stable ID tie-breaks.",
            )
        )

    imperative_index = kc_ids.index("gkc_imperative")
    imperative_candidates = [
        cell_id
        for cell_id, row in q_by_cell.items()
        if regimes[cell_id] == "seen" and row[imperative_index] == 1
    ]

    def rare_clause_key(cell_id: str) -> tuple[Any, ...]:
        item = representatives[cell_id]
        return (
            DISPOSITION_ORDER[audits[item["item_id"]]["audit"]["primary_disposition"]],
            0 if sum(q_by_cell[cell_id]) == 1 else 1,
            -len(cells[cell_id]["source_ids"]),
            representative_key(item, audits[item["item_id"]]),
            cell_id,
        )

    imperative_cell = min(imperative_candidates, key=rare_clause_key)
    if imperative_cell != EXPECTED_IMPERATIVE_CELL_ID:
        raise ValueError(f"imperative selection drift: {imperative_cell}")

    wh_index = kc_ids.index("gkc_non_subject_wh_question")
    wh_candidates = sorted(
        cell_id
        for cell_id, row in q_by_cell.items()
        if regimes[cell_id] == "seen" and row[wh_index] == 1
    )
    if wh_candidates != [EXPECTED_WH_CELL_ID]:
        raise ValueError(f"unexpected seen WH candidates: {wh_candidates}")
    wh_cell = wh_candidates[0]

    core_selections = [
        (role, find_exact_cell(cells, regimes, features), reason)
        for role, features, reason in CORE_TEMPLATES
    ]
    common_prefix = modal_selections + [
        (
            "imperative_anchor",
            imperative_cell,
            "The positive imperative is the only Q-isolating imperative row. "
            "Its existing prose UI is not reusable; the cell is retained as "
            "a mandatory redesign target.",
        ),
        (
            "non_subject_wh_rare_cell",
            wh_cell,
            "The only canonical non-subject-WH cell; mandatory for all-KC coverage.",
        ),
    ]
    full_specs = common_prefix + core_selections
    pilot_compressor = next(
        spec for spec in core_selections if spec[0] == "past_progressive_passive_contrast"
    )
    pilot_specs = common_prefix + [pilot_compressor]

    def select_probe_cell(grammar_regime: str) -> str:
        candidates = [
            cell_id
            for cell_id in cells
            if regimes[cell_id] == grammar_regime
            and cell_id not in {cell_id for _, cell_id, _ in full_specs}
        ]

        def probe_key(cell_id: str) -> tuple[Any, ...]:
            item = representatives[cell_id]
            judgment = audits[item["item_id"]]["audit"]
            return (
                DISPOSITION_ORDER[judgment["primary_disposition"]],
                -len(cells[cell_id]["source_ids"]),
                sum(q_by_cell[cell_id]),
                representative_key(item, audits[item["item_id"]]),
                cell_id,
            )

        if not candidates:
            raise ValueError(f"no candidate probe cell for {grammar_regime}")
        return min(candidates, key=probe_key)

    unseen_combination_cell = select_probe_cell("unseen_combination")
    unseen_value_cell = select_probe_cell("unseen_value")
    if unseen_combination_cell != EXPECTED_UNSEEN_COMBINATION_CELL_ID:
        raise ValueError(
            "unseen-combination probe selection drift: "
            f"{unseen_combination_cell} != {EXPECTED_UNSEEN_COMBINATION_CELL_ID}"
        )
    if unseen_value_cell != EXPECTED_UNSEEN_VALUE_CELL_ID:
        raise ValueError(
            f"unseen-value probe selection drift: {unseen_value_cell} != "
            f"{EXPECTED_UNSEEN_VALUE_CELL_ID}"
        )
    probe_specs = [
        (
            "unseen_combination_probe",
            unseen_combination_cell,
            "Probe-only cell chosen without outcomes: audited usable reference first, "
            "then greatest EGP source support, narrower Q row, representative-item "
            "quality, and stable ID. It recombines seen present and progressive "
            "values in a held-out exact GrammarCell.",
        ),
        (
            "unseen_value_probe",
            unseen_value_cell,
            "Probe-only cell chosen without outcomes: audited usable reference first, "
            "then greatest EGP source support, narrower Q row, representative-item "
            "quality, and stable ID. Its perfect-progressive aspect value is absent "
            "from acquisition while its component KCs remain declared in K*.",
        ),
    ]

    def materialise(specs: list[tuple[str, str, str]], tier: str) -> list[dict[str, Any]]:
        records: list[dict[str, Any]] = []
        for order, (role, cell_id, reason) in enumerate(specs, start=1):
            item = representatives[cell_id]
            judgment = audits[item["item_id"]]["audit"]
            row = q_by_cell[cell_id]
            records.append(
                {
                    "selection_schema": "matched_format_cell_selection_v1",
                    "tier": tier,
                    "selection_order": order,
                    "selection_role": role,
                    "selection_reason": reason,
                    "cell_id": cell_id,
                    "features": cells[cell_id]["features"],
                    "grammar_regime": regimes[cell_id],
                    "source_ids": cells[cell_id]["source_ids"],
                    "source_support_count": len(cells[cell_id]["source_ids"]),
                    "q_row": row,
                    "generator_kc_ids": [
                        kc_id for kc_id, active in zip(kc_ids, row) if active
                    ],
                    "q_cardinality": sum(row),
                    "q_isolating": sum(row) == 1,
                    "reference_item_id": item["item_id"],
                    "reference_prompt": item["prompt"],
                    "reference_target_answer": item["target_answer"],
                    "reference_accepted_answers": item["accepted_answers"],
                    "item_audit": {
                        field: judgment[field]
                        for field in (
                            "primary_disposition",
                            "task_comprehensibility",
                            "answer_determinacy",
                            "response_space_fairness",
                            "lexical_context_accessibility",
                            "pedagogical_plausibility",
                            "format_plausibility",
                            "measurement_purity",
                            "learner_overall",
                            "platform_overall",
                            "issue_tags",
                        )
                    },
                    "reference_stem_reuse": (
                        "redesign_required"
                        if judgment["primary_disposition"]
                        == "technically_valid_but_artificial"
                        else "usable_starting_point_not_automatic_final_item"
                    ),
                }
            )
        return records

    full_records = materialise(full_specs, "full_rank_18")
    pilot_records = materialise(pilot_specs, "coverage_pilot_12")
    probe_records = materialise(probe_specs, "held_out_probes_2")
    if len({record["cell_id"] for record in full_records}) != 18:
        raise ValueError("full cohort must contain 18 distinct cells")
    if len({record["cell_id"] for record in pilot_records}) != 12:
        raise ValueError("pilot cohort must contain 12 distinct cells")
    if not {record["cell_id"] for record in pilot_records} <= {
        record["cell_id"] for record in full_records
    }:
        raise ValueError("pilot must be a strict subset of the full cohort")
    if any(record["grammar_regime"] != "seen" for record in full_records):
        raise ValueError("selection contains a non-seen cell")
    if [record["grammar_regime"] for record in probe_records] != [
        "unseen_combination",
        "unseen_value",
    ]:
        raise ValueError("probe regimes or ordering drifted")

    full_matrix = [record["q_row"] for record in full_records]
    pilot_matrix = [record["q_row"] for record in pilot_records]
    full_metrics = selected_metrics(full_records, kc_ids)
    pilot_metrics = selected_metrics(pilot_records, kc_ids)
    if full_metrics["exact_rank"] != 18:
        raise ValueError(f"full cohort rank is {full_metrics['exact_rank']}, not 18")
    determinant = exact_determinant(full_matrix)
    if abs(determinant) != 1:
        raise ValueError(f"expected a unimodular basis, determinant={determinant}")
    if pilot_metrics["exact_rank"] != 12 or not pilot_metrics["all_kcs_covered"]:
        raise ValueError("pilot must cover all KCs with exact rank 12")

    seen_masks = [
        sum(active << index for index, active in enumerate(row))
        for cell_id, row in q_by_cell.items()
        if regimes[cell_id] == "seen"
    ]
    minimum_coverage_cells = minimum_set_cover_size(
        seen_masks, (1 << len(kc_ids)) - 1
    )
    if minimum_coverage_cells != 12:
        raise ValueError(
            f"minimum all-KC seen-cell cover drifted: {minimum_coverage_cells}"
        )

    full_inverse = exact_inverse(full_matrix)
    contrasts = []
    for kc_index, kc_id in enumerate(kc_ids):
        coefficients = [
            {
                "cell_id": full_records[cell_index]["cell_id"],
                "coefficient": fraction_json(coefficient),
            }
            for cell_index, coefficient in enumerate(full_inverse[kc_index])
            if coefficient
        ]
        reconstructed = [
            sum(
                full_inverse[kc_index][row_index] * full_matrix[row_index][column]
                for row_index in range(len(full_matrix))
            )
            for column in range(len(kc_ids))
        ]
        expected = [Fraction(int(column == kc_index)) for column in range(len(kc_ids))]
        if reconstructed != expected:
            raise ValueError(f"invalid identification contrast for {kc_id}")
        contrasts.append({"generator_kc_id": kc_id, "cell_coefficients": coefficients})

    bank_item_support = {
        kc_id: sum(row[kc_index] for row in q_by_item.values())
        for kc_index, kc_id in enumerate(kc_ids)
    }
    support_ledger = []
    for kc_id in kc_ids:
        support_ledger.append(
            {
                "generator_kc_id": kc_id,
                "bank_cell_support": kc_by_id[kc_id]["cell_support"],
                "bank_item_support": bank_item_support[kc_id],
                "rare_in_full_v1_fewer_than_6_items": bank_item_support[kc_id] < 6,
                "full_selection_cell_support": full_metrics[
                    "selected_cell_support_by_kc"
                ][kc_id],
                "pilot_selection_cell_support": pilot_metrics[
                    "selected_cell_support_by_kc"
                ][kc_id],
                "full_q_isolating_cell_id": full_metrics[
                    "q_isolating_cell_by_kc"
                ].get(kc_id),
                "pilot_q_isolating_cell_id": pilot_metrics[
                    "q_isolating_cell_by_kc"
                ].get(kc_id),
            }
        )

    summary = {
        "selection_schema": "matched_format_selection_summary_v1",
        "decision": {
            "full_tier": "full_rank_18",
            "pilot_tier": "coverage_pilot_12",
            "full_cell_ids": [record["cell_id"] for record in full_records],
            "full_reference_item_ids": [
                record["reference_item_id"] for record in full_records
            ],
            "pilot_cell_ids": [record["cell_id"] for record in pilot_records],
            "pilot_reference_item_ids": [
                record["reference_item_id"] for record in pilot_records
            ],
            "held_out_probe_cell_ids": [
                record["cell_id"] for record in probe_records
            ],
            "held_out_probe_reference_item_ids": [
                record["reference_item_id"] for record in probe_records
            ],
        },
        "scientific_boundary": {
            "learner_outcomes_read": False,
            "learner_truth_read": False,
            "response_probabilities_read": False,
            "downstream_model_results_read": False,
            "allowed_inputs": [
                "frozen GrammarCells and seen-regime labels",
                "frozen K* and deterministic Q*",
                "frozen learner-facing item records",
                "explicit non-human, outcome-free item-audit judgments",
            ],
            "item_audit_status": "Codex rubric judgments; not human validation",
        },
        "minimality": {
            "full_rank_row_lower_bound": len(kc_ids),
            "full_rank_achieved_rows": len(full_records),
            "full_rank_is_minimum": len(full_records) == len(kc_ids),
            "full_exact_determinant": fraction_json(determinant),
            "full_basis_is_unimodular": abs(determinant) == 1,
            "seen_cell_all_kc_coverage_minimum_from_exact_set_cover": minimum_coverage_cells,
            "pilot_achieves_minimum_coverage_size": len(pilot_records)
            == minimum_coverage_cells,
            "coverage_minimum_explanation": (
                "Nine mutually exclusive modal values need nine cells; imperative "
                "and the only non-subject-WH activation need two additional cells; "
                "those eleven cells contain no finite-past activation, so at least "
                "one further seen cell is necessary. The selected past-progressive "
                "passive supplies past, progressive, and passive in that twelfth row."
            ),
        },
        "full_rank_18": full_metrics,
        "coverage_pilot_12": pilot_metrics,
        "support_ledger": support_ledger,
        "risks": [
            "The imperative cell is scientifically mandatory but its best frozen "
            "reference item is annotation-like and must be redesigned, not reused.",
            "The non-subject-WH KC has one canonical cell and remains nested with "
            "present and negation in linguistic support despite algebraic separation.",
            "Nine modal KCs have only one selected cell each; matched formats can "
            "separate format nuisance within those cells but cannot establish broad "
            "cross-cell transfer for a modal KC.",
            "Full rank and determinant magnitude one establish exact algebraic "
            "identifiability only, not psychological or measurement validity.",
            "The 12-cell pilot has all-KC marginal coverage but equal activation "
            "columns and rank 12; it is for generation/validation feasibility only.",
            "The two held-out cells are non-updating probes and are excluded from "
            "the 18-row rank, determinant, support, and acquisition claims.",
            "The item audit is structured independent-agent evidence, not learner, "
            "teacher, product, or expert validation.",
        ],
    }

    input_manifest = {
        "manifest_schema": "matched_format_selection_inputs_v1",
        "dataset_id": manifest["dataset_id"],
        "dataset_manifest_id": manifest["manifest_id"],
        "full_v1_manifest_hashes_verified": frozen_hash_matches,
        "inputs": {
            key: {
                "path": str(path.relative_to(root)),
                "sha256": sha256(path),
                "bytes": path.stat().st_size,
            }
            for key, path in paths.items()
        },
        "forbidden_inputs_confirmed_not_opened": [
            "data/grammar_kt_full_v1/interactions.jsonl.gz",
            "data/grammar_kt_full_v1/oracle/learner_truth.jsonl.gz",
            "experiments/full_v1/**/results.json",
        ],
    }

    def canonical_entry(
        record: dict[str, Any], order: int, role: str, acquisition_updates: bool
    ) -> dict[str, Any]:
        return {
            "selection_order": order,
            "role": role,
            "selection_role": record["selection_role"],
            "cell_id": record["cell_id"],
            "grammar_regime": record["grammar_regime"],
            "acquisition_updates": acquisition_updates,
            "included_in_seen_rank_claim": acquisition_updates,
            "features": record["features"],
            "generator_kc_ids": record["generator_kc_ids"],
            "q_row": record["q_row"],
            "q_cardinality": record["q_cardinality"],
            "q_isolating": record["q_isolating"],
            "source_ids": record["source_ids"],
            "source_support_count": record["source_support_count"],
            "reference_item_id": record["reference_item_id"],
            "reference_prompt": record["reference_prompt"],
            "reference_target_answer": record["reference_target_answer"],
            "reference_accepted_answers": record["reference_accepted_answers"],
            "reference_stem_reuse": record["reference_stem_reuse"],
            "item_audit": record["item_audit"],
            "selection_rationale": record["selection_reason"],
        }

    canonical_seen = [
        canonical_entry(record, order, "seen_acquisition", True)
        for order, record in enumerate(full_records, start=1)
    ]
    canonical_held_out = [
        canonical_entry(record, order, record["selection_role"], False)
        for order, record in enumerate(probe_records, start=19)
    ]
    canonical_selection = {
        "selection_schema": "matched_format_selected_cells_v1",
        "dataset_id": manifest["dataset_id"],
        "purpose": (
            "Canonical matched-format design: an 18-cell seen acquisition basis "
            "plus one non-updating probe for each held-out grammar regime."
        ),
        "kc_order": kc_ids,
        "counts": {
            "total": 20,
            "seen_acquisition": 18,
            "unseen_combination_probe": 1,
            "unseen_value_probe": 1,
        },
        "seen_rank_claim": {
            "cell_count": 18,
            "exact_rank": full_metrics["exact_rank"],
            "exact_determinant": fraction_json(determinant),
            "held_out_cells_excluded": True,
        },
        "scientific_boundary": {
            **summary["scientific_boundary"],
            "held_out_probe_policy": (
                "acquisition_updates=false; exclude from acquisition and all seen-Q "
                "rank/determinant claims"
            ),
        },
        "input_hashes": {
            key: sha256(path) for key, path in paths.items()
        },
        "seen_cells": canonical_seen,
        "held_out_cells": canonical_held_out,
    }

    generated_paths = {
        "selected_cells": output_dir / "selected_cells.json",
        "full_rank_cells": output_dir / "full_rank_cells.jsonl",
        "pilot_cells": output_dir / "pilot_cells.jsonl",
        "full_rank_q": output_dir / "full_rank_q.csv",
        "pilot_q": output_dir / "pilot_q.csv",
        "identification_contrasts": output_dir / "identification_contrasts.json",
        "selection_summary": output_dir / "selection_summary.json",
        "input_manifest": output_dir / "input_manifest.json",
    }
    write_json(generated_paths["selected_cells"], canonical_selection)
    write_jsonl(generated_paths["full_rank_cells"], full_records)
    write_jsonl(generated_paths["pilot_cells"], pilot_records)
    write_q_csv(generated_paths["full_rank_q"], full_records, kc_ids)
    write_q_csv(generated_paths["pilot_q"], pilot_records, kc_ids)
    write_json(
        generated_paths["identification_contrasts"],
        {
            "schema": "matched_format_exact_identification_contrasts_v1",
            "meaning": "For each KC, the listed linear combination of selected Q "
            "rows reconstructs its unit column vector exactly.",
            "determinant": fraction_json(determinant),
            "contrasts": contrasts,
        },
    )
    write_json(generated_paths["selection_summary"], summary)
    write_json(generated_paths["input_manifest"], input_manifest)
    write_json(
        output_dir / "output_manifest.json",
        {
            "manifest_schema": "matched_format_selection_outputs_v1",
            "generator": str(Path(__file__).resolve().relative_to(root)),
            "artifacts": {
                key: {
                    "path": str(path.relative_to(root)),
                    "sha256": sha256(path),
                    "bytes": path.stat().st_size,
                }
                for key, path in generated_paths.items()
            },
        },
    )


if __name__ == "__main__":
    main()
