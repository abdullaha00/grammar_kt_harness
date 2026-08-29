from __future__ import annotations

import inspect

import pytest

from grammar_kt.canonicalise import canonicalise
from grammar_kt.generate import generate_items
from grammar_kt.io import load_typed_resource
from grammar_kt.normalise import (
    _validate_mapping,
    _validate_phase2_transition,
    normalise,
)
from grammar_kt.validate_items import (
    answer_span_consistency,
    bank_summary,
    select_item_bank,
    validate_items,
)

from .helpers import (
    GENERATION_DESIGN,
    GENERATION_PROMPT,
    GENERATION_RULEBOOK,
    GRAMMAR_SCHEMA,
    ITEM_FORMAT,
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
            "phase2_eligible": [],
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
    assert set(mapping) == {
        "source_id",
        "result",
        "cells",
        "phase2_eligible",
        "note",
    }
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
            "phase2_eligible": [],
            "note": None,
        },
        {
            "source_id": "source_b",
            "result": "complete",
            "cells": [PAST_NEGATIVE],
            "phase2_eligible": [],
            "note": None,
        },
        {
            "source_id": "source_partial",
            "result": "partial",
            "cells": [{**PAST_NEGATIVE, "tense": ["present", "past"]}],
            "phase2_eligible": ["tense"],
            "note": "Examples may distinguish the bounded tense alternatives.",
        },
        {
            "source_id": "source_oos",
            "result": "out_of_scope",
            "cells": [],
            "phase2_eligible": [],
            "note": "non-verbal",
        },
        {
            "source_id": "source_unresolved",
            "result": "unresolved",
            "cells": [],
            "phase2_eligible": [],
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
                "phase2_eligible": ["tense"],
                "note": "Examples may distinguish tense.",
            }
        return {
            "source_id": call["call_key"],
            "result": "complete",
            "cells": [PAST_NEGATIVE],
            "phase2_eligible": ["tense"],
            "note": "Example supports past.",
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
                "phase2_eligible": ["tense"],
                "note": "Examples may distinguish tense.",
            }
        return {
            "source_id": call["call_key"],
            "result": "complete",
            "cells": [{**PAST_NEGATIVE, "tense": "past", "voice": "passive"}],
            "phase2_eligible": ["tense"],
            "note": "Invalid voice replacement.",
        }

    with pytest.raises(ValueError, match="invalid branch"):
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


def test_phase2_eligibility_must_name_an_uncertain_dimension() -> None:
    mapping = {
        "source_id": "bad_eligibility",
        "result": "partial",
        "cells": [{**PRESENT, "polarity": None}],
        "phase2_eligible": ["tense"],
        "note": "Tense is exact, so it cannot be eligible.",
    }
    with pytest.raises(ValueError, match=r"not uncertain: \['tense'\]"):
        _validate_mapping(mapping, mapping["source_id"], GRAMMAR_SCHEMA)


def _transition_mapping(
    cells: list[dict],
    *,
    result: str,
    eligible: list[str] | None = None,
) -> dict:
    return {
        "source_id": "transition_control",
        "result": result,
        "cells": cells,
        "phase2_eligible": ["tense"] if eligible is None else eligible,
        "note": "adversarial transition control",
    }


def test_phase2_transition_rejects_changing_an_exact_field() -> None:
    first = _transition_mapping(
        [{**PRESENT, "tense": ["present", "past"]}], result="partial"
    )
    second = _transition_mapping(
        [{**PRESENT, "tense": "past", "voice": "passive"}], result="complete"
    )
    with pytest.raises(ValueError, match="invalid branch"):
        _validate_phase2_transition(first, second, GRAMMAR_SCHEMA)


def test_phase2_transition_rejects_broadening_an_eligible_field() -> None:
    first = _transition_mapping(
        [{**PRESENT, "tense": ["present", "past"]}], result="partial"
    )
    second = _transition_mapping(
        [{**PRESENT, "tense": None}], result="partial"
    )
    with pytest.raises(ValueError, match="invalid branch"):
        _validate_phase2_transition(first, second, GRAMMAR_SCHEMA)


def test_phase2_transition_rejects_cross_branch_recombination() -> None:
    first = _transition_mapping(
        [
            {**PRESENT, "tense": ["present", "past"]},
            {
                **PRESENT,
                "tense": ["present", "past"],
                "voice": "passive",
                "polarity": "negative",
            },
        ],
        result="partial",
    )
    second = _transition_mapping(
        [
            {**PRESENT, "tense": "present", "polarity": "negative"},
            {**PRESENT, "tense": "past", "voice": "passive"},
        ],
        result="complete",
    )
    with pytest.raises(ValueError, match="recombined"):
        _validate_phase2_transition(first, second, GRAMMAR_SCHEMA)


