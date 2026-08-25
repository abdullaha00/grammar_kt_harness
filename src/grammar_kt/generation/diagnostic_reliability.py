"""Stability summaries for repeated blind evaluators."""

from __future__ import annotations

import json
from collections import defaultdict
from typing import Any


def analyse_repeated_diagnostics(
    rows: list[dict[str, Any]], *, result_field: str
) -> dict[str, Any]:
    by_item: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        if row.get("result") is not None:
            by_item[row["item_id"]].append(row)
    repeated = {item_id: values for item_id, values in by_item.items() if len(values) > 1}
    comparisons = []
    for item_id, values in sorted(repeated.items()):
        signatures = [
            json.dumps(value["result"].get(result_field, value["result"]), sort_keys=True)
            for value in values
        ]
        comparisons.append(
            {
                "item_id": item_id,
                "evaluations": len(values),
                "exactly_stable": len(set(signatures)) == 1,
                "signatures": signatures,
            }
        )
    return {
        "repeated_items": len(comparisons),
        "exact_agreement_rate": (
            sum(row["exactly_stable"] for row in comparisons) / len(comparisons)
            if comparisons
            else None
        ),
        "comparisons": comparisons,
        "interpretation": "automated evaluator stability; not human inter-rater reliability",
    }
