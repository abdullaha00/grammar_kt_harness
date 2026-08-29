#!/usr/bin/env python3
"""Run the Phase-4 item-generation and independent-validation audit.

The experiment generates the maximum requested number of candidates once,
blinds and validates the pooled candidates once, and derives N=1/3/5 results
from prefixes of those frozen calls.  The legacy opportunity file contributes
only its 24 schema-valid GrammarCells and source links; no legacy items,
judgments, learner outcomes, or KC information are reused.
"""

from __future__ import annotations

import argparse
import json
import random
import re
import shutil
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Callable

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from grammar_kt.canonicalise import validate_cell
from grammar_kt.io import (
    ModelCall,
    call_model,
    read_jsonl,
    read_text,
    read_yaml,
    render,
    write_json,
    write_jsonl,
)


LEGACY_OPPORTUNITIES = (
    ROOT / "experiments/post_training_v1/data/pilot_v1/opportunities.jsonl"
)
READABLE_SOURCE_RECORDS = ROOT / "reference/pipeline_walkthrough/source_records.jsonl"
GRAMMAR_SCHEMA_PATH = ROOT / "modules/grammar/canonical/schema.yaml"
GENERATION_PROMPT_PATH = ROOT / "modules/items/generation/prompt.txt"
GENERATION_RULEBOOK_PATH = ROOT / "modules/items/generation/rulebook.md"
GENERATION_DESIGN_PATH = ROOT / "modules/items/generation/design.yaml"
ITEM_FORMAT_PATH = (
    ROOT / "modules/items/generation/formats/controlled_production.yaml"
)
CONTROLLED_LEXICON_PATH = (
    ROOT / "modules/items/generation/ablations/controlled_lexicon.jsonl"
)
VALIDATION_PROMPT_PATH = ROOT / "modules/items/validation/prompt.txt"
VALIDATION_CRITERIA_PATH = ROOT / "modules/items/validation/criteria.yaml"

GENERATION_MODEL = "gpt-5.6-sol"
VALIDATION_MODEL = "gpt-5.6-terra"
REASONING_EFFORT = "medium"
BLINDING_SEED = 20260827

# Eight difficult, structurally diverse sentinels fixed before seeing new item
# outcomes.  Three have recoverable readable source evidence.
PILOT_CELL_IDS = (
    "CELL_0A7F3FA2D498D97D",  # present perfect, negative
    "CELL_0ACC7E0377B19DC1",  # central modal
    "CELL_0D017AFB2B3A3DB5",  # past perfect progressive
    "CELL_29BDABD4E976923A",  # progressive passive
    "CELL_868FF555B70CAE2A",  # polar question
    "CELL_B6AF2E896B998C79",  # past passive
    "CELL_C20140C7DAD62DB2",  # past negative with DO-support
    "CELL_EE9DDB26E6C7D307",  # negative imperative
)

CONDITIONS = {
    "model_selected": {
        "maximum_n": 5,
        "prefixes": (1, 3, 5),
        "readable_source_evidence": False,
        "controlled_lexicon": False,
    },
    "controlled_lexicon": {
        "maximum_n": 5,
        "prefixes": (1, 3, 5),
        "readable_source_evidence": False,
        "controlled_lexicon": True,
    },
    "readable_source_evidence": {
        "maximum_n": 3,
        "prefixes": (1, 3),
        "readable_source_evidence": True,
        "controlled_lexicon": False,
    },
}

ALLOWED_OPERATION_TAGS = {
    "perfect",
    "progressive",
    "be_passive",
    "central_modal",
    "do_support",
    "negation",
    "operator_inversion",
    "subject_wh",
    "wh_fronting",
    "imperative",
    "emphatic_do",
    "let_imperative",
}

AUDIT_PROMPT_SUFFIX = """

AUDIT CANDIDATE POSITION:
{{candidate_position}}

LEXICAL INTERVENTION FOR THIS CONDITION:
{{lexical_intervention}}

Generate this candidate independently. Candidate position is an experimental
index, not learner-facing content: do not mention it in the exercise.
"""


