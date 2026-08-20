"""Shared grammar domains and validation at scientific record boundaries."""

from __future__ import annotations

from typing import Any


GRAMMAR_VALUES = {
    "tense": {"present", "past", "NA"},
    "aspect": {"none", "progressive", "perfect", "perfect_progressive"},
    "voice": {"active", "passive"},
    "polarity": {"positive", "negative"},
    "clause": {
        "declarative",
        "polar_question",
        "subject_wh_question",
        "non_subject_wh_question",
        "imperative",
    },
    "modal": {"none", "can", "could", "may", "might", "must", "shall", "should", "will", "would"},
}
DIMENSIONS = tuple(GRAMMAR_VALUES)
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
    "canonical_cell_id",
    "canonical_split",
    "sequence_index",
    "timestamp",
    "correct",
    "item_difficulty",
    "dataset_split",
}
FORBIDDEN_BASE_EVENT_FIELDS = FORBIDDEN_OBSERVABLE_FIELDS | {"kc_ids", "opportunity_indices"}
ORACLE_EVENT_FIELDS = {
    "event_id",
    "learner_id",
    "item_id",
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
    if value["clause"] == "imperative" and (value["tense"] != "NA" or value["modal"] != "none"):
        raise ValueError(f"{label}: imperatives require tense=NA and modal=none")
    if value["modal"] != "none" and value["tense"] != "NA":
        raise ValueError(f"{label}: modal cells require tense=NA")
    return value


def kc_opportunity(value: Any, *, label: str = "KC opportunity") -> dict[str, Any]:
    required = {
        "opportunity_id",
        "split",
        "canonical_cell_id",
        "cell",
        "realization_spec",
        "realization_operations",
        "source_descriptor_ids",
        "source_mapping_notes",
    }
    if not isinstance(value, dict) or not required <= set(value):
        raise ValueError(f"{label}: missing required fields {sorted(required - set(value or {}))}")
    grammar_cell(value["cell"], label=f"{label}.cell")
    if set(value["source_mapping_notes"]) != set(value["source_descriptor_ids"]):
        raise ValueError(f"{label}: source notes do not match source IDs")
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


# Compatibility names retain their former import surface while separating the
# two record concepts explicitly.
interaction = projected_kt_interaction
observable_interaction = observable_base_event
