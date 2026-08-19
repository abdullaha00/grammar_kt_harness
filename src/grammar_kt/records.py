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


def interaction(value: Any, *, label: str = "Interaction") -> dict[str, Any]:
    required = {
        "event_id",
        "learner_id",
        "item_id",
        "sequence_index",
        "timestamp",
        "correct",
        "kc_ids",
        "opportunity_indices",
        "dataset_split",
    }
    if not isinstance(value, dict) or not required <= set(value):
        raise ValueError(f"{label}: missing required fields")
    if value["correct"] not in {0, 1} or not value["kc_ids"]:
        raise ValueError(f"{label}: outcome must be binary and KC list non-empty")
    return value


def observable_interaction(value: Any, *, label: str = "Interaction") -> dict[str, Any]:
    interaction(value, label=label)
    leaked = FORBIDDEN_OBSERVABLE_FIELDS & set(value)
    if leaked:
        raise ValueError(f"{label}: oracle/content leakage {sorted(leaked)}")
    return value
