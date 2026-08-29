from __future__ import annotations

import copy
import json
import random
import subprocess
from pathlib import Path

import pytest
import yaml

from src.grammar_kt.grammar_regimes import (
    GrammarRegimeDesignError,
    design_grammar_regimes,
    recommended_regime_design,
)

ROOT = Path(__file__).resolve().parents[1]


def test_researcher_facing_full_v1_design_matches_code_default() -> None:
    declared = yaml.safe_load(
        (ROOT / "modules/simulation/grammar_regimes_full_v1.yaml").read_text(
            encoding="utf-8"
        )
    )
    assert declared == recommended_regime_design()


def _schema() -> dict:
    return {
        "schema_id": "opaque_toy_v1",
        "dimension_order": ["mood", "person", "polarity"],
        "dimensions": {
            "mood": {
                "allowed_values": ["indicative", "subjunctive", "irrealis"]
            },
            "person": {"allowed_values": ["first", "third"]},
            "polarity": {"allowed_values": ["affirmative", "negative"]},
        },
    }


def _cells() -> list[dict]:
    rows = []
    counter = 0
    for mood in ["indicative", "subjunctive"]:
        for person in ["first", "third"]:
            for polarity in ["affirmative", "negative"]:
                counter += 1
                rows.append(
                    {
                        "cell_id": f"opaque_{counter}",
                        "features": {
                            "mood": mood,
                            "person": person,
                            "polarity": polarity,
                        },
                    }
                )
    rows.append(
        {
            "cell_id": "opaque_novel",
            "features": {
                "mood": "irrealis",
                "person": "first",
                "polarity": "affirmative",
            },
        }
    )
    return rows


def _kcs(include_novel: bool = False) -> list[dict]:
    rows = [
        {
            "id": "opaque_kc_subjunctive",
            "activation_rule": {"cell": {"mood": "subjunctive"}},
        },
        {
            "id": "opaque_kc_third",
            "activation_rule": {"cell": {"person": "third"}},
        },
    ]
    if include_novel:
        rows.append(
            {
                "id": "opaque_kc_irrealis",
                "activation_rule": {"cell": {"mood": "irrealis"}},
            }
        )
    return rows


def _design() -> dict:
    design = recommended_regime_design()
    design["unseen_value"].update(
        {
            "target_cells": 1,
            "minimum_cells": 1,
            "maximum_cells": 1,
            "maximum_unseen_value_only_kcs": 0,
        }
    )
    design["unseen_combination"].update(
        {"target_cells": 2, "minimum_cells": 2, "beam_width": 32}
    )
    return design


def _semantic_assignments(result: dict) -> dict:
    return {
        tuple(row["features"].items()): (
            row["grammar_regime"],
            row["combination_subtype"],
        )
        for row in result["assignments"]
    }


def test_semantic_regimes_are_genuine_and_pairwise_seen() -> None:
    result = design_grammar_regimes(
        _schema(), _cells(), generator_kcs=_kcs(), design=_design()
    )

    assert result["audit"]["counts"] == {
        "cells": 9,
        "seen_cells": 6,
        "unseen_combination_cells": 2,
        "unseen_value_cells": 1,
        "pairwise_seen_unseen_combination_cells": 2,
    }
    novel = [
        row for row in result["assignments"] if row["grammar_regime"] == "unseen_value"
    ]
    assert len(novel) == 1
    assert novel[0]["unseen_values_relative_to_seen"] == [
        {"dimension": "mood", "value": "irrealis"}
    ]
    combinations = [
        row
        for row in result["assignments"]
        if row["grammar_regime"] == "unseen_combination"
    ]
    assert all(row["constituent_seen"] for row in combinations)
    assert all(row["pairwise_seen"] for row in combinations)
    assert all(not row["full_tuple_seen"] for row in combinations)
    assert {row["combination_subtype"] for row in combinations} == {
        "pairwise_seen_full_tuple_unseen"
    }
    assert result["audit"]["generator_kcs_absent_from_seen"] == []


def test_selection_is_row_order_and_cell_id_invariant() -> None:
    cells = _cells()
    baseline = design_grammar_regimes(
        _schema(), cells, generator_kcs=_kcs(), design=_design()
    )
    shuffled = copy.deepcopy(cells)
    random.Random(184).shuffle(shuffled)
    for index, row in enumerate(shuffled):
        row["cell_id"] = f"renamed_{index}"
    replay = design_grammar_regimes(
        _schema(), shuffled, generator_kcs=_kcs(), design=_design()
    )

    assert _semantic_assignments(baseline) == _semantic_assignments(replay)
    assert (
        baseline["audit"]["semantic_assignment_sha256"]
        == replay["audit"]["semantic_assignment_sha256"]
    )
    assert baseline["audit"]["metadata"]["cell_ids_used_for_selection"] is False


def test_item_text_and_answers_cannot_affect_holdouts() -> None:
    cells = _cells()
    first_items = [
        {
            "item_id": f"item_{index}",
            "cell_id": cell["cell_id"],
            "prompt": f"prompt {index}",
            "target_answer": "alpha",
        }
        for index, cell in enumerate(cells)
    ]
    second_items = copy.deepcopy(first_items)
    for row in second_items:
        row["prompt"] = "completely changed"
        row["target_answer"] = "omega"
    first = design_grammar_regimes(
        _schema(), cells, generator_kcs=_kcs(), items=first_items, design=_design()
    )
    second = design_grammar_regimes(
        _schema(), cells, generator_kcs=_kcs(), items=second_items, design=_design()
    )

    assert _semantic_assignments(first) == _semantic_assignments(second)
    assert first["audit"]["metadata"]["item_text_read"] is False
    assert first["audit"]["metadata"]["item_answers_read"] is False
    assert "item_support_not_audited" not in first["audit"]["limitations"]


