from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

import pytest

from grammar_kt.io import read_jsonl, read_yaml
from scripts.run_full_dataset import (
    GENERATION_DESIGN_PATH,
    GRAMMAR_SCHEMA_PATH,
    INTERVENTION_INDICES,
    INTERVENTION_PROTOCOL,
    INTERVENTION_STATUS,
    RESCUE_INDICES,
    RESCUE_STATUS,
    _write_item_state,
    cells_missing_generation_attempts,
    generate_and_validate_determinacy_intervention,
    generate_and_validate_missing,
    generate_and_validate_rescue,
    make_source_cell_relations,
    missing_generation_positions,
    reuse_phase4_pilot,
    write_manifest,
)
from grammar_kt.canonicalise import canonicalise


ROOT = Path(__file__).resolve().parents[1]


def _retained_medium_inventory():
    schema = read_yaml(GRAMMAR_SCHEMA_PATH)
    dataset = ROOT / "data/grammar_kt_medium_v1"
    sources = read_jsonl(dataset / "source/descriptors.jsonl")
    mappings = read_jsonl(dataset / "normalisation/mappings.jsonl")
    cells = canonicalise(mappings, schema)
    return schema, sources, mappings, cells


def test_retained_139_descriptors_reproduce_exact_24_cell_inventory() -> None:
    schema, sources, mappings, cells = _retained_medium_inventory()
    relations = make_source_cell_relations(mappings, cells, schema)

    assert len(sources) == 139
    assert len({row["source_id"] for row in sources}) == 139
    assert Counter(row["result"] for row in mappings) == {
        "complete": 44,
        "partial": 77,
        "out_of_scope": 16,
        "unresolved": 2,
    }
    assert sum(bool(row["phase2_eligible"]) for row in mappings) == 9
    assert len(cells) == 24
    assert len(relations) == 48
    assert len({row["source_id"] for row in relations}) == 44

    assert cells == read_jsonl(
        ROOT / "data/grammar_kt_medium_v1/canonical/cells.jsonl"
    )


def test_live_pilot_reuse_is_feature_tuple_only_and_leaves_16_cells() -> None:
    schema, _, _, cells = _retained_medium_inventory()
    attempts, candidates, judgments = reuse_phase4_pilot(cells, schema)

    assert len(attempts) == 24
    assert len(candidates) == 23  # one retained generation payload was malformed
    assert len(judgments) == 23
    assert len({row["cell_id"] for row in attempts}) == 8
    assert len(cells_missing_generation_attempts(cells, attempts)) == 16
    assert len(missing_generation_positions(cells, attempts)) == 48
    assert all(row["cell_id"].startswith("cell_") for row in candidates)
    assert all("operation_tags" not in row for row in candidates)

    accepted = [row for row in judgments if row["accepted"]]
    # The active precheck now also catches answer punctuation duplicated by
    # punctuation already printed after the slot. Three formerly accepted
    # pilot packages are therefore rejected before post-generation curation.
    assert len(accepted) == 14
    candidates_by_id = {row["item_id"]: row for row in candidates}
    accepted_cells = Counter(
        candidates_by_id[row["item_id"]]["cell_id"]
        for row in accepted
    )
    assert len(accepted_cells) == 7
    assert min(accepted_cells.values()) >= 1
    assert sum(
        row["rejection_stage"] == "deterministic_precheck_reapplied"
        for row in judgments
    ) == 7


def test_missing_cell_path_calls_active_generation_and_validation(
    tmp_path: Path,
) -> None:
    _, _, _, cells = _retained_medium_inventory()
    one_cell = [cells[0]]

    def fixture_model(prompt, **call):
        if call["stage"] == "generation":
            index = call["input_data"]["candidate_position"]["index"]
            answer = f"The learner writes sentence {index}."
            return {
                "prompt": f"Write response {index}: ____",
                "target_answer": answer,
                "accepted_answers": [answer],
            }
        return {
            "judgments": {
                name: {"passed": True, "note": "Deterministic contract fixture."}
                for name in call["input_data"]["criteria"]
            }
        }

    attempts, candidates, judgments = generate_and_validate_missing(
        tmp_path,
        one_cell,
        [],
        [],
        [],
        workers=1,
        generation_model="fixture",
        validation_model="fixture",
        reasoning_effort="deterministic",
        model_call=fixture_model,
    )
    assert len(attempts) == len(candidates) == len(judgments) == 3
    assert all(row["accepted"] for row in judgments)
    assert all(
        row["validation_metadata"]["status"] == "phase6_live_model_evidence"
        for row in judgments
    )


