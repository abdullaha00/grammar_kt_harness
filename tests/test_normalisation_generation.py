from __future__ import annotations

from copy import deepcopy

import pytest

from grammar_kt.canonicalise import canonicalise
from grammar_kt.generate import generate_items
from grammar_kt.io import load_typed_resource, read_yaml
from grammar_kt.normalise import normalise
from grammar_kt.validate_items import validate_items

from .helpers import PAST_NEGATIVE, PRESENT, base_config, validator_output


def test_normalisation_boundary_and_canonicalisation_contracts() -> None:
    config = base_config()
    resource = load_typed_resource(config["resource"]["data"], config["resource"]["schema"])[0]

    def fake_model(prompt, input_data, _config, stage, call_key, evidence_dir):
        assert stage == "normalisation.phase1"
        assert "examples" not in input_data["descriptor"]
        return {"source_id": call_key, "result": "complete", "cells": [PRESENT], "note": None}

    mapping = normalise([resource], config["normalisation"], model_call=fake_model)[0]
    assert set(mapping) == {"source_id", "result", "cells", "note"}
    assert not {"guideword", "can_do", "supercategory", "subcategory", "examples"} & set(mapping)
    assert canonicalise([mapping], config["canonical"]["schema"])[0]["features"] == PRESENT


def test_only_complete_exact_mappings_become_deduplicated_cells_with_provenance() -> None:
    config = base_config()
    mappings = [
        {"source_id": "source_a", "result": "complete", "cells": [PAST_NEGATIVE], "note": None},
        {"source_id": "source_b", "result": "complete", "cells": [PAST_NEGATIVE], "note": None},
        {
            "source_id": "source_partial",
            "result": "partial",
            "cells": [{**PAST_NEGATIVE, "tense": ["present", "past"]}],
            "note": "phase2 eligible: tense",
        },
        {"source_id": "source_oos", "result": "out_of_scope", "cells": [], "note": "non-verbal"},
        {"source_id": "source_unresolved", "result": "unresolved", "cells": [], "note": "conflict"},
    ]
    cells = canonicalise(mappings, config["canonical"]["schema"])
    assert cells == [{"cell_id": "cell_001", "features": PAST_NEGATIVE, "source_ids": ["source_a", "source_b"]}]


def test_phase2_receives_examples_only_for_declared_refinement() -> None:
    config = base_config()
    resource = {
        "source_id": "source_phase2",
        "supercategory": "VERBS",
        "subcategory": "finite forms",
        "guideword": "PRESENT OR PAST NEGATIVE",
        "can_do": "Can use a negative finite form in a stated time context.",
        "examples": ["Yesterday, she did not work."],
    }
    calls = []

    def fake_model(prompt, input_data, _config, stage, call_key, evidence_dir):
        calls.append((stage, input_data))
        if stage == "normalisation.phase1":
            return {
                "source_id": call_key,
                "result": "partial",
                "cells": [{**PAST_NEGATIVE, "tense": ["present", "past"]}],
                "note": "phase2 eligible: tense",
            }
        return {
            "source_id": call_key,
            "result": "complete",
            "cells": [PAST_NEGATIVE],
            "note": "phase2 eligible: tense",
        }

    mapping = normalise([resource], config["normalisation"], model_call=fake_model)[0]
    assert mapping["result"] == "complete"
    assert "examples" not in calls[0][1]["descriptor"]
    assert calls[1][1]["examples"] == resource["examples"]


def test_canonicalisation_rejects_uncertainty_mislabeled_complete() -> None:
    config = base_config()
    mapping = {
        "source_id": "bad",
        "result": "complete",
        "cells": [{**PRESENT, "tense": ["present", "past"]}],
        "note": None,
    }
    with pytest.raises(ValueError):
        canonicalise([mapping], config["canonical"]["schema"])


def test_generation_sees_cells_but_no_fold_kcs_or_simulation() -> None:
    config = base_config()
    cell = {"cell_id": "cell_001", "features": PRESENT, "source_ids": ["source_a"]}
    captured = {}

    def fake_model(prompt, input_data, call_config, stage, call_key, evidence_dir):
        captured.update(input_data)
        assert stage == "generation"
        flat = repr(input_data).lower()
        assert "kc" not in flat and "fold" not in flat and "simulation" not in flat and "learner" not in flat
        return {
            "prompt": "Every day, Lina ___ by bus. (travel)",
            "target_answer": "Every day, Lina travels by bus.",
            "accepted_answers": ["Every day, Lina travels by bus."],
            "operation_tags": [],
            "note": "fixture",
        }

    items = generate_items([cell], config["generation"], model_call=fake_model)
    assert items[0]["cell_id"] == "cell_001"
    assert {"item_id", "cell_id", "format", "prompt", "target_answer", "accepted_answers"} <= set(items[0])
    assert set(captured) == {"target_cell", "source_support", "item_format", "design", "lexical_material"}

    contaminated = deepcopy(config["generation"])
    contaminated["kc"] = "forbidden"
    with pytest.raises(ValueError, match="forbidden"):
        generate_items([cell], contaminated, model_call=fake_model)


def test_validation_accepts_all_required_passes_and_rejects_one_failure() -> None:
    config = base_config()
    criteria = read_yaml(config["validation"]["criteria"])["criteria"]
    cell = {"cell_id": "cell_001", "features": PRESENT, "source_ids": ["source_a"]}
    item = {
        "item_id": "item_001",
        "cell_id": "cell_001",
        "format": "controlled_production",
        "prompt": "Every day, Lina ___. (work)",
        "target_answer": "Every day, Lina works.",
        "accepted_answers": ["Every day, Lina works."],
        "operation_tags": [],
        "generation_metadata": {},
    }

    def passing(*_args):
        return validator_output(criteria)

    accepted, judgments = validate_items([item], [cell], config["validation"], model_call=passing)
    assert accepted == [item]
    assert judgments[0]["accepted"] is True

    def failing(*_args):
        return validator_output(criteria, failing="determinacy")

    accepted, judgments = validate_items([item], [cell], config["validation"], model_call=failing)
    assert accepted == []
    assert judgments[0]["accepted"] is False