def load_frozen_cells() -> list[dict[str, Any]]:
    """Deduplicate and validate the 24 legacy cells without reusing old items."""

    schema = read_yaml(GRAMMAR_SCHEMA_PATH)
    by_id: dict[str, dict[str, Any]] = {}
    for row in read_jsonl(LEGACY_OPPORTUNITIES):
        cell_id = row["canonical_cell_id"]
        features = row["cell"]
        validate_cell(features, schema)
        if cell_id not in by_id:
            by_id[cell_id] = {
                "cell_id": cell_id,
                "features": features,
                "source_ids": set(),
            }
        elif by_id[cell_id]["features"] != features:
            raise ValueError(f"inconsistent legacy GrammarCell: {cell_id}")
        by_id[cell_id]["source_ids"].update(row.get("source_descriptor_ids", []))

    if len(by_id) != 24:
        raise ValueError(f"expected 24 frozen legacy cells, found {len(by_id)}")
    return [
        {
            "cell_id": row["cell_id"],
            "features": row["features"],
            "source_ids": sorted(row["source_ids"]),
        }
        for row in sorted(by_id.values(), key=lambda value: value["cell_id"])
    ]


def recover_readable_source_support(
    cells: list[dict[str, Any]],
) -> dict[str, list[dict[str, str]]]:
    """Recover only guideword/can-do pairs linked to a frozen GrammarCell."""

    source_by_id = {
        row["egp_id"]: row for row in read_jsonl(READABLE_SOURCE_RECORDS)
    }
    support: dict[str, list[dict[str, str]]] = {}
    for cell in cells:
        pairs: list[dict[str, str]] = []
        seen: set[tuple[str, str]] = set()
        for source_id in cell["source_ids"]:
            source = source_by_id.get(source_id)
            if source is None:
                continue
            key = (source["guideword"], source["can_do"])
            if key not in seen:
                pairs.append({"guideword": key[0], "can_do": key[1]})
                seen.add(key)
        if pairs:
            support[cell["cell_id"]] = pairs
    return support


def load_controlled_lexicon() -> list[dict[str, Any]]:
    """Load the six-entry ablation without opaque IDs or CEFR labels."""

    fields = (
        "lemma",
        "predicate_class",
        "passive_compatible",
        "example_subject",
        "example_object",
    )
    rows = [
        {name: row[name] for name in fields if name in row}
        for row in read_jsonl(CONTROLLED_LEXICON_PATH)
    ]
    if len(rows) != 6:
        raise ValueError(f"controlled lexicon must contain six entries, found {len(rows)}")
    return rows


def _source_input(evidence: list[dict[str, str]]) -> dict[str, Any]:
    if evidence:
        return {
            "available": True,
            "evidence": evidence,
            "instruction": (
                "Use this readable resource evidence only to support the fixed "
                "GrammarCell; do not copy wording or add unsupported grammar."
            ),
        }
    return {
        "available": False,
        "evidence": [],
        "instruction": "No source evidence is supplied in this condition.",
    }


def _lexical_input(
    controlled_lexicon: list[dict[str, Any]] | None,
) -> dict[str, Any]:
    if controlled_lexicon is None:
        return {
            "mode": "model_selected",
            "instruction": (
                "Choose common, transparent lexical and contextual material "
                "compatible with the fixed GrammarCell."
            ),
        }
    return {
        "mode": "controlled_six_entry_lexicon",
        "instruction": (
            "Choose a grammatically compatible predicate and arguments only from "
            "these six entries. Inflect the selected lemma as required."
        ),
        "entries": controlled_lexicon,
    }


