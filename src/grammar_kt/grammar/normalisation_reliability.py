"""Explicit agreement diagnostics for repeated structured normalisation units."""

from __future__ import annotations

import json
from collections import Counter
from typing import Any

from ..io import stable_id
from ..records import DIMENSIONS, grammar_cell


def _cell_set(mapping: dict[str, Any]) -> list[str]:
    return sorted(
        json.dumps(cell, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        for cell in mapping.get("cells", [])
    )


def _dimension_values(mapping: dict[str, Any], dimension: str) -> list[str]:
    return sorted(
        json.dumps(cell.get(dimension), ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        for cell in mapping.get("cells", [])
        if isinstance(cell, dict)
    )


def canonical_contributions(mapping: dict[str, Any]) -> list[str]:
    if mapping.get("result") != "complete":
        return []
    result = []
    for raw in mapping.get("cells", []):
        cell = grammar_cell({field: raw[field] for field in DIMENSIONS})
        payload = json.dumps(
            {field: cell[field] for field in DIMENSIONS},
            ensure_ascii=False,
            separators=(",", ":"),
        )
        result.append(stable_id("CELL", payload))
    return sorted(set(result))


def analyse_repeated_normalisations(
    units: list[dict[str, Any]], by_unit: dict[str, dict[str, Any]]
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    comparisons = []
    for alternate in units:
        primary_id = alternate.get("duplicate_of")
        if primary_id is None:
            continue
        if primary_id not in by_unit or alternate["unit_id"] not in by_unit:
            raise RuntimeError(f"repeated normalisation pair is incomplete: {primary_id}")
        primary_result = by_unit[primary_id]
        alternate_result = by_unit[alternate["unit_id"]]
        primary = primary_result["output"]
        repeat = alternate_result["output"]
        comparable = bool(primary.get("cells")) and bool(repeat.get("cells"))
        dimension_agreement = {
            field: (
                _dimension_values(primary, field) == _dimension_values(repeat, field)
                if comparable
                else None
            )
            for field in DIMENSIONS
        }
        primary_cells = canonical_contributions(primary)
        alternate_cells = canonical_contributions(repeat)
        added = sorted(set(alternate_cells) - set(primary_cells))
        removed = sorted(set(primary_cells) - set(alternate_cells))
        comparisons.append(
            {
                "egp_id": alternate["egp_id"],
                "primary_unit_id": primary_id,
                "alternate_unit_id": alternate["unit_id"],
                "primary_result": primary["result"],
                "alternate_result": repeat["result"],
                "result_category_agreement": primary["result"] == repeat["result"],
                "comparable_cell_outputs": comparable,
                "exact_cell_set_agreement": _cell_set(primary) == _cell_set(repeat) if comparable else None,
                "dimension_agreement": dimension_agreement,
                "complete_vs_partial_disagreement": {primary["result"], repeat["result"]} == {"complete", "partial"},
                "primary_routed_to_phase2": primary_result.get("phase2") is not None,
                "alternate_routed_to_phase2": alternate_result.get("phase2") is not None,
                "phase2_routing_agreement": (primary_result.get("phase2") is None) == (alternate_result.get("phase2") is None),
                "primary_canonical_cell_ids": primary_cells,
                "alternate_canonical_cell_ids": alternate_cells,
                "same_canonical_cell_contribution": primary_cells == alternate_cells,
                "alternate_substitution_added_cell_ids": added,
                "alternate_substitution_removed_cell_ids": removed,
                "affects_downstream_canonical_inventory": bool(added or removed),
            }
        )

    comparable_rows = [row for row in comparisons if row["comparable_cell_outputs"]]

    def rate(numerator: int, denominator: int) -> float | None:
        return numerator / denominator if denominator else None

    category_counts = Counter(
        f"{row['primary_result']}->{row['alternate_result']}" for row in comparisons
    )
    summary = {
        "method": "explicit repeated-unit agreement; no single scalar coefficient",
        "repeated_pairs": len(comparisons),
        "result_category": {
            "agreements": sum(row["result_category_agreement"] for row in comparisons),
            "agreement_rate": rate(sum(row["result_category_agreement"] for row in comparisons), len(comparisons)),
            "pair_counts": dict(sorted(category_counts.items())),
        },
        "exact_cell_set": {
            "comparable_pairs": len(comparable_rows),
            "agreements": sum(bool(row["exact_cell_set_agreement"]) for row in comparable_rows),
            "agreement_rate": rate(sum(bool(row["exact_cell_set_agreement"]) for row in comparable_rows), len(comparable_rows)),
        },
        "dimension_wise": {
            field: {
                "comparable_pairs": len(comparable_rows),
                "agreements": sum(bool(row["dimension_agreement"][field]) for row in comparable_rows),
                "agreement_rate": rate(sum(bool(row["dimension_agreement"][field]) for row in comparable_rows), len(comparable_rows)),
            }
            for field in DIMENSIONS
        },
        "complete_vs_partial_disagreements": {
            "count": sum(row["complete_vs_partial_disagreement"] for row in comparisons),
            "egp_ids": sorted(row["egp_id"] for row in comparisons if row["complete_vs_partial_disagreement"]),
        },
        "phase2_routing": {
            "agreements": sum(row["phase2_routing_agreement"] for row in comparisons),
            "agreement_rate": rate(sum(row["phase2_routing_agreement"] for row in comparisons), len(comparisons)),
        },
        "canonical_contribution": {
            "same": sum(row["same_canonical_cell_contribution"] for row in comparisons),
            "different": sum(not row["same_canonical_cell_contribution"] for row in comparisons),
            "agreement_rate": rate(sum(row["same_canonical_cell_contribution"] for row in comparisons), len(comparisons)),
            "downstream_affecting_egp_ids": sorted(row["egp_id"] for row in comparisons if row["affects_downstream_canonical_inventory"]),
            "downstream_neutral_egp_ids": sorted(row["egp_id"] for row in comparisons if not row["affects_downstream_canonical_inventory"]),
        },
        "alternate_substitution_question": (
            "For each repeated descriptor, added/removed canonical cell IDs show what would change "
            "if the alternate annotation replaced the primary."
        ),
    }
    return summary, comparisons
