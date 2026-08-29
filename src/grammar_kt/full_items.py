"""Resumable, outcome-free item construction for the full baseline dataset.

The functions in this module deliberately operate on only a canonical cell,
the declared item-generation/validation resources, and model-call settings.
They never receive source descriptors, generator KCs, learner records, folds,
or downstream evaluation results.

Raw model evidence remains the responsibility of the injected ``model_call``.
This module validates and reconstructs the small public rows that can safely be
checkpointed and, later, packaged with the frozen dataset.
"""

from __future__ import annotations

import hashlib
import json
import re
from copy import deepcopy
from pathlib import Path
from typing import Any, Iterable

from .io import ModelCall, render
from .validate_items import answer_span_consistency


ACTIVE_CANDIDATES_PER_CELL = 3
UNCHANGED_RESCUE_CANDIDATES_PER_CELL = 2
DETERMINACY_INTERVENTION_CANDIDATES_PER_CELL = 2
UNCHANGED_RESCUE_ID = "unchanged_prompt_zero_coverage_rescue_v1"
DETERMINACY_INTERVENTION_ID = "explicit_construction_determinacy_intervention_v1"
PACKAGING_CORRECTION_ID = "full_v1_validator_named_answer_packaging_correction_v1"
_CANDIDATE_PAYLOAD_FIELDS = {"prompt", "target_answer", "accepted_answers"}
_VISIBLE_ITEM_FIELDS = (
    "item_id",
    "format",
    "prompt",
    "target_answer",
    "accepted_answers",
)
_RESPONSE_SLOT = re.compile(
    r"_{2,}|\[\s*blank\s*\]|<\s*blank\s*>", re.IGNORECASE
)
_SAFE_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]*\Z")
_SUFFIX_BOUNDARY = re.compile(r"[.!?;\n\r]|(?=[([{<])")
_LEXICAL_TOKEN = re.compile(r"[^\W_]+(?:['’][^\W_]+)*", re.UNICODE)
_TERMINAL_SENTENCE_PUNCTUATION = re.compile(
    r"\s*[.!?…]+[\"'’”\)\]]*\s*\Z"
)


def _sha256(value: Any) -> str:
    payload = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _generation_fingerprint(generation_call: dict[str, Any]) -> str:
    return _sha256(
        {
            "stage": "full_v1.item_generation",
            "candidate_id": generation_call["candidate_id"],
            "model": generation_call["model"],
            "reasoning_effort": generation_call["reasoning_effort"],
            "model_input": generation_call["model_input"],
            "rendered_prompt": generation_call["rendered_prompt"],
        }
    )


def _campaign_generation_fingerprint(generation_call: dict[str, Any]) -> str:
    """Fingerprint one separately declared post-N=3 campaign input."""

    return _sha256(
        {
            "stage": "full_v1.item_campaign_generation",
            "campaign_id": generation_call["campaign_id"],
            "campaign_declaration": generation_call["campaign_declaration"],
            "candidate_id": generation_call["candidate_id"],
            "model": generation_call["model"],
            "reasoning_effort": generation_call["reasoning_effort"],
            "model_input": generation_call["model_input"],
            "rendered_prompt": generation_call["rendered_prompt"],
        }
    )


def _validation_fingerprint(validation_call: dict[str, Any]) -> str:
    return _sha256(
        {
            "stage": "full_v1.item_validation",
            "candidate_id": validation_call["candidate_id"],
            "policy_id": validation_call["policy_id"],
            "acceptance_rule": validation_call["acceptance_rule"],
            "model": validation_call["model"],
            "reasoning_effort": validation_call["reasoning_effort"],
            "deterministic_checks": validation_call["deterministic_checks"],
            "model_input": validation_call["model_input"],
            "rendered_prompt": validation_call["rendered_prompt"],
        }
    )


def _assert_fingerprint(call: dict[str, Any], expected: str, stage: str) -> None:
    actual = call.get("input_sha256")
    if actual != expected:
        raise ValueError(f"{stage} call input drift")


