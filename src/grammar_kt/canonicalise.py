"""Stage 2: exact, validated and deduplicated GrammarCells."""

from __future__ import annotations

from typing import Any

from .io import read_yaml


def _condition_matches(features: dict[str, str], condition: dict[str, Any]) -> bool:
    for field, expected in condition.items():
        actual = features[field]
        if isinstance(expected, list) and actual not in expected:
            return False
        if isinstance(expected, dict) and actual == expected["not"]:
            return False
        if not isinstance(expected, (list, dict)) and actual != expected:
            return False
    return True


def validate_cell(features: dict[str, str], schema: dict[str, Any]) -> None:
    dimensions = schema["dimensions"]
    if list(features) != schema["dimension_order"]:
        raise ValueError("GrammarCell dimensions must follow canonical schema order")
    for name, value in features.items():
        if not isinstance(value, str) or value not in dimensions[name]["allowed_values"]:
            raise ValueError(f"invalid exact GrammarCell value: {name}={value}")
    for constraint in schema.get("constraints", []):
        if _condition_matches(features, constraint["if"]):
            for field, required in constraint["then"].items():
                if features[field] != required:
                    raise ValueError(f"GrammarCell violates constraint: {constraint['description']}")


def canonicalise(mappings: list[dict[str, Any]], schema_path: str) -> list[dict[str, Any]]:
    """Keep complete mappings, validate exact cells, deduplicate, and number them."""

    schema = read_yaml(schema_path)
    dimensions = schema["dimension_order"]
    unique: dict[tuple[str, ...], dict[str, Any]] = {}
    for mapping in mappings:
        if mapping["result"] != "complete":
            continue
        for raw_cell in mapping["cells"]:
            features = {name: raw_cell[name] for name in dimensions}
            validate_cell(features, schema)
            key = tuple(features[name] for name in dimensions)
            if key not in unique:
                unique[key] = {"features": features, "source_ids": []}
            if mapping["source_id"] not in unique[key]["source_ids"]:
                unique[key]["source_ids"].append(mapping["source_id"])

    cells = []
    for number, row in enumerate(unique.values(), 1):
        cells.append({"cell_id": f"cell_{number:03d}", "features": row["features"], "source_ids": row["source_ids"]})
    return cells
