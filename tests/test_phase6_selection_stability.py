from __future__ import annotations

from pathlib import Path

from scripts.run_phase6_selection_stability import (
    FULL_LEARNERS,
    NESTED_LEARNERS,
    REFERENCE_SEED,
    SEEDS,
    _read_events,
    _write_events,
    selection_schedule,
    simulate_event_stream,
    subset_selection_events,
)


def test_default_schedule_is_staged_nine_selections_not_cartesian() -> None:
    schedule = selection_schedule()
    assert len(schedule) == 9
    assert len({row["condition_id"] for row in schedule}) == 9
    assert {
        row["learners"] for row in schedule if row["seed"] == REFERENCE_SEED
    } == set(NESTED_LEARNERS)
    assert {
        row["seed"] for row in schedule if row["learners"] == FULL_LEARNERS
    } == set(SEEDS)
    assert not any(
        row["seed"] != REFERENCE_SEED and row["learners"] != FULL_LEARNERS
        for row in schedule
    )


def test_nested_selection_subset_is_numeric_and_excludes_all_probe_outcomes() -> None:
    inventory = {"development_item_ids": ["dev_item"]}
    events = []
    for learner in ("learner_010", "learner_002", "learner_001"):
        events.extend(
            [
                {
                    "event_id": f"{learner}_train",
                    "learner_id": learner,
                    "item_id": "dev_item",
                    "dataset_split": "train",
                    "grammar_split": "development",
                },
                {
                    "event_id": f"{learner}_validation",
                    "learner_id": learner,
                    "item_id": "dev_item",
                    "dataset_split": "validation",
                    "grammar_split": "development",
                },
                {
                    "event_id": f"{learner}_development_probe",
                    "learner_id": learner,
                    "item_id": "dev_item",
                    "dataset_split": "test",
                    "grammar_split": "development",
                },
                {
                    "event_id": f"{learner}_holdout_probe",
                    "learner_id": learner,
                    "item_id": "holdout_item",
                    "dataset_split": "test",
                    "grammar_split": "compositional_holdout",
                },
            ]
        )
    selected, evidence = subset_selection_events(events, inventory, 2)
    assert evidence["learner_ids"] == ["learner_001", "learner_002"]
    assert len(selected) == 4
    assert {row["dataset_split"] for row in selected} == {"train", "validation"}
    assert {row["grammar_split"] for row in selected} == {"development"}
    assert evidence["holdout_events_supplied"] == 0
    assert evidence["reserved_test_events_supplied"] == 0


def test_toy_frozen_stream_and_deterministic_gzip_are_reproducible(
    tmp_path: Path,
) -> None:
    schema = {
        "schema_id": "toy_mood",
        "dimension_order": ["mood"],
        "dimensions": {"mood": {"allowed_values": ["plain", "marked"]}},
    }
    cells = [
        {"cell_id": "toy_dev", "features": {"mood": "plain"}},
        {"cell_id": "toy_holdout", "features": {"mood": "marked"}},
    ]
    items = [
        {"item_id": "item_dev", "cell_id": "toy_dev"},
        {"item_id": "item_holdout", "cell_id": "toy_holdout"},
    ]
    fold = [
        {
            "cell_id": "toy_dev",
            "grammar_split": "development",
            "features": {"mood": "plain"},
        },
        {
            "cell_id": "toy_holdout",
            "grammar_split": "compositional_holdout",
            "features": {"mood": "marked"},
        },
    ]
    world = {
        "world_id": "toy_world",
        "seed": 7,
        "learners": 3,
        "latent_structure": {
            "components": [
                {
                    "kind": "feature_values",
                    "background_values": {"mood": ["plain"]},
                    "initial_mastery_beta": [2.0, 2.0],
                    "learning_rate": 0.1,
                    "weight": 1.0,
                }
            ]
        },
        "background_mastery_beta": [2.0, 2.0],
        "background_learning_rate": 0.1,
        "difficulty": {
            "base": 0.0,
            "per_active_dimension": 0.0,
            "adjustments": [],
        },
        "response": {
            "discrimination": 2.0,
            "guess_floor": 0.05,
            "slip_ceiling": 0.05,
        },
    }
    protocol = {
        "protocol_id": "toy_frozen",
        "mode": "frozen_probe",
        "acquisition_passes": 2,
        "selection_train_passes": 1,
        "probe_repeats": 1,
        "item_order": "counterbalanced_rotate_by_learner_and_pass",
    }
    first, first_world = simulate_event_stream(
        cells=cells,
        items=items,
        fold=fold,
        schema=schema,
        world_design=world,
        protocol=protocol,
        seed=17,
        learners=3,
    )
    second, second_world = simulate_event_stream(
        cells=cells,
        items=items,
        fold=fold,
        schema=schema,
        world_design=world,
        protocol=protocol,
        seed=17,
        learners=3,
    )
    assert first == second
    assert first_world == second_world
    assert not any(
        row["protocol_phase"] == "acquisition"
        and row["grammar_split"] != "development"
        for row in first
    )

    left = tmp_path / "left.jsonl.gz"
    right = tmp_path / "right.jsonl.gz"
    left_hashes = _write_events(left, first)
    right_hashes = _write_events(right, second)
    assert left_hashes == right_hashes
    assert left.read_bytes() == right.read_bytes()
    loaded, content_hash = _read_events(left)
    assert loaded == first
    assert content_hash == left_hashes[1]
