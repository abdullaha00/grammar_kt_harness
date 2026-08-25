"""Derive grammatical operations from a GrammarCell and structural conditions.

This module deliberately stops at structural evidence.  It contains no lexicon
and cannot produce English surface text.
"""

from __future__ import annotations

from typing import Any

from ..records import grammar_cell


PREDICATE_CLASSES = {"lexical_transitive", "lexical_intransitive", "copular"}
SUBJECT_NUMBERS = {"singular", "plural"}
WH_ROLES = {None, "subject", "object", "adjunct"}
IMPERATIVE_SUBTYPES = {
    None,
    "ordinary",
    "emphatic_do",
    "lets",
    "lets_not",
    "let_pronoun",
}
STRUCTURAL_CONDITION_FIELDS = {
    "predicate_class",
    "subject_person",
    "subject_number",
    "wh_role",
    "imperative_subtype",
}


def validate_structural_conditions(
    cell: dict[str, str], conditions: Any
) -> dict[str, Any]:
    """Validate the generator-invariant structural conditions for one cell."""

    grammar_cell(cell)
    if not isinstance(conditions, dict) or set(conditions) != STRUCTURAL_CONDITION_FIELDS:
        raise ValueError(
            "structural_conditions must contain exactly "
            f"{sorted(STRUCTURAL_CONDITION_FIELDS)}"
        )
    if conditions["predicate_class"] not in PREDICATE_CLASSES:
        raise ValueError("unknown predicate_class")
    if conditions["subject_person"] not in {1, 2, 3}:
        raise ValueError("subject_person must be 1, 2, or 3")
    if conditions["subject_number"] not in SUBJECT_NUMBERS:
        raise ValueError("subject_number must be singular or plural")
    if conditions["wh_role"] not in WH_ROLES:
        raise ValueError("invalid wh_role")
    if conditions["imperative_subtype"] not in IMPERATIVE_SUBTYPES:
        raise ValueError("invalid imperative_subtype")

    clause = cell["clause"]
    wh_role = conditions["wh_role"]
    expected_roles = {
        "subject_wh_question": {"subject"},
        "non_subject_wh_question": {"object", "adjunct"},
    }
    if clause in expected_roles and wh_role not in expected_roles[clause]:
        raise ValueError(f"{clause} requires wh_role in {sorted(expected_roles[clause])}")
    if clause not in expected_roles and wh_role is not None:
        raise ValueError("wh_role supplied to a non-WH clause")
    if wh_role == "object" and (
        conditions["predicate_class"] != "lexical_transitive"
        or cell["voice"] != "active"
    ):
        raise ValueError("object WH requires an active lexical_transitive predicate")
    subtype = conditions["imperative_subtype"]
    if clause == "imperative" and subtype is None:
        raise ValueError("imperative clause requires an imperative_subtype")
    if clause != "imperative" and subtype is not None:
        raise ValueError("imperative_subtype supplied to a non-imperative clause")
    if cell["voice"] == "passive" and conditions["predicate_class"] != "lexical_transitive":
        raise ValueError("passive cells require a lexical_transitive predicate")
    return conditions


def _has_inherent_operator(cell: dict[str, str], conditions: dict[str, Any]) -> bool:
    return (
        cell["modal"] != "none"
        or cell["aspect"] != "none"
        or cell["voice"] == "passive"
        or conditions["predicate_class"] == "copular"
    )


