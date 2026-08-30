from __future__ import annotations

import importlib.util
import json
import shutil
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/experiments/measurement_realism_dialogue_live.py"
STATIC = ROOT / "experiments/measurement_realism/dialogue_pilot_live_v1"
SOURCE_PILOT = ROOT / "experiments/measurement_realism/dialogue_pilot"
SPEC = importlib.util.spec_from_file_location("measurement_realism_dialogue_live", SCRIPT)
assert SPEC and SPEC.loader
dialogue_live = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(dialogue_live)


def copy_static_protocol(tmp_path: Path) -> Path:
    output = tmp_path / "dialogue_pilot_live_v1"
    shutil.copytree(STATIC, output)
    for generated in (
        "study_plan.json",
        "generation_call_plan.jsonl",
        "generated_families.jsonl",
        "generation_manifest.json",
        "critic_call_plan.jsonl",
        "critic_envelopes.jsonl",
        "critic_judgments.jsonl",
        "critique_manifest.json",
        "analysis.json",
        "analysis_manifest.json",
        "report.md",
        "call_evidence_bundle.jsonl",
        "package_manifest.json",
        "verification.json",
    ):
        path = output / generated
        if path.exists():
            path.unlink()
    return output


def generated_family(call_input: dict) -> dict:
    family_id = call_input["family_id"]
    target = f"Canonical target for {family_id}."
    opportunities = []
    for slot in call_input["formats"]:
        format_id = slot["format"]
        open_dialogue = format_id == "open_dialogue"
        opportunities.append(
            {
                "opportunity_id": slot["opportunity_id"],
                "format": format_id,
                "viability": "candidate",
                "instruction": "Write one suitable response.",
                "context": "Two people are discussing a familiar event.",
                "stimulus": "Use the supplied information.",
                "dialogue_history": (
                    [{"speaker": "A", "text": "What happened?"}]
                    if format_id in {"dialogue_completion", "open_dialogue"}
                    else []
                ),
                "response_mechanism": {
                    "type": dialogue_live.RESPONSE_TYPES[format_id],
                    "visible_component": "One text response field",
                    "options": [],
                },
                "canonical_target_example": target,
                "scoring_interpretation": {
                    "kind": "interpretive_rubric" if open_dialogue else "bounded_variants",
                    "accepted_responses": [] if open_dialogue else [target],
                    "normalization": "Trim outer whitespace and terminal punctuation.",
                    "rubric": "Evidence must instantiate the declared target in context.",
                },
                "feedback_target": "Give feedback on the declared grammatical operation.",
                "opportunity_boundary": "The learner's single submitted response.",
                "anticipated_incidental_grammar": [],
                "viability_note": "Candidate pending independent automated and human review.",
            }
        )
    return {
        "schema_version": "dialogue_continuum_family_v1",
        "family_id": family_id,
        "cell_id": call_input["cell_id"],
        "pilot_stratum": call_input["pilot_stratum"],
        "grammar_cell": call_input["grammar_cell"],
        "active_generator_kc_ids": call_input["active_generator_kc_ids"],
        "q_row": list(call_input["q_row"]),
        "shared_semantic_specification": {
            "scenario": "A familiar everyday event.",
            "entities_and_referents": ["speaker A", "speaker B"],
            "lexical_head": "work",
            "target_proposition": "One event has the declared temporal relation.",
            "intended_response_function": "Produce one contextually relevant target clause.",
            "canonical_target_example": target,
            "non_target_vocabulary_policy": "Use only common concrete words.",
        },
        "opportunities": opportunities,
        "generation_notes": ["Synthetic test fixture, not scientific evidence."],
    }


