"""Generator-independent candidate and accepted-item records."""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any

from ..io import stable_id


ITEM_FIELDS = {
    "item_id",
    "measurement_opportunity_id",
    "canonical_cell_id",
    "source_descriptor_ids",
    "generator_id",
    "item_family",
    "content",
    "target_answer",
    "accepted_answers",
    "validated_structure",
    "quality_diagnostics",
    "generation_metadata",
    "validation_metadata",
}
FORBIDDEN_GENERATION_KEYS = {
    "kc_id",
    "kc_ids",
    "kc_policy",
    "canonical_split",
    "dataset_split",
    "fold",
    "fold_id",
    "evaluation_role",
    "probe_type",
}
KNOWN_FAMILIES = {"standalone_completion", "dialogue_completion"}


def nested_keys(value: Any) -> set[str]:
    found: set[str] = set()
    if isinstance(value, dict):
        for key, child in value.items():
            found.add(str(key))
            found.update(nested_keys(child))
    elif isinstance(value, list):
        for child in value:
            found.update(nested_keys(child))
    return found


def valid_content(item_family: str, content: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(content, dict):
        return ["content must be an object"]
    if item_family == "standalone_completion":
        if set(content) != {"prompt"} or not isinstance(content.get("prompt"), str) or not content.get("prompt", "").strip():
            errors.append("standalone content requires exactly one non-empty prompt")
    elif item_family == "dialogue_completion":
        if set(content) != {"turns", "learner_prompt"}:
            errors.append("dialogue content requires turns and learner_prompt")
        turns = content.get("turns")
        if not isinstance(turns, list) or not turns:
            errors.append("dialogue turns must be a non-empty list")
        elif any(
            not isinstance(turn, dict)
            or set(turn) != {"speaker", "text"}
            or not isinstance(turn["speaker"], str)
            or not isinstance(turn["text"], str)
            or not turn["text"].strip()
            for turn in turns
        ):
            errors.append("each dialogue turn requires non-empty speaker and text strings")
        if not isinstance(content.get("learner_prompt"), str) or not content.get("learner_prompt", "").strip():
            errors.append("dialogue learner_prompt must be non-empty")
    else:
        errors.append(f"unknown item_family {item_family!r}")
    return errors


def item_identity(item: dict[str, Any]) -> str:
    """Hash opportunity identity plus concrete surface content and generator."""

    return stable_id(
        "ITEM",
        "generator_independent_item_v1",
        item["measurement_opportunity_id"],
        item["canonical_cell_id"],
        item["generator_id"],
        item["item_family"],
        item["content"],
        item["target_answer"],
        item["accepted_answers"],
    )


def candidate_item(
    *,
    opportunity: dict[str, Any],
    generator_id: str,
    item_family: str,
    content: dict[str, Any],
    target_answer: str,
    accepted_answers: list[str],
    generation_metadata: dict[str, Any],
) -> dict[str, Any]:
    errors = valid_content(item_family, content)
    if errors:
        raise ValueError("; ".join(errors))
    if not isinstance(target_answer, str) or not target_answer.strip():
        raise ValueError("target_answer must be a non-empty string")
    if (
        not isinstance(accepted_answers, list)
        or not accepted_answers
        or any(not isinstance(value, str) or not value.strip() for value in accepted_answers)
        or len(accepted_answers) != len(set(accepted_answers))
        or target_answer not in accepted_answers
    ):
        raise ValueError("accepted_answers must be unique strings containing target_answer")
    item = {
        "item_id": "",
        "measurement_opportunity_id": opportunity["measurement_opportunity_id"],
        "canonical_cell_id": opportunity["canonical_cell_id"],
        "source_descriptor_ids": list(opportunity["source_descriptor_ids"]),
        "generator_id": generator_id,
        "item_family": item_family,
        "content": content,
        "target_answer": target_answer,
        "accepted_answers": accepted_answers,
        "validated_structure": {},
        "quality_diagnostics": {},
        "generation_metadata": generation_metadata,
        "validation_metadata": {},
    }
    item["item_id"] = item_identity(item)
    return item


def item_bank_record(item: dict[str, Any]) -> dict[str, Any]:
    """Return the intrinsic accepted item, excluding evaluator evidence."""

    fields = (
        "item_id",
        "measurement_opportunity_id",
        "canonical_cell_id",
        "source_descriptor_ids",
        "generator_id",
        "item_family",
        "content",
        "target_answer",
        "accepted_answers",
    )
    return {field: item[field] for field in fields}


def item_bank_fingerprint(items: list[dict[str, Any]]) -> str:
    records = [item_bank_record(row) for row in sorted(items, key=lambda row: row["item_id"])]
    payload = json.dumps(records, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def valid_item_id(value: Any) -> bool:
    return bool(re.fullmatch(r"ITEM_[A-F0-9]{16}", str(value)))