def derive_operations(
    cell: dict[str, str], structural_conditions: dict[str, Any]
) -> list[str]:
    """Return ordered structural operations and never surface wording.

    The function is intentionally pure: equal cells and conditions yield equal
    operations regardless of generator, fold, lexical choice, or KC policy.
    """

    validate_structural_conditions(cell, structural_conditions)
    operations: list[str] = []
    aspect = cell["aspect"]
    if aspect in {"perfect", "perfect_progressive"}:
        operations.append("perfect")
    if aspect in {"progressive", "perfect_progressive"}:
        operations.append("progressive")
    if cell["voice"] == "passive":
        operations.append("be_passive")
    if cell["modal"] != "none":
        operations.append("central_modal")

    clause = cell["clause"]
    needs_operator = (
        cell["polarity"] == "negative"
        or clause in {"polar_question", "non_subject_wh_question"}
    )
    if needs_operator and not _has_inherent_operator(cell, structural_conditions):
        operations.append("do_support")
    if cell["polarity"] == "negative":
        operations.append("negation")
    if clause == "polar_question":
        operations.append("operator_inversion")
    elif clause == "subject_wh_question":
        operations.append("subject_wh")
    elif clause == "non_subject_wh_question":
        operations.extend(["wh_fronting", "operator_inversion"])
    elif clause == "imperative":
        operations.append("imperative")
        subtype = structural_conditions["imperative_subtype"]
        if subtype == "emphatic_do":
            operations.append("emphatic_do")
        elif subtype in {"lets", "lets_not", "let_pronoun"}:
            operations.append("let_imperative")
    return operations


def derive_agreement_site(
    cell: dict[str, str], structural_conditions: dict[str, Any]
) -> str:
    """Derive the finite agreement site from the same structural inputs."""

    operations = derive_operations(cell, structural_conditions)
    if cell["clause"] == "imperative":
        return "none"
    if cell["modal"] != "none":
        return "modal"
    if "do_support" in operations:
        return "do"
    if cell["aspect"] in {"perfect", "perfect_progressive"}:
        return "have"
    if (
        cell["aspect"] == "progressive"
        or cell["voice"] == "passive"
        or structural_conditions["predicate_class"] == "copular"
    ):
        return "be"
    return "main_verb"


def structural_evidence(
    cell: dict[str, str], structural_conditions: dict[str, Any]
) -> dict[str, Any]:
    """Canonical evidence record shared by measurement, KCs, and simulation."""

    return {
        "cell": dict(grammar_cell(cell)),
        "operations": derive_operations(cell, structural_conditions),
        "predicate_class": structural_conditions["predicate_class"],
        "agreement_site": derive_agreement_site(cell, structural_conditions),
        "agreement_conditions": {
            "subject_person": structural_conditions["subject_person"],
            "subject_number": structural_conditions["subject_number"],
        },
    }


def evaluate_structural_rule(
    expression: dict[str, Any], evidence: dict[str, Any]
) -> tuple[bool, dict[str, Any]]:
    """Evaluate the small declarative rule language over structural evidence."""

    if "all" in expression:
        evaluated = [evaluate_structural_rule(part, evidence) for part in expression["all"]]
        matched = all(result for result, _ in evaluated)
        return matched, {"matched": matched, "operator": "all", "parts": [row for _, row in evaluated]}
    if "any" in expression:
        evaluated = [evaluate_structural_rule(part, evidence) for part in expression["any"]]
        matched = any(result for result, _ in evaluated)
        return matched, {"matched": matched, "operator": "any", "parts": [row for _, row in evaluated]}
    if "cell" in expression:
        checks = []
        for field, expected in expression["cell"].items():
            actual = evidence["cell"][field]
            matched = actual in expected if isinstance(expected, list) else actual == expected
            checks.append({"field": f"cell.{field}", "expected": expected, "actual": actual, "matched": matched})
        matched = all(row["matched"] for row in checks)
        return matched, {"matched": matched, "operator": "cell", "checks": checks}
    if "operation" in expression:
        expected = expression["operation"]
        actual = evidence["operations"]
        matched = expected in actual
        return matched, {"matched": matched, "field": "operations", "expected": expected, "actual": actual}
    for field in ("agreement_site", "predicate_class"):
        if field in expression:
            expected = expression[field]
            actual = evidence[field]
            matched = actual in expected if isinstance(expected, list) else actual == expected
            return matched, {"matched": matched, "field": field, "expected": expected, "actual": actual}
    raise ValueError(f"unknown structural activation expression: {expression}")