def _nonempty_string(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value or value != value.strip():
        raise ValueError(f"{name} must be a non-empty, trimmed string")
    return value


def _nonblank_text(value: Any, name: str) -> str:
    """Validate declared text resources without normalising their bytes."""

    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be non-blank text")
    return value


def _cell_identity(cell: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    if not isinstance(cell, dict):
        raise ValueError("GrammarCell must be an object")
    cell_id = _nonempty_string(cell.get("cell_id"), "cell_id")
    if not _SAFE_ID.fullmatch(cell_id):
        raise ValueError("cell_id contains characters unsafe for a stable candidate ID")
    features = cell.get("features")
    if not isinstance(features, dict) or not features:
        raise ValueError("GrammarCell features must be a non-empty object")
    for name, value in features.items():
        _nonempty_string(name, "GrammarCell feature name")
        _nonempty_string(value, f"GrammarCell feature {name}")
    return cell_id, deepcopy(features)


def stable_candidate_id(cell_id: str, candidate_index: int) -> str:
    """Return the active stable ID for one of the fixed three candidates."""

    _nonempty_string(cell_id, "cell_id")
    if not _SAFE_ID.fullmatch(cell_id):
        raise ValueError("cell_id contains characters unsafe for a stable candidate ID")
    if isinstance(candidate_index, bool) or not isinstance(candidate_index, int):
        raise ValueError("candidate_index must be an integer")
    if not 1 <= candidate_index <= ACTIVE_CANDIDATES_PER_CELL:
        raise ValueError(
            "candidate_index must be between 1 and "
            f"{ACTIVE_CANDIDATES_PER_CELL}"
        )
    return f"candidate_{cell_id}_{candidate_index:02d}"


def _campaign_spec(campaign_id: str) -> dict[str, Any]:
    specs = {
        UNCHANGED_RESCUE_ID: {
            "prefix": "unchanged_rescue",
            "count": UNCHANGED_RESCUE_CANDIDATES_PER_CELL,
            "selection_offset": ACTIVE_CANDIDATES_PER_CELL,
            "trigger": "zero_validator_accepted_after_baseline_n3",
            "cohort": "all_zero_accepted_cells_after_baseline_n3",
            "generation_prompt": "baseline_unchanged",
        },
        DETERMINACY_INTERVENTION_ID: {
            "prefix": "determinacy_intervention",
            "count": DETERMINACY_INTERVENTION_CANDIDATES_PER_CELL,
            "selection_offset": (
                ACTIVE_CANDIDATES_PER_CELL
                + UNCHANGED_RESCUE_CANDIDATES_PER_CELL
            ),
            "trigger": "residual_zero_coverage_with_determinacy_dominant",
            "cohort": "all_eligible_residual_zero_coverage_cells",
            "generation_prompt": "explicit_construction",
        },
    }
    if campaign_id not in specs:
        raise ValueError(f"unknown item campaign: {campaign_id}")
    return specs[campaign_id]


def stable_campaign_candidate_id(
    cell_id: str, campaign_index: int, campaign_id: str
) -> str:
    """Return a stable ID disjoint across baseline and both rescue campaigns."""

    _nonempty_string(cell_id, "cell_id")
    if not _SAFE_ID.fullmatch(cell_id):
        raise ValueError("cell_id contains characters unsafe for a stable candidate ID")
    spec = _campaign_spec(campaign_id)
    if isinstance(campaign_index, bool) or not isinstance(campaign_index, int):
        raise ValueError("campaign_index must be an integer")
    if not 1 <= campaign_index <= spec["count"]:
        raise ValueError(
            "campaign_index must be between 1 and " f"{spec['count']}"
        )
    return f"{spec['prefix']}_{cell_id}_{campaign_index:02d}"


def stable_unchanged_rescue_candidate_id(
    cell_id: str, campaign_index: int
) -> str:
    return stable_campaign_candidate_id(
        cell_id, campaign_index, UNCHANGED_RESCUE_ID
    )


def stable_determinacy_intervention_candidate_id(
    cell_id: str, campaign_index: int
) -> str:
    return stable_campaign_candidate_id(
        cell_id, campaign_index, DETERMINACY_INTERVENTION_ID
    )


def stable_packaging_correction_item_id(source_item_id: str) -> str:
    _nonempty_string(source_item_id, "source_item_id")
    if not _SAFE_ID.fullmatch(source_item_id):
        raise ValueError("source_item_id contains characters unsafe for a stable ID")
    return f"packaging_correction_{source_item_id}"


def _neutral_validation_item_id(candidate_id: str) -> str:
    """Hide generation order from an otherwise independent validator."""

    return "validation_item_" + hashlib.sha256(
        candidate_id.encode("utf-8")
    ).hexdigest()[:16]


def _validate_generation_declarations(
    design: dict[str, Any], item_format: dict[str, Any]
) -> tuple[dict[str, Any], str]:
    if not isinstance(design, dict) or not isinstance(design.get("generation"), dict):
        raise ValueError("generation design must contain a generation object")
    generation = design["generation"]
    count = generation.get("candidates_per_cell")
    if isinstance(count, bool) or count != ACTIVE_CANDIDATES_PER_CELL:
        raise ValueError("full baseline generation is frozen to N=3")
    if generation.get("candidate_calls") != "independent":
        raise ValueError("full baseline candidates must use independent calls")
    design_id = _nonempty_string(design.get("design_id"), "design_id")

    if not isinstance(item_format, dict):
        raise ValueError("item format must be an object")
    format_id = _nonempty_string(item_format.get("format_id"), "format_id")
    required_fields = item_format.get("required_fields")
    if (
        not isinstance(required_fields, list)
        or len(required_fields) != len(_CANDIDATE_PAYLOAD_FIELDS)
        or set(required_fields) != _CANDIDATE_PAYLOAD_FIELDS
    ):
        raise ValueError(
            "active item format must require exactly prompt, target_answer, "
            "and accepted_answers"
        )
    if design.get("format") != format_id:
        raise ValueError("generation design and item format IDs disagree")
    return {"design_id": design_id, **deepcopy(generation)}, format_id


def build_generation_call(
    cell: dict[str, Any],
    prompt: str,
    rulebook: str,
    design: dict[str, Any],
    item_format: dict[str, Any],
    *,
    candidate_index: int,
    model: str,
    reasoning_effort: str,
) -> dict[str, Any]:
    """Build one complete generation call without invoking a model.

    The fingerprint covers all scientific input, the rendered prompt, and the
    declared backend settings. Reusing a checkpoint after any of these change
    is therefore rejected as input drift.
    """

    cell_id, features = _cell_identity(cell)
    active_design, _ = _validate_generation_declarations(design, item_format)
    candidate_id = stable_candidate_id(cell_id, candidate_index)
    prompt = _nonblank_text(prompt, "generation prompt")
    rulebook = _nonblank_text(rulebook, "generation rulebook")
    model = _nonempty_string(model, "generation model")
    reasoning_effort = _nonempty_string(
        reasoning_effort, "generation reasoning_effort"
    )
    model_input = {
        "target_cell": {"cell_id": cell_id, "features": features},
        "candidate_position": {
            "index": candidate_index,
            "count": ACTIVE_CANDIDATES_PER_CELL,
        },
        "item_format": deepcopy(item_format),
        "design": active_design,
    }
    rendered_prompt = render(prompt, {**model_input, "rulebook": rulebook})
    generation_call = {
        "candidate_id": candidate_id,
        "cell_id": cell_id,
        "candidate_index": candidate_index,
        "model": model,
        "reasoning_effort": reasoning_effort,
        "model_input": model_input,
        "rendered_prompt": rendered_prompt,
    }
    generation_call["input_sha256"] = _generation_fingerprint(generation_call)
    return generation_call


def _validate_campaign_declaration(
    declaration: dict[str, Any], item_format: dict[str, Any]
) -> tuple[dict[str, Any], str]:
    if not isinstance(declaration, dict):
        raise ValueError("item-campaign declaration must be an object")
    campaign_id = declaration.get("campaign_id")
    spec = _campaign_spec(campaign_id)
    if declaration.get("trigger") != spec["trigger"]:
        raise ValueError("unexpected item-campaign trigger")
    if declaration.get("cohort") != spec["cohort"]:
        raise ValueError("unexpected item-campaign cohort")
    if declaration.get("generation_prompt") != spec["generation_prompt"]:
        raise ValueError("unexpected item-campaign generation prompt policy")
    generation = declaration.get("generation")
    if not isinstance(generation, dict):
        raise ValueError("item-campaign declaration must contain generation settings")
    if generation.get("candidates_per_cell") != spec["count"]:
        raise ValueError("full-v1 post-N=3 campaigns are frozen to two candidates")
    if generation.get("candidate_calls") != "independent":
        raise ValueError("item-campaign candidates must use independent calls")
    expected_prompt_change = campaign_id == DETERMINACY_INTERVENTION_ID
    if generation.get("only_generation_prompt_changes") is not expected_prompt_change:
        raise ValueError("item-campaign prompt-change declaration is inconsistent")
    validation = declaration.get("validation")
    if not isinstance(validation, dict) or validation != {
        "reuse_baseline_prompt": True,
        "reuse_baseline_criteria": True,
        "independent_and_blinded": True,
    }:
        raise ValueError("item campaigns must reuse unchanged independent validation")

    if not isinstance(item_format, dict):
        raise ValueError("item format must be an object")
    format_id = _nonempty_string(item_format.get("format_id"), "format_id")
    required_fields = item_format.get("required_fields")
    if (
        not isinstance(required_fields, list)
        or len(required_fields) != len(_CANDIDATE_PAYLOAD_FIELDS)
        or set(required_fields) != _CANDIDATE_PAYLOAD_FIELDS
    ):
        raise ValueError(
            "active item format must require exactly prompt, target_answer, "
            "and accepted_answers"
        )
    if declaration.get("format") != format_id:
        raise ValueError("item-campaign declaration and item format IDs disagree")
    return deepcopy(declaration), format_id


def build_campaign_generation_call(
    cell: dict[str, Any],
    prompt: str,
    rulebook: str,
    design: dict[str, Any],
    declaration: dict[str, Any],
    item_format: dict[str, Any],
    *,
    campaign_index: int,
    model: str,
    reasoning_effort: str,
) -> dict[str, Any]:
    """Build one frozen post-N=3 campaign call without invoking a model.

    Positions are local to their frozen campaign.  Their
    public IDs and fingerprints are disjoint from the original N=3 evidence.
    Selection indices preserve baseline, unchanged-rescue, intervention order.
    """

    cell_id, features = _cell_identity(cell)
    active_design, _ = _validate_generation_declarations(design, item_format)
    active_declaration, _ = _validate_campaign_declaration(
        declaration, item_format
    )
    campaign_id = active_declaration["campaign_id"]
    spec = _campaign_spec(campaign_id)
    candidate_id = stable_campaign_candidate_id(
        cell_id, campaign_index, campaign_id
    )
    prompt = _nonblank_text(prompt, "item-campaign generation prompt")
    rulebook = _nonblank_text(rulebook, "generation rulebook")
    model = _nonempty_string(model, "generation model")
    reasoning_effort = _nonempty_string(
        reasoning_effort, "generation reasoning_effort"
    )
    model_input = {
        "target_cell": {"cell_id": cell_id, "features": features},
        "candidate_position": {
            "index": campaign_index,
            "count": spec["count"],
        },
        "item_format": deepcopy(item_format),
        # Keep the original generation design in model-visible input.  The
        # campaign declaration is fingerprinted/provenance-only and therefore
        # cannot itself change model behaviour.
        "design": active_design,
    }
    rendered_prompt = render(prompt, {**model_input, "rulebook": rulebook})
    generation_call = {
        "candidate_id": candidate_id,
        "cell_id": cell_id,
        "campaign_index": campaign_index,
        "campaign_id": campaign_id,
        "campaign_declaration": active_declaration,
        "model": model,
        "reasoning_effort": reasoning_effort,
        "model_input": model_input,
        "rendered_prompt": rendered_prompt,
    }
    generation_call["input_sha256"] = _campaign_generation_fingerprint(
        generation_call
    )
    return generation_call


def _validate_candidate_payload(parsed: Any) -> None:
    if not isinstance(parsed, dict) or set(parsed) != _CANDIDATE_PAYLOAD_FIELDS:
        raise ValueError(
            "generator output must be one object containing exactly prompt, "
            "target_answer, and accepted_answers"
        )
    _nonempty_string(parsed["prompt"], "generator prompt")
    _nonempty_string(parsed["target_answer"], "generator target_answer")
    answers = parsed["accepted_answers"]
    if not isinstance(answers, list) or not answers:
        raise ValueError("accepted_answers must be a non-empty list")
    for index, answer in enumerate(answers):
        _nonempty_string(answer, f"accepted_answers[{index}]")
    if len(answers) != len(set(answers)):
        raise ValueError("accepted_answers must not contain duplicates")


def recover_generated_candidate(
    parsed: Any, generation_call: dict[str, Any]
) -> dict[str, Any]:
    """Strictly reconstruct one canonical candidate from parsed model JSON."""

    _validate_candidate_payload(parsed)
    candidate_id = stable_candidate_id(
        generation_call["cell_id"], generation_call["candidate_index"]
    )
    if generation_call.get("candidate_id") != candidate_id:
        raise ValueError("generation call candidate ID drift")
    _assert_fingerprint(
        generation_call,
        _generation_fingerprint(generation_call),
        "generation",
    )
    input_sha256 = generation_call["input_sha256"]
    format_id = generation_call["model_input"]["item_format"]["format_id"]
    return {
        "item_id": candidate_id,
        "cell_id": generation_call["cell_id"],
        "format": format_id,
        "prompt": parsed["prompt"],
        "target_answer": parsed["target_answer"],
        "accepted_answers": deepcopy(parsed["accepted_answers"]),
        "generation_metadata": {
            "candidate_index": generation_call["candidate_index"],
            "candidate_count": ACTIVE_CANDIDATES_PER_CELL,
            "model": generation_call["model"],
            "reasoning_effort": generation_call["reasoning_effort"],
            "input_sha256": input_sha256,
        },
    }


def recover_campaign_candidate(
    parsed: Any, generation_call: dict[str, Any]
) -> dict[str, Any]:
    """Strictly reconstruct one candidate from a frozen post-N=3 campaign."""

    _validate_candidate_payload(parsed)
    campaign_id = generation_call.get("campaign_id")
    spec = _campaign_spec(campaign_id)
    campaign_index = generation_call.get("campaign_index")
    candidate_id = stable_campaign_candidate_id(
        generation_call["cell_id"], campaign_index, campaign_id
    )
    if generation_call.get("candidate_id") != candidate_id:
        raise ValueError("item-campaign generation call candidate ID drift")
    _assert_fingerprint(
        generation_call,
        _campaign_generation_fingerprint(generation_call),
        "item-campaign generation",
    )
    format_id = generation_call["model_input"]["item_format"]["format_id"]
    return {
        "item_id": candidate_id,
        "cell_id": generation_call["cell_id"],
        "format": format_id,
        "prompt": parsed["prompt"],
        "target_answer": parsed["target_answer"],
        "accepted_answers": deepcopy(parsed["accepted_answers"]),
        "generation_metadata": {
            "candidate_index": spec["selection_offset"] + campaign_index,
            "candidate_count": (
                ACTIVE_CANDIDATES_PER_CELL
                + UNCHANGED_RESCUE_CANDIDATES_PER_CELL
                + DETERMINACY_INTERVENTION_CANDIDATES_PER_CELL
            ),
            "campaign": campaign_id,
            "campaign_candidate_index": campaign_index,
            "model": generation_call["model"],
            "reasoning_effort": generation_call["reasoning_effort"],
            "input_sha256": generation_call["input_sha256"],
        },
    }


def construct_packaging_corrected_candidate(
    source_candidate: dict[str, Any],
    correction: dict[str, Any],
    *,
    config_sha256: str,
) -> dict[str, Any]:
    """Copy one frozen candidate and append only declared accepted answers."""

    if not isinstance(correction, dict) or set(correction) != {
        "correction_id",
        "source_item_id",
        "corrected_item_id",
        "source_candidate_sha256",
        "source_judgment_sha256",
        "append_accepted_answers",
    }:
        raise ValueError("packaging correction declaration fields changed")
    source_visible = _visible_item(source_candidate)
    source_item_id = correction["source_item_id"]
    if source_visible["item_id"] != source_item_id:
        raise ValueError("packaging correction source item mismatch")
    if _sha256(source_candidate) != correction["source_candidate_sha256"]:
        raise ValueError("packaging correction source candidate drift")
    expected_id = stable_packaging_correction_item_id(source_item_id)
    if correction["corrected_item_id"] != expected_id:
        raise ValueError("packaging correction copied ID drift")
    _nonempty_string(correction["correction_id"], "correction_id")
    _nonempty_string(config_sha256, "config_sha256")
    additions = correction["append_accepted_answers"]
    if not isinstance(additions, list) or not additions:
        raise ValueError("packaging correction must append at least one answer")
    for index, answer in enumerate(additions):
        _nonempty_string(answer, f"append_accepted_answers[{index}]")
    original_answers = source_visible["accepted_answers"]
    if len(additions) != len(set(additions)) or set(additions) & set(original_answers):
        raise ValueError("packaging correction answers must be new and unique")
    source_metadata = source_candidate.get("generation_metadata")
    if (
        not isinstance(source_metadata, dict)
        or source_metadata.get("campaign") != DETERMINACY_INTERVENTION_ID
    ):
        raise ValueError("packaging correction source must be an intervention item")
    correction_input = {
        "protocol_id": PACKAGING_CORRECTION_ID,
        "config_sha256": config_sha256,
        "declaration": correction,
        "source_candidate_sha256": _sha256(source_candidate),
    }
    corrected = {
        "item_id": expected_id,
        "cell_id": source_candidate["cell_id"],
        "format": source_visible["format"],
        "prompt": source_visible["prompt"],
        "target_answer": source_visible["target_answer"],
        "accepted_answers": [*deepcopy(original_answers), *deepcopy(additions)],
        "generation_metadata": {
            "candidate_index": source_metadata["candidate_index"],
            "candidate_count": source_metadata["candidate_count"],
            "campaign": PACKAGING_CORRECTION_ID,
            "source_item_id": source_item_id,
            "source_campaign": DETERMINACY_INTERVENTION_ID,
            "model": source_metadata["model"],
            "reasoning_effort": source_metadata["reasoning_effort"],
            "input_sha256": _sha256(correction_input),
        },
        "correction_metadata": {
            "protocol_id": PACKAGING_CORRECTION_ID,
            "correction_id": correction["correction_id"],
            "source_item_id": source_item_id,
            "source_candidate_sha256": correction["source_candidate_sha256"],
            "source_judgment_sha256": correction["source_judgment_sha256"],
            "config_sha256": config_sha256,
            "operation": "append_accepted_answers_only",
            "appended_accepted_answers": deepcopy(additions),
            "input_sha256": _sha256(correction_input),
        },
    }
    _validate_candidate_payload(
        {name: corrected[name] for name in _CANDIDATE_PAYLOAD_FIELDS}
    )
    # Guard the central scientific contract explicitly: no prompt, target,
    # format, or cell field can be altered by this operation.
    for name in ("cell_id", "format", "prompt", "target_answer"):
        if corrected[name] != source_candidate[name]:  # pragma: no cover
            raise AssertionError(f"packaging correction altered {name}")
    return corrected


def generate_one_candidate(
    generation_call: dict[str, Any],
    *,
    model_call: ModelCall,
    evidence_dir: Path | None = None,
) -> dict[str, Any]:
    """Invoke an injectable backend and recover one candidate."""

    _assert_fingerprint(
        generation_call,
        _generation_fingerprint(generation_call),
        "generation",
    )
    parsed = model_call(
        generation_call["rendered_prompt"],
        model=generation_call["model"],
        reasoning_effort=generation_call["reasoning_effort"],
        input_data=generation_call["model_input"],
        stage="generation",
        call_key=generation_call["candidate_id"],
        evidence_dir=evidence_dir,
    )
    return recover_generated_candidate(parsed, generation_call)


def generate_one_campaign_candidate(
    generation_call: dict[str, Any],
    *,
    model_call: ModelCall,
    evidence_dir: Path | None = None,
) -> dict[str, Any]:
    """Invoke an injectable backend for one frozen post-N=3 position."""

    _assert_fingerprint(
        generation_call,
        _campaign_generation_fingerprint(generation_call),
        "item-campaign generation",
    )
    parsed = model_call(
        generation_call["rendered_prompt"],
        model=generation_call["model"],
        reasoning_effort=generation_call["reasoning_effort"],
        input_data=generation_call["model_input"],
        stage="generation",
        call_key=generation_call["candidate_id"],
        evidence_dir=evidence_dir,
    )
    return recover_campaign_candidate(parsed, generation_call)


def _validate_criteria(validation_criteria: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(validation_criteria, dict):
        raise ValueError("validation criteria must be an object")
    if validation_criteria.get("acceptance_rule") != "all_required_criteria_pass":
        raise ValueError(
            "full baseline validation requires all_required_criteria_pass"
        )
    _nonempty_string(validation_criteria.get("policy_id"), "validation policy_id")
    criteria = validation_criteria.get("criteria")
    if not isinstance(criteria, dict) or not criteria:
        raise ValueError("validation criteria must contain declared criteria")
    for name, declaration in criteria.items():
        _nonempty_string(name, "criterion name")
        if not isinstance(declaration, dict) or set(declaration) != {
            "required",
            "question",
        }:
            raise ValueError(f"criterion {name} must declare required and question")
        if not isinstance(declaration["required"], bool):
            raise ValueError(f"criterion {name}.required must be boolean")
        _nonempty_string(declaration["question"], f"criterion {name}.question")
    return deepcopy(criteria)


def _visible_item(candidate: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(candidate, dict):
        raise ValueError("candidate must be an object")
    missing = set(_VISIBLE_ITEM_FIELDS) - set(candidate)
    if missing:
        raise ValueError(f"candidate lacks visible fields: {sorted(missing)}")
    visible = {name: deepcopy(candidate[name]) for name in _VISIBLE_ITEM_FIELDS}
    _validate_candidate_payload(
        {name: visible[name] for name in _CANDIDATE_PAYLOAD_FIELDS}
    )
    _nonempty_string(visible["item_id"], "candidate item_id")
    _nonempty_string(visible["format"], "candidate format")
    return visible


def _visible_lexical_suffix(prompt: str, slot: re.Match[str]) -> list[str]:
    """Return clause tokens printed after a slot, excluding later instructions."""

    # Spaces may separate a slot from the rest of its clause. A line break is
    # instead an instruction boundary and must remain visible to the matcher.
    suffix = prompt[slot.end() :].lstrip(" \t")
    boundary = _SUFFIX_BOUNDARY.search(suffix)
    if boundary:
        suffix = suffix[: boundary.start()]
    return [match.group(0).casefold() for match in _LEXICAL_TOKEN.finditer(suffix)]


def _answer_tokens(answer: str) -> list[str]:
    return [match.group(0).casefold() for match in _LEXICAL_TOKEN.finditer(answer)]


def _accepted_answer_suffix_check(
    visible: dict[str, Any], slots: list[re.Match[str]]
) -> tuple[bool, str]:
    if len(slots) != 1:
        return False, "not_evaluated: expected exactly one recognised response slot"
    suffix_tokens = _visible_lexical_suffix(visible["prompt"], slots[0])
    if not suffix_tokens:
        return True, "passed: no lexical clause suffix follows the response slot"
    for index, answer in enumerate(visible["accepted_answers"]):
        answer_tokens = _answer_tokens(answer)
        if (
            len(answer_tokens) >= len(suffix_tokens)
            and answer_tokens[-len(suffix_tokens) :] == suffix_tokens
        ):
            return (
                False,
                f"failed: accepted answer {index} repeats all "
                f"{len(suffix_tokens)} lexical token(s) visibly printed after the slot",
            )
    return (
        True,
        "passed: accepted answers do not repeat the visible lexical slot suffix",
    )


def _normalise_answer_span(text: str) -> str:
    normalised = " ".join(text.casefold().split())
    return _TERMINAL_SENTENCE_PUNCTUATION.sub("", normalised).strip()


def _target_contains_accepted_span(
    visible: dict[str, Any]
) -> tuple[bool, str]:
    target = _normalise_answer_span(visible["target_answer"])
    for index, answer in enumerate(visible["accepted_answers"]):
        span = _normalise_answer_span(answer)
        if span and re.search(r"(?<!\w)" + re.escape(span) + r"(?!\w)", target):
            return (
                True,
                f"passed: normalized target contains accepted answer span {index}",
            )
    return (
        False,
        "failed: normalized target contains none of the declared accepted answer spans",
    )


def deterministic_candidate_checks(candidate: dict[str, Any]) -> dict[str, Any]:
    """Apply format-level checks that do not require linguistic judgment."""

    visible = _visible_item(candidate)
    slots = list(_RESPONSE_SLOT.finditer(visible["prompt"]))
    slot_passed = len(slots) == 1
    span_passed, span_note = answer_span_consistency(candidate)
    suffix_passed, suffix_note = _accepted_answer_suffix_check(visible, slots)
    target_span_passed, target_span_note = _target_contains_accepted_span(visible)
    no_slots_in_answers = not _RESPONSE_SLOT.search(visible["target_answer"]) and all(
        not _RESPONSE_SLOT.search(answer) for answer in visible["accepted_answers"]
    )
    return {
        "visible_response_slot": {
            "passed": slot_passed,
            "note": (
                "passed: exactly one recognised response slot"
                if slot_passed
                else f"failed: expected one recognised response slot, found {len(slots)}"
            ),
        },
        "answer_span_consistency": {
            "passed": span_passed,
            "note": span_note,
        },
        "accepted_answer_visible_suffix": {
            "passed": suffix_passed,
            "note": suffix_note,
        },
        "target_contains_accepted_answer_span": {
            "passed": target_span_passed,
            "note": target_span_note,
        },
        "no_response_slot_in_answers": {
            "passed": no_slots_in_answers,
            "note": (
                "passed: target and accepted answers contain no response slot"
                if no_slots_in_answers
                else "failed: target or accepted answer contains a response slot"
            ),
        },
    }


def build_validation_call(
    candidate: dict[str, Any],
    cell: dict[str, Any],
    prompt: str,
    validation_criteria: dict[str, Any],
    *,
    model: str,
    reasoning_effort: str,
) -> dict[str, Any]:
    """Build one independent validation call and its deterministic prechecks."""

    visible = _visible_item(candidate)
    cell_id, features = _cell_identity(cell)
    if candidate.get("cell_id") != cell_id:
        raise ValueError("candidate and validation GrammarCell disagree")
    metadata = candidate.get("generation_metadata")
    if not isinstance(metadata, dict):
        raise ValueError("candidate lacks generation_metadata")
    campaign_id = metadata.get("campaign")
    if campaign_id == PACKAGING_CORRECTION_ID:
        source_item_id = metadata.get("source_item_id")
        expected_candidate_id = stable_packaging_correction_item_id(source_item_id)
        if metadata.get("source_campaign") != DETERMINACY_INTERVENTION_ID:
            raise ValueError("packaging correction source campaign drift")
        correction_metadata = candidate.get("correction_metadata")
        if (
            not isinstance(correction_metadata, dict)
            or correction_metadata.get("protocol_id") != PACKAGING_CORRECTION_ID
            or correction_metadata.get("source_item_id") != source_item_id
            or correction_metadata.get("input_sha256")
            != metadata.get("input_sha256")
        ):
            raise ValueError("packaging correction provenance drift")
    elif campaign_id in {UNCHANGED_RESCUE_ID, DETERMINACY_INTERVENTION_ID}:
        campaign_index = metadata.get("campaign_candidate_index")
        spec = _campaign_spec(campaign_id)
        expected_candidate_id = stable_campaign_candidate_id(
            cell_id, campaign_index, campaign_id
        )
        if metadata.get("candidate_index") != (
            spec["selection_offset"] + campaign_index
        ):
            raise ValueError("item-campaign candidate selection index drift")
        if metadata.get("candidate_count") != (
            ACTIVE_CANDIDATES_PER_CELL
            + UNCHANGED_RESCUE_CANDIDATES_PER_CELL
            + DETERMINACY_INTERVENTION_CANDIDATES_PER_CELL
        ):
            raise ValueError("item-campaign candidate count drift")
    else:
        expected_candidate_id = stable_candidate_id(
            cell_id, metadata["candidate_index"]
        )
    if candidate["item_id"] != expected_candidate_id:
        raise ValueError("candidate item_id does not match its cell and index")
    visible["item_id"] = _neutral_validation_item_id(candidate["item_id"])
    criteria = _validate_criteria(validation_criteria)
    prompt = _nonblank_text(prompt, "validation prompt")
    model = _nonempty_string(model, "validation model")
    reasoning_effort = _nonempty_string(
        reasoning_effort, "validation reasoning_effort"
    )
    deterministic_checks = deterministic_candidate_checks(candidate)
    model_input = {
        "visible_item": visible,
        "target_cell": features,
        "criteria": criteria,
    }
    rendered_prompt = render(prompt, model_input)
    validation_call = {
        "candidate_id": candidate["item_id"],
        "cell_id": cell_id,
        "model": model,
        "reasoning_effort": reasoning_effort,
        "policy_id": validation_criteria["policy_id"],
        "acceptance_rule": validation_criteria["acceptance_rule"],
        "criteria": criteria,
        "deterministic_checks": deterministic_checks,
        "model_input": model_input,
        "rendered_prompt": rendered_prompt,
        "call_required": all(
            check["passed"] for check in deterministic_checks.values()
        ),
    }
    validation_call["input_sha256"] = _validation_fingerprint(validation_call)
    return validation_call


def _validate_validator_payload(parsed: Any, criteria: dict[str, Any]) -> None:
    if not isinstance(parsed, dict) or set(parsed) != {"judgments"}:
        raise ValueError(
            "validator output must be one object containing exactly judgments"
        )
    judgments = parsed["judgments"]
    if not isinstance(judgments, dict) or set(judgments) != set(criteria):
        raise ValueError("validator must judge exactly every declared criterion")
    for name, judgment in judgments.items():
        if not isinstance(judgment, dict) or set(judgment) != {"passed", "note"}:
            raise ValueError(f"validator judgment {name} must contain passed and note")
        if not isinstance(judgment["passed"], bool):
            raise ValueError(f"validator judgment {name}.passed must be boolean")
        _nonempty_string(judgment["note"], f"validator judgment {name}.note")


def recover_validator_judgment(
    parsed: Any, validation_call: dict[str, Any]
) -> dict[str, Any]:
    """Strictly reconstruct the canonical judgment for a model-judged item."""

    if not validation_call.get("call_required"):
        raise ValueError("validator output supplied for a deterministic rejection")
    _assert_fingerprint(
        validation_call,
        _validation_fingerprint(validation_call),
        "validation",
    )
    criteria = validation_call["criteria"]
    _validate_validator_payload(parsed, criteria)
    judgments = deepcopy(parsed["judgments"])
    accepted = all(
        judgments[name]["passed"]
        for name, declaration in criteria.items()
        if declaration["required"]
    )
    return {
        "item_id": validation_call["candidate_id"],
        "deterministic_checks": deepcopy(
            validation_call["deterministic_checks"]
        ),
        "judgments": judgments,
        "accepted": accepted,
        "rejection_stage": None if accepted else "independent_model_judgment",
        "validation_metadata": {
            "policy_id": validation_call["policy_id"],
            "model": validation_call["model"],
            "reasoning_effort": validation_call["reasoning_effort"],
            "input_sha256": validation_call["input_sha256"],
        },
    }


def reconstruct_validation_judgment(
    validation_call: dict[str, Any], parsed: Any | None = None
) -> dict[str, Any]:
    """Reconstruct either a deterministic rejection or a model judgment."""

    _assert_fingerprint(
        validation_call,
        _validation_fingerprint(validation_call),
        "validation",
    )
    if validation_call.get("call_required"):
        if parsed is None:
            raise ValueError("a passing precheck requires validator output")
        return recover_validator_judgment(parsed, validation_call)
    if parsed is not None:
        raise ValueError("deterministically rejected candidates must not be judged")
    return {
        "item_id": validation_call["candidate_id"],
        "deterministic_checks": deepcopy(
            validation_call["deterministic_checks"]
        ),
        "judgments": {},
        "accepted": False,
        "rejection_stage": "deterministic_precheck",
        "validation_metadata": {
            "policy_id": validation_call["policy_id"],
            "model": validation_call["model"],
            "reasoning_effort": validation_call["reasoning_effort"],
            "input_sha256": validation_call["input_sha256"],
        },
    }


def validate_one_candidate(
    validation_call: dict[str, Any],
    *,
    model_call: ModelCall,
    evidence_dir: Path | None = None,
) -> dict[str, Any]:
    """Run at most one injectable validator call after deterministic checks."""

    _assert_fingerprint(
        validation_call,
        _validation_fingerprint(validation_call),
        "validation",
    )
    if not validation_call["call_required"]:
        return reconstruct_validation_judgment(validation_call)
    parsed = model_call(
        validation_call["rendered_prompt"],
        model=validation_call["model"],
        reasoning_effort=validation_call["reasoning_effort"],
        input_data=validation_call["model_input"],
        stage="validation",
        call_key=validation_call["candidate_id"],
        evidence_dir=evidence_dir,
    )
    return reconstruct_validation_judgment(validation_call, parsed)


def _expected_fingerprints(
    plans: Iterable[dict[str, Any]], *, id_field: str
) -> dict[str, str]:
    expected: dict[str, str] = {}
    for plan in plans:
        identifier = plan.get(id_field)
        fingerprint = plan.get("input_sha256")
        if not isinstance(identifier, str) or not identifier:
            raise ValueError(f"planned call lacks {id_field}")
        if identifier in expected:
            raise ValueError(f"duplicate planned call ID: {identifier}")
        if not isinstance(fingerprint, str) or not re.fullmatch(
            r"[0-9a-f]{64}", fingerprint
        ):
            raise ValueError(f"planned call lacks input_sha256: {identifier}")
        expected[identifier] = fingerprint
    return expected


def _merge_checkpoint_rows(
    existing: list[dict[str, Any]],
    completed: list[dict[str, Any]],
    expected: dict[str, str],
    *,
    id_field: str,
    metadata_field: str,
) -> list[dict[str, Any]]:
    merged: dict[str, dict[str, Any]] = {}
    for source_name, rows in (("existing", existing), ("new", completed)):
        for row in rows:
            if not isinstance(row, dict):
                raise ValueError(f"{source_name} checkpoint row must be an object")
            identifier = row.get(id_field)
            if not isinstance(identifier, str) or not identifier:
                raise ValueError(f"{source_name} checkpoint row lacks {id_field}")
            if identifier in merged:
                raise ValueError(f"duplicate completed checkpoint ID: {identifier}")
            if identifier not in expected:
                raise ValueError(f"checkpoint row is not in the frozen plan: {identifier}")
            metadata = row.get(metadata_field)
            if not isinstance(metadata, dict):
                raise ValueError(
                    f"checkpoint row lacks {metadata_field}: {identifier}"
                )
            fingerprint = metadata.get("input_sha256")
            if fingerprint != expected[identifier]:
                raise ValueError(f"checkpoint input drift: {identifier}")
            merged[identifier] = deepcopy(row)
    return [merged[identifier] for identifier in sorted(merged)]


def merge_completed_candidate_rows(
    existing: list[dict[str, Any]],
    completed: list[dict[str, Any]],
    generation_calls: Iterable[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Merge unique candidate checkpoints against a frozen generation plan."""

    expected = _expected_fingerprints(generation_calls, id_field="candidate_id")
    return _merge_checkpoint_rows(
        existing,
        completed,
        expected,
        id_field="item_id",
        metadata_field="generation_metadata",
    )


def merge_completed_judgment_rows(
    existing: list[dict[str, Any]],
    completed: list[dict[str, Any]],
    validation_calls: Iterable[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Merge unique judgment checkpoints against a frozen validation plan."""

    expected = _expected_fingerprints(validation_calls, id_field="candidate_id")
    return _merge_checkpoint_rows(
        existing,
        completed,
        expected,
        id_field="item_id",
        metadata_field="validation_metadata",
    )


def pending_generation_calls(
    generation_calls: list[dict[str, Any]], completed: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Validate a checkpoint and return its still-uncompleted frozen calls."""

    merge_completed_candidate_rows(completed, [], generation_calls)
    completed_ids = {row["item_id"] for row in completed}
    return [
        deepcopy(plan)
        for plan in generation_calls
        if plan["candidate_id"] not in completed_ids
    ]


def pending_validation_calls(
    validation_calls: list[dict[str, Any]], completed: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Validate a checkpoint and return its still-uncompleted frozen calls."""

    merge_completed_judgment_rows(completed, [], validation_calls)
    completed_ids = {row["item_id"] for row in completed}
    return [
        deepcopy(plan)
        for plan in validation_calls
        if plan["candidate_id"] not in completed_ids
    ]


def _unique_cells(cells: list[dict[str, Any]]) -> list[str]:
    cell_ids = []
    for cell in cells:
        cell_id, _ = _cell_identity(cell)
        cell_ids.append(cell_id)
    if len(cell_ids) != len(set(cell_ids)):
        raise ValueError("GrammarCell IDs must be unique")
    return sorted(cell_ids)


def candidate_audit_summary(
    cells: list[dict[str, Any]], candidates: list[dict[str, Any]]
) -> dict[str, Any]:
    """Return a text-free, public-safe generation-completion audit."""

    cell_ids = _unique_cells(cells)
    known = set(cell_ids)
    by_cell: dict[str, list[int]] = {cell_id: [] for cell_id in cell_ids}
    seen_items: set[str] = set()
    for candidate in candidates:
        visible = _visible_item(candidate)
        item_id = visible["item_id"]
        if item_id in seen_items:
            raise ValueError(f"duplicate candidate ID in audit: {item_id}")
        seen_items.add(item_id)
        cell_id = candidate.get("cell_id")
        if cell_id not in known:
            raise ValueError(f"candidate refers to unknown GrammarCell: {item_id}")
        metadata = candidate.get("generation_metadata")
        if not isinstance(metadata, dict):
            raise ValueError(f"candidate lacks generation_metadata: {item_id}")
        index = metadata.get("candidate_index")
        if stable_candidate_id(cell_id, index) != item_id:
            raise ValueError(f"candidate stable ID drift: {item_id}")
        if metadata.get("candidate_count") != ACTIVE_CANDIDATES_PER_CELL:
            raise ValueError(f"candidate count drift: {item_id}")
        by_cell[cell_id].append(index)
    for cell_id, indices in by_cell.items():
        if len(indices) != len(set(indices)):
            raise ValueError(f"duplicate candidate position for cell: {cell_id}")
    planned = len(cell_ids) * ACTIVE_CANDIDATES_PER_CELL
    per_cell = {
        cell_id: {
            "completed_candidates": len(by_cell[cell_id]),
            "completed_indices": sorted(by_cell[cell_id]),
            "missing_indices": sorted(
                set(range(1, ACTIVE_CANDIDATES_PER_CELL + 1)) - set(by_cell[cell_id])
            ),
        }
        for cell_id in cell_ids
    }
    return {
        "candidate_design": {"candidates_per_cell": ACTIVE_CANDIDATES_PER_CELL},
        "grammar_cells": len(cell_ids),
        "planned_candidates": planned,
        "completed_candidates": len(candidates),
        "completion_rate": len(candidates) / planned if planned else 0.0,
        "cells_with_all_candidates": sum(
            row["completed_candidates"] == ACTIVE_CANDIDATES_PER_CELL
            for row in per_cell.values()
        ),
        "cells_with_any_candidate": sum(
            row["completed_candidates"] > 0 for row in per_cell.values()
        ),
        "zero_candidate_cells": sum(
            row["completed_candidates"] == 0 for row in per_cell.values()
        ),
        "by_cell": per_cell,
    }


def validation_audit_summary(
    cells: list[dict[str, Any]],
    candidates: list[dict[str, Any]],
    judgments: list[dict[str, Any]],
    validation_criteria: dict[str, Any],
) -> dict[str, Any]:
    """Return public-safe acceptance and criterion aggregates without notes."""

    cell_ids = _unique_cells(cells)
    known = set(cell_ids)
    criteria = _validate_criteria(validation_criteria)
    candidate_cell: dict[str, str] = {}
    for candidate in candidates:
        item_id = _visible_item(candidate)["item_id"]
        if item_id in candidate_cell:
            raise ValueError(f"duplicate candidate ID in audit: {item_id}")
        cell_id = candidate.get("cell_id")
        if cell_id not in known:
            raise ValueError(f"candidate refers to unknown GrammarCell: {item_id}")
        candidate_cell[item_id] = cell_id

    seen: set[str] = set()
    per_cell = {
        cell_id: {"judged_candidates": 0, "accepted_candidates": 0}
        for cell_id in cell_ids
    }
    criterion_counts = {
        name: {"judged": 0, "passed": 0, "failed": 0}
        for name in criteria
    }
    rejection_stages: dict[str, int] = {}
    for row in judgments:
        item_id = row.get("item_id")
        if item_id in seen:
            raise ValueError(f"duplicate judgment ID in audit: {item_id}")
        seen.add(item_id)
        if item_id not in candidate_cell:
            raise ValueError(f"judgment has no recovered candidate: {item_id}")
        cell_id = candidate_cell[item_id]
        per_cell[cell_id]["judged_candidates"] += 1
        accepted = row.get("accepted")
        if not isinstance(accepted, bool):
            raise ValueError(f"judgment accepted must be boolean: {item_id}")
        per_cell[cell_id]["accepted_candidates"] += int(accepted)
        result = row.get("judgments")
        if not isinstance(result, dict) or not set(result) <= set(criteria):
            raise ValueError(f"judgment has undeclared criteria: {item_id}")
        for name, value in result.items():
            if not isinstance(value, dict) or not isinstance(value.get("passed"), bool):
                raise ValueError(f"invalid criterion judgment: {item_id}/{name}")
            criterion_counts[name]["judged"] += 1
            criterion_counts[name]["passed"] += int(value["passed"])
            criterion_counts[name]["failed"] += int(not value["passed"])
        stage = row.get("rejection_stage") or "accepted"
        rejection_stages[stage] = rejection_stages.get(stage, 0) + 1

    criterion_summary = {
        name: {
            **counts,
            "not_judged": len(judgments) - counts["judged"],
            "pass_rate": (
                counts["passed"] / counts["judged"] if counts["judged"] else 0.0
            ),
        }
        for name, counts in criterion_counts.items()
    }
    accepted_total = sum(bool(row.get("accepted")) for row in judgments)
    return {
        "recovered_candidates": len(candidates),
        "completed_judgments": len(judgments),
        "judgment_completion_rate": (
            len(judgments) / len(candidates) if candidates else 0.0
        ),
        "accepted_candidates": accepted_total,
        "acceptance_rate_among_judged": (
            accepted_total / len(judgments) if judgments else 0.0
        ),
        "accepted_cell_coverage": sum(
            row["accepted_candidates"] > 0 for row in per_cell.values()
        ),
        "rejection_stage_counts": dict(sorted(rejection_stages.items())),
        "criteria": criterion_summary,
        "by_cell": per_cell,
    }


def item_construction_audit(
    cells: list[dict[str, Any]],
    candidates: list[dict[str, Any]],
    judgments: list[dict[str, Any]],
    validation_criteria: dict[str, Any],
) -> dict[str, Any]:
    """Combine the two public-safe full-v1 item evidence summaries."""

    return {
        "generation": candidate_audit_summary(cells, candidates),
        "validation": validation_audit_summary(
            cells, candidates, judgments, validation_criteria
        ),
        "privacy": {
            "contains_source_descriptors": False,
            "contains_judgment_notes": False,
            "contains_learner_outcomes": False,
            "contains_generator_kcs": False,
        },
    }
