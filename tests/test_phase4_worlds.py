from __future__ import annotations

import copy

import pytest

from grammar_kt.io import read_jsonl, read_yaml

from grammar_kt.simulate import materialize_latent_world
from scripts.run_phase4_world_audit import WORLD_PATHS

from .helpers import ROOT


def _legacy_cells() -> list[dict]:
    rows = read_jsonl(
        ROOT / "experiments/post_training_v1/data/pilot_v1/opportunities.jsonl"
    )
    features = {row["canonical_cell_id"]: row["cell"] for row in rows}
    return [
        {"cell_id": cell_id, "features": values}
        for cell_id, values in sorted(features.items())
    ]


def test_phase4_world_declarations_materialize_active_dimensions() -> None:
    schema = read_yaml(ROOT / "modules/grammar/canonical/schema.yaml")
    cells = _legacy_cells()
    for path in WORLD_PATHS:
        world = materialize_latent_world(read_yaml(path), schema, cells)
        hidden = world["hidden_dimensions"]
        assert hidden
        assert len({row["id"] for row in hidden}) == len(hidden)
        assert all(
            any(
                all(
                    (
                        cell["features"][dimension] in expected
                        if isinstance(expected, list)
                        else (
                            cell["features"][dimension] != expected["not"]
                            if isinstance(expected, dict)
                            else cell["features"][dimension] == expected
                        )
                    )
                    for dimension, expected in row["activation"].items()
                )
                for cell in cells
            )
            for row in hidden
        )


def test_world_materialization_is_schema_generic() -> None:
    schema = {
        "dimension_order": ["mood", "person"],
        "dimensions": {
            "mood": {"allowed_values": ["plain", "marked"]},
            "person": {"allowed_values": ["first", "third"]},
        },
    }
    cells = [
        {
            "cell_id": "toy_a",
            "features": {"mood": "plain", "person": "first"},
        },
        {
            "cell_id": "toy_b",
            "features": {"mood": "marked", "person": "third"},
        },
    ]
    declaration = {
        "world_id": "toy",
        "latent_structure": {
            "components": [
                {
                    "kind": "feature_values",
                    "background_values": {"mood": ["plain"]},
                    "initial_mastery_beta": [2.0, 2.0],
                    "learning_rate": 0.1,
                    "weight": 1.0,
                },
                {
                    "kind": "exact_cells",
                    "scope": "all_cells",
                    "initial_mastery_beta": [2.0, 3.0],
                    "learning_rate": 0.05,
                    "weight": 0.5,
                },
            ]
        },
    }
    world = materialize_latent_world(declaration, schema, cells)
    activations = [row["activation"] for row in world["hidden_dimensions"]]
    assert {"mood": "marked"} in activations
    assert {"person": "first"} in activations
    assert {"person": "third"} in activations
    assert {"mood": "plain", "person": "first"} in activations
    assert {"mood": "marked", "person": "third"} in activations
    assert not any("tense" in row for row in activations)


def test_world_materialization_rejects_undeclared_activation_values() -> None:
    schema = read_yaml(ROOT / "modules/grammar/canonical/schema.yaml")
    cells = _legacy_cells()
    declared = read_yaml(ROOT / "modules/simulation/worlds/phase4_mixed.yaml")
    bad_interaction = copy.deepcopy(declared)
    bad_interaction["latent_structure"]["components"][1]["interactions"][0][
        "activation"
    ] = {"aspect": "undeclared"}
    with pytest.raises(ValueError, match="interaction.*undeclared values"):
        materialize_latent_world(bad_interaction, schema, cells)

    bad_adjustment = copy.deepcopy(declared)
    bad_adjustment["difficulty"]["adjustments"][0]["activation"] = {
        "unknown_dimension": "anything"
    }
    with pytest.raises(ValueError, match="difficulty adjustment.*unknown dimensions"):
        materialize_latent_world(bad_adjustment, schema, cells)


def test_generic_simulator_has_no_english_difficulty_shortcuts() -> None:
    source = (ROOT / "src/grammar_kt/simulate.py").read_text(encoding="utf-8")
    assert "passive_extra" not in source
    assert "question_extra" not in source
