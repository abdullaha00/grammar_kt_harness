from __future__ import annotations

import pytest

from grammar_kt.canonicalise import canonicalise
from grammar_kt.generate import generate_items
from grammar_kt.io import load_typed_resource
from grammar_kt.normalise import normalise
from grammar_kt.validate_items import validate_items

from .helpers import (
    GENERATION_DESIGN,
    GENERATION_PROMPT,
    GENERATION_RULEBOOK,
    GRAMMAR_SCHEMA,
    ITEM_FORMAT,
    LEXICON,
    NORMALISATION_RULEBOOK,
    PAST_NEGATIVE,
    PHASE1_PROMPT,
    PHASE2_PROMPT,
    PRESENT,
    RESOURCE_PATH,
    RESOURCE_SCHEMA,
    VALIDATION_CRITERIA,
    VALIDATION_PROMPT,
    validator_output,
)


def test_normalisation_boundary_and_canonicalisation_contracts() -> None:
    resource = load_typed_resource(RESOURCE_PATH, RESOURCE_SCHEMA)[0]

    def fake_model(prompt, **call):
        assert call["stage"] == "normalisation.phase1"
        assert "examples" not in call["input_data"]["descriptor"]
        return {
            "source_id": call["call_key"],
            "result": "complete",
            "cells": [PRESENT],
            "note": None,
        }

    mapping = normalise(
        [resource],
        PHASE1_PROMPT,
        PHASE2_PROMPT,
        NORMALISATION_RULEBOOK,
        GRAMMAR_SCHEMA,
        model="fixture",
        reasoning_effort="deterministic",
        model_call=fake_model,
    )[0]
    assert set(mapping) == {"source_id", "result", "cells", "note"}
    assert not {
        "guideword",
        "can_do",
        "supercategory",
        "subcategory",
        "examples",
    } & set(mapping)
    assert canonicalise([mapping], GRAMMAR_SCHEMA)[0]["features"] == PRESENT


def test_only_complete_exact_mappings_become_deduplicated_cells_with_provenance() -> None:
    mappings = [
        {
            "source_id": "source_a",
            "result": "complete",
            "cells": [PAST_NEGATIVE],
            "note": None,
        },
        {
            "source_id": "source_b",
            "result": "complete",
            "cells": [PAST_NEGATIVE],
            "note": None,
        },
        {
            "source_id": "source_partial",
            "result": "partial",
            "cells": [{**PAST_NEGATIVE, "tense": ["present", "past"]}],
            "note": "phase2 eligible: tense",
        },
        {
            "source_id": "source_oos",
            "result": "out_of_scope",
            "cells": [],
            "note": "non-verbal",
        },
        {
            "source_id": "source_unresolved",
            "result": "unresolved",
            "cells": [],
            "note": "conflict",
        },
    ]
    cells = canonicalise(mappings, GRAMMAR_SCHEMA)
    assert cells == [
        {
            "cell_id": "cell_001",
            "features": PAST_NEGATIVE,
            "source_ids": ["source_a", "source_b"],
        }
    ]


def test_phase2_receives_examples_only_for_declared_refinement() -> None:
    resource = {
        "source_id": "source_phase2",
        "supercategory": "VERBS",
        "subcategory": "finite forms",
        "guideword": "PRESENT OR PAST NEGATIVE",
        "can_do": "Can use a negative finite form in a stated time context.",
        "examples": ["Yesterday, she did not work."],
    }
    calls = []

    def fake_model(prompt, **call):
        calls.append((call["stage"], call["input_data"]))
        if call["stage"] == "normalisation.phase1":
            return {
                "source_id": call["call_key"],
                "result": "partial",
                "cells": [{**PAST_NEGATIVE, "tense": ["present", "past"]}],
                "note": "phase2 eligible: tense",
            }
        return {
            "source_id": call["call_key"],
            "result": "complete",
            "cells": [PAST_NEGATIVE],
            "note": "phase2 eligible: tense",
        }

    mapping = normalise(
        [resource],
        PHASE1_PROMPT,
        PHASE2_PROMPT,
        NORMALISATION_RULEBOOK,
        GRAMMAR_SCHEMA,
        model="fixture",
        reasoning_effort="deterministic",
        model_call=fake_model,
    )[0]
    assert mapping["result"] == "complete"
    assert "examples" not in calls[0][1]["descriptor"]
    assert calls[1][1]["examples"] == resource["examples"]


