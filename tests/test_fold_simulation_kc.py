from __future__ import annotations

import copy
import inspect

import pytest

from grammar_kt import simulate as simulation_module
from grammar_kt.kc import project_kcs
from grammar_kt.simulate import _response_probability, simulate

from .helpers import (
    FACTORIZED_POLICY,
    SIMULATION_WORLD,
    base_bank,
)


def test_reference_fold_is_disjoint_and_has_expected_roles() -> None:
    _mappings, _cells, _candidates, _accepted, _judgments, fold = base_bank()
    by_split = {
        split: {row["cell_id"] for row in fold if row["grammar_split"] == split}
        for split in (
            "development",
            "compositional_holdout",
            "novel_feature_holdout",
        )
    }
    assert by_split["development"] == {
        "cell_001",
        "cell_002",
        "cell_003",
        "cell_004",
    }
    assert by_split["compositional_holdout"] == {"cell_005"}
    assert by_split["novel_feature_holdout"] == {"cell_006"}
    assert not (by_split["development"] & by_split["compositional_holdout"])
    assert not (by_split["development"] & by_split["novel_feature_holdout"])


def test_simulation_uses_fixed_accepted_bank_and_is_seed_deterministic() -> None:
    _mappings, _cells, _candidates, accepted, _judgments, fold = base_bank()
    first = simulate(accepted, fold, SIMULATION_WORLD)
    second = simulate(accepted, fold, SIMULATION_WORLD)
    assert first == second
    assert len({row["learner_id"] for row in first}) == 24
    assert len(first) == 24 * 4 * len(accepted)
    assert {row["item_id"] for row in first} == {
        row["item_id"] for row in accepted
    }
    assert list(inspect.signature(simulate).parameters) == [
        "accepted_items",
        "fold",
        "world",
        "oracle_path",
    ]
    source = inspect.getsource(simulation_module)
    assert "grammar_kt.kc" not in source
    assert "q_matrix" not in source


def test_counterbalanced_item_order_changes_start_across_learners() -> None:
    _mappings, _cells, _candidates, accepted, _judgments, fold = base_bank()
    world = copy.deepcopy(SIMULATION_WORLD)
    world["learners"] = 2
    world["passes"] = 1
    world["item_order"] = "counterbalanced_rotate_by_learner_and_pass"
    events = simulate(accepted, fold, world)
    first_items = [
        next(row for row in events if row["learner_id"] == learner)["item_id"]
        for learner in ("learner_001", "learner_002")
    ]
    assert first_items == [accepted[0]["item_id"], accepted[1]["item_id"]]


def test_simulated_probability_increases_with_mastery_and_decreases_with_difficulty() -> None:
    response = {"discrimination": 2.2, "guess_floor": 0.08, "slip_ceiling": 0.08}
    baseline = _response_probability(0.5, 0.0, response)
    assert _response_probability(0.8, 0.0, response) > baseline
    assert _response_probability(0.2, 0.0, response) < baseline
    assert _response_probability(0.5, 0.4, response) < baseline


def test_predefined_policy_and_projection_contract() -> None:
    _mappings, cells, _candidates, accepted, _judgments, _fold = base_bank()
    projection = project_kcs(accepted, cells, FACTORIZED_POLICY)
    by_item = {row["item_id"]: row["kc_ids"] for row in projection}
    assert by_item["candidate_cell_002_01"] == ["kc_past", "kc_negation"]
    assert by_item["candidate_cell_005_01"] == [
        "kc_present",
        "kc_progressive",
        "kc_passive",
        "kc_negation",
    ]
    assert len(projection) == len(accepted)
    before = copy.deepcopy(accepted)
    project_kcs(accepted, cells, FACTORIZED_POLICY)
    assert accepted == before

    unknown = [{**accepted[0], "cell_id": "cell_unknown"}]
    with pytest.raises(ValueError, match="unknown GrammarCell"):
        project_kcs(unknown, cells, FACTORIZED_POLICY)
