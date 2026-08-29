from __future__ import annotations

from copy import deepcopy

import pytest

from grammar_kt.full_items import (
    build_generation_call,
    build_validation_call,
    candidate_audit_summary,
    deterministic_candidate_checks,
    generate_one_candidate,
    item_construction_audit,
    merge_completed_candidate_rows,
    merge_completed_judgment_rows,
    pending_generation_calls,
    recover_generated_candidate,
    reconstruct_validation_judgment,
    stable_candidate_id,
    validate_one_candidate,
)
from grammar_kt.io import read_text, read_yaml

from .helpers import ROOT


GENERATION_PROMPT = read_text(ROOT / "modules/items/generation/prompt.txt")
GENERATION_RULEBOOK = read_text(ROOT / "modules/items/generation/rulebook.md")
GENERATION_DESIGN = read_yaml(ROOT / "modules/items/generation/design.yaml")
ITEM_FORMAT = read_yaml(
    ROOT / "modules/items/generation/formats/controlled_production.yaml"
)
VALIDATION_PROMPT = read_text(ROOT / "modules/items/validation/prompt.txt")
VALIDATION_CRITERIA = read_yaml(ROOT / "modules/items/validation/criteria.yaml")


def _cell(cell_id: str = "toy_cell") -> dict:
    return {
        "cell_id": cell_id,
        "features": {"mood": "irrealis", "person": "first"},
        "source_ids": ["consult-only-source"],
        "learner_outcomes": [1, 0, 1],
        "generator_kc_ids": ["must_not_leak"],
    }


def _payload(prompt: str = "In this situation, I ___. (work)") -> dict:
    return {
        "prompt": prompt,
        "target_answer": "In this situation, I work.",
        "accepted_answers": ["work"],
    }


def _generation_call(cell_id: str = "toy_cell", index: int = 1) -> dict:
    return build_generation_call(
        _cell(cell_id),
        GENERATION_PROMPT,
        GENERATION_RULEBOOK,
        GENERATION_DESIGN,
        ITEM_FORMAT,
        candidate_index=index,
        model="fixture-generator",
        reasoning_effort="medium",
    )


def _candidate(cell_id: str = "toy_cell", index: int = 1) -> dict:
    return recover_generated_candidate(_payload(), _generation_call(cell_id, index))


def _passing_judgments() -> dict:
    return {
        "judgments": {
            name: {"passed": True, "note": "Independent fixture judgment."}
            for name in VALIDATION_CRITERIA["criteria"]
        }
    }


def test_generation_call_is_stable_n3_and_reads_only_canonical_cell() -> None:
    call = _generation_call(index=2)

    assert call["candidate_id"] == "candidate_toy_cell_02"
    assert call["model_input"]["candidate_position"] == {"index": 2, "count": 3}
    assert set(call["model_input"]) == {
        "target_cell",
        "candidate_position",
        "item_format",
        "design",
    }
    flattened = str(call["model_input"])
    assert "consult-only-source" not in flattened
    assert "learner_outcomes" not in flattened
    assert "generator_kc_ids" not in flattened
    assert call == _generation_call(index=2)
    assert call["input_sha256"] != _generation_call(index=3)["input_sha256"]

    changed_prompt = GENERATION_PROMPT.replace(
        "Create one", "Create exactly one", 1
    )
    changed = build_generation_call(
        _cell(),
        changed_prompt,
        GENERATION_RULEBOOK,
        GENERATION_DESIGN,
        ITEM_FORMAT,
        candidate_index=2,
        model="fixture-generator",
        reasoning_effort="medium",
    )
    assert changed["input_sha256"] != call["input_sha256"]

    invalid_design = deepcopy(GENERATION_DESIGN)
    invalid_design["generation"]["candidates_per_cell"] = 2
    with pytest.raises(ValueError, match="frozen to N=3"):
        build_generation_call(
            _cell(),
            GENERATION_PROMPT,
            GENERATION_RULEBOOK,
            invalid_design,
            ITEM_FORMAT,
            candidate_index=1,
            model="fixture-generator",
            reasoning_effort="medium",
        )


def test_generation_recovery_requires_exact_three_field_payload() -> None:
    call = _generation_call(index=3)
    candidate = recover_generated_candidate(_payload(), call)

    assert candidate["item_id"] == stable_candidate_id("toy_cell", 3)
    assert candidate["cell_id"] == "toy_cell"
    assert candidate["generation_metadata"] | {
        "candidate_index": 3,
        "candidate_count": 3,
        "model": "fixture-generator",
        "reasoning_effort": "medium",
    } == candidate["generation_metadata"]

    extra = {**_payload(), "note": "undeclared field"}
    with pytest.raises(ValueError, match="exactly"):
        recover_generated_candidate(extra, call)
    duplicate = {**_payload(), "accepted_answers": ["work", "work"]}
    with pytest.raises(ValueError, match="duplicates"):
        recover_generated_candidate(duplicate, call)
    untrimmed = {**_payload(), "target_answer": " In this situation, I work."}
    with pytest.raises(ValueError, match="trimmed"):
        recover_generated_candidate(untrimmed, call)


