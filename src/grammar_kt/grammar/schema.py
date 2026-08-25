"""Load and check the authoritative researcher-facing GrammarCell declaration."""

from __future__ import annotations

from typing import Any

from ..io import ROOT, read_json, read_yaml


SCHEMA_PATH = ROOT / "modules" / "grammar" / "canonical" / "grammar_schema.yaml"
MAPPING_SCHEMA_PATH = (
    ROOT / "modules" / "grammar" / "normalisation" / "configs" / "mapping_schema.json"
)


def load_canonical_schema() -> dict[str, Any]:
    schema = read_yaml(SCHEMA_PATH)
    order = schema.get("dimension_order")
    dimensions = schema.get("dimensions")
    if not isinstance(order, list) or not isinstance(dimensions, dict):
        raise ValueError("canonical schema requires dimension_order and dimensions")
    if order != list(dimensions):
        raise ValueError("canonical schema dimension order differs from dimensions")
    for name, declaration in dimensions.items():
        values = declaration.get("allowed_values")
        if not isinstance(values, list) or not values or len(values) != len(set(values)):
            raise ValueError(f"canonical schema {name} values must be non-empty and unique")
        if not all(isinstance(value, str) and value for value in values):
            raise ValueError(f"canonical schema {name} values must be strings")
    return schema


CANONICAL_SCHEMA = load_canonical_schema()
DIMENSION_ORDER = tuple(CANONICAL_SCHEMA["dimension_order"])
DIMENSION_VALUES = {
    name: set(CANONICAL_SCHEMA["dimensions"][name]["allowed_values"])
    for name in DIMENSION_ORDER
}


def prompt_declaration() -> str:
    """Render the exact value inventory placed in the isolated model prompt."""

    lines = [
        f"Canonical schema: {CANONICAL_SCHEMA['schema_id']}",
        "",
        "GrammarCell exact dimensions (normalisation may additionally use a list or null):",
    ]
    for name in DIMENSION_ORDER:
        values = " | ".join(CANONICAL_SCHEMA["dimensions"][name]["allowed_values"])
        lines.append(f"  {name}: {values}")
    lines.extend(
        [
            "",
            "Dimensions inside a cell are AND constraints; cells are OR branches.",
            "A scalar is exact, a list is a bounded constraint, and null is unknown.",
            "Never infer Cartesian combinations.",
            "modal:none differs from modal:null; tense:NA differs from tense:null.",
        ]
    )
    return "\n".join(lines)


def structured_output_values() -> dict[str, list[str]]:
    schema = read_json(MAPPING_SCHEMA_PATH)
    definitions = schema["$defs"]
    names = {
        "tense": "TenseConstraint",
        "aspect": "AspectConstraint",
        "voice": "VoiceConstraint",
        "polarity": "PolarityConstraint",
        "clause": "ClauseConstraint",
        "modal": "ModalConstraint",
    }
    return {
        field: list(definitions[definition]["anyOf"][0]["enum"])
        for field, definition in names.items()
    }


def cross_field_errors(cell: dict[str, str]) -> list[str]:
    """Apply the declared implications; Python only executes the declaration."""

    errors = []
    for constraint in CANONICAL_SCHEMA.get("cross_field_constraints", []):
        antecedent = constraint["if"]
        matches = all(
            cell.get(field) in (expected if isinstance(expected, list) else [expected])
            for field, expected in antecedent.items()
        )
        if not matches:
            continue
        for field, expected in constraint["then"].items():
            allowed = expected if isinstance(expected, list) else [expected]
            if cell.get(field) not in allowed:
                errors.append(
                    f"{constraint['constraint_id']}: {field} must be one of {allowed}"
                )
    return errors


def consistency_report() -> dict[str, Any]:
    declared = {
        field: CANONICAL_SCHEMA["dimensions"][field]["allowed_values"]
        for field in DIMENSION_ORDER
    }
    structured = structured_output_values()
    mismatches = {
        field: {"canonical": declared[field], "structured_output": structured.get(field)}
        for field in DIMENSION_ORDER
        if declared[field] != structured.get(field)
    }
    prompt = prompt_declaration()
    prompt_missing = [
        f"{field}:{value}"
        for field in DIMENSION_ORDER
        for value in declared[field]
        if value not in next(
            line for line in prompt.splitlines() if line.strip().startswith(f"{field}:")
        )
    ]
    return {
        "status": "PASS" if not mismatches and not prompt_missing else "FAIL",
        "schema_id": CANONICAL_SCHEMA["schema_id"],
        "dimension_order": list(DIMENSION_ORDER),
        "structured_output_mismatches": mismatches,
        "prompt_values_missing": prompt_missing,
    }
