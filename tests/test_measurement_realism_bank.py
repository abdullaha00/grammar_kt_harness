from __future__ import annotations

import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/experiments/measurement_realism_bank.py"
SPEC = importlib.util.spec_from_file_location("measurement_realism_bank", SCRIPT)
assert SPEC and SPEC.loader
bank = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(bank)


def valid_family(spec: dict, config: dict, round_index: int = 1) -> dict:
    family_id = spec["family_id"]
    candidate = bank.candidate_id(family_id, round_index)
    canonical = "Can Mia swim?"
    common_payload = {
        "sentence_template": None,
        "dialogue_turns": [],
        "incomplete_turn_template": None,
        "stem": None,
        "options": [],
        "source_sentence": None,
        "transformation_cue": None,
    }

    def item(item_format: str, response_mode: str, payload: dict, target: str, accepted: list[str], key=None, distractors=None) -> dict:
        return {
            "candidate_item_id": bank.candidate_item_id(candidate, item_format, config),
            "format": item_format,
            "response_mode": response_mode,
            "instruction": "Complete the grammar practice item.",
            "context": "Mia is at the pool.",
            "format_payload": {**common_payload, **payload},
            "scoring": {
                "target_response": target,
                "accepted_responses": accepted,
                "completed_target": canonical,
                "correct_choice_id": key,
            },
            "distractor_annotations": distractors or [],
        }

    items = [
        item("constrained_cloze", "short_text", {"sentence_template": "[[RESPONSE]]"}, canonical, [canonical]),
        item("dialogue_completion", "short_text", {"dialogue_turns": ["Leo: Mia enjoys the pool."], "incomplete_turn_template": "[[RESPONSE]]"}, canonical, [canonical]),
        item(
            "multiple_choice",
            "single_choice",
            {
                "stem": "Choose the question that asks about Mia's ability.",
                "options": [
                    {"id": "A", "text": canonical},
                    {"id": "B", "text": "Mia can swim?"},
                    {"id": "C", "text": "Does Mia can swim?"},
                    {"id": "D", "text": "Can Mia swims?"},
                ],
            },
            "A",
            ["A"],
            "A",
            [
                {"option_id": "B", "intended_operation_error": "question order"},
                {"option_id": "C", "intended_operation_error": "extra auxiliary"},
                {"option_id": "D", "intended_operation_error": "modal complement"},
            ],
        ),
        item(
            "sentence_transformation",
            "full_sentence",
            {"source_sentence": "Mia is able to swim.", "transformation_cue": "Ask whether this is true. Use can."},
            canonical,
            [canonical],
        ),
    ]
    return {
        "protocol_id": config["protocol_id"],
        "family_id": family_id,
        "candidate_id": candidate,
        "candidate_round": round_index,
        "cell_id": spec["cell_id"],
        "grammar_regime": spec["grammar_regime"],
        "semantic_variant_index": spec["semantic_variant_index"],
        "intended_cefr": "B2",
        "canonical_target_sentence": canonical,
        "semantic_frame": {
            "situation_summary": "Ask about Mia swimming at a pool.",
            "communicative_goal": "Ask about ability.",
            "participants": ["Mia"],
            "time_anchor": "now",
            "main_verb_lemma": "swim",
            "object_head": None,
        },
        "items": items,
    }


def test_preregistered_selection_expands_to_exact_full_rank_design() -> None:
    config, selected = bank.load_inputs()
    families = bank.family_specs(config, selected)
    assert len(families) == 38
    assert sum(row["grammar_regime"] == "seen" for row in families) == 36
    assert len({row["family_id"] for row in families}) == 38
    assert bank._exact_rank([row["q_row"] for row in selected["seen_cells"]]) == 18
    assert all(row["family_id"].startswith("mb0_8f8fa56e7109_") for row in families)