def test_phase2_transition_rejects_a_dropped_or_branch() -> None:
    first = _transition_mapping(
        [
            {**PRESENT, "tense": ["present", "past"]},
            {
                **PRESENT,
                "tense": ["present", "past"],
                "voice": "passive",
                "polarity": "negative",
            },
        ],
        result="partial",
    )
    second = _transition_mapping([PRESENT], result="complete")
    with pytest.raises(ValueError, match="dropped Phase-1 branches"):
        _validate_phase2_transition(first, second, GRAMMAR_SCHEMA)


def test_canonicalisation_rejects_uncertainty_mislabeled_complete() -> None:
    mapping = {
        "source_id": "bad",
        "result": "complete",
        "cells": [{**PRESENT, "tense": ["present", "past"]}],
        "phase2_eligible": [],
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
    captured = []

    def fake_model(prompt, **call):
        captured.append({"prompt": prompt, "input": call["input_data"]})
        assert call["stage"] == "generation"
        flat = repr(call["input_data"]).lower()
        assert "kc" not in flat
        assert "fold" not in flat
        assert "simulation" not in flat
        assert "learner" not in flat
        assert "lexical_material" not in call["input_data"]
        return {
            "prompt": "Every day, Lina ___ by bus. (travel)",
            "target_answer": "Every day, Lina travels by bus.",
            "accepted_answers": ["travels"],
        }

    items = generate_items(
        [cell],
        GENERATION_PROMPT,
        GENERATION_RULEBOOK,
        GENERATION_DESIGN,
        ITEM_FORMAT,
        model="fixture",
        reasoning_effort="deterministic",
        model_call=fake_model,
    )
    assert len(items) == 3
    assert [row["item_id"] for row in items] == [
        "candidate_cell_001_01",
        "candidate_cell_001_02",
        "candidate_cell_001_03",
    ]
    assert items[0]["cell_id"] == "cell_001"
    assert {
        "item_id",
        "cell_id",
        "format",
        "prompt",
        "target_answer",
        "accepted_answers",
    } <= set(items[0])
    assert set(captured[0]["input"]) == {
        "target_cell",
        "candidate_position",
        "item_format",
        "design",
    }
    assert captured[0]["input"]["candidate_position"] == {"index": 1, "count": 3}
    assert "source_a" not in captured[0]["prompt"]
    assert "source_support" not in captured[0]["prompt"]
    assert set(items[0]["generation_metadata"]) == {
        "candidate_index",
        "candidate_count",
        "model",
    }
    assert "operation_tags" not in items[0]
    assert "note" not in repr(items[0]).casefold()


def test_generation_api_has_no_lexicon_and_passive_choice_is_model_responsibility() -> None:
    assert list(inspect.signature(generate_items).parameters) == [
        "cells",
        "prompt",
        "rulebook",
        "design",
        "item_format",
        "model",
        "reasoning_effort",
        "model_call",
        "evidence_dir",
        "show_progress",
    ]
    passive = {**PRESENT, "voice": "passive", "tense": "past"}
    cell = {
        "cell_id": "cell_passive",
        "features": passive,
        "source_ids": ["source_passive"],
    }

    def fake_model(prompt, **call):
        assert call["input_data"]["target_cell"]["features"] == passive
        assert set(call["input_data"]) == {
            "target_cell",
            "candidate_position",
            "item_format",
            "design",
        }
        return {
            "prompt": "Yesterday, the window ___ by the caretaker. (close)",
            "target_answer": "Yesterday, the window was closed by the caretaker.",
            "accepted_answers": ["was closed"],
        }

    item = generate_items(
        [cell],
        GENERATION_PROMPT,
        GENERATION_RULEBOOK,
        GENERATION_DESIGN,
        ITEM_FORMAT,
        model="fixture",
        reasoning_effort="deterministic",
        model_call=fake_model,
    )[0]
    assert item["target_answer"] == (
        "Yesterday, the window was closed by the caretaker."
    )


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
        "accepted_answers": ["works"],
        "generation_metadata": {"candidate_index": 1},
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

    assert "non_target_language_simplicity" in criteria

    def failing(prompt, **call):
        return validator_output(criteria, failing="non_target_language_simplicity")

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


def test_validation_acceptance_rule_is_an_enforced_scientific_choice() -> None:
    cell = {
        "cell_id": "cell_bad_policy",
        "features": PRESENT,
        "source_ids": [],
    }
    item = {
        "item_id": "candidate_bad_policy_01",
        "cell_id": "cell_bad_policy",
        "format": "controlled_production",
        "prompt": "They ___ today. (work)",
        "target_answer": "They work today.",
        "accepted_answers": ["work"],
    }

    def should_not_call(*args, **kwargs):
        raise AssertionError("invalid validation policy must fail before judging")

    with pytest.raises(ValueError, match="all_required_criteria_pass"):
        validate_items(
            [item],
            [cell],
            VALIDATION_PROMPT,
            {**VALIDATION_CRITERIA, "acceptance_rule": "majority_vote"},
            model="fixture",
            reasoning_effort="deterministic",
            model_call=should_not_call,
        )


def test_answer_span_precheck_rejects_repeated_visible_subject_without_model_call() -> None:
    cell = {
        "cell_id": "cell_001",
        "features": PRESENT,
        "source_ids": ["source_a"],
    }
    item = {
        "item_id": "candidate_cell_001_01",
        "cell_id": "cell_001",
        "format": "controlled_production",
        "prompt": "Complete the response: Lena ___. (not / walk)",
        "target_answer": "Lena did not walk.",
        "accepted_answers": ["Lena did not walk."],
        "generation_metadata": {"candidate_index": 1},
    }
    assert answer_span_consistency(item)[0] is False

    def must_not_run(*args, **kwargs):
        raise AssertionError("deterministic rejection must precede model validation")

    accepted, judgments = validate_items(
        [item],
        [cell],
        VALIDATION_PROMPT,
        VALIDATION_CRITERIA,
        model="fixture",
        reasoning_effort="deterministic",
        model_call=must_not_run,
    )
    assert accepted == []
    assert judgments[0]["rejection_stage"] == "deterministic_precheck"
    assert judgments[0]["judgments"] == {}


def test_answer_span_precheck_rejects_repeated_suffix_punctuation() -> None:
    item = {
        "item_id": "candidate_cell_001_01",
        "cell_id": "cell_001",
        "format": "controlled_production",
        "prompt": "Tell your friend what to do: _____.",
        "target_answer": "Turn on the light.",
        "accepted_answers": ["Turn on the light."],
        "generation_metadata": {"candidate_index": 1},
    }
    passed, note = answer_span_consistency(item)
    assert passed is False
    assert "punctuation already printed" in note

    corrected = {**item, "accepted_answers": ["Turn on the light"]}
    assert answer_span_consistency(corrected)[0] is True


def test_bank_selection_is_order_invariant_and_uses_maximum_token_distance() -> None:
    def candidate(index: int, prompt: str) -> dict:
        return {
            "item_id": f"candidate_cell_x_{index:02d}",
            "cell_id": "cell_x",
            "format": "controlled_production",
            "prompt": prompt,
            "target_answer": prompt.replace("___", "works"),
            "accepted_answers": ["works"],
            "generation_metadata": {
                "candidate_index": index,
                "candidate_count": 3,
                "model": "fixture",
            },
        }

    rows = [
        candidate(1, "The child ___ at home."),
        candidate(2, "The child ___ at home today."),
        candidate(3, "Each morning, our neighbour ___ beside the river."),
    ]
    selected = select_item_bank(rows, GENERATION_DESIGN)
    reversed_selected = select_item_bank(list(reversed(rows)), GENERATION_DESIGN)
    assert [row["item_id"] for row in selected] == [
        "candidate_cell_x_01",
        "candidate_cell_x_03",
    ]
    assert selected == reversed_selected
    assert [row["selection_metadata"]["rank"] for row in selected] == [1, 2]


def test_bank_diagnostics_use_judgments_not_lexicon_metadata() -> None:
    criteria = VALIDATION_CRITERIA["criteria"]
    candidates = [
        {
            "item_id": "item_001",
            "cell_id": "cell_001",
            "format": "controlled_production",
            "prompt": "Every day, the child ___ home. (walk)",
            "target_answer": "Every day, the child walks home.",
            "accepted_answers": ["walks"],
            "generation_metadata": {
                "candidate_index": 1,
                "model": "fixture",
            },
        }
    ]
    judgments = [
        {
            "item_id": "item_001",
            "judgments": validator_output(criteria)["judgments"],
            "accepted": True,
        }
    ]
    summary = bank_summary(candidates, candidates, judgments, [])
    assert "cefr_distribution" not in summary
    assert (
        summary["criterion_pass_rates"]["non_target_language_simplicity"] == 1.0
    )
    assert summary["lexical_types"] > 0
    assert summary["lexical_tokens"] > 0
    assert summary["validator_accepted_candidates"] == 1
    assert summary["selected_bank_items"] == 1
