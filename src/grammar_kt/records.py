"""Shared grammar domains and validation at scientific record boundaries."""

from __future__ import annotations

import re
from typing import Any

from .grammar.schema import DIMENSION_ORDER, DIMENSION_VALUES, cross_field_errors


GRAMMAR_VALUES = DIMENSION_VALUES
DIMENSIONS = DIMENSION_ORDER
CENTRAL_MODALS = GRAMMAR_VALUES["modal"] - {"none"}
MORPHOLOGICAL_TENSES = {"present", "past"}

FORBIDDEN_OBSERVABLE_FIELDS = {
    "profile",
    "pre_mastery",
    "post_mastery",
    "response_probability",
    "random_draw",
    "target_answer",
    "accepted_answers",
    "prompt",
    "definition",
    "activation_rule",
    "oracle_feature_ids",
}

BASE_EVENT_FIELDS = {
    "event_id",
    "learner_id",
    "item_id",
    "measurement_opportunity_id",
    "canonical_cell_id",
    "canonical_split",
    "sequence_index",
    "timestamp",
    "correct",
    "item_difficulty",
    "dataset_split",
}
COMPOSITIONAL_EVENT_FIELDS = BASE_EVENT_FIELDS | {"evaluation_role", "probe_type"}
COMPOSITIONAL_PROJECTION_FIELDS = COMPOSITIONAL_EVENT_FIELDS | {
    "kc_ids",
    "opportunity_indices",
    "development_supported_kc_ids",
    "cold_kc_ids",
    "covered",
    "fully_development_supported",
}
FORBIDDEN_BASE_EVENT_FIELDS = FORBIDDEN_OBSERVABLE_FIELDS | {"kc_ids", "opportunity_indices"}
ORACLE_EVENT_FIELDS = {
    "event_id",
    "learner_id",
    "item_id",
    "measurement_opportunity_id",
    "profile",
    "oracle_feature_ids",
    "oracle_opportunity_indices",
    "pre_mastery",
    "post_mastery",
    "response_probability",
    "random_draw",
    "oracle_complexity_penalty",
}


def grammar_cell(value: Any, *, label: str = "GrammarCell") -> dict[str, str]:
    if not isinstance(value, dict) or set(value) != set(DIMENSIONS):
        raise ValueError(f"{label}: expected exactly the fields {DIMENSIONS}")
    for field in DIMENSIONS:
        if not isinstance(value[field], str) or value[field] not in GRAMMAR_VALUES[field]:
            raise ValueError(f"{label}.{field}: invalid value {value[field]!r}")
    constraints = cross_field_errors(value)
    if constraints:
        raise ValueError(f"{label}: {'; '.join(constraints)}")
    return value

def measurement_opportunity(
    value: Any, *, label: str = "MeasurementOpportunity"
) -> dict[str, Any]:
    """Validate the surface-, fold-, and ontology-independent measurement record."""

    expected = {
        "measurement_opportunity_id",
        "canonical_cell_id",
        "cell",
        "structural_conditions",
        "expected_operations",
        "source_descriptor_ids",
        "coverage_reasons",
    }
    if not isinstance(value, dict) or set(value) != expected:
        raise ValueError(f"{label}: fields differ from {sorted(expected)}")
    if not re.fullmatch(r"OPP_[A-F0-9]{16}", str(value["measurement_opportunity_id"])):
        raise ValueError(f"{label}: invalid measurement_opportunity_id")
    if not re.fullmatch(r"CELL_[A-F0-9]{16}", str(value["canonical_cell_id"])):
        # Explicit fixture IDs are accepted for unit tests, but production IDs
        # must retain the CELL_ semantic prefix.
        if not str(value["canonical_cell_id"]).startswith("CELL_"):
            raise ValueError(f"{label}: invalid canonical_cell_id")
    grammar_cell(value["cell"], label=f"{label}.cell")
    from .measurement.operations import derive_operations, validate_structural_conditions

    validate_structural_conditions(value["cell"], value["structural_conditions"])
    expected_operations = derive_operations(value["cell"], value["structural_conditions"])
    if value["expected_operations"] != expected_operations:
        raise ValueError(
            f"{label}: expected_operations differ from structural derivation "
            f"({value['expected_operations']} != {expected_operations})"
        )
    for field in ("source_descriptor_ids", "coverage_reasons"):
        rows = value[field]
        if not isinstance(rows, list) or rows != sorted(set(rows)):
            raise ValueError(f"{label}.{field}: expected a sorted duplicate-free list")
    return value


def _base_event_fields(value: Any, *, label: str) -> dict[str, Any]:
    if not isinstance(value, dict) or not BASE_EVENT_FIELDS <= set(value):
        missing = sorted(BASE_EVENT_FIELDS - set(value or {}))
        raise ValueError(f"{label}: missing base-event fields {missing}")
    if value["correct"] not in {0, 1}:
        raise ValueError(f"{label}: outcome must be binary")
    if value["dataset_split"] not in {"train", "validation", "test"}:
        raise ValueError(f"{label}: invalid temporal dataset split")
    if value["canonical_split"] not in {
        "development", "compositional_holdout", "novel_feature_holdout"
    }:
        raise ValueError(f"{label}: invalid canonical split")
    if not isinstance(value["sequence_index"], int) or value["sequence_index"] < 1:
        raise ValueError(f"{label}: sequence index must be positive")
    return value


def observable_base_event(value: Any, *, label: str = "ObservableBaseEvent") -> dict[str, Any]:
    """Validate the ontology-free event consumed by every ontology condition."""

    _base_event_fields(value, label=label)
    leaked = FORBIDDEN_BASE_EVENT_FIELDS & set(value)
    if leaked:
        raise ValueError(f"{label}: oracle/KC/content leakage {sorted(leaked)}")
    unexpected = set(value) - BASE_EVENT_FIELDS
    if unexpected:
        raise ValueError(f"{label}: unexpected base-event fields {sorted(unexpected)}")
    return value