def test_phase2_cannot_change_an_ineligible_dimension() -> None:
    resource = {
        "source_id": "source_phase2",
        "supercategory": "VERBS",
        "subcategory": "finite forms",
        "guideword": "PRESENT OR PAST NEGATIVE",
        "can_do": "Can use a negative finite form in a stated time context.",
        "examples": ["Yesterday, she did not work."],
    }

    def fake_model(prompt, **call):
        if call["stage"] == "normalisation.phase1":
            return {
                "source_id": call["call_key"],
                "result": "partial",
                "cells": [{**PAST_NEGATIVE, "tense": ["present", "past"]}],
                "note": "phase2 eligible: tense",
            }
        return {
            "source_id": call["call_key"],
            "result": "complete",
            "cells": [{**PAST_NEGATIVE, "tense": "past", "voice": "passive"}],
            "note": "phase2 eligible: tense",
        }

    with pytest.raises(ValueError, match="ineligible dimension: voice"):
        normalise(
            [resource],
            PHASE1_PROMPT,
            PHASE2_PROMPT,
            NORMALISATION_RULEBOOK,
            GRAMMAR_SCHEMA,
            model="fixture",
            reasoning_effort="deterministic",
            model_call=fake_model,
        )


def test_canonicalisation_rejects_uncertainty_mislabeled_complete() -> None:
    mapping = {
        "source_id": "bad",
        "result": "complete",
        "cells": [{**PRESENT, "tense": ["present", "past"]}],
        "note": None,
    }
    with pytest.raises(ValueError):
        canonicalise([mapping], GRAMMAR_SCHEMA)


def test_generation_receives_only_the_declared_scientific_inputs() -> None:
    cell = {
        "cell_id": "cell_001",
        "features": PRESENT,
        "source_ids": ["source_a"],
    }
    captured = {}

    def fake_model(prompt, **call):
        captured.update(call["input_data"])
        assert call["stage"] == "generation"
        flat = repr(call["input_data"]).lower()
        assert "kc" not in flat
        assert "fold" not in flat
        assert "simulation" not in flat
        assert "learner" not in flat
        return {
            "prompt": "Every day, Lina ___ by bus. (travel)",
            "target_answer": "Every day, Lina travels by bus.",
            "accepted_answers": ["Every day, Lina travels by bus."],
            "operation_tags": [],
            "note": "fixture",
        }

    items = generate_items(
        [cell],
        GENERATION_PROMPT,
        GENERATION_RULEBOOK,
        GENERATION_DESIGN,
        ITEM_FORMAT,
        LEXICON,
        model="fixture",
        reasoning_effort="deterministic",
        model_call=fake_model,
    )
    assert items[0]["cell_id"] == "cell_001"
    assert {
        "item_id",
        "cell_id",
        "format",
        "prompt",
        "target_answer",
        "accepted_answers",
    } <= set(items[0])
    assert set(captured) == {
        "target_cell",
        "source_support",
        "item_format",
        "design",
        "lexical_material",
    }


def test_validation_accepts_all_required_passes_and_rejects_one_failure() -> None:
    criteria = VALIDATION_CRITERIA["criteria"]
    cell = {
        "cell_id": "cell_001",
        "features": PRESENT,
        "source_ids": ["source_a"],
    }
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

    def passing(prompt, **call):
        assert call["input_data"]["target_cell"] == PRESENT
        assert "generation_metadata" not in call["input_data"]["visible_item"]
        return validator_output(criteria)

    accepted, judgments = validate_items(
        [item],
        [cell],
        VALIDATION_PROMPT,
        VALIDATION_CRITERIA,
        model="fixture",
        reasoning_effort="deterministic",
        model_call=passing,
    )
    assert accepted == [item]
    assert judgments[0]["accepted"] is True

    def failing(prompt, **call):
        return validator_output(criteria, failing="determinacy")

    accepted, judgments = validate_items(
        [item],
        [cell],
        VALIDATION_PROMPT,
        VALIDATION_CRITERIA,
        model="fixture",
        reasoning_effort="deterministic",
        model_call=failing,
    )
    assert accepted == []
    assert judgments[0]["accepted"] is False