def build_generation_tasks(
    cells: list[dict[str, Any]],
    source_support: dict[str, list[dict[str, str]]],
    controlled_lexicon: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Declare all maximum-N calls before any generation or validation."""

    tasks: list[dict[str, Any]] = []
    for condition, declaration in CONDITIONS.items():
        eligible_cells = cells
        if declaration["readable_source_evidence"]:
            eligible_cells = [cell for cell in cells if cell["cell_id"] in source_support]
        for cell in eligible_cells:
            evidence = (
                source_support[cell["cell_id"]]
                if declaration["readable_source_evidence"]
                else []
            )
            lexicon = controlled_lexicon if declaration["controlled_lexicon"] else None
            for index in range(1, declaration["maximum_n"] + 1):
                tasks.append(
                    {
                        "condition": condition,
                        "cell": cell,
                        "candidate_index": index,
                        "candidate_count": declaration["maximum_n"],
                        "source_support": _source_input(evidence),
                        "lexical_intervention": _lexical_input(lexicon),
                    }
                )
    return tasks


def candidate_payload_errors(payload: Any) -> list[str]:
    """Check the observable item contract before sending a candidate to a judge."""

    required = {
        "prompt",
        "target_answer",
        "accepted_answers",
        "operation_tags",
        "note",
    }
    if not isinstance(payload, dict):
        return ["output is not a JSON object"]
    errors = []
    if set(payload) != required:
        errors.append(
            f"output fields differ: missing={sorted(required - set(payload))}, "
            f"unknown={sorted(set(payload) - required)}"
        )
    for name in ("prompt", "target_answer", "note"):
        if not isinstance(payload.get(name), str) or not payload.get(name, "").strip():
            errors.append(f"{name} must be a non-empty string")
    prompt = payload.get("prompt", "")
    if isinstance(prompt, str) and not re.search(
        r"_{2,}|\[\s*blank\s*\]|<\s*blank\s*>", prompt, flags=re.IGNORECASE
    ):
        errors.append("prompt has no visible response slot")
    answers = payload.get("accepted_answers")
    if (
        not isinstance(answers, list)
        or not answers
        or any(not isinstance(answer, str) or not answer.strip() for answer in answers)
    ):
        errors.append("accepted_answers must be a non-empty list of non-empty strings")
    elif len(set(answers)) != len(answers):
        errors.append("accepted_answers contains duplicates")
    elif payload.get("target_answer") not in answers:
        errors.append("target_answer must be included in accepted_answers")
    tags = payload.get("operation_tags")
    if not isinstance(tags, list) or any(not isinstance(tag, str) for tag in tags):
        errors.append("operation_tags must be a list of strings")
    elif len(set(tags)) != len(tags):
        errors.append("operation_tags contains duplicates")
    elif set(tags) - ALLOWED_OPERATION_TAGS:
        errors.append(f"unknown operation tags: {sorted(set(tags) - ALLOWED_OPERATION_TAGS)}")
    return errors


def _generation_model_input(
    task: dict[str, Any],
    design: dict[str, Any],
    item_format: dict[str, Any],
) -> dict[str, Any]:
    return {
        "target_cell": {
            "cell_id": task["cell"]["cell_id"],
            "features": task["cell"]["features"],
        },
        "source_support": task["source_support"],
        "item_format": item_format,
        "design": design,
        "candidate_position": {
            "index": task["candidate_index"],
            "count": task["candidate_count"],
        },
        "lexical_intervention": task["lexical_intervention"],
    }


def generate_one(
    task: dict[str, Any],
    *,
    prompt: str,
    rulebook: str,
    design: dict[str, Any],
    item_format: dict[str, Any],
    model: str,
    reasoning_effort: str,
    model_call: ModelCall,
    evidence_dir: Path,
) -> tuple[dict[str, Any], dict[str, Any] | None]:
    """Make and structurally inspect one independent generation call."""

    condition = task["condition"]
    cell_id = task["cell"]["cell_id"]
    index = task["candidate_index"]
    candidate_id = f"candidate_{condition}_{cell_id}_{index:02d}"
    model_input = _generation_model_input(task, design, item_format)
    rendered_prompt = render(
        prompt,
        {**model_input, "rulebook": rulebook},
    )
    started = time.monotonic()
    try:
        parsed = model_call(
            rendered_prompt,
            model=model,
            reasoning_effort=reasoning_effort,
            input_data=model_input,
            stage="generation",
            call_key=candidate_id,
            evidence_dir=evidence_dir / condition / cell_id / f"candidate_{index:02d}",
        )
        errors = candidate_payload_errors(parsed)
        call_error = None
    except Exception as error:  # retain model/parse failures as audit outcomes
        parsed = None
        errors = [f"{type(error).__name__}: {error}"]
        call_error = type(error).__name__
    attempt = {
        "candidate_id": candidate_id,
        "condition": condition,
        "cell_id": cell_id,
        "candidate_index": index,
        "candidate_count": task["candidate_count"],
        "structurally_valid": not errors,
        "structural_errors": errors,
        "call_error": call_error,
        "runtime_seconds": time.monotonic() - started,
    }
    if errors or parsed is None:
        return attempt, None
    candidate = {
        "item_id": candidate_id,
        "cell_id": cell_id,
        "format": item_format["format_id"],
        "prompt": parsed["prompt"],
        "target_answer": parsed["target_answer"],
        "accepted_answers": parsed["accepted_answers"],
        "operation_tags": parsed["operation_tags"],
        "generation_metadata": {
            "condition": condition,
            "candidate_index": index,
            "candidate_count": task["candidate_count"],
            "model": model,
            "note": parsed["note"],
            "readable_source_records": len(task["source_support"]["evidence"]),
            "controlled_lexicon": condition == "controlled_lexicon",
        },
    }
    return attempt, candidate


def blind_candidates(
    candidates: list[dict[str, Any]], seed: int = BLINDING_SEED
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Pool, seed-shuffle, neutrally relabel, and strip generator metadata."""

    shuffled = sorted(candidates, key=lambda row: row["item_id"])
    random.Random(seed).shuffle(shuffled)
    blinded = []
    mapping = []
    for order, candidate in enumerate(shuffled, 1):
        blind_id = f"blind_item_{order:04d}"
        blinded.append(
            {
                "item_id": blind_id,
                "cell_id": candidate["cell_id"],
                "format": candidate["format"],
                "prompt": candidate["prompt"],
                "target_answer": candidate["target_answer"],
                "accepted_answers": candidate["accepted_answers"],
            }
        )
        metadata = candidate["generation_metadata"]
        mapping.append(
            {
                "validation_order": order,
                "blind_item_id": blind_id,
                "candidate_id": candidate["item_id"],
                "condition": metadata["condition"],
                "cell_id": candidate["cell_id"],
                "candidate_index": metadata["candidate_index"],
            }
        )
    return blinded, mapping


def judgment_payload_errors(
    payload: Any, criteria: dict[str, Any]
) -> list[str]:
    if not isinstance(payload, dict) or set(payload) != {"judgments"}:
        return ["validator output must contain exactly the judgments mapping"]
    judgments = payload["judgments"]
    if not isinstance(judgments, dict) or set(judgments) != set(criteria):
        return ["validator did not judge exactly every declared criterion"]
    errors = []
    for name, judgment in judgments.items():
        if not isinstance(judgment, dict) or set(judgment) != {"passed", "note"}:
            errors.append(f"{name} must contain exactly passed and note")
            continue
        if not isinstance(judgment["passed"], bool):
            errors.append(f"{name}.passed must be boolean")
        if not isinstance(judgment["note"], str) or not judgment["note"].strip():
            errors.append(f"{name}.note must be a non-empty string")
    return errors


def validate_one_blinded(
    blinded: dict[str, Any],
    *,
    cells_by_id: dict[str, dict[str, Any]],
    prompt: str,
    validation_criteria: dict[str, Any],
    model: str,
    reasoning_effort: str,
    model_call: ModelCall,
    evidence_dir: Path,
) -> dict[str, Any]:
    """Validate one item from only its neutral ID, visible content, and target."""

    criteria = validation_criteria["criteria"]
    visible_item = {
        name: blinded[name]
        for name in (
            "item_id",
            "format",
            "prompt",
            "target_answer",
            "accepted_answers",
        )
    }
    model_input = {
        "visible_item": visible_item,
        "target_cell": cells_by_id[blinded["cell_id"]]["features"],
        "criteria": criteria,
    }
    rendered_prompt = render(prompt, model_input)
    started = time.monotonic()
    try:
        parsed = model_call(
            rendered_prompt,
            model=model,
            reasoning_effort=reasoning_effort,
            input_data=model_input,
            stage="validation",
            call_key=blinded["item_id"],
            evidence_dir=evidence_dir / "calls" / blinded["item_id"],
        )
        errors = judgment_payload_errors(parsed, criteria)
        judgments = parsed.get("judgments", {}) if isinstance(parsed, dict) else {}
    except Exception as error:  # retain model/parse failures as audit outcomes
        errors = [f"{type(error).__name__}: {error}"]
        judgments = {}
    output_valid = not errors
    accepted = output_valid and all(
        judgments[name]["passed"]
        for name, declaration in criteria.items()
        if declaration["required"]
    )
    return {
        "blind_item_id": blinded["item_id"],
        "validator_output_valid": output_valid,
        "validation_errors": errors,
        "judgments": judgments,
        "accepted": accepted,
        "runtime_seconds": time.monotonic() - started,
    }


def _token_distance(first: dict[str, Any], second: dict[str, Any]) -> float:
    def tokens(row: dict[str, Any]) -> set[str]:
        text = f"{row['prompt']} {row['target_answer']}".casefold()
        return set(re.findall(r"[a-z]+", text))

    left, right = tokens(first), tokens(second)
    union = left | right
    return 1.0 - len(left & right) / len(union) if union else 0.0


def prefix_results(
    attempts: list[dict[str, Any]],
    candidates: list[dict[str, Any]],
    validation: list[dict[str, Any]],
    *,
    select_second: bool,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Derive all N results without making any additional model calls."""

    candidate_by_id = {row["item_id"]: row for row in candidates}
    validation_by_id = {row["candidate_id"]: row for row in validation}
    metric_rows = []
    selections = []
    for condition, declaration in CONDITIONS.items():
        for prefix_n in declaration["prefixes"]:
            prefix_attempts = [
                row
                for row in attempts
                if row["condition"] == condition
                and row["candidate_index"] <= prefix_n
            ]
            eligible_cell_ids = sorted({row["cell_id"] for row in prefix_attempts})
            prefix_candidates = [
                row
                for row in candidates
                if row["generation_metadata"]["condition"] == condition
                and row["generation_metadata"]["candidate_index"] <= prefix_n
            ]
            prefix_validation = [
                validation_by_id[row["item_id"]]
                for row in prefix_candidates
                if row["item_id"] in validation_by_id
            ]
            valid_outputs = [
                row for row in prefix_validation if row["validator_output_valid"]
            ]
            accepted = [
                candidate_by_id[row["candidate_id"]]
                for row in prefix_validation
                if row["accepted"]
            ]
            covered = {row["cell_id"] for row in accepted}
            prompts = [row["prompt"].casefold().strip() for row in accepted]
            tokens = [
                token
                for prompt_text in prompts
                for token in re.findall(r"[a-z]+", prompt_text)
            ]
            criteria = (
                list(valid_outputs[0]["judgments"]) if valid_outputs else []
            )
            metric_rows.append(
                {
                    "condition": condition,
                    "prefix_n": prefix_n,
                    "maximum_n_generated": declaration["maximum_n"],
                    "eligible_cells": len(eligible_cell_ids),
                    "planned_generation_attempts": len(prefix_attempts),
                    "structurally_valid_candidates": len(prefix_candidates),
                    "structural_success_rate": (
                        len(prefix_candidates) / len(prefix_attempts)
                        if prefix_attempts
                        else 0.0
                    ),
                    "valid_validator_outputs": len(valid_outputs),
                    "accepted_candidates": len(accepted),
                    "acceptance_rate_among_valid_judgments": (
                        len(accepted) / len(valid_outputs) if valid_outputs else 0.0
                    ),
                    "end_to_end_acceptance_rate": (
                        len(accepted) / len(prefix_attempts) if prefix_attempts else 0.0
                    ),
                    "covered_cells": len(covered),
                    "cell_coverage_rate": (
                        len(covered) / len(eligible_cell_ids)
                        if eligible_cell_ids
                        else 0.0
                    ),
                    "unique_prompt_rate": (
                        len(set(prompts)) / len(prompts) if prompts else 0.0
                    ),
                    "lexical_types": len(set(tokens)),
                    "lexical_tokens": len(tokens),
                    "lexical_diversity": (
                        len(set(tokens)) / len(tokens) if tokens else 0.0
                    ),
                    "criterion_pass_rates": {
                        name: (
                            sum(row["judgments"][name]["passed"] for row in valid_outputs)
                            / len(valid_outputs)
                        )
                        for name in criteria
                    },
                }
            )

            by_cell: dict[str, list[dict[str, Any]]] = {}
            for candidate in accepted:
                by_cell.setdefault(candidate["cell_id"], []).append(candidate)
            for cell_id, rows in sorted(by_cell.items()):
                rows.sort(key=lambda row: row["generation_metadata"]["candidate_index"])
                first = rows[0]
                selections.append(
                    _selection_row(condition, prefix_n, cell_id, 1, "earliest_valid", first, 0.0)
                )
                if select_second and len(rows) > 1:
                    second = min(
                        rows[1:],
                        key=lambda row: (
                            -_token_distance(first, row),
                            row["generation_metadata"]["candidate_index"],
                        ),
                    )
                    selections.append(
                        _selection_row(
                            condition,
                            prefix_n,
                            cell_id,
                            2,
                            "maximum_token_set_distance_from_first",
                            second,
                            _token_distance(first, second),
                        )
                    )
    return metric_rows, selections


def _selection_row(
    condition: str,
    prefix_n: int,
    cell_id: str,
    rank: int,
    rule: str,
    candidate: dict[str, Any],
    distance: float,
) -> dict[str, Any]:
    return {
        "condition": condition,
        "prefix_n": prefix_n,
        "cell_id": cell_id,
        "selection_rank": rank,
        "selection_rule": rule,
        "candidate_id": candidate["item_id"],
        "candidate_index": candidate["generation_metadata"]["candidate_index"],
        "token_set_distance_from_first": distance,
        "prompt": candidate["prompt"],
        "target_answer": candidate["target_answer"],
        "accepted_answers": candidate["accepted_answers"],
    }


def _parallel_map(
    rows: list[Any], function: Callable[[Any], Any], workers: int, label: str
) -> list[Any]:
    if workers < 1:
        raise ValueError("workers must be positive")
    results: list[Any] = [None] * len(rows)
    if workers == 1:
        for index, row in enumerate(rows):
            results[index] = function(row)
            if (index + 1) % 10 == 0 or index + 1 == len(rows):
                print(f"{label}: {index + 1}/{len(rows)}", flush=True)
        return results
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {
            executor.submit(function, row): index for index, row in enumerate(rows)
        }
        completed = 0
        for future in as_completed(futures):
            results[futures[future]] = future.result()
            completed += 1
            if completed % 10 == 0 or completed == len(rows):
                print(f"{label}: {completed}/{len(rows)}", flush=True)
    return results


def offline_model_call(
    prompt: str,
    *,
    model: str,
    reasoning_effort: str,
    input_data: dict[str, Any],
    stage: str,
    call_key: str,
    evidence_dir: Path | None = None,
) -> dict[str, Any]:
    """Deterministic software fixture; its judgments are not research evidence."""

    if stage == "generation":
        index = input_data["candidate_position"]["index"]
        entries = input_data["lexical_intervention"].get("entries", [])
        if entries:
            lemma = entries[(index - 1) % len(entries)]["lemma"]
        else:
            lemma = ("visit", "read", "clean", "prepare", "travel")[(index - 1) % 5]
        answer = f"The learner uses {lemma} in a short sentence."
        parsed = {
            "prompt": f"Complete the sentence: The learner ___ in a short sentence. ({lemma})",
            "target_answer": answer,
            "accepted_answers": [answer],
            "operation_tags": [],
            "note": "Deterministic software fixture; not linguistic evidence.",
        }
    elif stage == "validation":
        parsed = {
            "judgments": {
                name: {
                    "passed": True,
                    "note": "Deterministic software fixture; not a quality judgment.",
                }
                for name in input_data["criteria"]
            }
        }
    else:
        raise ValueError(f"unsupported offline stage: {stage}")

    if evidence_dir is not None:
        write_json(evidence_dir / "input.json", input_data)
        evidence_dir.mkdir(parents=True, exist_ok=True)
        (evidence_dir / "rendered_prompt.txt").write_text(prompt, encoding="utf-8")
        (evidence_dir / "raw_output.txt").write_text(
            json.dumps(parsed, ensure_ascii=False) + "\n", encoding="utf-8"
        )
        write_json(evidence_dir / "parsed_result.json", parsed)
        write_json(
            evidence_dir / "model_settings.json",
            {"model": model, "reasoning_effort": reasoning_effort},
        )
    return parsed


def run_audit(arguments: argparse.Namespace) -> dict[str, Any]:
    output_dir = arguments.output_dir
    output_dir.mkdir(parents=True, exist_ok=False)

    all_cells = load_frozen_cells()
    selected_ids = set(PILOT_CELL_IDS) if arguments.pilot else {
        row["cell_id"] for row in all_cells
    }
    cells = [row for row in all_cells if row["cell_id"] in selected_ids]
    if arguments.pilot and len(cells) != 8:
        raise ValueError("pilot declaration did not resolve to eight frozen cells")
    source_support = recover_readable_source_support(cells)
    controlled_lexicon = load_controlled_lexicon()
    tasks = build_generation_tasks(cells, source_support, controlled_lexicon)

    generation_prompt = read_text(GENERATION_PROMPT_PATH).rstrip() + AUDIT_PROMPT_SUFFIX
    generation_rulebook = read_text(GENERATION_RULEBOOK_PATH)
    generation_design = read_yaml(GENERATION_DESIGN_PATH)
    item_format = read_yaml(ITEM_FORMAT_PATH)
    validation_prompt = read_text(VALIDATION_PROMPT_PATH)
    validation_criteria = read_yaml(VALIDATION_CRITERIA_PATH)
    model_call = offline_model_call if arguments.offline else call_model
    generation_model = "offline_fixture" if arguments.offline else arguments.generation_model
    validation_model = "offline_fixture" if arguments.offline else arguments.validation_model

    manifest = {
        "experiment": "phase4_item_generation_validation_audit",
        "artifact_status": (
            "software_verification" if arguments.offline else "live_model_evidence"
        ),
        "scientific_evidence": not arguments.offline,
        "scope": "pilot_8_cells" if arguments.pilot else "full_24_cells",
        "frozen_cell_count": len(cells),
        "frozen_cell_ids": [row["cell_id"] for row in cells],
        "recoverable_readable_source_cells": sorted(source_support),
        "conditions": CONDITIONS,
        "blinding_seed": BLINDING_SEED,
        "candidate_reuse": "maximum N generated and validated once; N=1/3/5 are prefixes",
        "selection": {
            "first": "earliest valid candidate",
            "second": (
                "maximum token-set distance from first"
                if arguments.select_second
                else "not requested"
            ),
        },
        "models": {
            "generation": generation_model,
            "validation": validation_model,
            "reasoning_effort": arguments.reasoning_effort,
        },
        "planned_generation_calls": len(tasks),
        "inputs": {
            "legacy_cells": str(LEGACY_OPPORTUNITIES.relative_to(ROOT)),
            "readable_sources": str(READABLE_SOURCE_RECORDS.relative_to(ROOT)),
            "controlled_lexicon": str(CONTROLLED_LEXICON_PATH.relative_to(ROOT)),
            "generation_prompt": str(GENERATION_PROMPT_PATH.relative_to(ROOT)),
            "generation_rulebook": str(GENERATION_RULEBOOK_PATH.relative_to(ROOT)),
            "validation_prompt": str(VALIDATION_PROMPT_PATH.relative_to(ROOT)),
            "validation_criteria": str(VALIDATION_CRITERIA_PATH.relative_to(ROOT)),
        },
        "exact_command": " ".join([sys.executable, *sys.argv]),
    }
    write_json(output_dir / "manifest.json", manifest)
    write_jsonl(output_dir / "frozen_cells.jsonl", cells)
    write_jsonl(
        output_dir / "readable_source_support.jsonl",
        [
            {"cell_id": cell_id, "evidence": evidence}
            for cell_id, evidence in sorted(source_support.items())
        ],
    )

    def generate(task: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any] | None]:
        return generate_one(
            task,
            prompt=generation_prompt,
            rulebook=generation_rulebook,
            design=generation_design,
            item_format=item_format,
            model=generation_model,
            reasoning_effort=arguments.reasoning_effort,
            model_call=model_call,
            evidence_dir=output_dir / "generation_evidence",
        )

    generated = _parallel_map(tasks, generate, arguments.workers, "generation")
    attempts = [row[0] for row in generated]
    candidates = [row[1] for row in generated if row[1] is not None]
    write_jsonl(output_dir / "generation_attempts.jsonl", attempts)
    write_jsonl(output_dir / "candidates.jsonl", candidates)

    blinded, blind_map = blind_candidates(candidates)
    write_jsonl(output_dir / "blinding_map.jsonl", blind_map)
    cells_by_id = {row["cell_id"]: row for row in cells}

    def validate(blind_item: dict[str, Any]) -> dict[str, Any]:
        return validate_one_blinded(
            blind_item,
            cells_by_id=cells_by_id,
            prompt=validation_prompt,
            validation_criteria=validation_criteria,
            model=validation_model,
            reasoning_effort=arguments.reasoning_effort,
            model_call=model_call,
            evidence_dir=output_dir / "validation_evidence",
        )

    blind_validation = _parallel_map(
        blinded, validate, arguments.workers, "validation"
    )
    map_by_blind = {row["blind_item_id"]: row for row in blind_map}
    validation = []
    for row in blind_validation:
        mapping = map_by_blind[row["blind_item_id"]]
        validation.append({**mapping, **row})
    validation.sort(key=lambda row: row["validation_order"])
    write_jsonl(output_dir / "validation.jsonl", validation)

    metrics, selections = prefix_results(
        attempts,
        candidates,
        validation,
        select_second=arguments.select_second,
    )
    write_jsonl(output_dir / "prefix_metrics.jsonl", metrics)
    write_jsonl(output_dir / "selected_items.jsonl", selections)
    summary = {
        "artifact_status": manifest["artifact_status"],
        "scope": manifest["scope"],
        "cells": len(cells),
        "source_evidence_cells": len(source_support),
        "generation_attempts": len(attempts),
        "structurally_valid_candidates": len(candidates),
        "structural_generation_failures": sum(
            not row["structurally_valid"] for row in attempts
        ),
        "validation_calls": len(validation),
        "valid_validator_outputs": sum(
            row["validator_output_valid"] for row in validation
        ),
        "accepted_candidates": sum(row["accepted"] for row in validation),
        "prefix_metrics": metrics,
        "important_boundary": (
            "Offline fixture outputs verify software only and must not be used as "
            "item-quality evidence."
            if arguments.offline
            else "Live generator and independent-validator outputs are research evidence."
        ),
    }
    write_json(output_dir / "summary.json", summary)
    return summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the Phase-4 fixed-cell item-generation audit."
    )
    scope = parser.add_mutually_exclusive_group(required=True)
    scope.add_argument("--pilot", action="store_true", help="Use eight frozen sentinels.")
    scope.add_argument("--full", action="store_true", help="Use all 24 frozen cells.")
    parser.add_argument(
        "--offline",
        action="store_true",
        help="Use deterministic software responses (not scientific evidence).",
    )
    parser.add_argument(
        "--select-second",
        action="store_true",
        help="Also retain the valid item farthest in token set from the first.",
    )
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--generation-model", default=GENERATION_MODEL)
    parser.add_argument("--validation-model", default=VALIDATION_MODEL)
    parser.add_argument("--reasoning-effort", default=REASONING_EFFORT)
    parser.add_argument("--output-dir", type=Path, required=True)
    arguments = parser.parse_args()
    if not arguments.offline and shutil.which("codex") is None:
        parser.error("codex CLI is unavailable; use --offline for software verification")
    return arguments


def main() -> int:
    arguments = parse_args()
    summary = run_audit(arguments)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