def test_generation_backend_is_injected_with_exact_active_input() -> None:
    call = _generation_call()
    captured = {}

    def fake_model(prompt, **kwargs):
        captured["prompt"] = prompt
        captured.update(kwargs)
        return _payload()

    candidate = generate_one_candidate(call, model_call=fake_model)
    assert candidate["item_id"] == "candidate_toy_cell_01"
    assert captured["stage"] == "generation"
    assert captured["call_key"] == candidate["item_id"]
    assert captured["input_data"] == call["model_input"]
    assert captured["prompt"] == call["rendered_prompt"]


def test_deterministic_rejection_never_calls_validator() -> None:
    candidate = _candidate()
    candidate["prompt"] = "This malformed prompt has no response slot."
    call = build_validation_call(
        candidate,
        _cell(),
        VALIDATION_PROMPT,
        VALIDATION_CRITERIA,
        model="fixture-validator",
        reasoning_effort="medium",
    )
    assert call["call_required"] is False
    assert call["deterministic_checks"]["visible_response_slot"]["passed"] is False

    def must_not_run(*args, **kwargs):
        raise AssertionError("deterministic prechecks must precede validation")

    row = validate_one_candidate(call, model_call=must_not_run)
    assert row["accepted"] is False
    assert row["judgments"] == {}
    assert row["rejection_stage"] == "deterministic_precheck"
    with pytest.raises(ValueError, match="must not be judged"):
        reconstruct_validation_judgment(call, _passing_judgments())


def test_deterministic_suffix_check_rejects_repeated_visible_clause_text() -> None:
    call = _generation_call()
    candidate = recover_generated_candidate(
        {
            "prompt": "The child ___ home today. (walk)",
            "target_answer": "The child walks home today.",
            "accepted_answers": ["walks home today"],
        },
        call,
    )

    checks = deterministic_candidate_checks(candidate)
    suffix = checks["accepted_answer_visible_suffix"]
    assert suffix["passed"] is False
    assert "2 lexical token(s) visibly printed after the slot" in suffix["note"]
    assert checks["target_contains_accepted_answer_span"]["passed"] is True


def test_packaging_checks_accept_partial_slot_and_whole_answer_forms() -> None:
    partial = recover_generated_candidate(
        {
            "prompt": "The child ___ home today. (walk)",
            "target_answer": "The child walks home today.",
            "accepted_answers": ["walks"],
        },
        _generation_call(index=1),
    )
    partial_checks = deterministic_candidate_checks(partial)
    assert partial_checks["accepted_answer_visible_suffix"]["passed"] is True
    assert partial_checks["target_contains_accepted_answer_span"]["passed"] is True

    whole = recover_generated_candidate(
        {
            "prompt": "Write the sentence: ____\nCue: she / work",
            "target_answer": "She works.",
            "accepted_answers": ["She works!"],
        },
        _generation_call(index=2),
    )
    whole_checks = deterministic_candidate_checks(whole)
    assert whole_checks["accepted_answer_visible_suffix"]["passed"] is True
    assert "no lexical clause suffix" in whole_checks[
        "accepted_answer_visible_suffix"
    ]["note"]
    assert whole_checks["target_contains_accepted_answer_span"]["passed"] is True


def test_target_answer_must_contain_a_normalized_accepted_span() -> None:
    candidate = recover_generated_candidate(
        {
            "prompt": "The learner ___. (work)",
            "target_answer": "The learner works.",
            "accepted_answers": ["work"],
        },
        _generation_call(),
    )

    checks = deterministic_candidate_checks(candidate)
    target_span = checks["target_contains_accepted_answer_span"]
    assert target_span["passed"] is False
    assert "contains none" in target_span["note"]

    validation_call = build_validation_call(
        candidate,
        _cell(),
        VALIDATION_PROMPT,
        VALIDATION_CRITERIA,
        model="fixture-validator",
        reasoning_effort="medium",
    )
    assert validation_call["call_required"] is False