def critic_envelope(call_input: dict) -> dict:
    role = call_input["critic_role"]
    family_id = call_input["family_id"]
    critic_id = call_input["critic_id"]
    judgments = []
    for opportunity in call_input["family_view"]["opportunities"]:
        open_dialogue = opportunity["format"] == "open_dialogue"
        judgments.append(
            {
                "judgment_schema": "dialogue_continuum_critic_v1",
                "critic_id": critic_id,
                "critic_role": role,
                "family_id": family_id,
                "opportunity_id": opportunity["opportunity_id"],
                "format": opportunity["format"],
                "ratings": {
                    "task_comprehensibility": "pass",
                    "context_naturalness": "pass",
                    "interaction_naturalness": "pass" if open_dialogue else "minor_concern",
                    "platform_plausibility": "pass",
                    "answer_determinacy": "bounded_multiple" if open_dialogue else "determinate",
                    "accepted_response_coverage": "not_applicable" if role == "learner" else ("minor_gap" if open_dialogue else "complete"),
                    "lexical_nuisance": "low",
                    "kc_attribution": "not_applicable" if role == "learner" else ("partial" if open_dialogue else "clear"),
                },
                "plausible_response_lower_bound": 2 if open_dialogue else 1,
                "incidental_grammar_operations": ["discourse_pragmatics"] if open_dialogue else [],
                "target_avoiding_shortcut": None if role == "learner" else False,
                "primary_concern": "Open response breadth needs human validation." if open_dialogue else "No material automated concern.",
            }
        )
    return {"critic_role": role, "family_id": family_id, "judgments": judgments}


def fake_audited_call(
    prompt: str,
    *,
    model: str,
    reasoning_effort: str,
    input_data: dict,
    stage: str,
    call_key: str,
    evidence_dir: Path,
    output_schema: dict,
) -> dict:
    evidence_dir.mkdir(parents=True, exist_ok=False)
    if stage == "dialogue_continuum_generation":
        result = generated_family(input_data["exact_model_input"])
    else:
        result = critic_envelope(input_data)
    files = {
        "input.json": json.dumps(input_data, ensure_ascii=False, indent=2) + "\n",
        "rendered_prompt.txt": prompt,
        "model_settings.json": json.dumps(
            {
                "model": model,
                "reasoning_effort": reasoning_effort,
                "stage": stage,
                "call_key": call_key,
                "command": ["fixture"],
                "output_schema_supplied": True,
            },
            indent=2,
        )
        + "\n",
        "output_schema.json": json.dumps(output_schema, ensure_ascii=False, indent=2) + "\n",
        "raw_output.txt": json.dumps(result, ensure_ascii=False) + "\n",
        "cli_stderr.txt": "fixture; no live model call\n",
        "call_metadata.json": json.dumps(
            {
                "returncode": 0,
                "runtime_seconds": 0.01,
                "tokens_used": 0,
                "token_metric": "fixture",
            },
            indent=2,
        )
        + "\n",
        "parsed_result.json": json.dumps(result, ensure_ascii=False, indent=2) + "\n",
    }
    for name, content in files.items():
        (evidence_dir / name).write_text(content, encoding="utf-8")
    return result