def test_failed_positions_and_judgments_are_checkpointed_without_recall(
    tmp_path: Path,
) -> None:
    _, _, _, cells = _retained_medium_inventory()
    one_cell = [cells[0]]
    calls = Counter()

    def partly_malformed_model(prompt, **call):
        stage = call["stage"]
        calls[stage] += 1
        if stage == "generation":
            index = call["input_data"]["candidate_position"]["index"]
            if index == 2:
                return {"prompt": "Malformed: ____"}
            answer = f"The learner writes sentence {index}."
            return {
                "prompt": f"Write response {index}: ____",
                "target_answer": answer,
                "accepted_answers": [answer],
            }
        if call["input_data"]["visible_item"]["item_id"].endswith("_03"):
            return {"malformed": True}
        return {
            "judgments": {
                name: {"passed": True, "note": "Deterministic contract fixture."}
                for name in call["input_data"]["criteria"]
            }
        }

    attempts, candidates, judgments = generate_and_validate_missing(
        tmp_path,
        one_cell,
        [],
        [],
        [],
        workers=1,
        generation_model="fixture",
        validation_model="fixture",
        reasoning_effort="deterministic",
        model_call=partly_malformed_model,
    )
    assert calls == {"generation": 3, "validation": 2}
    assert len(attempts) == 3
    assert len(candidates) == 2
    assert len(judgments) == 2
    assert sum(not row["structurally_valid"] for row in attempts) == 1
    assert sum(
        row["rejection_stage"] == "validator_call_or_output_failure"
        for row in judgments
    ) == 1
    assert missing_generation_positions(one_cell, attempts) == []

    def unexpected_recall(prompt, **call):
        raise AssertionError("a retained candidate position or judgment was re-called")

    replayed = generate_and_validate_missing(
        tmp_path,
        one_cell,
        attempts,
        candidates,
        judgments,
        workers=1,
        generation_model="fixture",
        validation_model="fixture",
        reasoning_effort="deterministic",
        model_call=unexpected_recall,
    )
    assert replayed == (attempts, candidates, judgments)


def test_conditional_rescue_requires_complete_default_n3_and_incomplete_bank(
    tmp_path: Path,
) -> None:
    _, _, _, cells = _retained_medium_inventory()
    one_cell = [cells[0]]

    with pytest.raises(ValueError, match="all default N=3"):
        generate_and_validate_rescue(
            tmp_path,
            one_cell,
            [],
            [],
            [],
            workers=1,
            generation_model="fixture",
            validation_model="fixture",
            reasoning_effort="deterministic",
            model_call=lambda *_args, **_kwargs: (_ for _ in ()).throw(
                AssertionError("guard must precede model calls")
            ),
        )

    def all_valid_model(prompt, **call):
        if call["stage"] == "generation":
            index = call["input_data"]["candidate_position"]["index"]
            answer = f"They complete response {index}."
            return {
                "prompt": "Complete the response: ____",
                "target_answer": answer,
                "accepted_answers": [answer],
            }
        return {
            "judgments": {
                name: {"passed": True, "note": "Fixture pass."}
                for name in call["input_data"]["criteria"]
            }
        }

    attempts, candidates, judgments = generate_and_validate_missing(
        tmp_path,
        one_cell,
        [],
        [],
        [],
        workers=1,
        generation_model="fixture",
        validation_model="fixture",
        reasoning_effort="deterministic",
        model_call=all_valid_model,
    )
    with pytest.raises(ValueError, match="already covers every GrammarCell"):
        generate_and_validate_rescue(
            tmp_path,
            one_cell,
            attempts,
            candidates,
            judgments,
            workers=1,
            generation_model="fixture",
            validation_model="fixture",
            reasoning_effort="deterministic",
            model_call=lambda *_args, **_kwargs: (_ for _ in ()).throw(
                AssertionError("guard must precede model calls")
            ),
        )


