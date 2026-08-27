from __future__ import annotations

import copy
import inspect

import pytest

from grammar_kt import simulate as simulation_module
from grammar_kt.kc import project_kcs, select_kcs
from grammar_kt.simulate import simulate

from .helpers import (
    CANDIDATE_SPACE,
    FACTORIZED_POLICY,
    OBLIGATION_POLICY,
    SELECTOR,
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


def test_predefined_policy_and_projection_contract() -> None:
    _mappings, cells, _candidates, accepted, _judgments, _fold = base_bank()
    projection = project_kcs(accepted, cells, FACTORIZED_POLICY)
    by_item = {row["item_id"]: row["kc_ids"] for row in projection}
    assert by_item["item_002"] == ["kc_past", "kc_negation"]
    assert by_item["item_005"] == [
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


def test_selected_policy_uses_development_only_and_prefers_covering_interaction() -> None:
    _mappings, cells, _candidates, accepted, _judgments, fold = base_bank()
    first = select_kcs(
        cells,
        accepted,
        fold,
        CANDIDATE_SPACE,
        OBLIGATION_POLICY,
        SELECTOR,
    )
    holdout_ids = {
        row["cell_id"]
        for row in fold
        if row["grammar_split"] != "development"
    }
    changed = copy.deepcopy(cells)
    for cell in changed:
        if cell["cell_id"] in holdout_ids:
            cell["features"] = {
                name: "UNREAD_HOLDOUT" for name in cell["features"]
            }
            cell["source_ids"] = ["mutated_holdout"]
    second = select_kcs(
        changed,
        accepted,
        fold,
        CANDIDATE_SPACE,
        OBLIGATION_POLICY,
        SELECTOR,
    )
    assert first == second
    metadata = first["selection_metadata"]
    assert metadata["holdout_content_read"] is False
    assert set(metadata["development_cell_ids"]) == {
        "cell_001",
        "cell_002",
        "cell_003",
        "cell_004",
    }
    assert all(
        item_id in {"item_001", "item_002", "item_003", "item_004"}
        for item_id in metadata["development_item_ids"]
    )
    selected_ids = {row["id"] for row in first["kcs"]}
    assert "kc_past_negative" in selected_ids
    assert not {"kc_past", "kc_negation"} & selected_ids