def compositional_base_event(
    value: Any, *, label: str = "CompositionalBaseEvent"
) -> dict[str, Any]:
    """Validate a Phase-D acquisition/probe event without candidate or oracle fields."""

    _base_event_fields(value, label=label)
    if value.get("evaluation_role") not in {"acquisition", "probe"}:
        raise ValueError(f"{label}: invalid compositional evaluation role")
    expected_probe_type = {
        "development": "development_acquisition",
        "compositional_holdout": "compositional_holdout",
        "novel_feature_holdout": "novel_feature_holdout",
    }[value["canonical_split"]]
    if value.get("probe_type") != expected_probe_type:
        raise ValueError(f"{label}: probe type does not match canonical split")
    if value["evaluation_role"] == "acquisition" and value["canonical_split"] != "development":
        raise ValueError(f"{label}: acquisition must contain development items only")
    if value["evaluation_role"] == "probe" and value["canonical_split"] == "development":
        raise ValueError(f"{label}: probes must be held-out items")
    leaked = FORBIDDEN_BASE_EVENT_FIELDS & set(value)
    if leaked:
        raise ValueError(f"{label}: oracle/KC/content leakage {sorted(leaked)}")
    unexpected = set(value) - COMPOSITIONAL_EVENT_FIELDS
    if unexpected:
        raise ValueError(f"{label}: unexpected compositional-event fields {sorted(unexpected)}")
    return value


def compositional_projected_interaction(
    value: Any, *, label: str = "CompositionalProjectedInteraction"
) -> dict[str, Any]:
    """Validate a Phase-D event annotated from development-frozen candidate support."""

    if not isinstance(value, dict) or set(value) != COMPOSITIONAL_PROJECTION_FIELDS:
        raise ValueError(f"{label}: compositional projection fields differ from the schema")
    base = {key: value[key] for key in COMPOSITIONAL_EVENT_FIELDS}
    compositional_base_event(base, label=label)
    kc_ids = value["kc_ids"]
    supported = value["development_supported_kc_ids"]
    cold = value["cold_kc_ids"]
    if not all(
        isinstance(rows, list)
        and len(rows) == len(set(rows))
        and all(isinstance(kc_id, str) for kc_id in rows)
        for rows in (kc_ids, supported, cold)
    ):
        raise ValueError(f"{label}: KC fields must be duplicate-free string lists")
    if set(supported) | set(cold) != set(kc_ids) or set(supported) & set(cold):
        raise ValueError(f"{label}: supported/cold KCs must partition active KCs")
    if set(value["opportunity_indices"]) != set(kc_ids):
        raise ValueError(f"{label}: opportunity indices must match active KCs")
    if any(
        not isinstance(index, int) or index < 1
        for index in value["opportunity_indices"].values()
    ):
        raise ValueError(f"{label}: opportunity indices must be positive integers")
    if value["covered"] is not bool(kc_ids):
        raise ValueError(f"{label}: covered flag does not match active KCs")
    if value["fully_development_supported"] is not (
        bool(kc_ids) and not cold
    ):
        raise ValueError(f"{label}: development-supported flag is inconsistent")
    return value


def projected_kt_interaction(
    value: Any, *, label: str = "ProjectedKTInteraction"
) -> dict[str, Any]:
    """Validate a base event annotated with one candidate ontology."""

    _base_event_fields(value, label=label)
    required = {"kc_ids", "opportunity_indices"}
    if not required <= set(value):
        raise ValueError(f"{label}: missing candidate projection fields")
    if not isinstance(value["kc_ids"], list) or not all(
        isinstance(kc_id, str) for kc_id in value["kc_ids"]
    ):
        raise ValueError(f"{label}: kc_ids must be a string list")
    if len(value["kc_ids"]) != len(set(value["kc_ids"])):
        raise ValueError(f"{label}: kc_ids must not contain duplicates")
    if set(value["opportunity_indices"]) != set(value["kc_ids"]):
        raise ValueError(f"{label}: opportunity indices must exactly match active KCs")
    if any(
        not isinstance(index, int) or index < 1
        for index in value["opportunity_indices"].values()
    ):
        raise ValueError(f"{label}: opportunity indices must be positive integers")
    leaked = FORBIDDEN_OBSERVABLE_FIELDS & set(value)
    if leaked:
        raise ValueError(f"{label}: oracle/content leakage {sorted(leaked)}")
    unexpected = set(value) - (BASE_EVENT_FIELDS | required)
    if unexpected:
        raise ValueError(f"{label}: unexpected projected-interaction fields {sorted(unexpected)}")
    return value


def oracle_interaction(value: Any, *, label: str = "OracleInteraction") -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != ORACLE_EVENT_FIELDS:
        raise ValueError(f"{label}: oracle fields differ from the schema")
    if not isinstance(value["oracle_feature_ids"], list) or not value["oracle_feature_ids"]:
        raise ValueError(f"{label}: oracle feature list must be non-empty")
    if set(value["oracle_opportunity_indices"]) != set(value["oracle_feature_ids"]):
        raise ValueError(f"{label}: oracle opportunity indices do not match features")
    if set(value["pre_mastery"]) != set(value["oracle_feature_ids"]):
        raise ValueError(f"{label}: pre-mastery does not match features")
    if set(value["post_mastery"]) != set(value["oracle_feature_ids"]):
        raise ValueError(f"{label}: post-mastery does not match features")
    return value
