"""Stage 6: ontology-independent synthetic learner events over the fixed bank."""

from __future__ import annotations

import copy
import math
import re
from pathlib import Path
from typing import Any

import numpy as np

from .io import write_json


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


def _slug(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", "_", str(value).lower()).strip("_") or "empty"


def _validate_schema_activation(
    activation: dict[str, Any],
    schema: dict[str, Any],
    *,
    context: str,
) -> None:
    """Validate the small feature-condition language against a declared schema."""

    if not isinstance(activation, dict) or not activation:
        raise ValueError(f"{context} activation must be a non-empty mapping")
    dimensions = schema["dimensions"]
    unknown_dimensions = set(activation) - set(dimensions)
    if unknown_dimensions:
        raise ValueError(
            f"{context} uses unknown dimensions: {sorted(unknown_dimensions)}"
        )
    for dimension, expected in activation.items():
        if isinstance(expected, list):
            if not expected:
                raise ValueError(f"{context} has an empty value list for {dimension}")
            values = set(expected)
        elif isinstance(expected, dict):
            if set(expected) != {"not"}:
                raise ValueError(
                    f"{context} has an invalid condition for {dimension}: {expected}"
                )
            values = {expected["not"]}
        elif isinstance(expected, str):
            values = {expected}
        else:
            raise ValueError(
                f"{context} has an invalid condition for {dimension}: {expected}"
            )
        unknown_values = values - set(dimensions[dimension]["allowed_values"])
        if unknown_values:
            raise ValueError(
                f"{context} uses undeclared values for {dimension}: "
                f"{sorted(unknown_values)}"
            )


def _validate_world_inputs(
    declared: dict[str, Any],
    schema: dict[str, Any],
    cells: list[dict[str, Any]],
) -> None:
    dimensions = list(schema["dimension_order"])
    if len(dimensions) != len(set(dimensions)) or set(dimensions) != set(
        schema["dimensions"]
    ):
        raise ValueError("grammar schema has inconsistent dimensions")
    for cell in cells:
        features = cell["features"]
        if set(features) != set(dimensions):
            raise ValueError(f"latent-world cell has wrong dimensions: {cell['cell_id']}")
        _validate_schema_activation(
            features,
            schema,
            context=f"cell {cell['cell_id']}",
        )
    for index, adjustment in enumerate(
        declared.get("difficulty", {}).get("adjustments", [])
    ):
        _validate_schema_activation(
            adjustment["activation"],
            schema,
            context=f"difficulty adjustment {index}",
        )


def materialize_latent_world(
    declared: dict[str, Any],
    schema: dict[str, Any],
    cells: list[dict[str, Any]],
) -> dict[str, Any]:
    """Expand concise latent components without language-specific constants."""

    _validate_world_inputs(declared, schema, cells)
    dimensions = list(schema["dimension_order"])
    observed = {
        dimension: {cell["features"][dimension] for cell in cells}
        for dimension in dimensions
    }
    hidden: list[dict[str, Any]] = []
    components = declared.get("latent_structure", {}).get("components")
    if components is None:
        # Historical/fixture declarations may spell out dimensions directly.
        # They still pass through the same schema and support validation.
        hidden = copy.deepcopy(declared.get("hidden_dimensions", []))
        if not hidden:
            raise ValueError("latent world declares no latent components")
        for dimension in hidden:
            _validate_schema_activation(
                dimension["activation"],
                schema,
                context=f"latent dimension {dimension['id']}",
            )
    else:
        if not isinstance(components, list) or not components:
            raise ValueError("latent_structure.components must be a non-empty list")
    for component in components or []:
        common = {
            "initial_mastery_beta": list(component["initial_mastery_beta"]),
            "learning_rate": float(component["learning_rate"]),
            "weight": float(component.get("weight", 1.0)),
        }
        kind = component["kind"]
        if kind == "feature_values":
            background = {
                dimension: set(values)
                for dimension, values in component.get(
                    "background_values", {}
                ).items()
            }
            unknown_dimensions = set(background) - set(dimensions)
            if unknown_dimensions:
                raise ValueError(
                    f"unknown background dimensions: {sorted(unknown_dimensions)}"
                )
            for dimension in dimensions:
                allowed = schema["dimensions"][dimension]["allowed_values"]
                unknown_values = background.get(dimension, set()) - set(allowed)
                if unknown_values:
                    raise ValueError(
                        f"unknown background values for {dimension}: "
                        f"{sorted(unknown_values)}"
                    )
                for value in allowed:
                    if value in observed[dimension] and value not in background.get(
                        dimension, set()
                    ):
                        hidden.append(
                            {
                                "id": (
                                    f"hidden_feature__{_slug(dimension)}"
                                    f"__{_slug(value)}"
                                ),
                                "activation": {dimension: value},
                                **common,
                            }
                        )
        elif kind == "declared_interactions":
            for interaction in component["interactions"]:
                activation = dict(interaction["activation"])
                _validate_schema_activation(
                    activation,
                    schema,
                    context=f"interaction {interaction['id']}",
                )
                hidden.append(
                    {
                        "id": f"hidden_interaction__{_slug(interaction['id'])}",
                        "activation": activation,
                        **common,
                    }
                )
        elif kind == "exact_cells":
            if component["scope"] != "all_cells":
                raise ValueError(f"unknown exact-cell scope: {component['scope']}")
            for cell in sorted(
                cells,
                key=lambda row: tuple(
                    row["features"][dimension] for dimension in dimensions
                ),
            ):
                activation = {
                    dimension: cell["features"][dimension]
                    for dimension in dimensions
                }
                label = "__".join(
                    f"{_slug(dimension)}_{_slug(activation[dimension])}"
                    for dimension in dimensions
                )
                hidden.append(
                    {
                        "id": f"hidden_cell__{label}",
                        "activation": activation,
                        **common,
                    }
                )
        else:
            raise ValueError(f"unknown latent component kind: {kind}")

    for dimension in hidden:
        _validate_schema_activation(
            dimension["activation"],
            schema,
            context=f"materialized latent dimension {dimension['id']}",
        )
    ids = [row["id"] for row in hidden]
    if len(ids) != len(set(ids)):
        raise ValueError("materialized latent dimensions have duplicate IDs")
    unsupported = [
        row["id"]
        for row in hidden
        if not any(_matches(cell["features"], row["activation"]) for cell in cells)
    ]
    if unsupported:
        raise ValueError(f"latent dimensions activate no cells: {unsupported}")
    materialized = copy.deepcopy(declared)
    materialized["hidden_dimensions"] = hidden
    return materialized


def _difficulty(features: dict[str, str], world: dict[str, Any], active_count: int) -> float:
    policy = world["difficulty"]
    value = policy["base"] + policy["per_active_dimension"] * active_count
    for adjustment in policy.get("adjustments", []):
        if _matches(features, adjustment["activation"]):
            value += adjustment["amount"]
    return float(value)


def _temporal_split(sequence_index: int, event_count: int, policy: dict[str, float]) -> str:
    position = (sequence_index - 1) / event_count
    if position < policy["train_fraction"]:
        return "train"
    if position < policy["train_fraction"] + policy["validation_fraction"]:
        return "validation"
    return "test"


def _ordered_items(
    accepted_items: list[dict[str, Any]],
    item_order: str,
    learner_number: int,
    pass_number: int,
) -> list[dict[str, Any]]:
    if item_order == "rotate_each_pass":
        offset = pass_number % len(accepted_items)
    elif item_order == "counterbalanced_rotate_by_learner_and_pass":
        offset = (learner_number - 1 + pass_number) % len(accepted_items)
    else:
        raise ValueError(f"unknown simulation item_order: {item_order}")
    return accepted_items[offset:] + accepted_items[:offset]


def _response_probability(
    mastery: float, difficulty: float, response: dict[str, float]
) -> float:
    latent = 1.0 / (
        1.0
        + math.exp(
            -(
                response["discrimination"] * (mastery - 0.5)
                - difficulty
            )
        )
    )
    return float(
        response["guess_floor"]
        + (1.0 - response["guess_floor"] - response["slip_ceiling"]) * latent
    )


def _response_for_features(
    features: dict[str, str],
    mastery: dict[str, float],
    background: float,
    world: dict[str, Any],
) -> tuple[list[dict[str, Any]], float, float]:
    active = [
        dimension
        for dimension in world["hidden_dimensions"]
        if _matches(features, dimension["activation"])
    ]
    if active:
        total_weight = sum(float(row.get("weight", 1.0)) for row in active)
        active_mastery = sum(
            mastery[row["id"]] * float(row.get("weight", 1.0)) for row in active
        ) / total_weight
    else:
        active_mastery = background
    difficulty = _difficulty(features, world, len(active))
    probability = _response_probability(
        active_mastery, difficulty, world["response"]
    )
    return active, difficulty, probability


def _update_mastery(
    active: list[dict[str, Any]],
    mastery: dict[str, float],
    background: float,
    world: dict[str, Any],
) -> float:
    if active:
        for dimension in active:
            current = mastery[dimension["id"]]
            mastery[dimension["id"]] = current + dimension["learning_rate"] * (
                1.0 - current
            )
        return background
    rate = float(world.get("background_learning_rate", 0.08))
    return background + rate * (1.0 - background)


def simulate(
    accepted_items: list[dict[str, Any]],
    fold: list[dict[str, Any]],
    world: dict[str, Any],
    *,
    oracle_path: Path | None = None,
) -> list[dict[str, Any]]:
    """Generate fixed BaseEvents without reading candidate KC definitions."""

    rng = np.random.default_rng(world["seed"])
    fold_by_cell = {row["cell_id"]: row for row in fold}
    if {item["cell_id"] for item in accepted_items} - set(fold_by_cell):
        raise ValueError("accepted item bank contains an unknown GrammarCell")

    hidden = world["hidden_dimensions"]
    events = []
    oracle_rows = []
    total_per_learner = len(accepted_items) * world["passes"]
    for learner_number in range(1, world["learners"] + 1):
        learner_id = f"learner_{learner_number:03d}"
        mastery = {
            dimension["id"]: float(rng.beta(*dimension["initial_mastery_beta"]))
            for dimension in hidden
        }
        background = float(rng.beta(*world["background_mastery_beta"]))
        sequence_index = 0
        for pass_number in range(world["passes"]):
            ordered_items = _ordered_items(
                accepted_items,
                world["item_order"],
                learner_number,
                pass_number,
            )
            for item in ordered_items:
                sequence_index += 1
                fold_row = fold_by_cell[item["cell_id"]]
                features = fold_row["features"]
                active, difficulty, probability = _response_for_features(
                    features, mastery, background, world
                )
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
                background = _update_mastery(active, mastery, background, world)

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


def simulate_frozen_probes(
    accepted_items: list[dict[str, Any]],
    fold: list[dict[str, Any]],
    world: dict[str, Any],
    protocol: dict[str, Any],
    *,
    oracle_path: Path | None = None,
) -> list[dict[str, Any]]:
    """Development acquisition followed by non-updating grammar probes."""

    if protocol["mode"] != "frozen_probe":
        raise ValueError(f"unknown simulation protocol mode: {protocol['mode']}")
    acquisition_passes = int(protocol["acquisition_passes"])
    train_passes = int(protocol["selection_train_passes"])
    probe_repeats = int(protocol["probe_repeats"])
    if not 0 < train_passes < acquisition_passes or probe_repeats < 1:
        raise ValueError(
            "frozen probes require train_passes < acquisition_passes and probes"
        )

    fold_by_cell = {row["cell_id"]: row for row in fold}
    if len(fold_by_cell) != len(fold):
        raise ValueError("grammar fold contains duplicate cell IDs")
    if {item["cell_id"] for item in accepted_items} - set(fold_by_cell):
        raise ValueError("accepted item bank contains an unknown GrammarCell")
    ordered_bank = sorted(accepted_items, key=lambda row: row["item_id"])
    development_items = [
        row
        for row in ordered_bank
        if fold_by_cell[row["cell_id"]]["grammar_split"] == "development"
    ]
    if not development_items:
        raise ValueError("frozen-probe acquisition has no development items")

    rng = np.random.default_rng(world["seed"])
    events: list[dict[str, Any]] = []
    oracle_rows: list[dict[str, Any]] = []
    for learner_number in range(1, int(world["learners"]) + 1):
        learner_id = f"learner_{learner_number:03d}"
        mastery = {
            dimension["id"]: float(
                rng.beta(*dimension["initial_mastery_beta"])
            )
            for dimension in world["hidden_dimensions"]
        }
        background = float(rng.beta(*world["background_mastery_beta"]))
        sequence_index = 0

        schedule: list[tuple[str, str, bool, bool, int, list[dict[str, Any]]]] = []
        for pass_number in range(acquisition_passes):
            schedule.append(
                (
                    "acquisition",
                    "train" if pass_number < train_passes else "validation",
                    True,
                    True,
                    pass_number,
                    development_items,
                )
            )
        for probe_number in range(probe_repeats):
            schedule.append(
                (
                    "probe",
                    "test",
                    False,
                    False,
                    acquisition_passes + probe_number,
                    ordered_bank,
                )
            )

        for phase, dataset_split, updates_mastery, updates_history, order_index, bank in schedule:
            for item in _ordered_items(
                bank,
                protocol["item_order"],
                learner_number,
                order_index,
            ):
                sequence_index += 1
                fold_row = fold_by_cell[item["cell_id"]]
                features = fold_row["features"]
                active, difficulty, probability = _response_for_features(
                    features, mastery, background, world
                )
                correct = int(rng.random() < probability)
                event_id = f"event_{len(events) + 1:07d}"
                events.append(
                    {
                        "event_id": event_id,
                        "learner_id": learner_id,
                        "item_id": item["item_id"],
                        "correct": correct,
                        "sequence_index": sequence_index,
                        "dataset_split": dataset_split,
                        "item_difficulty": round(difficulty, 6),
                        "grammar_split": fold_row["grammar_split"],
                        "protocol_phase": phase,
                        "updates_mastery": updates_mastery,
                        "updates_history": updates_history,
                    }
                )
                oracle_rows.append(
                    {
                        "event_id": event_id,
                        "active_hidden_dimensions": [row["id"] for row in active],
                        "response_probability": round(probability, 8),
                        "updates_mastery": updates_mastery,
                    }
                )
                if updates_mastery:
                    background = _update_mastery(
                        active, mastery, background, world
                    )

    if oracle_path is not None:
        write_json(
            oracle_path,
            {
                "warning": "Private simulation evidence; never supplied to KC selection or KT.",
                "world_id": world["world_id"],
                "protocol_id": protocol["protocol_id"],
                "events": oracle_rows,
            },
        )
    return events