@pytest.mark.parametrize("field", ["correct", "outcome", "learner_id", "mastery_before"])
def test_learner_observation_fields_are_rejected(field: str) -> None:
    cells = _cells()
    items = [
        {"item_id": f"item_{index}", "cell_id": cell["cell_id"]}
        for index, cell in enumerate(cells)
    ]
    items[0][field] = 1
    with pytest.raises(GrammarRegimeDesignError, match="learner-observation"):
        design_grammar_regimes(_schema(), cells, items=items, design=_design())


def test_unseen_value_only_kcs_are_explicit_and_bounded() -> None:
    design = _design()
    with pytest.raises(GrammarRegimeDesignError, match="no unseen-value cohort"):
        design_grammar_regimes(
            _schema(), _cells(), generator_kcs=_kcs(include_novel=True), design=design
        )

    design["unseen_value"]["maximum_unseen_value_only_kcs"] = 1
    result = design_grammar_regimes(
        _schema(), _cells(), generator_kcs=_kcs(include_novel=True), design=design
    )
    assert result["audit"]["generator_kcs_unique_to_unseen_value"] == [
        "opaque_kc_irrealis"
    ]
    assert result["audit"]["generator_kcs_absent_from_seen"] == [
        "opaque_kc_irrealis"
    ]
    assert "generator_kcs_unique_to_unseen_value" in result["audit"]["limitations"]


def test_impossible_unseen_value_and_pairwise_designs_fail_closed() -> None:
    impossible_value = _design()
    impossible_value["unseen_value"].update(
        {"target_cells": 2, "minimum_cells": 2, "maximum_cells": 2}
    )
    with pytest.raises(GrammarRegimeDesignError, match="no unseen-value cohort"):
        design_grammar_regimes(_schema(), _cells(), design=impossible_value)

    impossible_pairs = _design()
    impossible_pairs["unseen_combination"]["minimum_seen_cells_per_pair"] = 2
    with pytest.raises(GrammarRegimeDesignError, match="no unseen-combination cohort"):
        design_grammar_regimes(_schema(), _cells(), design=impossible_pairs)


def test_duplicate_feature_tuple_and_unknown_item_cell_fail_closed() -> None:
    duplicate = _cells()
    duplicate.append(
        {"cell_id": "different_id", "features": dict(duplicate[0]["features"])}
    )
    with pytest.raises(GrammarRegimeDesignError, match="unique feature tuples"):
        design_grammar_regimes(_schema(), duplicate, design=_design())

    with pytest.raises(GrammarRegimeDesignError, match="unknown GrammarCell"):
        design_grammar_regimes(
            _schema(),
            _cells(),
            items=[{"item_id": "bad", "cell_id": "not_a_cell"}],
            design=_design(),
        )


def test_two_dimension_schema_supports_constituent_seen_mode() -> None:
    schema = {
        "dimension_order": ["mood", "person"],
        "dimensions": {
            "mood": {"allowed_values": ["plain", "marked", "novel"]},
            "person": {"allowed_values": ["one", "two"]},
        },
    }
    cells = [
        {
            "cell_id": f"c_{mood}_{person}",
            "features": {"mood": mood, "person": person},
        }
        for mood in ["plain", "marked"]
        for person in ["one", "two"]
    ] + [{"cell_id": "c_novel", "features": {"mood": "novel", "person": "one"}}]
    design = _design()
    design["unseen_combination"].update(
        {
            "target_cells": 1,
            "minimum_cells": 1,
            "require_pairwise_seen": False,
        }
    )
    result = design_grammar_regimes(schema, cells, design=design)
    combination = next(
        row
        for row in result["assignments"]
        if row["grammar_regime"] == "unseen_combination"
    )
    assert combination["constituent_seen"] is True
    assert combination["pairwise_seen"] is False
    assert combination["combination_subtype"] == "constituent_seen_full_tuple_unseen"


def test_cli_writes_assignments_and_audit(tmp_path: Path) -> None:
    schema_path = tmp_path / "schema.yaml"
    cells_path = tmp_path / "cells.jsonl"
    design_path = tmp_path / "design.yaml"
    assignments_path = tmp_path / "assignments.jsonl"
    audit_path = tmp_path / "audit.json"
    schema_path.write_text(yaml.safe_dump(_schema()), encoding="utf-8")
    cells_path.write_text(
        "".join(json.dumps(row) + "\n" for row in _cells()), encoding="utf-8"
    )
    design_path.write_text(yaml.safe_dump(_design()), encoding="utf-8")

    completed = subprocess.run(
        [
            ".venv/bin/python",
            "scripts/design_grammar_regimes.py",
            "--schema",
            str(schema_path),
            "--cells",
            str(cells_path),
            "--design",
            str(design_path),
            "--assignments-output",
            str(assignments_path),
            "--audit-output",
            str(audit_path),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    assert len(assignments_path.read_text(encoding="utf-8").splitlines()) == 9
    assert json.loads(audit_path.read_text(encoding="utf-8"))["status"] == "PASS"
    assert json.loads(completed.stdout)["metadata"]["learner_outcomes_read"] is False