def test_plan_is_zero_call_and_preserves_source(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    output = copy_static_protocol(tmp_path)
    source_hashes = {
        path.relative_to(SOURCE_PILOT): dialogue_live.file_sha256(path)
        for path in SOURCE_PILOT.rglob("*")
        if path.is_file()
    }
    invoked = False

    def must_not_call(*args, **kwargs):
        nonlocal invoked
        invoked = True
        raise AssertionError("plan made a live call")

    monkeypatch.setattr(dialogue_live, "audited_model_call", must_not_call)
    result = dialogue_live.plan(output / "config.yaml", output)
    assert invoked is False
    assert result["scale"] == {
        "families": 4,
        "formats": 5,
        "opportunities": 20,
        "generation_calls": 4,
        "critic_calls": 20,
        "critic_judgments": 100,
    }
    assert result["authorization"]["live_calls_authorized_by_plan"] is False
    calls = dialogue_live.read_jsonl(output / "generation_call_plan.jsonl")
    assert len(calls) == 4
    assert all(call["model"] == "gpt-5.6-sol" for call in calls)
    assert all(call["reasoning_effort"] == "medium" for call in calls)
    assert all("learner outcomes" in call["input"]["generator_must_not_use"] for call in calls)
    assert source_hashes == {
        path.relative_to(SOURCE_PILOT): dialogue_live.file_sha256(path)
        for path in SOURCE_PILOT.rglob("*")
        if path.is_file()
    }
    with pytest.raises(PermissionError, match="root approval"):
        dialogue_live.generate(
            output / "config.yaml", output, tmp_path / "evidence", 1, False
        )


def test_complete_pipeline_retains_24_calls_and_no_scalar(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    output = copy_static_protocol(tmp_path)
    evidence = tmp_path / "evidence"
    monkeypatch.setattr(dialogue_live, "audited_model_call", fake_audited_call)
    dialogue_live.plan(output / "config.yaml", output)
    generation = dialogue_live.generate(
        output / "config.yaml", output, evidence, 4, True
    )
    assert generation["calls"] == 4
    assert generation["opportunities"] == 20
    critique = dialogue_live.critic(
        output / "config.yaml", output, evidence, 4, True
    )
    assert critique["calls"] == 20
    assert critique["judgments"] == 100
    critic_calls = dialogue_live.read_jsonl(output / "critic_call_plan.jsonl")
    assert len(critic_calls) == 20
    assert all(call["model"] == "gpt-5.6-terra" for call in critic_calls)
    assert len({call["call_key"] for call in critic_calls}) == 20
    learner_calls = [call for call in critic_calls if call["critic_role"] == "learner"]
    assert all("grammar_cell" not in call["input"]["family_view"] for call in learner_calls)
    assert all(
        "scoring_interpretation" not in opportunity
        for call in learner_calls
        for opportunity in call["input"]["family_view"]["opportunities"]
    )
    analysis_manifest = dialogue_live.analyse(output / "config.yaml", output)
    assert analysis_manifest["scale"]["judgments"] == 100
    assert analysis_manifest["scalar_realism_score_computed"] is False
    package = dialogue_live.package(output / "config.yaml", output, evidence)
    assert package["calls"] == 24
    verification = dialogue_live.verify(output / "config.yaml", output)
    assert verification["status"] == "VERIFIED_COMPLETE_AUTOMATED_DIALOGUE_PILOT"
    assert verification["byte_exact_call_evidence_rows"] == 24
    assert verification["scalar_realism_score_computed"] is False
    assert verification["dataset_release_justified_by_this_pilot_alone"] is False
    assert len(dialogue_live.read_jsonl(output / "call_evidence_bundle.jsonl")) == 24
    report = (output / "report.md").read_text(encoding="utf-8")
    assert "not human learner" in report
    assert "No scalar realism score" in report


def test_strict_local_validation_rejects_identity_drift(tmp_path: Path) -> None:
    output = copy_static_protocol(tmp_path)
    dialogue_live.plan(output / "config.yaml", output)
    call = dialogue_live.read_jsonl(output / "generation_call_plan.jsonl")[0]
    family = generated_family(call["input"])
    family["q_row"][0] = 1 - family["q_row"][0]
    local_schema = dialogue_live.read_json(
        SOURCE_PILOT / "schemas/generated_family.schema.json"
    )
    with pytest.raises(ValueError, match="frozen q_row"):
        dialogue_live.validate_generated_family(family, call, local_schema)


def test_provider_preflight_rejects_known_unsupported_keywords() -> None:
    bad = {
        "type": "object",
        "properties": {"x": {"type": "object", "minProperties": 1}},
        "required": ["x"],
        "additionalProperties": False,
    }
    with pytest.raises(ValueError, match="unsupported keys"):
        dialogue_live.assert_provider_compatible(bad)
