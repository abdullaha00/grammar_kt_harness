from __future__ import annotations

import json
from pathlib import Path

from scripts.run_item_audit import (
    AUDIT_PROMPT_SUFFIX,
    PILOT_CELL_IDS,
    blind_candidates,
    build_generation_tasks,
    candidate_payload_errors,
    generate_one,
    load_controlled_lexicon,
    load_frozen_cells,
    prefix_results,
    recover_readable_source_support,
    validate_one_blinded,
)
from grammar_kt.io import read_text, read_yaml


ROOT = Path(__file__).resolve().parents[1]


def _payload(prompt: str = "Complete: The learner ___. (work)") -> dict:
    answer = "The learner works."
    return {
        "prompt": prompt,
        "target_answer": answer,
        "accepted_answers": [answer],
        "operation_tags": [],
        "note": "A structurally complete fixture.",
    }


def _candidate(index: int, prompt: str) -> dict:
    return {
        "item_id": f"candidate_model_selected_cell_x_{index:02d}",
        "cell_id": "cell_x",
        "format": "controlled_production",
        "prompt": prompt,
        "target_answer": prompt.replace("___", "works"),
        "accepted_answers": [prompt.replace("___", "works")],
        "operation_tags": [],
        "generation_metadata": {
            "condition": "model_selected",
            "candidate_index": index,
            "candidate_count": 5,
            "model": "fixture",
            "note": "fixture",
            "readable_source_records": 0,
            "controlled_lexicon": False,
        },
    }


def test_frozen_bank_and_recoverable_source_boundary() -> None:
    cells = load_frozen_cells()
    assert len(cells) == 24
    assert len(set(PILOT_CELL_IDS)) == 8
    assert set(PILOT_CELL_IDS) <= {row["cell_id"] for row in cells}

    support = recover_readable_source_support(cells)
    assert len(support) == 5
    assert all(
        set(evidence) == {"guideword", "can_do"}
        for rows in support.values()
        for evidence in rows
    )
    assert not any(
        forbidden in json.dumps(support).casefold()
        for forbidden in ("egp_id", "source_id", "cefr", "examples")
    )


def test_generation_conditions_have_the_intended_inputs_and_candidate_position(
    tmp_path: Path,
) -> None:
    cells = [row for row in load_frozen_cells() if row["cell_id"] in PILOT_CELL_IDS]
    support = recover_readable_source_support(cells)
    lexicon = load_controlled_lexicon()
    tasks = build_generation_tasks(cells, support, lexicon)
    assert len(tasks) == 89  # 8*(5+5) plus 3 recoverable cells*3

    model_task = next(row for row in tasks if row["condition"] == "model_selected")
    controlled_task = next(
        row for row in tasks if row["condition"] == "controlled_lexicon"
    )
    source_task = next(
        row
        for row in tasks
        if row["condition"] == "readable_source_evidence"
        and row["candidate_index"] == 2
    )
    assert model_task["source_support"]["evidence"] == []
    assert "entries" not in model_task["lexical_intervention"]
    assert controlled_task["source_support"]["evidence"] == []
    assert len(controlled_task["lexical_intervention"]["entries"]) == 6
    assert all(
        set(row) <= {
            "lemma",
            "predicate_class",
            "passive_compatible",
            "example_subject",
            "example_object",
        }
        for row in controlled_task["lexical_intervention"]["entries"]
    )

    captured = {}

    def fake_model(prompt, **call):
        captured["prompt"] = prompt
        captured["input"] = call["input_data"]
        return _payload()

    generation_prompt = (
        read_text(ROOT / "modules/items/generation/prompt.txt").rstrip()
        + AUDIT_PROMPT_SUFFIX
    )
    attempt, candidate = generate_one(
        source_task,
        prompt=generation_prompt,
        rulebook=read_text(ROOT / "modules/items/generation/rulebook.md"),
        design=read_yaml(ROOT / "modules/items/generation/design.yaml"),
        item_format=read_yaml(
            ROOT / "modules/items/generation/formats/controlled_production.yaml"
        ),
        model="fixture",
        reasoning_effort="deterministic",
        model_call=fake_model,
        evidence_dir=tmp_path,
    )
    assert attempt["structurally_valid"] is True
    assert candidate is not None
    assert captured["input"]["candidate_position"] == {"index": 2, "count": 3}
    assert '"index": 2' in captured["prompt"]
    assert '"count": 3' in captured["prompt"]
    assert all(
        set(row) == {"guideword", "can_do"}
        for row in captured["input"]["source_support"]["evidence"]
    )