def test_conditional_rescue_uses_indices_four_five_marks_provenance_and_resumes(
    tmp_path: Path,
) -> None:
    _, _, _, cells = _retained_medium_inventory()
    one_cell = [cells[0]]

    def all_rejected_default_model(prompt, **call):
        if call["stage"] == "generation":
            index = call["input_data"]["candidate_position"]["index"]
            answer = f"They complete response {index}."
            return {
                "prompt": "Complete the response: ____",
                "target_answer": answer,
                "accepted_answers": [answer],
            }
        judgments = {
            name: {"passed": True, "note": "Fixture pass."}
            for name in call["input_data"]["criteria"]
        }
        judgments["determinacy"] = {
            "passed": False,
            "note": "Fixture default rejection.",
        }
        return {"judgments": judgments}

    attempts, candidates, judgments = generate_and_validate_missing(
        tmp_path,
        one_cell,
        [],
        [],
        [],
        workers=1,
        generation_model="fixture",
        validation_model="fixture",
        reasoning_effort="deterministic",
        model_call=all_rejected_default_model,
    )
    calls = Counter()

    def rescue_model(prompt, **call):
        calls[call["stage"]] += 1
        if call["stage"] == "generation":
            position = call["input_data"]["candidate_position"]
            assert position["index"] in RESCUE_INDICES
            assert position["count"] == max(RESCUE_INDICES)
            answer = f"They complete rescue response {position['index']}."
            return {
                "prompt": "Complete the rescue response: ____",
                "target_answer": answer,
                "accepted_answers": [answer],
            }
        return {
            "judgments": {
                name: {"passed": True, "note": "Fixture rescue pass."}
                for name in call["input_data"]["criteria"]
            }
        }

    rescued = generate_and_validate_rescue(
        tmp_path,
        one_cell,
        attempts,
        candidates,
        judgments,
        workers=1,
        generation_model="fixture",
        validation_model="fixture",
        reasoning_effort="deterministic",
        model_call=rescue_model,
    )
    attempts, candidates, judgments = rescued
    assert calls == {"generation": 2, "validation": 2}
    rescue_attempts = [row for row in attempts if row["candidate_index"] > 3]
    rescue_candidates = [
        row
        for row in candidates
        if row["generation_metadata"]["candidate_index"] > 3
    ]
    rescue_judgments = [
        row
        for row in judgments
        if row.get("validation_metadata", {}).get("status") == RESCUE_STATUS
    ]
    assert [row["candidate_index"] for row in rescue_attempts] == [4, 5]
    assert all(row["provenance"]["status"] == RESCUE_STATUS for row in rescue_attempts)
    assert all(
        row["generation_metadata"]["provenance"]["status"] == RESCUE_STATUS
        for row in rescue_candidates
    )
    assert all(
        row["validation_metadata"]["status"] == RESCUE_STATUS
        for row in rescue_judgments
    )
    assert missing_generation_positions(one_cell, attempts) == []
    assert len(read_jsonl(tmp_path / "items/generation_attempts.jsonl")) == 5
    assert len(read_jsonl(tmp_path / "items/validation.jsonl")) == 5

    def unexpected_recall(prompt, **call):
        raise AssertionError("a retained rescue position or judgment was re-called")

    replayed = generate_and_validate_rescue(
        tmp_path,
        one_cell,
        attempts,
        candidates,
        judgments,
        workers=1,
        generation_model="fixture",
        validation_model="fixture",
        reasoning_effort="deterministic",
        model_call=unexpected_recall,
    )
    assert replayed == rescued


def test_determinacy_intervention_requires_completed_rescue(
    tmp_path: Path,
) -> None:
    _, _, _, cells = _retained_medium_inventory()
    one_cell = [cells[0]]

    def rejected_default_model(prompt, **call):
        if call["stage"] == "generation":
            index = call["input_data"]["candidate_position"]["index"]
            answer = f"They complete response {index}."
            return {
                "prompt": "Complete the response: ____",
                "target_answer": answer,
                "accepted_answers": [answer],
            }
        judgments = {
            name: {"passed": True, "note": "Fixture pass."}
            for name in call["input_data"]["criteria"]
        }
        judgments["determinacy"] = {
            "passed": False,
            "note": "Fixture ambiguity.",
        }
        return {"judgments": judgments}

    attempts, candidates, judgments = generate_and_validate_missing(
        tmp_path,
        one_cell,
        [],
        [],
        [],
        workers=1,
        generation_model="fixture",
        validation_model="fixture",
        reasoning_effort="deterministic",
        model_call=rejected_default_model,
    )
    with pytest.raises(ValueError, match="frozen unchanged-prompt rescue"):
        generate_and_validate_determinacy_intervention(
            tmp_path,
            one_cell,
            attempts,
            candidates,
            judgments,
            workers=1,
            generation_model="fixture",
            validation_model="fixture",
            reasoning_effort="deterministic",
            model_call=lambda *_args, **_kwargs: (_ for _ in ()).throw(
                AssertionError("guard must precede model calls")
            ),
        )