def test_provider_schema_constants_and_enums_have_explicit_types() -> None:
    """Guard the structured-output subset used by the live Codex provider."""

    def walk(value):
        if isinstance(value, dict):
            if "const" in value or "enum" in value:
                assert "type" in value
            for child in value.values():
                walk(child)
        elif isinstance(value, list):
            for child in value:
                walk(child)

    for name in (
        "generated_family.schema.json",
        "solver_response.schema.json",
        "critic_response.schema.json",
    ):
        walk(bank._schema(bank.MODULE / "schemas" / name))

    dynamic = bank._dynamic_schema(
        bank._schema(bank.MODULE / "schemas/generated_family.schema.json"),
        {"family_id": "family", "candidate_round": 1},
    )
    assert dynamic["properties"]["family_id"] == {
        "type": "string",
        "const": "family",
    }
    assert dynamic["properties"]["candidate_round"] == {
        "type": "integer",
        "const": 1,
    }


def test_plan_freezes_every_input_and_all_three_candidate_rounds(tmp_path: Path) -> None:
    run_root = tmp_path / "unit_plan"
    plan = bank.create_plan(run_root, bank.DEFAULT_CONFIG, bank.DEFAULT_SELECTED)
    requests = bank.read_jsonl(run_root / "plans/generation_requests.jsonl")
    assert plan["status"] == "PREREGISTERED_BEFORE_MATCHED_BANK_MODEL_CALLS"
    assert len(requests) == 114
    assert {row["candidate_round"] for row in requests} == {1, 2, 3}
    assert len({row["request_id"] for row in requests}) == 114
    assert len(list((run_root / "frozen/schemas").glob("*.json"))) >= 6
    assert len(list((run_root / "frozen/prompts").glob("*.txt"))) == 5
    bank.validate_run(run_root)


def test_deterministic_family_checks_reconstruction_and_answer_space() -> None:
    config, selected = bank.load_inputs()
    spec = bank.family_specs(config, selected)[0]
    family = valid_family(spec, config)
    schema = bank._schema(bank.MODULE / "schemas/generated_family.schema.json")
    bank.validate_schema(family, schema, "fixture")
    result = bank.deterministic_family_checks(family, spec, 1, config)
    assert result["passed"], result

    labelled_dialogue = json.loads(json.dumps(family))
    labelled_dialogue["items"][1]["format_payload"][
        "incomplete_turn_template"
    ] = "Mia: [[RESPONSE]]"
    result = bank.deterministic_family_checks(labelled_dialogue, spec, 1, config)
    assert result["passed"], result

    broken = json.loads(json.dumps(family))
    broken["items"][0]["scoring"]["accepted_responses"].append("Can Mia swim")
    result = bank.deterministic_family_checks(broken, spec, 1, config)
    assert not result["passed"]
    assert "constrained_cloze:accepted_responses_not_unique" in result["failed_checks"]


def test_solver_plan_is_oracle_blind_and_never_batches_matched_formats(tmp_path: Path) -> None:
    run_root = tmp_path / "solver_plan"
    bank.create_plan(run_root, bank.DEFAULT_CONFIG, bank.DEFAULT_SELECTED)
    config, selected = bank.load_inputs()
    for spec in bank.family_specs(config, selected):
        family = valid_family(spec, config)
        bank.write_frozen_json(
            run_root / "parsed/generation" / f"{family['candidate_id']}.json",
            family,
            "fixture family",
        )
        check = bank.deterministic_family_checks(family, spec, 1, config)
        bank.write_frozen_json(
            run_root / "provenance/deterministic_checks" / f"{family['candidate_id']}.json",
            check,
            "fixture check",
        )
    requests = bank.build_solver_requests(run_root, 1)
    assert len(requests) == 24
    assert sum(len(row["input"]["learner_views"]) for row in requests) == 304
    for request in requests:
        views = request["input"]["learner_views"]
        assert len(set(request["family_ids"])) == len(views)
        encoded = bank.canonical_json(request["input"])
        assert "family_id" not in encoded
        assert "q_row" not in encoded
        assert "generator_kc" not in encoded
        assert "canonical_target_sentence" not in encoded
        assert "scoring" not in encoded