def test_structural_candidate_validation_precedes_model_judgment() -> None:
    assert candidate_payload_errors(_payload()) == []
    assert "prompt has no visible response slot" in candidate_payload_errors(
        _payload("The learner works.")
    )
    unknown_tag = _payload()
    unknown_tag["operation_tags"] = ["english_specific_guess"]
    assert any("unknown operation tags" in error for error in candidate_payload_errors(unknown_tag))
    missing_answer = _payload()
    missing_answer["accepted_answers"] = ["A different answer."]
    assert "target_answer must be included in accepted_answers" in candidate_payload_errors(
        missing_answer
    )


def test_seeded_blinding_strips_condition_and_candidate_rank() -> None:
    candidates = [
        _candidate(1, "One ___ here. (work)"),
        _candidate(2, "Two ___ here. (work)"),
        _candidate(3, "Three ___ here. (work)"),
    ]
    first, first_map = blind_candidates(candidates)
    second, second_map = blind_candidates(list(reversed(candidates)))
    assert first == second
    assert first_map == second_map
    assert [row["item_id"] for row in first] == [
        "blind_item_0001",
        "blind_item_0002",
        "blind_item_0003",
    ]
    assert all(
        set(row)
        == {
            "item_id",
            "cell_id",
            "format",
            "prompt",
            "target_answer",
            "accepted_answers",
        }
        for row in first
    )


def test_validator_input_is_neutral_and_contains_no_generation_metadata(
    tmp_path: Path,
) -> None:
    candidate = _candidate(4, "The child ___ home. (walk)")
    blinded, _ = blind_candidates([candidate])
    captured = {}
    criteria = read_yaml(ROOT / "modules/items/validation/criteria.yaml")

    def fake_validator(prompt, **call):
        captured.update(call["input_data"])
        return {
            "judgments": {
                name: {"passed": True, "note": "Independent fixture judgment."}
                for name in criteria["criteria"]
            }
        }

    result = validate_one_blinded(
        blinded[0],
        cells_by_id={
            "cell_x": {
                "cell_id": "cell_x",
                "features": {
                    "tense": "present",
                    "aspect": "none",
                    "voice": "active",
                    "polarity": "positive",
                    "clause": "declarative",
                    "modal": "none",
                },
            }
        },
        prompt=read_text(ROOT / "modules/items/validation/prompt.txt"),
        validation_criteria=criteria,
        model="fixture",
        reasoning_effort="deterministic",
        model_call=fake_validator,
        evidence_dir=tmp_path,
    )
    assert result["accepted"] is True
    assert set(captured) == {"visible_item", "target_cell", "criteria"}
    assert captured["visible_item"]["item_id"] == "blind_item_0001"
    flattened = json.dumps(captured).casefold()
    assert "condition" not in flattened
    assert "candidate_index" not in flattened
    assert "generation_metadata" not in flattened


def test_prefixes_reuse_maximum_n_and_selection_rules_are_deterministic() -> None:
    prompts = {
        1: "The cat ___ home. (walk)",
        2: "The cat ___ home today. (walk)",
        3: "The cat ___ home quickly today. (walk)",
        4: "The cat ___ home after lunch. (walk)",
        5: "Yesterday, the scientists ___ a distant island. (visit)",
    }
    candidates = [_candidate(index, prompt) for index, prompt in prompts.items()]
    attempts = [
        {
            "candidate_id": row["item_id"],
            "condition": "model_selected",
            "cell_id": "cell_x",
            "candidate_index": row["generation_metadata"]["candidate_index"],
            "candidate_count": 5,
            "structurally_valid": True,
            "structural_errors": [],
            "call_error": None,
            "runtime_seconds": 0.0,
        }
        for row in candidates
    ]
    validation = [
        {
            "candidate_id": row["item_id"],
            "validator_output_valid": True,
            "judgments": {},
            "accepted": row["generation_metadata"]["candidate_index"] in {2, 3, 5},
        }
        for row in candidates
    ]
    metrics, selections = prefix_results(
        attempts, candidates, validation, select_second=True
    )
    model_metrics = [row for row in metrics if row["condition"] == "model_selected"]
    assert [row["planned_generation_attempts"] for row in model_metrics] == [1, 3, 5]
    assert [row["covered_cells"] for row in model_metrics] == [0, 1, 1]

    n3 = [
        row
        for row in selections
        if row["condition"] == "model_selected" and row["prefix_n"] == 3
    ]
    n5 = [
        row
        for row in selections
        if row["condition"] == "model_selected" and row["prefix_n"] == 5
    ]
    assert [(row["selection_rank"], row["candidate_index"]) for row in n3] == [
        (1, 2),
        (2, 3),
    ]
    assert [(row["selection_rank"], row["candidate_index"]) for row in n5] == [
        (1, 2),
        (2, 5),
    ]