def test_determinacy_intervention_freezes_indices_six_seven_and_resumes(
    tmp_path: Path,
) -> None:
    _, _, _, cells = _retained_medium_inventory()
    one_cell = [cells[0]]

    def rejected_model(prompt, **call):
        if call["stage"] == "generation":
            index = call["input_data"]["candidate_position"]["index"]
            answer = f"They complete response {index}."
            return {
                "prompt": "Complete the response: ____",
                "target_answer": answer,
                "accepted_answers": [answer],
            }
        judgments = {
            name: {"passed": True, "note": "Fixture pass."}
            for name in call["input_data"]["criteria"]
        }
        judgments["determinacy"] = {
            "passed": False,
            "note": "Fixture ambiguity.",
        }
        return {"judgments": judgments}

    attempts, candidates, judgments = generate_and_validate_missing(
        tmp_path,
        one_cell,
        [],
        [],
        [],
        workers=1,
        generation_model="fixture",
        validation_model="fixture",
        reasoning_effort="deterministic",
        model_call=rejected_model,
    )
    attempts, candidates, judgments = generate_and_validate_rescue(
        tmp_path,
        one_cell,
        attempts,
        candidates,
        judgments,
        workers=1,
        generation_model="fixture",
        validation_model="fixture",
        reasoning_effort="deterministic",
        model_call=rejected_model,
    )
    pre_intervention_attempts = [dict(row) for row in attempts]
    pre_intervention_candidates = [dict(row) for row in candidates]
    pre_intervention_judgments = [dict(row) for row in judgments]
    calls = Counter()

    def intervention_model(prompt, **call):
        calls[call["stage"]] += 1
        if call["stage"] == "generation":
            position = call["input_data"]["candidate_position"]
            assert position["index"] in INTERVENTION_INDICES
            assert position["count"] == max(INTERVENTION_INDICES)
            assert "DETERMINACY INTERVENTION" in prompt
            assert "may explicitly name" in prompt
            answer = f"They complete explicit response {position['index']}."
            return {
                "prompt": (
                    "Use the declared target construction to complete: ____"
                ),
                "target_answer": answer,
                "accepted_answers": [answer],
            }
        return {
            "judgments": {
                name: {"passed": True, "note": "Fixture intervention pass."}
                for name in call["input_data"]["criteria"]
            }
        }

    intervened = generate_and_validate_determinacy_intervention(
        tmp_path,
        one_cell,
        attempts,
        candidates,
        judgments,
        workers=1,
        generation_model="fixture",
        validation_model="fixture",
        reasoning_effort="deterministic",
        model_call=intervention_model,
    )
    attempts, candidates, judgments = intervened
    assert calls == {"generation": 2, "validation": 2}
    assert attempts[:5] == pre_intervention_attempts
    assert candidates[:5] == pre_intervention_candidates
    assert judgments[:5] == pre_intervention_judgments

    intervention_attempts = [
        row for row in attempts if row["candidate_index"] in INTERVENTION_INDICES
    ]
    intervention_candidates = [
        row
        for row in candidates
        if row["generation_metadata"].get("provenance", {}).get("status")
        == INTERVENTION_STATUS
    ]
    intervention_judgments = [
        row
        for row in judgments
        if row.get("validation_metadata", {}).get("status")
        == INTERVENTION_STATUS
    ]
    assert [row["candidate_index"] for row in intervention_attempts] == [6, 7]
    assert all(
        row["provenance"]["protocol"] == INTERVENTION_PROTOCOL
        for row in intervention_attempts
    )
    assert len(intervention_candidates) == len(intervention_judgments) == 2
    assert all(row["accepted"] for row in intervention_judgments)

    plan = json.loads(
        (tmp_path / "items/determinacy_intervention_plan.json").read_text()
    )
    assert plan["cell_ids"] == [one_cell[0]["cell_id"]]
    assert plan["candidate_indices"] == [6, 7]
    assert plan["prior_determinacy_failures_by_cell"] == {
        one_cell[0]["cell_id"]: 5
    }
    assert plan["only_generation_prompt_changes"] is True

    summary = _write_item_state(
        tmp_path,
        attempts,
        candidates,
        judgments,
        one_cell,
        read_yaml(GENERATION_DESIGN_PATH),
    )
    manifest = write_manifest(
        tmp_path,
        {},
        summary,
        one_cell,
        attempts,
        exact_command="fixture intervention",
        generation_model="fixture",
        validation_model="fixture",
        reasoning_effort="deterministic",
    )
    assert manifest["status"] == "fixed_item_bank_complete"
    counts = manifest["item_construction_counts"]
    assert counts["default"]["attempts"] == 3
    assert counts["default"]["validator_accepted"] == 0
    assert counts["conditional_rescue"]["attempts"] == 2
    assert counts["conditional_rescue"]["validator_accepted"] == 0
    assert counts["determinacy_intervention"] == {
        "activated": True,
        "protocol": INTERVENTION_PROTOCOL,
        "cell_ids": [one_cell[0]["cell_id"]],
        "candidate_indices": [6, 7],
        "planned_attempts": 2,
        "attempts": 2,
        "structurally_valid_candidates": 2,
        "validation_judgments": 2,
        "validator_accepted": 2,
    }

    def unexpected_recall(prompt, **call):
        raise AssertionError(
            "a retained determinacy-intervention position was re-called"
        )

    replayed = generate_and_validate_determinacy_intervention(
        tmp_path,
        one_cell,
        attempts,
        candidates,
        judgments,
        workers=1,
        generation_model="fixture",
        validation_model="fixture",
        reasoning_effort="deterministic",
        model_call=unexpected_recall,
    )
    assert replayed == intervened
