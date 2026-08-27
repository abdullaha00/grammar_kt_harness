"""Stage 6: ontology-independent synthetic learner events over the fixed bank."""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any

import numpy as np

from .io import read_yaml, write_json


def _matches(features: dict[str, str], condition: dict[str, Any]) -> bool:
    for field, expected in condition.items():
        actual = features[field]
        if isinstance(expected, list) and actual not in expected:
            return False
        if isinstance(expected, dict) and actual == expected["not"]:
            return False
        if not isinstance(expected, (list, dict)) and actual != expected:
            return False
    return True


def _difficulty(features: dict[str, str], world: dict[str, Any], active_count: int) -> float:
    policy = world["difficulty"]
    value = policy["base"] + policy["per_active_dimension"] * active_count
    if features["voice"] == "passive":
        value += policy.get("passive_extra", 0.0)
    if features["clause"] != "declarative":
        value += policy.get("question_extra", 0.0)
    return float(value)


def _temporal_split(sequence_index: int, event_count: int, policy: dict[str, float]) -> str:
    position = (sequence_index - 1) / event_count
    if position < policy["train_fraction"]:
        return "train"
    if position < policy["train_fraction"] + policy["validation_fraction"]:
        return "validation"
    return "test"


def simulate(
    accepted_items: list[dict[str, Any]],
    fold: list[dict[str, Any]],
    config: dict[str, Any],
    *,
    oracle_path: Path | None = None,
) -> list[dict[str, Any]]:
    """Generate fixed BaseEvents without reading candidate KC definitions."""

    world = read_yaml(config["world"])
    rng = np.random.default_rng(int(world["seed"]))
    fold_by_cell = {row["cell_id"]: row for row in fold}
    if {item["cell_id"] for item in accepted_items} - set(fold_by_cell):
        raise ValueError("accepted item bank contains an unknown GrammarCell")

    hidden = world["hidden_dimensions"]
    events = []
    oracle_rows = []
    total_per_learner = len(accepted_items) * int(world["passes"])
    for learner_number in range(1, int(world["learners"]) + 1):
        learner_id = f"learner_{learner_number:03d}"
        mastery = {
            dimension["id"]: float(rng.beta(*dimension["initial_mastery_beta"]))
            for dimension in hidden
        }
        background = float(rng.beta(*world["background_mastery_beta"]))
        sequence_index = 0
        for pass_number in range(int(world["passes"])):
            offset = pass_number % len(accepted_items)
            ordered_items = accepted_items[offset:] + accepted_items[:offset]
            for item in ordered_items:
                sequence_index += 1
                fold_row = fold_by_cell[item["cell_id"]]
                features = fold_row["features"]
                active = [dimension for dimension in hidden if _matches(features, dimension["activation"])]
                active_mastery = (
                    sum(mastery[row["id"]] for row in active) / len(active)
                    if active
                    else background
                )
                difficulty = _difficulty(features, world, len(active))
                response = world["response"]
                latent = 1.0 / (
                    1.0
                    + math.exp(
                        -response["discrimination"] * (active_mastery - 0.5)
                        + difficulty
                    )
                )
                probability = response["guess_floor"] + (
                    1.0 - response["guess_floor"] - response["slip_ceiling"]
                ) * latent
                correct = int(rng.random() < probability)
                event_id = f"event_{len(events) + 1:05d}"
                events.append(
                    {
                        "event_id": event_id,
                        "learner_id": learner_id,
                        "item_id": item["item_id"],
                        "correct": correct,
                        "sequence_index": sequence_index,
                        "dataset_split": _temporal_split(sequence_index, total_per_learner, world["temporal_split"]),
                        "item_difficulty": round(difficulty, 6),
                        "grammar_split": fold_row["grammar_split"],
                    }
                )
                oracle_rows.append(
                    {
                        "event_id": event_id,
                        "active_hidden_dimensions": [row["id"] for row in active],
                        "response_probability": round(probability, 8),
                    }
                )
                if active:
                    for dimension in active:
                        current = mastery[dimension["id"]]
                        mastery[dimension["id"]] = current + dimension["learning_rate"] * (1.0 - current)
                else:
                    background += 0.08 * (1.0 - background)

    if oracle_path is not None:
        write_json(
            oracle_path,
            {
                "warning": "Private simulation evidence; never supplied to KC selection or KT.",
                "world_id": world["world_id"],
                "events": oracle_rows,
            },
        )
    return events