def test_validator_recovery_is_exact_typed_and_independent() -> None:
    candidate = _candidate()
    call = build_validation_call(
        candidate,
        _cell(),
        VALIDATION_PROMPT,
        VALIDATION_CRITERIA,
        model="fixture-validator",
        reasoning_effort="medium",
    )
    assert call["call_required"] is True
    assert set(call["model_input"]) == {"visible_item", "target_cell", "criteria"}
    assert call["model_input"]["visible_item"]["item_id"].startswith(
        "validation_item_"
    )
    assert candidate["item_id"] not in str(call["model_input"])
    flattened = str(call["model_input"])
    assert "generation_metadata" not in flattened
    assert "candidate_index" not in flattened
    assert "learner_outcomes" not in flattened
    assert "generator_kc_ids" not in flattened

    row = reconstruct_validation_judgment(call, _passing_judgments())
    assert row["accepted"] is True
    assert row["rejection_stage"] is None

    missing = _passing_judgments()
    missing["judgments"].pop(next(iter(missing["judgments"])))
    with pytest.raises(ValueError, match="exactly every"):
        reconstruct_validation_judgment(call, missing)
    extra = {**_passing_judgments(), "summary": "not licensed"}
    with pytest.raises(ValueError, match="exactly judgments"):
        reconstruct_validation_judgment(call, extra)
    wrong_type = _passing_judgments()
    criterion = next(iter(wrong_type["judgments"]))
    wrong_type["judgments"][criterion]["passed"] = 1
    with pytest.raises(ValueError, match="must be boolean"):
        reconstruct_validation_judgment(call, wrong_type)


def test_validation_backend_is_injected_only_after_prechecks() -> None:
    candidate = _candidate()
    call = build_validation_call(
        candidate,
        _cell(),
        VALIDATION_PROMPT,
        VALIDATION_CRITERIA,
        model="fixture-validator",
        reasoning_effort="medium",
    )
    captured = {}

    def fake_validator(prompt, **kwargs):
        captured["prompt"] = prompt
        captured.update(kwargs)
        return _passing_judgments()

    row = validate_one_candidate(call, model_call=fake_validator)
    assert row["accepted"] is True
    assert captured["stage"] == "validation"
    assert captured["call_key"] == candidate["item_id"]
    assert captured["input_data"] == call["model_input"]


def test_checkpoint_merge_rejects_duplicate_unknown_and_input_drift() -> None:
    first_call = _generation_call(index=1)
    second_call = _generation_call(index=2)
    calls = [first_call, second_call]
    first = recover_generated_candidate(_payload(), first_call)
    second = recover_generated_candidate(_payload(), second_call)

    assert merge_completed_candidate_rows([second], [first], calls) == [first, second]
    assert pending_generation_calls(calls, [first]) == [second_call]
    with pytest.raises(ValueError, match="duplicate completed"):
        merge_completed_candidate_rows([first], [first], calls)

    drifted = deepcopy(first)
    drifted["generation_metadata"]["input_sha256"] = "0" * 64
    with pytest.raises(ValueError, match="input drift"):
        merge_completed_candidate_rows([drifted], [], calls)

    unknown = deepcopy(first)
    unknown["item_id"] = "candidate_unknown_01"
    with pytest.raises(ValueError, match="not in the frozen plan"):
        merge_completed_candidate_rows([], [unknown], calls)

    validation_call = build_validation_call(
        first,
        _cell(),
        VALIDATION_PROMPT,
        VALIDATION_CRITERIA,
        model="fixture-validator",
        reasoning_effort="medium",
    )
    judgment = reconstruct_validation_judgment(
        validation_call, _passing_judgments()
    )
    assert merge_completed_judgment_rows([], [judgment], [validation_call]) == [
        judgment
    ]
    drifted_judgment = deepcopy(judgment)
    drifted_judgment["validation_metadata"]["input_sha256"] = "f" * 64
    with pytest.raises(ValueError, match="input drift"):
        merge_completed_judgment_rows(
            [drifted_judgment], [], [validation_call]
        )


def test_public_audit_contains_counts_not_prompts_or_judgment_notes() -> None:
    cell = _cell()
    candidate = _candidate()
    validation_call = build_validation_call(
        candidate,
        cell,
        VALIDATION_PROMPT,
        VALIDATION_CRITERIA,
        model="fixture-validator",
        reasoning_effort="medium",
    )
    parsed = _passing_judgments()
    failed_criterion = "determinacy"
    parsed["judgments"][failed_criterion] = {
        "passed": False,
        "note": "PRIVATE-JUDGMENT-NOTE",
    }
    judgment = reconstruct_validation_judgment(validation_call, parsed)

    generation = candidate_audit_summary([cell], [candidate])
    assert generation["planned_candidates"] == 3
    assert generation["completed_candidates"] == 1
    assert generation["by_cell"]["toy_cell"]["missing_indices"] == [2, 3]

    audit = item_construction_audit(
        [cell], [candidate], [judgment], VALIDATION_CRITERIA
    )
    assert audit["validation"]["accepted_candidates"] == 0
    assert audit["validation"]["criteria"][failed_criterion] | {
        "judged": 1,
        "passed": 0,
        "failed": 1,
        "not_judged": 0,
        "pass_rate": 0.0,
    } == audit["validation"]["criteria"][failed_criterion]
    rendered = str(audit)
    assert candidate["prompt"] not in rendered
    assert "PRIVATE-JUDGMENT-NOTE" not in rendered
    assert "consult-only-source" not in rendered
    assert audit["privacy"] == {
        "contains_source_descriptors": False,
        "contains_judgment_notes": False,
        "contains_learner_outcomes": False,
        "contains_generator_kcs": False,
    }