def test_variant_diversity_is_a_transparent_hard_gate() -> None:
    config, selected = bank.load_inputs()
    specs = bank.family_specs(config, selected)
    first = valid_family(specs[0], config)
    second = valid_family(specs[1], config)
    failures = bank.variant_diversity_gate(second, first, config)
    assert "semantic_variant:distinct_main_verb_lemma" in failures
    assert "semantic_variant:context_token_jaccard" in failures


def test_all_pass_fixture_freezes_and_replays_exact_152_item_projection(tmp_path: Path) -> None:
    run_root = tmp_path / "freeze_fixture"
    bank.create_plan(run_root, bank.DEFAULT_CONFIG, bank.DEFAULT_SELECTED)
    config, selected = bank.load_inputs()
    for spec in bank.family_specs(config, selected):
        family = valid_family(spec, config)
        if spec["semantic_variant_index"] == 2:
            family["semantic_frame"]["main_verb_lemma"] = "dive"
            family["semantic_frame"]["situation_summary"] = (
                "Check a diving ability during beach practice."
            )
        bank.write_frozen_json(
            run_root / "parsed/generation" / f"{family['candidate_id']}.json",
            family,
            "fixture family",
        )
        bank.write_frozen_json(
            run_root / "provenance/deterministic_checks" / f"{family['candidate_id']}.json",
            bank.deterministic_family_checks(family, spec, 1, config),
            "fixture checks",
        )
        for item in family["items"]:
            for replicate in (1, 2):
                submitted = item["scoring"]["target_response"]
                solver = {
                    "solver_attempt_id": f"{item['candidate_item_id']}_solver_r{replicate}",
                    "item_id": item["candidate_item_id"],
                    "instruction_understanding": "Complete the visible item.",
                    "task_understood": True,
                    "response_mechanism_clear": True,
                    "submitted_response": submitted,
                    "multiple_material_responses_reasonable": False,
                    "major_ambiguity": False,
                    "other_reasonable_responses": [],
                    "vocabulary_or_context_blocked": False,
                    "ambiguity_explanation": "None.",
                    "batch_id": f"fixture_{replicate}",
                    "replicate": replicate,
                    "keyed_match": True,
                    "reasonable_unkeyed_responses": [],
                }
                bank.write_frozen_json(
                    run_root / "parsed/solver" / f"{solver['solver_attempt_id']}.json",
                    solver,
                    "fixture solver",
                )
        for role in bank.ROLES:
            contract = config["independent_validation"]["roles"][role]

            def criterion(name: str) -> dict:
                return {
                    "criterion": name,
                    "severity": "pass",
                    "evidence": "Fixture pass used only to exercise deterministic orchestration.",
                    "blocking": False,
                }

            judgment = {
                "role": role,
                "batch_id": f"fixture_{role}",
                "family_id": family["family_id"],
                "candidate_id": family["candidate_id"],
                "item_judgments": [
                    {
                        "item_id": item["candidate_item_id"],
                        "criteria": [
                            criterion(name) for name in contract["exact_item_criteria"]
                        ],
                    }
                    for item in family["items"]
                ],
                "family_judgments": [
                    criterion(name) for name in contract["exact_family_criteria"]
                ],
                "overall_accept": True,
                "summary": "Fixture pass.",
            }
            bank.write_frozen_json(
                run_root
                / "parsed/validation"
                / role
                / f"{family['candidate_id']}.json",
                judgment,
                "fixture critic",
            )
    curation = bank.curate_round(run_root, 1)
    assert curation["accepted_total"] == 38
    manifest = bank.freeze_bank(run_root)
    assert manifest["counts"]["items"] == 152
    replay = bank.verify_bank(run_root)
    assert replay == {
        "verified": True,
        "run_id": "freeze_fixture",
        "families": 38,
        "items": 152,
        "seen_q_rank": 18,
        "manifest_sha256": bank.sha256_file(run_root / "bank/manifest.json"),
        "v1_manifest_sha256": bank.read_json(run_root / "plan.json")["inputs"]["v1_manifest"]["sha256"],
    }
