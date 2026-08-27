from __future__ import annotations

from copy import deepcopy
from typing import Any

from grammar_kt.canonicalise import canonicalise
from grammar_kt.fold import apply_fold
from grammar_kt.generate import generate_items
from grammar_kt.io import load_experiment, load_typed_resource
from grammar_kt.normalise import normalise
from grammar_kt.validate_items import validate_items


PRESENT = {
    "tense": "present",
    "aspect": "none",
    "voice": "active",
    "polarity": "positive",
    "clause": "declarative",
    "modal": "none",
}
PAST_NEGATIVE = {**PRESENT, "tense": "past", "polarity": "negative"}


def base_config() -> dict[str, Any]:
    return load_experiment("fixture")


def base_bank() -> tuple[
    dict[str, Any],
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
]:
    config = base_config()
    resources = load_typed_resource(config["resource"]["data"], config["resource"]["schema"])
    mappings = normalise(resources, config["normalisation"])
    cells = canonicalise(mappings, config["canonical"]["schema"])
    candidates = generate_items(cells, config["generation"])
    accepted, judgments = validate_items(candidates, cells, config["validation"])
    fold = apply_fold(cells, config["fold"])
    return config, mappings, cells, candidates, accepted, judgments, fold


def validator_output(criteria: dict[str, Any], failing: str | None = None) -> dict[str, Any]:
    return {
        "judgments": {
            name: {"passed": name != failing, "note": "fixture judgment"}
            for name in criteria
        }
    }


def copy_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return deepcopy(rows)
